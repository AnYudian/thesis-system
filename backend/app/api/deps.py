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


async def get_current_user(
    db: DBDep,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    # 兜底：浏览器直接打开文件（视频/PDF 预览）时带不了请求头，
    # 允许把令牌放查询参数里。仅用于文件类只读接口，接口清单里其余接口仍要求请求头。
    raw_token = credentials.credentials if credentials else request.query_params.get("token")
    if not raw_token:
        raise AppError(40100, "请先登录", http_status=401)

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


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role):
    allowed = {role.value for role in roles}

    async def _checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppError(40300, "没有权限执行该操作", http_status=403)
        return user

    return _checker
