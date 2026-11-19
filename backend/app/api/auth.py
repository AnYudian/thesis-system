"""认证接口。"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBDep
from app.core.response import ApiResponse, ok
from app.core.security import create_access_token
from app.schemas.auth import LoginData, LoginRequest, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=ApiResponse[LoginData], summary="账号密码登录")
async def login(payload: LoginRequest, db: DBDep) -> ApiResponse[LoginData]:
    user = await auth_service.authenticate(db, payload.username, payload.password)
    token, expires_in = create_access_token(user.id, user.role)
    await auth_service.record_login(db, user)
    return ok(
        LoginData(access_token=token, expires_in=expires_in, user=UserOut.model_validate(user)),
        message="登录成功",
    )


@router.get("/me", response_model=ApiResponse[UserOut], summary="当前登录用户")
async def me(user: CurrentUser) -> ApiResponse[UserOut]:
    return ok(UserOut.model_validate(user))
