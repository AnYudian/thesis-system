"""指导记录接口。

权限：
- 教师：只能给自己名下的学生登记 / 查看 / 删除自己登记过的记录
- 管理员：全校只读（阶段流转详情页要核实指导次数与证据），不代教师补记录
- 学生：只能看自己的，知道老师记了什么、有没有证据

证据文件走带 token 的下载接口，不能让前端直接拼文件路径。
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DBDep, EvidenceActor
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.core.security import create_evidence_ticket
from app.models.enums import GuidanceMethod, Role, Stage
from app.models.student import Student
from app.models.user import User
from app.schemas.guidance import GuidanceOut, GuidancePage, GuidanceSummary
from app.services import guidance_service as svc
from app.services import log_service
from app.services import student_service as student_svc

router = APIRouter(prefix="/guidance", tags=["指导记录"])


def _ensure_view(student: Student, actor: User) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value and student.teacher_id == actor.id:
        return
    if actor.role == Role.STUDENT.value and student.user_id == actor.id:
        return
    raise AppError(40300, "没有权限查看该学生的指导记录", http_status=403)


def _ensure_write(student: Student, actor: User) -> None:
    if actor.role == Role.TEACHER.value and student.teacher_id == actor.id:
        return
    raise AppError(40300, "只有该生的指导教师可以登记指导记录", http_status=403)


def _parse_when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # el-date-picker 传的是 "2026-11-19 14:30:00"，fromisoformat 能直接吃
        return datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise AppError(42255, "沟通时间格式不正确，请重新选择", http_status=422) from exc


def _to_out(record, student: Student, actor: User) -> GuidanceOut:
    return GuidanceOut(
        id=record.id,
        student_id=record.student_id,
        student_name=student.name,
        sno=student.sno,
        teacher_id=record.teacher_id,
        teacher_name=(actor.real_name or actor.username) if record.teacher_id == actor.id else None,
        stage=record.stage,
        method=record.method,
        happened_at=record.happened_at,
        content=record.content,
        evidence_name=record.evidence_name,
        evidence_size=record.evidence_size,
        evidence_type=record.evidence_type,
        created_at=record.created_at,
    )


@router.get("", response_model=ApiResponse[GuidancePage], summary="指导记录列表")
async def list_records(
    db: DBDep,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    stage: Annotated[Stage | None, Query()] = None,
    student_id: Annotated[int | None, Query()] = None,
) -> ApiResponse[GuidancePage]:
    scope_teacher_id = actor.id if actor.role == Role.TEACHER.value else None
    scope_student_id: int | None = None

    if actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is None:
            return ok(GuidancePage(items=[], total=0, page=page, size=size))
        scope_student_id = student.id
    elif actor.role not in (Role.ADMIN.value, Role.TEACHER.value):
        raise AppError(40300, "没有权限查看指导记录", http_status=403)

    items, total = await svc.list_records(
        db,
        scope_teacher_id=scope_teacher_id,
        scope_student_id=scope_student_id,
        student_id=student_id,
        stage=stage.value if stage else None,
        page=page,
        size=size,
    )
    return ok(GuidancePage(items=items, total=total, page=page, size=size))


@router.get("/summary", response_model=ApiResponse[GuidanceSummary], summary="指导次数汇总")
async def summary(
    db: DBDep, actor: CurrentUser, student_id: Annotated[int, Query()]
) -> ApiResponse[GuidanceSummary]:
    student = await student_svc.get_student_or_404(db, student_id)
    _ensure_view(student, actor)
    return ok(await svc.summary(db, student.id))


@router.post("", response_model=ApiResponse[GuidanceOut], summary="登记一次指导记录")
async def create_record(
    db: DBDep,
    actor: CurrentUser,
    student_id: Annotated[int, Form(description="学生 ID")],
    content: Annotated[str, Form(min_length=1, max_length=2000, description="聊了什么")],
    stage: Annotated[Stage, Form()] = Stage.MIDTERM,
    method: Annotated[GuidanceMethod, Form()] = GuidanceMethod.MEET,
    happened_at: Annotated[str | None, Form(description="沟通时间，ISO 格式")] = None,
    file: Annotated[
        UploadFile | None,
        File(description="证据：图片 / PDF / 代码压缩包 / 视频；视频 100MB、压缩包 30MB、其他 10MB 以内"),
    ] = None,
) -> ApiResponse[GuidanceOut]:
    student = await student_svc.get_student_or_404(db, student_id)
    _ensure_write(student, actor)

    record = await svc.create_record(
        db,
        student=student,
        teacher_id=actor.id,
        stage=stage.value,
        method=method.value,
        happened_at=_parse_when(happened_at),
        content=content,
        upload=file,
    )
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="GUIDANCE_CREATE",
        target_type="STUDENT",
        target_id=student.id,
        detail={
            "record_id": record.id,
            "stage": record.stage,
            "method": record.method,
            "has_evidence": bool(record.evidence_name),
        },
    )
    return ok(_to_out(record, student, actor), message="指导记录已登记")


@router.post("/{record_id}/ticket", response_model=ApiResponse[dict], summary="签发证据预览票据")
async def evidence_ticket(db: DBDep, actor: CurrentUser, record_id: int) -> ApiResponse[dict]:
    """点"查看"时先换一张 3 分钟有效、只读这一个文件的票据。

    把登录令牌直接放进 URL 会出现在地址栏、浏览器历史和访问日志里，
    一旦被复制就等于账号被拿走；票据过期即失效，且只能读指定文件。
    """
    record, student = await svc.get_or_404(db, record_id)
    _ensure_view(student, actor)
    ttl = 180
    return ok({"ticket": create_evidence_ticket(actor.id, record_id, ttl), "expires_in": ttl})


@router.get("/{record_id}/evidence", summary="查看 / 下载指导证据")
async def download_evidence(
    db: DBDep, actor: EvidenceActor, record_id: int
) -> FileResponse:
    record, student = await svc.get_or_404(db, record_id)
    _ensure_view(student, actor)
    path = svc.absolute_evidence(record)
    return FileResponse(
        path,
        filename=record.evidence_name or f"guidance-{record.id}",
        media_type=record.evidence_type or "application/octet-stream",
        # inline 才会在浏览器里直接播放/预览；attachment 会变成下载
        content_disposition_type="inline",
        # 证据文件会被替换（例如重新登记），禁止浏览器复用旧副本
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/{record_id}", response_model=ApiResponse[None], summary="删除指导记录")
async def delete_record(
    db: DBDep, actor: CurrentUser, record_id: int
) -> ApiResponse[None]:
    record, student = await svc.get_or_404(db, record_id)
    if not (actor.role == Role.TEACHER.value and record.teacher_id == actor.id):
        raise AppError(40300, "只能删除自己登记的指导记录", http_status=403)
    info = (record.stage, record.method)
    await svc.delete_record(db, record)
    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="GUIDANCE_DELETE",
        target_type="STUDENT",
        target_id=student.id,
        detail={"record_id": record_id, "stage": info[0], "method": info[1]},
    )
    return ok(message="指导记录已删除")
