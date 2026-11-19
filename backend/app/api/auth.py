"""认证接口。"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBDep
from app.core.response import ApiResponse, ok
from app.core.security import create_access_token
from app.schemas.auth import ChangePasswordIn, LoginData, LoginRequest, UserOut
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


@router.post("/change-password", response_model=ApiResponse[None], summary="修改自己的密码")
async def change_password(
    payload: ChangePasswordIn, db: DBDep, user: CurrentUser
) -> ApiResponse[None]:
    await auth_service.change_password(db, user, payload.old_password, payload.new_password)
    return ok(message="密码已修改，下次登录请使用新密码")
