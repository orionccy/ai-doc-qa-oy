"""FastAPI 应用入口:定义所有 HTTP 接口,并托管前端页面。

接口一览:
  GET    /                    返回前端页面(index.html)
  POST   /api/upload          上传文档 → 解析 → 切分 → 向量化 → 入库
  POST   /api/chat            问答(流式返回文本,类似 SSE)
  GET    /api/docs            已入库文档列表
  DELETE /api/docs?name=xxx   删除指定文档

FastAPI 的魔法:
  - 函数参数里写 UploadFile / dict,框架自动帮你解析请求体
  - 返回 dict 自动转成 JSON;返回 StreamingResponse 做流式传输
"""
import logging
import time
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR
from .parse import extract_text
from .rag import ask_question, ingest_document
from .storage import store

# ================= 日志配置(企业级第一步) =================
# logging 是 Python 标准库,不用装任何东西
# 级别从低到高:DEBUG < INFO < WARNING < ERROR < CRITICAL
# 生产环境一般开到 INFO:看到正常流程 + 警告 + 错误,不刷屏
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-doc-qa")  # 用模块名区分日志来源

app = FastAPI(title="AI 文档问答助手")

# 托管前端静态文件:浏览器访问 /static/... 会映射到 static/ 目录
# 用 __file__ 定位,保证无论从哪启动都能找到(相对 main.py 所在目录)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ================= 请求日志中间件(企业级第一步) =================
# 中间件 = 每个请求进来/出去时都会经过的"关卡"
# 作用:记录 谁在什么时间调了哪个接口、花了多久、结果如何
@app.middleware("http")
async def log_requests(request, call_next):
    start = time.perf_counter()  # 高精度计时
    response = await call_next(request)  # 放行请求,拿到响应
    cost_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.0fms)",
        request.method,          # 请求方法 GET/POST/DELETE
        request.url.path,        # 请求路径 /api/upload ...
        response.status_code,    # 响应状态码 200/400/500
        cost_ms,                 # 耗时毫秒
    )
    return response


# ================= 全局异常处理器(企业级第二步) =================
# 兜底机制:任何接口里没被 try/except 接住的异常,都会走到这里。
# 作用:1) 完整堆栈记进日志(方便排查) 2) 返回友好的 JSON,不把堆栈裸给用户
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("未捕获异常:%s %s", request.method, request.url.path)
    return JSONResponse({"error": "服务器内部错误,请稍后重试"}, status_code=500)


# ================= 安全配置(企业级第三步) =================
# 1) 上传大小限制:防止恶意大文件耗尽服务器内存/带宽
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
# 2) 扩展名白名单:只允许明确支持的格式,其余一律拒绝
ALLOWED_EXTENSIONS = {"txt", "md", "markdown", "pdf", "docx", "csv", "json", "log", "html"}
# 3) 密钥保护:API key 只从 .env 读取,不进代码、不进日志(已由 config.py 保证)


# ================= 页面 =================
@app.get("/")
def index():
    """访问 http://localhost:8000 时返回前端页面。"""
    return FileResponse(STATIC_DIR / "index.html")


# ================= 上传入库 =================
@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    """接收一个或多个文件:解析 → 切分 → 向量化 → 入库。

    安全三道关(企业级第三步):
      1) 大小限制:超过 20MB 直接拒绝
      2) 类型白名单:不在白名单的扩展名直接拒绝
      3) 文件名清洗:只取文件名本身,去掉路径部分(防路径注入,也覆盖空文件名)
    """
    result = {"added": 0, "docs": []}
    for f in files:
        # 安全关卡 1:大小限制(读取后判断,防大文件耗尽内存)
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            logger.warning("拒绝超限文件:%s (%dMB)", f.filename, len(data) // 1024 // 1024)
            return JSONResponse({"error": f"{f.filename} 超过 20MB 大小限制"}, status_code=413)

        # 安全关卡 3:文件名清洗。
        # Path(...).name 只保留文件名部分,天然去掉 "../" 等路径注入;
        # 文件名为空(None 或空串)也在这里统一拦截。
        safe_name = Path(f.filename).name if f.filename else ""
        if not safe_name:
            logger.warning("拒绝空文件名上传")
            return JSONResponse({"error": "文件名不能为空"}, status_code=400)

        # 安全关卡 2:类型白名单
        ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning("拒绝不支持类型:%s (.%s)", safe_name, ext)
            return JSONResponse({"error": f"不支持的文件类型: .{ext}"}, status_code=400)

        try:
            text = extract_text(safe_name, data)          # 解析成纯文本
            n = ingest_document(safe_name, text)          # 走 RAG 入库流程
            if n > 0:
                result["added"] += n
                result["docs"].append(safe_name)
        except Exception as e:
            # 企业级错误处理:异常必须打日志(含完整堆栈),不能只返回给前端
            logger.exception("上传文件 %s 处理失败", safe_name)
            return JSONResponse({"error": f"{safe_name}: {e}"}, status_code=500)
    return {
        **result,
        "docs_list": store.list_docs(),      # 最新文档列表(前端刷新用)
        "chunk_count": store.total_chunks(), # 总片段数
    }


# ================= 问答(流式) =================
@app.post("/api/chat")
async def chat(payload: dict):
    """RAG 问答接口。请求体:{"messages": [{"role":"user","content":"问题"}]}

    返回:流式纯文本。StreamingResponse 会逐段把生成器产出转发给前端,
    浏览器收到后立刻开始渲染(打字机效果)。
    """
    # 输入校验(企业级第三步):messages 必须是合法的消息列表,否则拒绝
    # 防止格式错误的请求进来,也让接口契约更明确
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return JSONResponse({"error": "消息格式不正确"}, status_code=400)

    # 从对话历史里取最后一条用户消息作为问题
    question = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            question = m.get("content", "")
            break
    if not question:
        return JSONResponse({"error": "没有收到问题"}, status_code=400)
    return StreamingResponse(
        ask_question(question), media_type="text/plain; charset=utf-8"
    )


# ================= 文档管理 =================
@app.get("/api/docs")
def list_docs():
    """已入库文档列表(前端页面加载时调用)。"""
    return {"docs": store.list_docs(), "chunk_count": store.total_chunks()}


@app.delete("/api/docs")
def delete_doc(name: str):
    """删除指定文档。FastAPI 自动从 URL 参数 ?name=xxx 取值。"""
    if not name:
        return JSONResponse({"error": "缺少文档名"}, status_code=400)
    removed = store.delete_doc(name)
    return {"ok": True, "removed": removed, "chunk_count": store.total_chunks()}


# ================= 启动入口 =================
if __name__ == "__main__":
    # 直接在项目根目录运行:python -m app.main
    # 或使用命令:.venv/bin/uvicorn app.main:app --reload
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
