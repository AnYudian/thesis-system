"""账号管理接口（仅管理员）。

学生账号不在这里新建：它随「学生与课题」建档开通，这里只做查看、停用、
重置密码；教师账号也在这里新建。管理员账号只保留内置的一个，不再开放创建。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import DBDep, require_role
from app.core.response import ApiResponse, ok
from app.models.enums import Role
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.user import (
    AccountCreate,
    AccountCreated,
    AccountOut,
    AccountPage,
    AccountUpdate,
    ResetPasswordOut,
    SetPasswordIn,
)
from app.services import account_service as svc
from app.services import log_service

router = APIRouter(prefix="/users", tags=["账号管理"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


@router.get("/teachers", response_model=ApiResponse[list[UserOut]], summary="教师列表（仅管理员，用于指派导师）")
async def list_teachers(db: DBDep, _: AdminUser) -> ApiResponse[list[UserOut]]:
    users = (
        await db.scalars(
            select(User)
            .where(User.role == Role.TEACHER.value, User.is_active.is_(True))
            .order_by(User.id)
        )
    ).all()
    return ok([UserOut.model_validate(user) for user in users])


@router.get("", response_model=ApiResponse[AccountPage], summary="账号列表（仅管理员）")
async def list_accounts(
    db: DBDep,
    _: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
    role: Annotated[Role | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> ApiResponse[AccountPage]:
    items, total = await svc.list_accounts(
        db, page=page, size=size, keyword=keyword, role=role, is_active=is_active
    )
    return ok(AccountPage(items=items, total=total, page=page, size=size))


@router.post("", response_model=ApiResponse[AccountCreated], summary="新建教师 / 管理员账号")
async def create_account(
    db: DBDep, actor: AdminUser, data: AccountCreate
) -> ApiResponse[AccountCreated]:
    user, password = await svc.create_account(db, data)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="ACCOUNT_CREATE",
        target_type="USER",
        target_id=user.id,
        detail={"username": user.username, "role": user.role},
    )
    return ok(
        AccountCreated(user=svc.to_out(user), initial_password=password),
        message="账号已创建",
    )


@router.patch("/{user_id}", response_model=ApiResponse[AccountOut], summary="修改姓名 / 启停账号")
async def update_account(
    db: DBDep, actor: AdminUser, user_id: int, data: AccountUpdate
) -> ApiResponse[AccountOut]:
    account = await svc.get_account_or_404(db, user_id)
    before_active = account.is_active
    account = await svc.update_account(db, actor=actor, account=account, data=data)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="ACCOUNT_UPDATE",
        target_type="USER",
        target_id=account.id,
        detail={
            "username": account.username,
            "is_active": account.is_active,
            "was_active": before_active,
        },
    )
    message = "已停用该账号" if before_active and not account.is_active else "已保存"
    return ok(svc.to_out(account), message=message)


@router.post(
    "/{user_id}/reset-password",
    response_model=ApiResponse[ResetPasswordOut],
    summary="重置为初始密码",
)
async def reset_password(
    db: DBDep, actor: AdminUser, user_id: int
) -> ApiResponse[ResetPasswordOut]:
    account = await svc.get_account_or_404(db, user_id)
    password = await svc.reset_password(db, account)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="ACCOUNT_RESET_PASSWORD",
        target_type="USER",
        target_id=account.id,
        detail={"username": account.username},
    )
    return ok(ResetPasswordOut(password=password), message="密码已重置")


@router.post("/{user_id}/set-password", response_model=ApiResponse[None], summary="直接设置新密码")
async def set_password(
    db: DBDep, actor: AdminUser, user_id: int, data: SetPasswordIn
) -> ApiResponse[None]:
    account = await svc.get_account_or_404(db, user_id)
    await svc.set_password(db, account, data.password)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="ACCOUNT_SET_PASSWORD",
        target_type="USER",
        target_id=account.id,
        detail={"username": account.username},
    )
    return ok(message="密码已设置")
