"""操作日志：写入与查询。

写入口集中在 record()，业务代码不再各自 new AuditLog：
日志字段（动作名、对象类型）统一了，前端才不用为每种动作单独适配。
"""

from sqlalchemy import Select, Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import LogOut


async def record(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | str | None = None,
    detail: dict | None = None,
) -> None:
    """只把日志挂到当前会话上，由调用方随业务一起 commit，保证两者同生共死。"""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=None if target_id is None else str(target_id),
            detail=detail,
        )
    )


async def commit_record(db: AsyncSession, **kwargs) -> None:
    """业务已经自己 commit 完了的场景用这个，单独提交一条日志。"""
    await record(db, **kwargs)
    await db.commit()


def _apply_filters(
    stmt: Select, *, action: str | None, keyword: str | None, target_type: str | None
) -> Select:
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if keyword:
        like = f"%{keyword.strip()}%"
        # 除了操作人，也搜对象和详情：管理员手里通常只有一个学号/姓名/材料名，
        # 让他能直接搜到相关动作，而不是先猜操作人是谁。
        stmt = stmt.where(
            or_(
                User.username.ilike(like),
                User.real_name.ilike(like),
                AuditLog.target_id.ilike(like),
                cast(AuditLog.detail, Text).ilike(like),
            )
        )
    return stmt


async def list_logs(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    action: str | None = None,
    keyword: str | None = None,
    target_type: str | None = None,
) -> tuple[list[LogOut], int]:
    filters = {"action": action, "keyword": keyword, "target_type": target_type}

    count_stmt = _apply_filters(
        select(func.count()).select_from(AuditLog).outerjoin(User, AuditLog.user_id == User.id),
        **filters,
    )
    total = await db.scalar(count_stmt) or 0

    stmt = _apply_filters(
        select(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id), **filters
    )
    stmt = stmt.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)

    rows = (await db.execute(stmt)).all()
    items = [
        LogOut(
            id=log.id,
            user_id=log.user_id,
            username=user.username if user else None,
            real_name=user.real_name if user else None,
            role=user.role if user else None,  # type: ignore[arg-type]
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            detail=log.detail,
            created_at=log.created_at,
        )
        for log, user in rows
    ]
    return items, total
