"""学生与课题建档接口。

权限口径：
- 管理员：全部学生，可增删改、指派导师、设置课题
- 教师：只看自己名下的学生，可为自己名下学生设置课题（选题阶段实际由教师出题）
- 学生：只能看自己
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DBDep, require_role
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.models.enums import Role, Stage, StudentStatus
from app.models.student import Student
from app.models.user import User
from app.schemas.student import (
    StudentCreate,
    StudentCreated,
    StudentDetail,
    StudentOut,
    StudentPage,
    StudentUpdate,
    TopicIn,
    TopicOut,
)
from app.services import student_service as svc

router = APIRouter(prefix="/students", tags=["学生与课题"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


def _ensure_view(student: Student, actor: User) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value and student.teacher_id == actor.id:
        return
    if actor.role == Role.STUDENT.value and student.user_id == actor.id:
        return
    raise AppError(40300, "没有权限查看该学生", http_status=403)


def _ensure_topic_write(student: Student, actor: User) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value and student.teacher_id == actor.id:
        return
    raise AppError(40300, "只有管理员或该生的指导教师可以设置课题", http_status=403)


@router.get("", response_model=ApiResponse[StudentPage], summary="学生列表")
async def list_students(
    db: DBDep,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
    stage: Annotated[Stage | None, Query()] = None,
    status: Annotated[StudentStatus | None, Query()] = None,
    teacher_id: Annotated[int | None, Query()] = None,
) -> ApiResponse[StudentPage]:
    if actor.role not in (Role.ADMIN.value, Role.TEACHER.value):
        raise AppError(40300, "没有权限查看学生列表", http_status=403)

    items, total = await svc.list_students(
        db,
        scope_teacher_id=actor.id if actor.role == Role.TEACHER.value else None,
        page=page,
        size=size,
        keyword=keyword,
        stage=stage.value if stage else None,
        status=status.value if status else None,
        teacher_id=teacher_id,
    )
    return ok(StudentPage(items=items, total=total, page=page, size=size))


# 必须放在 /{student_id} 之前，否则 "me" 会被当成路径参数
@router.get("/me", response_model=ApiResponse[StudentDetail | None], summary="学生查看自己的档案")
async def my_profile(db: DBDep, actor: CurrentUser) -> ApiResponse[StudentDetail | None]:
    student = await svc.get_student_by_user(db, actor.id)
    # 账号已开通但还没建档是正常状态，不是错误：返回 null 让前端展示引导文案，
    # 而不是弹一个红色错误提示。
    if student is None:
        return ok(None, message="尚未建立学生档案")
    return ok(await svc.get_detail(db, student))


@router.get("/{student_id}", response_model=ApiResponse[StudentDetail], summary="学生详情")
async def get_student(db: DBDep, actor: CurrentUser, student_id: int) -> ApiResponse[StudentDetail]:
    student = await svc.get_student_or_404(db, student_id)
    _ensure_view(student, actor)
    return ok(await svc.get_detail(db, student))


@router.post("", response_model=ApiResponse[StudentCreated], summary="新建学生（仅管理员）")
async def create_student(db: DBDep, _: AdminUser, data: StudentCreate) -> ApiResponse[StudentCreated]:
    student, initial_password = await svc.create_student(db, data)
    detail = await svc.get_detail(db, student)
    return ok(
        StudentCreated(
            student=StudentOut(**detail.model_dump(exclude={"topic"})),
            initial_password=initial_password,
        ),
        message="学生已建档" if initial_password is None else "学生已建档，登录账号已开通",
    )


@router.patch("/{student_id}", response_model=ApiResponse[StudentDetail], summary="修改学生（仅管理员）")
async def update_student(
    db: DBDep, _: AdminUser, student_id: int, data: StudentUpdate
) -> ApiResponse[StudentDetail]:
    student = await svc.get_student_or_404(db, student_id)
    student = await svc.update_student(db, student, data)
    return ok(await svc.get_detail(db, student), message="已保存")


@router.delete("/{student_id}", response_model=ApiResponse[None], summary="删除学生（仅管理员）")
async def delete_student(db: DBDep, _: AdminUser, student_id: int) -> ApiResponse[None]:
    student = await svc.get_student_or_404(db, student_id)
    await svc.delete_student(db, student)
    return ok(message="已删除学生及其登录账号")


@router.put("/{student_id}/topic", response_model=ApiResponse[TopicOut], summary="设置/修改课题")
async def upsert_topic(
    db: DBDep, actor: CurrentUser, student_id: int, data: TopicIn
) -> ApiResponse[TopicOut]:
    student = await svc.get_student_or_404(db, student_id)
    _ensure_topic_write(student, actor)
    topic = await svc.upsert_topic(db, student, data)
    return ok(TopicOut.model_validate(topic), message="课题已保存")


@router.delete("/{student_id}/topic", response_model=ApiResponse[None], summary="清除课题")
async def delete_topic(db: DBDep, actor: CurrentUser, student_id: int) -> ApiResponse[None]:
    student = await svc.get_student_or_404(db, student_id)
    _ensure_topic_write(student, actor)
    await svc.delete_topic(db, student)
    return ok(message="课题已清除")
