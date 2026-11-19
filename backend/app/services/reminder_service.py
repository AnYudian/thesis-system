"""催交提醒业务。

规则：
- 只有该生的指导教师能催交（和阶段审核同一把权限尺子）
- 提醒落在学生"当前环节"，学生点「我知道了」才算已读
- 每次催交同时写一条审计日志，管理员事后能查"哪位老师催过谁"
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.audit_log import AuditLog
from app.models.enums import STAGE_LABELS, Stage, StudentStatus
from app.models.reminder import Reminder
from app.models.student import Student
from app.models.user import User
from app.schemas.reminder import ReminderOut

DEFAULT_TEMPLATE = "请在「{stage}」环节尽快提交材料，有疑问随时联系我。"


def _stage_label(stage: str) -> str:
    try:
        return STAGE_LABELS[Stage(stage)]
    except ValueError:
        return stage


def to_out(reminder: Reminder, student: Student, teacher_name: str | None) -> ReminderOut:
    return ReminderOut(
        id=reminder.id,
        student_id=student.id,
        sno=student.sno,
        student_name=student.name,
        teacher_name=teacher_name,
        stage=reminder.stage,  # type: ignore[arg-type]
        content=reminder.content,
        created_at=reminder.created_at,
        read_at=reminder.read_at,
    )


async def remind(
    db: AsyncSession,
    *,
    teacher: User,
    student: Student,
    content: str | None = None,
) -> ReminderOut:
    if student.status == StudentStatus.ARCHIVED.value:
        raise AppError(40911, "该学生已归档，不需要再催交", http_status=409)

    text = (content or "").strip() or DEFAULT_TEMPLATE.format(stage=_stage_label(student.current_stage))
    reminder = Reminder(
        student_id=student.id,
        teacher_id=teacher.id,
        stage=student.current_stage,
        content=text,
    )
    db.add(reminder)
    db.add(
        AuditLog(
            user_id=teacher.id,
            action="REMIND",
            target_type="STUDENT",
            target_id=str(student.id),
            detail={"stage": student.current_stage, "content": text},
        )
    )
    await db.commit()
    await db.refresh(reminder)
    return to_out(reminder, student, teacher.real_name or teacher.username)


async def list_for_student(
    db: AsyncSession, *, student: Student, unread_only: bool = True, limit: int = 20
) -> tuple[list[ReminderOut], int]:
    unread = await db.scalar(
        select(func.count())
        .select_from(Reminder)
        .where(Reminder.student_id == student.id, Reminder.read_at.is_(None))
    ) or 0

    stmt = (
        select(Reminder, User.real_name, User.username)
        .outerjoin(User, Reminder.teacher_id == User.id)
        .where(Reminder.student_id == student.id)
        .order_by(Reminder.id.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Reminder.read_at.is_(None))

    rows = (await db.execute(stmt)).all()
    items = [to_out(r, student, name or username) for r, name, username in rows]
    return items, unread


async def mark_read(db: AsyncSession, *, reminder: Reminder, student_id: int) -> None:
    if reminder.student_id != student_id:
        raise AppError(40300, "只能处理自己的催交提醒", http_status=403)
    if reminder.read_at is None:
        reminder.read_at = datetime.now(timezone.utc)
        await db.commit()
