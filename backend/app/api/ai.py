"""AI 预审接口。

权限口径与材料一致：
- 学生：只看自己的预审记录；不能触发（避免反复刷建议、反复烧 key）
- 教师：名下学生的记录，可手动重跑
- 管理员：全部可看，可重跑
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import AppError
from app.core.response import ApiResponse, ok
from app.models.enums import Role, Stage
from app.models.user import User
from app.schemas.ai import AiRunCreate, AiRunOut, AiRunPage, AiStatusOut
from app.services import ai_service, config_service, log_service, material_service
from app.services import student_service as student_svc

router = APIRouter(prefix="/ai", tags=["AI 预审"])


async def _ensure_view(db, actor: User, student_id: int) -> None:
    if actor.role == Role.ADMIN.value:
        return
    if actor.role == Role.TEACHER.value:
        student = await student_svc.get_student_or_404(db, student_id)
        if student.teacher_id == actor.id:
            return
        raise AppError(40310, "只能查看自己名下学生的预审记录", http_status=403)
    if actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is not None and student.id == student_id:
            return
        raise AppError(40311, "只能查看自己的预审记录", http_status=403)
    raise AppError(40312, "没有权限查看预审记录", http_status=403)


@router.get("/status", response_model=ApiResponse[AiStatusOut], summary="AI 预审是否启用")
async def ai_status(db: DBDep, actor: CurrentUser) -> ApiResponse[AiStatusOut]:
    return ok(await ai_service.status(db))


@router.get("/runs", response_model=ApiResponse[AiRunPage], summary="预审记录列表")
async def list_runs(
    db: DBDep,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
    student_id: Annotated[int | None, Query()] = None,
    material_id: Annotated[int | None, Query()] = None,
    stage: Annotated[Stage | None, Query()] = None,
    status: Annotated[str | None, Query(max_length=16)] = None,
) -> ApiResponse[AiRunPage]:
    scope_student_id: int | None = None
    scope_teacher_id: int | None = None

    if actor.role == Role.STUDENT.value:
        student = await student_svc.get_student_by_user(db, actor.id)
        if student is None:
            return ok(AiRunPage(items=[], total=0, page=page, size=size))
        scope_student_id = student.id
    elif actor.role == Role.TEACHER.value:
        scope_teacher_id = actor.id
    elif actor.role != Role.ADMIN.value:
        raise AppError(40312, "没有权限查看预审记录", http_status=403)

    items, total = await ai_service.list_runs(
        db,
        scope_student_id=scope_student_id,
        scope_teacher_id=scope_teacher_id,
        student_id=student_id,
        material_id=material_id,
        stage=stage.value if stage else None,
        status=status,
        page=page,
        size=size,
    )
    return ok(AiRunPage(items=items, total=total, page=page, size=size))


@router.get("/runs/{run_id}", response_model=ApiResponse[AiRunOut], summary="预审记录详情")
async def get_run(db: DBDep, actor: CurrentUser, run_id: int) -> ApiResponse[AiRunOut]:
    run, student_id = await ai_service.get_run(db, run_id)
    await _ensure_view(db, actor, student_id)
    return ok(run)


@router.post("/runs", response_model=ApiResponse[AiRunOut], summary="手动重跑预审")
async def create_run(
    db: DBDep,
    actor: CurrentUser,
    background: BackgroundTasks,
    body: AiRunCreate,
) -> ApiResponse[AiRunOut]:
    if actor.role not in (Role.ADMIN.value, Role.TEACHER.value):
        raise AppError(40313, "学生不能主动触发 AI 预审，提交材料后会自动审阅", http_status=403)

    material, student = await material_service.get_material_or_404(db, body.material_id)
    if actor.role == Role.TEACHER.value and student.teacher_id != actor.id:
        raise AppError(40310, "只能对自己名下的学生发起预审", http_status=403)

    enabled, daily_limit = await config_service.get_ai_settings(db)
    if not enabled:
        raise AppError(42230, "AI 预审未启用，请联系管理员在参数配置里打开", http_status=422)
    if not ai_service.supports_stage(material.stage):
        raise AppError(42231, "当前只接入了开题报告的 AI 预审", http_status=422)
    if daily_limit and await ai_service.used_today(db) >= daily_limit:
        raise AppError(
            42910,
            f"今日 AI 预审次数已达上限（{daily_limit} 次），请明天再试",
            http_status=429,
        )

    run = await ai_service.enqueue(db, material=material, trigger="MANUAL", actor_id=actor.id)
    if run is None:
        raise AppError(42232, "没能创建预审任务，请确认 AI 开关与材料环节", http_status=422)

    await log_service.commit_record(
        db,
        user_id=actor.id,
        action="AI_REVIEW",
        target_type="STUDENT",
        target_id=student.id,
        detail={
            "material_id": material.id,
            "run_id": run.id,
            "stage": material.stage,
            "version": material.version,
        },
    )
    background.add_task(ai_service.execute, run.id)

    item, _ = await ai_service.get_run(db, run.id)
    return ok(item, message="已提交 AI 预审，稍后刷新查看结果")
