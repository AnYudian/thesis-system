"""按环节的智能审阅接口。

与 /api/ai/runs（单材料预审）并存：
- /ai/runs        旧的单材料链路，保留给本地模型与历史数据；
- /ai/reviews     按「学生 + 环节」打包送外部智能审阅服务，P8 的主线。

权限沿用材料口径：学生只看自己，教师看名下学生，管理员全部。
"""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.models.agent_review import AgentReview
from app.models.enums import Role, Stage
from app.models.student import Student
from app.models.user import User
from app.schemas.agent_review import (
    AgentReviewCreate,
    AgentReviewDetail,
    AgentReviewItemOut,
    AgentReviewOut,
    AgentReviewPage,
    PackageFileOut,
    PackagePreview,
)
from app.services import agent_review_service as svc
from app.services import student_service as student_svc

router = APIRouter(prefix="/ai/reviews", tags=["智能审阅"])


async def _ensure_view(db, actor: User, student_id: int) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value:
        student = await student_svc.get_student_or_404(db, student_id)
        if student.teacher_id == actor.id:
            return
        raise AppError(40320, "只能查看自己名下学生的审阅记录", http_status=403)
    if actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is not None and student.id == student_id:
            return
        raise AppError(40321, "只能查看自己的审阅记录", http_status=403)
    raise AppError(40322, "没有权限查看审阅记录", http_status=403)


def _items(review: AgentReview) -> list[AgentReviewItemOut]:
    return [
        AgentReviewItemOut(
            material_id=i.material_id,
            stage=i.stage,
            material_version=i.material_version,
            file_name=i.file_name,
            file_size=i.file_size,
            role=i.role,
            included=i.included,
            skip_reason=i.skip_reason,
        )
        for i in review.items
    ]


def _to_out(review: AgentReview) -> AgentReviewOut:
    return AgentReviewOut(
        id=review.id,
        student_id=review.student_id,
        stage=review.stage,
        project_id=review.project_id,
        status=review.status,
        external_id=review.external_id,
        external_db_status=review.external_db_status,
        review_mode=review.review_mode,
        model=review.model,
        simulation_only=review.simulation_only,
        summary=review.summary,
        check_total=review.check_total,
        check_failed=review.check_failed,
        check_pending=review.check_pending,
        error=review.error,
        error_code=review.error_code,
        submitted_at=review.submitted_at,
        started_at=review.started_at,
        finished_at=review.finished_at,
        created_at=review.created_at,
        items=_items(review),
    )


@router.get("/preview", response_model=ApiResponse[PackagePreview], summary="预览本次要送审的材料")
async def preview(
    db: DBDep,
    actor: CurrentUser,
    student_id: Annotated[int, Query(ge=1)],
    stage: Annotated[Stage, Query()],
) -> ApiResponse[PackagePreview]:
    """只算不提交，让老师在点「审查」之前先看到会送哪几份、缺什么。"""
    await _ensure_view(db, actor, student_id)
    pkg = await svc.build_package(db, student_id, stage.value)
    return ok(
        PackagePreview(
            student_id=pkg.student_id,
            stage=pkg.stage,
            project_id=pkg.project_id,
            total_files=len(pkg.included),
            missing_stages=pkg.missing_stages,
            warnings=pkg.warnings,
            files=[
                PackageFileOut(
                    material_id=f.material_id,
                    stage=f.stage,
                    material_version=f.version,
                    file_name=f.file_name,
                    file_size=f.file_size,
                    role=f.role,
                    included=f.included,
                    skip_reason=f.skip_reason,
                )
                for f in pkg.files
            ],
        )
    )


@router.post("", response_model=ApiResponse[AgentReviewOut], summary="创建审阅记录（仅打包，未提交）")
async def create(
    db: DBDep, actor: CurrentUser, payload: AgentReviewCreate
) -> ApiResponse[AgentReviewOut]:
    if actor.role == Role.STUDENT.value:
        # 对方串行处理，每人 3-4 分钟；学生反复点会直接把队列堵死
        raise AppError(40323, "学生不能发起智能审阅", http_status=403)
    await _ensure_view(db, actor, payload.student_id)
    pkg = await svc.build_package(db, payload.student_id, payload.stage.value)
    if not pkg.included:
        reason = "；".join(pkg.warnings) or "该环节没有可送审的材料"
        raise AppError(40020, f"无法创建审阅：{reason}", http_status=400)
    review = await svc.create_review_record(db, pkg, triggered_by=actor.id, trigger=payload.trigger)
    return ok(_to_out(review), message="已创建，等待提交（提交逻辑在 P8.2 接入）")


@router.get("", response_model=ApiResponse[AgentReviewPage], summary="审阅记录列表")
async def list_reviews(
    db: DBDep,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
    student_id: Annotated[int | None, Query(ge=1)] = None,
    stage: Annotated[Stage | None, Query()] = None,
) -> ApiResponse[AgentReviewPage]:
    stmt = select(AgentReview)
    if student_id is not None:
        await _ensure_view(db, actor, student_id)
        stmt = stmt.where(AgentReview.student_id == student_id)
    elif actor.role == Role.TEACHER.value:
        stmt = stmt.join(Student, Student.id == AgentReview.student_id).where(
            Student.teacher_id == actor.id
        )
    elif actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is None:
            return ok(AgentReviewPage(items=[], total=0, page=page, size=size))
        stmt = stmt.where(AgentReview.student_id == student.id)
    if stage is not None:
        stmt = stmt.where(AgentReview.stage == stage.value)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(AgentReview.created_at.desc()).offset((page - 1) * size).limit(size)
        )
    ).scalars().all()
    return ok(AgentReviewPage(items=[_to_out(r) for r in rows], total=total, page=page, size=size))


@router.get("/{review_id}", response_model=ApiResponse[AgentReviewDetail], summary="审阅记录详情")
async def detail(db: DBDep, actor: CurrentUser, review_id: int) -> ApiResponse[AgentReviewDetail]:
    review = await db.get(AgentReview, review_id)
    if review is None:
        raise AppError(40420, "审阅记录不存在", http_status=404)
    await _ensure_view(db, actor, review.student_id)
    base = _to_out(review)
    return ok(AgentReviewDetail(**base.model_dump(), result=review.result))
