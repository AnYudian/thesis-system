"""认证业务逻辑。

接口层只管收参和返回，业务判断都在这里：
这样以后加"微信扫码登录"时，只需要新增一个 authenticate_by_openid，
API 层保持不变。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.models.audit_log import AuditLog
from app.models.user import User


async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.username == username))
    # 用户名不存在和密码错误给同一句提示，避免被用来探测账号
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(40101, "用户名或密码错误", http_status=401)
    if not user.is_active:
        raise AppError(40301, "账号已被停用，请联系管理员", http_status=403)
    return user


async def record_login(db: AsyncSession, user: User) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            action="LOGIN",
            target_type="USER",
            target_id=str(user.id),
            detail={"username": user.username, "role": user.role},
        )
    )
    await db.commit()


async def change_password(db: AsyncSession, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise AppError(40102, "原密码不正确", http_status=401)
    if old_password == new_password:
        raise AppError(42240, "新密码不能与原密码相同", http_status=422)

    user.password_hash = hash_password(new_password)
    db.add(
        AuditLog(
            user_id=user.id,
            action="PASSWORD_CHANGE",
            target_type="USER",
            target_id=str(user.id),
            detail={"username": user.username},
        )
    )
    # 已签发的 token 仍然有效：本系统 token 只含 user_id，
    # 改密后主动失效需要引入 token 版本号，等接入统一认证时一起做。
    await db.commit()
