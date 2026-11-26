"""接口依赖：取当前用户、校验角色。

权限一律用依赖注入实现，不在每个接口里手写 if：
漏写依赖的接口默认是"未登录不可访问"，比默认放开安全。
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User

_bearer = HTTPBearer(auto_error=False, description="登录接口返回的 Bearer Token")

DBDep = Annotated[AsyncSession, Depends(get_db)]


async def _user_from_token(db: AsyncSession, raw_token: str) -> User:
    payload = decode_token(raw_token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(40100, "登录已失效，请重新登录", http_status=401) from exc

    user = await db.get(User, user_id)
    # 每次都回库查：管理员停用账号、调整角色后立即生效，不必等 token 过期
    if user is None or not user.is_active:
        raise AppError(40100, "登录已失效，请重新登录", http_status=401)
    return user


async def get_current_user(
    db: DBDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None:
        raise AppError(40100, "请先登录", http_status=401)
    return await _user_from_token(db, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_evidence_actor(
    request: Request,
    db: DBDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    """证据文件专用鉴权：优先用请求头，其次用短票据。

    浏览器新标签直接打开文件带不了请求头，只能把凭据放进 URL。
    这里只接受"只读某一个文件、3 分钟有效"的票据，不接受登录令牌本身。
    """
    if credentials is not None:
        return await _user_from_token(db, credentials.credentials)

    ticket = request.query_params.get("ticket")
    if not ticket:
        raise AppError(40100, "链接已失效，请回到页面重新打开", http_status=401)

    payload = decode_token(ticket)
    if payload.get("scope") != "evidence_read":
        raise AppError(40300, "该链接只能用于查看证据", http_status=403)
    record_id = request.path_params.get("record_id")
    if str(payload.get("rid")) != str(record_id):
        raise AppError(40300, "票据与文件不匹配", http_status=403)
    return await _user_from_token(db, ticket)


EvidenceActor = Annotated[User, Depends(get_evidence_actor)]


def require_role(*roles: Role):
    allowed = {role.value for role in roles}

    async def _checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppError(40300, "没有权限执行该操作", http_status=403)
        return user

    return _checker
