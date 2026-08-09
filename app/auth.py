"""认证模块:JWT 签发与校验 + FastAPI 依赖注入。

JWT(JSON Web Token)是什么:
- 一段"自包含"的令牌:服务端签名,客户端保存,每次请求带上
- 服务端不用存会话,验签即验身份(无状态认证)
- 结构: header.payload.signature,payload 里放用户信息(如部门)

本模块提供:
  create_token(user)      → 登录成功后签发 token
  get_current_user        → FastAPI 依赖:每个受保护接口注入当前用户
"""
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, Header, HTTPException

from .config import JWT_SECRET, TOKEN_EXPIRE_MINUTES
from .user_store import User, UserStore, user_store


def create_token(user: User) -> str:
    """签发 JWT:把用户身份(含部门)写进 payload,设置过期时间。

    payload 里的信息会随 token 返回前端,所以只放非敏感字段。
    """
    payload = {
        "sub": user.username,        # subject:用户名
        "department": user.department,  # 部门(多租户隔离的关键)
        "role": user.role,           # 角色
        "exp": datetime.now() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(
    authorization: str = Header(default=""),
    store: UserStore = Depends(lambda: user_store),
) -> User:
    """FastAPI 依赖:从请求头解析 token,返回当前用户。

    用法:在接口参数里声明 `user: User = Depends(get_current_user)`,
    接口就能拿到当前登录用户,未登录/无效 token 自动 401。
    """
    # 1) 从 "Bearer xxx" 里取出 token 部分
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录:缺少认证信息")
    token = authorization.removeprefix("Bearer ").strip()

    # 2) 验签 + 检查过期,失败统一返回 401(不泄露具体原因)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期,请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的登录凭证")

    # 3) 按 token 里的用户名查库(防止用户被删除后 token 仍有效)
    user = store.get_user(payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
