"""账号管理接口。本期只提供管理员查看账号列表，增删改在 P2 补。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DBDep, require_role
from app.core.response import ApiResponse, ok
from app.models.enums import Role
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["账号管理"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


@router.get("", response_model=ApiResponse[list[UserOut]], summary="账号列表（仅管理员）")
async def list_users(db: DBDep, _: AdminUser) -> ApiResponse[list[UserOut]]:
    users = (await db.scalars(select(User).order_by(User.id))).all()
    return ok([UserOut.model_validate(user) for user in users])
