"""认证业务逻辑。

接口层只管收参和返回，业务判断都在这里：
这样以后加"微信扫码登录"时，只需要新增一个 authenticate_by_openid，
API 层保持不变。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import verify_password
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
