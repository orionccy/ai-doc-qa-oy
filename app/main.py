"""FastAPI 应用入口:定义所有 HTTP 接口,并托管前端页面。

接口一览:
  POST   /api/register     注册(用户名/密码/部门)
  POST   /api/login        登录 → 返回 JWT token
  GET    /api/me           当前登录用户信息(前端显示部门/角色用)
  GET    /api/users        用户列表(仅管理员)
  DELETE /api/users/{name} 删除用户(仅管理员)
  POST   /api/upload       上传文档 → 解析 → 切分 → 向量化 → 入库(需登录)
  POST   /api/chat         问答(流式,需登录,只查本部门知识库)
  GET    /api/docs         本部门文档列表(需登录)
  DELETE /api/docs?name=xx 删除本部门文档(需登录)

多租户设计(企业级):
  - 每个用户属于一个部门(注册时指定)
  - 文档入库时打部门标签;查询时强制按"当前登录用户的部门"过滤
  - 部门 ID 只从 JWT 解析,绝不信任前端传参——这是数据隔离的核心
"""
import logging
import sqlite3
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import create_token, get_current_user
from .chat_store import chat_store
from .config import BASE_DIR
from .parse import extract_text
from .rag import ask_question, ingest_document
from .storage import store
from .user_store import User, user_store

# ================= 日志配置(企业级第一步) =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-doc-qa")

app = FastAPI(title="AI 文档问答助手(多租户版)")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ================= 请求日志中间件 =================
@app.middleware("http")
async def log_requests(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    cost_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.0fms)",
        request.method, request.url.path, response.status_code, cost_ms,
    )
    return response


# ================= 全局异常处理器 =================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("未捕获异常:%s %s", request.method, request.url.path)
    return JSONResponse({"error": "服务器内部错误,请稍后重试"}, status_code=500)


# ================= 安全配置 =================
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = {"txt", "md", "markdown", "pdf", "docx", "csv", "json", "log", "html"}

# 可选的部门列表(前端注册页下拉用;也允许自定义,企业可改成从数据库读)
DEFAULT_DEPARTMENTS = ["研发部", "市场部", "销售部", "客服部", "财务部", "人事部"]


# ================= 认证:注册 / 登录 =================
@app.post("/api/register")
def register(payload: dict):
    """注册新用户。参数:{username, password, department}

    第一个注册的用户自动成为 admin(方便初始化);
    之后注册的都是普通用户(user)。
    """
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    department = (payload.get("department") or "").strip()

    # 输入校验:不允许空值,密码至少 6 位(企业最小要求)
    if not username or not password or not department:
        return JSONResponse({"error": "用户名/密码/部门不能为空"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "密码长度至少 6 位"}, status_code=400)

    # 第一个用户自动成为管理员
    role = "admin" if len(user_store.list_users()) == 0 else "user"
    # 用户名不区分大小写:注册前检查是否已存在(否则大小写变体可重复注册)
    if user_store.get_user(username) is not None:
        return JSONResponse({"error": "用户名已存在"}, status_code=409)
    try:
        user = user_store.create_user(username, password, department, role)
    except sqlite3.IntegrityError:
        return JSONResponse({"error": "用户名已存在"}, status_code=409)
    logger.info("新用户注册:%s (部门:%s, 角色:%s)", username, department, role)
    return {"ok": True, "user": user.to_dict()}


@app.post("/api/login")
def login(payload: dict):
    """登录:校验用户名密码,签发 JWT token。"""
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    user = user_store.verify_password(username, password)
    if user is None:
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)
    token = create_token(user)
    logger.info("用户登录:%s (部门:%s)", username, user.department)
    return {"ok": True, "token": token, "user": user.to_dict()}


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    """返回当前登录用户信息(前端顶部栏显示用)。"""
    return user.to_dict()


# ================= 用户管理(仅管理员) =================
@app.get("/api/users")
def list_users(user: User = Depends(get_current_user)):
    """用户列表。普通用户只能看自己,管理员看全部。"""
    if user.role == "admin":
        return {"users": user_store.list_users()}
    return {"users": [u for u in user_store.list_users() if u["username"] == user.username]}


@app.delete("/api/users/{username}")
def delete_user(username: str, user: User = Depends(get_current_user)):
    """删除用户(仅管理员),顺带删除该用户的文档。"""
    if user.role != "admin":
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    if username == user.username:
        return JSONResponse({"error": "不能删除自己"}, status_code=400)
    removed = store.delete_doc_by_uploader(username)
    deleted = user_store.delete_user(username)
    if not deleted:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    logger.info("管理员 %s 删除了用户 %s(清理文档 %d 块)", user.username, username, removed)
    return {"ok": True, "deleted": deleted, "removed_docs": removed}


@app.post("/api/users/{username}/reset-password")
def reset_password(username: str, payload: dict, user: User = Depends(get_current_user)):
    """重置用户密码(仅管理员)。参数:{new_password}"""
    if user.role != "admin":
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    new_password = payload.get("new_password") or ""
    if len(new_password) < 6:
        return JSONResponse({"error": "新密码长度至少 6 位"}, status_code=400)
    ok = user_store.update_password(username, new_password)
    if not ok:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    logger.info("管理员 %s 重置了用户 %s 的密码", user.username, username)
    return {"ok": True}


@app.get("/api/departments")
def departments():
    """可选部门列表(注册页下拉用)。"""
    return {"departments": DEFAULT_DEPARTMENTS}


# ================= 上传入库(需登录,归属当前部门) =================
@app.post("/api/upload")
async def upload(
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
):
    """接收一个或多个文件:解析 → 切分 → 向量化 → 入库。

    多租户:文档归属当前登录用户的部门(department 从 token 取,不信任前端)。
    """
    result = {"added": 0, "docs": []}
    for f in files:
        # 安全关卡 1:大小限制
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            logger.warning("拒绝超限文件:%s (%dMB)", f.filename, len(data) // 1024 // 1024)
            return JSONResponse({"error": f"{f.filename} 超过 20MB 大小限制"}, status_code=413)

        # 安全关卡 2:文件名清洗(防路径注入)
        safe_name = Path(f.filename).name if f.filename else ""
        if not safe_name:
            logger.warning("拒绝空文件名上传")
            return JSONResponse({"error": "文件名不能为空"}, status_code=400)

        # 安全关卡 3:类型白名单
        ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning("拒绝不支持类型:%s (.%s)", safe_name, ext)
            return JSONResponse({"error": f"不支持的文件类型: .{ext}"}, status_code=400)

        try:
            text = extract_text(safe_name, data)
            # 多租户:入库打上当前用户的部门标签 + 上传者(审计用)
            n = ingest_document(safe_name, text,
                                department=user.department, uploader=user.username)
            if n > 0:
                result["added"] += n
                result["docs"].append(safe_name)
        except Exception as e:
            logger.exception("上传文件 %s 处理失败", safe_name)
            return JSONResponse({"error": f"{safe_name}: {e}"}, status_code=500)
    return {
        **result,
        "docs_list": store.list_docs(department=user.department),
        "chunk_count": store.total_chunks(department=user.department),
    }


# ================= 问答(流式,只查本部门) =================
@app.post("/api/chat")
async def chat(
    payload: dict,
    user: User = Depends(get_current_user),
):
    """RAG 问答接口。请求体:{"messages": [{"role":"user","content":"问题"}]}

    多租户:ask_question 只检索当前用户部门的文档——数据隔离在这里生效。
    对话持久化:用户问题和助手回答都存入 SQLite,刷新页面不丢。
    """
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return JSONResponse({"error": "消息格式不正确"}, status_code=400)

    question = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            question = m.get("content", "")
            break
    if not question:
        return JSONResponse({"error": "没有收到问题"}, status_code=400)

    # 保存用户消息(持久化)
    chat_store.add_message(user.username, "user", question)

    def generate():
        """包装生成器:边流式输出,边收集完整回答;结束后落库保存。"""
        collected: list[str] = []
        try:
            for chunk in ask_question(question, department=user.department):
                collected.append(chunk)
                yield chunk
        finally:
            # 无论正常结束还是客户端断开,都尽量保存已生成的部分
            if collected:
                chat_store.add_message(user.username, "assistant", "".join(collected))

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@app.get("/api/history")
def history(user: User = Depends(get_current_user)):
    """拉取当前用户的对话历史(最近 100 条,时间正序)。"""
    return {"messages": chat_store.list_messages(user.username, limit=100)}


@app.delete("/api/history")
def clear_history(user: User = Depends(get_current_user)):
    """清空当前用户的对话历史。"""
    removed = chat_store.clear_history(user.username)
    return {"ok": True, "removed": removed}


# ================= 文档管理(本部门可见) =================
@app.get("/api/docs")
def list_docs(user: User = Depends(get_current_user)):
    """本部门已入库文档列表。"""
    return {
        "docs": store.list_docs(department=user.department),
        "chunk_count": store.total_chunks(department=user.department),
    }


@app.delete("/api/docs")
def delete_doc(name: str, user: User = Depends(get_current_user)):
    """删除本部门的指定文档(无法删除其他部门文档)。"""
    if not name:
        return JSONResponse({"error": "缺少文档名"}, status_code=400)
    removed = store.delete_doc(name, department=user.department)
    return {
        "ok": True,
        "removed": removed,
        "chunk_count": store.total_chunks(department=user.department),
    }


# ================= 启动入口 =================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
