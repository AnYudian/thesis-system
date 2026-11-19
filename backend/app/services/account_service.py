"""账号管理业务。

边界：
- 这里只新建教师 / 管理员；学生账号随学生建档开通，不在这里建，
  否则会出现"有账号没档案"或"有档案再来改账号"的两套入口。
- 停用账号而不是删除：历史材料、审核记录、日志都要能追溯到人。
- 不允许停用自己，也不允许停用最后一个管理员，避免把系统锁死。
"""

import re

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.enums import Role
from app.models.user import User
from app.schemas.user import AccountCreate, AccountOut, AccountUpdate

DEFAULT_PASSWORD = "123456"
CREATABLE_ROLES = {Role.TEACHER}

# 教师档案四项：教师要靠这些信息联系学生，管理员也用它在详情页核实指导记录
TEACHER_PROFILE_FIELDS = (
    ("college", "学院"),
    ("major", "专业"),
    ("phone", "手机号"),
    ("qq", "QQ"),
)


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _ensure_contact_format(phone: str | None, qq: str | None) -> None:
    if phone and not re.fullmatch(r"1[3-9]\d{9}", phone):
        raise AppError(42236, "手机号格式不正确，请填 11 位手机号", http_status=422)
    if qq and not re.fullmatch(r"[1-9]\d{4,11}", qq):
        raise AppError(42237, "QQ 号格式不正确，请填 5-12 位数字", http_status=422)


def _ensure_teacher_profile(user: User) -> None:
    """教师账号必须有完整档案：缺哪项说哪项，别让管理员猜。"""
    missing = [label for attr, label in TEACHER_PROFILE_FIELDS if not getattr(user, attr)]
    if missing:
        raise AppError(
            42235,
            f"教师账号需要填写{'、'.join(missing)}",
            http_status=422,
        )


def to_out(user: User, last_login_at=None) -> AccountOut:
    return AccountOut(
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        role=user.role,  # type: ignore[arg-type]
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=last_login_at,
        college=user.college,
        major=user.major,
        phone=user.phone,
        qq=user.qq,
    )


def _apply_filters(
    stmt: Select, *, keyword: str | None, role: Role | None, is_active: bool | None
) -> Select:
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.real_name.ilike(like)))
    if role is not None:
        stmt = stmt.where(User.role == role.value)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    return stmt


async def list_accounts(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    keyword: str | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
) -> tuple[list[AccountOut], int]:
    filters = {"keyword": keyword, "role": role, "is_active": is_active}
    total = await db.scalar(
        _apply_filters(select(func.count()).select_from(User), **filters)
    ) or 0

    users = list(
        (
            await db.scalars(
                _apply_filters(select(User), **filters)
                # 管理员 → 教师 → 学生：账号管理页首先要看到的是"人"，
                # 学生账号数量最多，按 id 倒序会把他们挤到后面
                .order_by(
                    case((User.role == Role.ADMIN.value, 0), (User.role == Role.TEACHER.value, 1), else_=2),
                    User.id.desc(),
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
    )
    if not users:
        return [], total

    # 最近登录时间从审计日志取：users 表不存登录时间，避免每次登录都写一次用户行
    last_logins = {
        user_id: last_at
        for user_id, last_at in (
            await db.execute(
                select(AuditLog.user_id, func.max(AuditLog.created_at))
                .where(AuditLog.action == "LOGIN", AuditLog.user_id.in_([u.id for u in users]))
                .group_by(AuditLog.user_id)
            )
        ).all()
    }
    return [to_out(user, last_logins.get(user.id)) for user in users], total


async def get_account_or_404(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(40402, "账号不存在", http_status=404)
    return user


async def create_account(db: AsyncSession, data: AccountCreate) -> tuple[User, str]:
    if data.role not in CREATABLE_ROLES:
        raise AppError(42230, "系统只保留一个管理员账号，这里只能新建教师账号", http_status=422)
    if await db.scalar(select(User.id).where(User.username == data.username)):
        raise AppError(40902, f"账号 {data.username} 已存在", http_status=409)

    password = data.password or DEFAULT_PASSWORD
    user = User(
        username=data.username,
        real_name=data.real_name,
        role=data.role.value,
        password_hash=hash_password(password),
    )
    if data.role is Role.TEACHER:
        # 手机号/QQ 先做格式校验再落库，避免以后按号码加人时混进无法使用的数据
        _ensure_contact_format(_clean(data.phone), _clean(data.qq))
        user.college = _clean(data.college)
        user.major = _clean(data.major)
        user.phone = _clean(data.phone)
        user.qq = _clean(data.qq)
        _ensure_teacher_profile(user)

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, password


async def update_account(
    db: AsyncSession, *, actor: User, account: User, data: AccountUpdate
) -> User:
    if data.is_active is not None and data.is_active != account.is_active:
        if account.id == actor.id and not data.is_active:
            raise AppError(42231, "不能停用当前登录的账号", http_status=422)
        if not data.is_active and account.role == Role.ADMIN.value:
            others = await db.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.role == Role.ADMIN.value,
                    User.is_active.is_(True),
                    User.id != account.id,
                )
            ) or 0
            if not others:
                raise AppError(42232, "至少保留一个启用状态的管理员，否则没人能管理系统", http_status=422)
        account.is_active = data.is_active

    if data.real_name is not None:
        account.real_name = data.real_name

    # 四项档案都用"传了才改"的语义；管理员改教师资料时前端会把四项一起提交
    if data.college is not None:
        account.college = _clean(data.college)
    if data.major is not None:
        account.major = _clean(data.major)
    if data.phone is not None:
        account.phone = _clean(data.phone)
    if data.qq is not None:
        account.qq = _clean(data.qq)

    if account.role == Role.TEACHER.value:
        _ensure_contact_format(account.phone, account.qq)
        _ensure_teacher_profile(account)

    await db.commit()
    await db.refresh(account)
    return account


async def reset_password(db: AsyncSession, account: User) -> str:
    """重置为统一初始密码。不生成随机密码：本系统没有改密入口，
    随机密码只会让管理员多转述一次，反而更容易丢。"""
    account.password_hash = hash_password(DEFAULT_PASSWORD)
    await db.commit()
    return DEFAULT_PASSWORD


async def set_password(db: AsyncSession, account: User, password: str) -> None:
    account.password_hash = hash_password(password)
    await db.commit()
