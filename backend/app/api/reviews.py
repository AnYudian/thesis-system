"""阶段审核接口。

权限设计（按老师的要求：智能体只给建议，放行与否由人决定）：
- TEACHER：审自己名下学生的当前环节，能看自己学生的流转记录
- ADMIN：只读，能看全校流转记录用于监督和统计，不代替教师放行
- STUDENT：能看自己的审核记录，知道上一环节被退回时老师说了什么
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.models.enums import ReviewAction, Role, Stage
from app.schemas.review import PendingItem, ReviewIn, ReviewOut, ReviewPage, ReviewResult
from app.services import stage_review_service as svc
from app.services import student_service as student_svc

router = APIRouter(prefix="/reviews", tags=["阶段审核"])


@router.get("/pending", response_model=ApiResponse[list[PendingItem]], summary="在途学生进度")
async def list_pending(
    db: DBDep,
    actor: CurrentUser,
    stage: Annotated[Stage | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
    teacher_id: Annotated[int | None, Query()] = None,
) -> ApiResponse[list[PendingItem]]:
    # 这张表同时是教师的"待批"和管理员的"全校在途学生"：
    # 教师的数据范围永远是本人名下，管理员可以再按导师筛，二者互不影响。
    if actor.role == Role.TEACHER.value:
        scope_teacher_id: int | None = actor.id
        teacher_id = None  # 教师传了别人的 id 也不会越权，范围在下面夹死
    elif actor.role == Role.ADMIN.value:
        scope_teacher_id = None
    else:
        raise AppError(40300, "阶段审核由指导教师完成", http_status=403)

    items = await svc.pending(
        db,
        teacher_id=scope_teacher_id,
        filter_teacher_id=teacher_id,
        stage=stage.value if stage else None,
        keyword=keyword,
    )
    return ok(items)


@router.get("", response_model=ApiResponse[ReviewPage], summary="审核记录")
async def list_reviews(
    db: DBDep,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    stage: Annotated[Stage | None, Query()] = None,
    action: Annotated[ReviewAction | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=50)] = None,
    student_id: Annotated[int | None, Query()] = None,
    teacher_id: Annotated[int | None, Query()] = None,
) -> ApiResponse[ReviewPage]:
    # 数据范围在服务端夹死，前端传什么 student_id 都不会越权
    scope_teacher_id: int | None = None
    scope_student_id: int | None = None

    if actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is None:
            return ok(ReviewPage(items=[], total=0, page=page, size=size))
        scope_student_id = student.id
    elif actor.role == Role.TEACHER.value:
        scope_teacher_id = actor.id
    elif actor.role != Role.ADMIN.value:
        raise AppError(40300, "没有权限查看审核记录", http_status=403)

    items, total = await svc.list_reviews(
        db,
        scope_teacher_id=scope_teacher_id,
        scope_student_id=scope_student_id,
        student_id=student_id,
        stage=stage.value if stage else None,
        action=action.value if action else None,
        keyword=keyword,
        teacher_id=teacher_id,
        page=page,
        size=size,
    )
    return ok(ReviewPage(items=items, total=total, page=page, size=size))


@router.post(
    "/{student_id}",
    response_model=ApiResponse[ReviewResult],
    summary="通过 / 退回",
    description=(
        "教师的最终决定，通过进入下一环节、退回留在本环节。\n\n"
        "- 退回必须写原因；`comment` 最长 500 字\n"
        "- 可选 `ai_run_id` + `ai_adopted`：记录这次决定参考了哪次 AI 预审、采纳了哪几条问题，"
        "未勾选视为未采纳；预审记录必须属于该学生当前环节，否则返回 42225\n"
        "- AI 本身不会写审核记录，审核历史里只出现老师本人的决定"
    ),
)
async def decide(
    db: DBDep,
    actor: CurrentUser,
    student_id: int,
    payload: ReviewIn,
) -> ApiResponse[ReviewResult]:
    if actor.role != Role.TEACHER.value:
        raise AppError(40300, "阶段审核由指导教师完成", http_status=403)

    student = await student_svc.get_student_or_404(db, student_id)
    # 教师只能批自己带的学生：同科室老师互相代批属于越权，
    # 真需要代批时再单独做"转交/代理"功能，不能靠角色放开。
    if student.teacher_id != actor.id:
        raise AppError(40300, "只能审核自己指导的学生", http_status=403)

    review, updated = await svc.decide(
        db,
        student_id=student_id,
        reviewer=actor,
        action=payload.action,
        comment=payload.comment,
        ai_run_id=payload.ai_run_id,
        ai_adopted=[issue.model_dump() for issue in payload.ai_adopted] if payload.ai_adopted else None,
    )

    result = ReviewResult(
        review=ReviewOut(
            id=review.id,
            student_id=review.student_id,
            student_name=updated.name,
            sno=updated.sno,
            teacher_name=actor.real_name or actor.username,
            stage=review.stage,  # type: ignore[arg-type]
            action=review.action,  # type: ignore[arg-type]
            from_stage=review.from_stage,  # type: ignore[arg-type]
            to_stage=review.to_stage,  # type: ignore[arg-type]
            material_version=review.material_version,
            comment=review.comment,
            ai_run_id=review.ai_run_id,
            ai_adopted=review.ai_adopted,
            reviewer_name=actor.real_name or actor.username,
            created_at=review.created_at,
        ),
        current_stage=updated.current_stage,  # type: ignore[arg-type]
        status=updated.status,
    )
    message = (
        "已退回，学生仍停留在本环节"
        if payload.action is ReviewAction.RETURN
        else ("已通过，学生进入归档" if updated.status == "ARCHIVED" else "已通过，进入下一环节")
    )
    return ok(result, message=message)
