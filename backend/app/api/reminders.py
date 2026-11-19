"""催交提醒接口。

- TEACHER：只能给本人名下的学生催交（当前环节）
- STUDENT：查看自己的未读提醒、标记已读
- ADMIN：不在这里操作；管理员在阶段流转里能看到"最近催交时间"
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.models.enums import Role, TeacherType
from app.models.reminder import Reminder
from app.schemas.reminder import ReminderIn, ReminderList, ReminderOut
from app.services import reminder_service as svc
from app.services import student_service as student_svc

router = APIRouter(prefix="/reminders", tags=["催交提醒"])


@router.post("/{student_id}", response_model=ApiResponse[ReminderOut], summary="催交材料")
async def remind(
    db: DBDep,
    actor: CurrentUser,
    student_id: int,
    payload: ReminderIn | None = None,
) -> ApiResponse[ReminderOut]:
    if actor.role != Role.TEACHER.value:
        raise AppError(40300, "只有指导教师能催交材料", http_status=403)
    if actor.teacher_type != TeacherType.SUPERVISOR.value:
        raise AppError(40300, "评阅教师不带学生，不需要催交材料", http_status=403)

    student = await student_svc.get_student_or_404(db, student_id)
    # 和阶段审核同一把尺子：只能催自己带的学生，避免跨导师打扰
    if student.teacher_id != actor.id:
        raise AppError(40300, "只能催交自己指导的学生", http_status=403)

    reminder = await svc.remind(
        db, teacher=actor, student=student, content=payload.content if payload else None
    )
    return ok(reminder, message=f"已提醒 {student.name}")


@router.get("/mine", response_model=ApiResponse[ReminderList], summary="我的催交提醒")
async def list_mine(
    db: DBDep,
    actor: CurrentUser,
    unread_only: Annotated[bool, Query()] = True,
) -> ApiResponse[ReminderList]:
    if actor.role != Role.STUDENT.value:
        raise AppError(40300, "该接口仅学生使用", http_status=403)

    student = await student_svc.get_student_by_user(db, actor.id)
    if student is None:
        return ok(ReminderList(items=[], unread=0))

    items, unread = await svc.list_for_student(db, student=student, unread_only=unread_only)
    return ok(ReminderList(items=items, unread=unread))


@router.post("/{reminder_id}/read", response_model=ApiResponse[None], summary="标记已读")
async def mark_read(db: DBDep, actor: CurrentUser, reminder_id: int) -> ApiResponse[None]:
    if actor.role != Role.STUDENT.value:
        raise AppError(40300, "该接口仅学生使用", http_status=403)

    student = await student_svc.get_student_by_user(db, actor.id)
    if student is None:
        raise AppError(40300, "没有找到你的学生档案", http_status=403)

    reminder = await db.get(Reminder, reminder_id)
    if reminder is None:
        raise AppError(40410, "提醒不存在", http_status=404)
    await svc.mark_read(db, reminder=reminder, student_id=student.id)
    return ok(message="已标记为已读")
