"""AI 预审编排。

职责边界：
- 这里只做"排队 / 取文本 / 调 provider / 落库 / 查询"，评分标准在 agents/proposal.py；
- 每次运行独立会话，因为它在 BackgroundTasks 里跑，不能复用请求的会话
  （请求结束会话就关了，后台任务再用会报 closed）；
- 任何异常都要落到 ai_runs.status，不能把错误抛回上传接口——
  AI 挂掉绝不能影响学生正常提交材料。
"""

import asyncio
import logging
import time
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AiError, AiSkipped, ReviewRequest
from app.agents.extract import clean, extract_text
from app.agents.proposal import PROMPT_VERSION, normalize
from app.agents.providers import get_provider
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.session import SessionLocal
from app.models.ai_run import AiRun
from app.models.enums import AI_RUN_STATUS_LABELS, AiRunStatus, Stage
from app.models.material import Material
from app.models.student import Student
from app.models.user import User
from app.schemas.ai import AiResult, AiRunOut, AiStatusOut
from app.services import config_service, material_service

logger = logging.getLogger(__name__)

# 第一版只接入开题报告：prompt 与评分细则都按这个环节写，其它环节先不跑
SUPPORTED_STAGES: tuple[Stage, ...] = (Stage.PROPOSAL,)
_SUPPORTED_VALUES = {stage.value for stage in SUPPORTED_STAGES}


def _now() -> datetime:
    return datetime.now().astimezone()


def _today_start() -> datetime:
    return _now().replace(hour=0, minute=0, second=0, microsecond=0)


def supports_stage(stage: str) -> bool:
    """第一版只接开题报告；其它环节调用直接给明确提示，而不是静默失败。"""
    return stage in _SUPPORTED_VALUES


# ---------- 状态与额度 ----------


async def used_today(db: AsyncSession) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(AiRun)
            .where(AiRun.created_at >= _today_start(), AiRun.status != AiRunStatus.SKIPPED.value)
        )
    ) or 0


async def status(db: AsyncSession) -> AiStatusOut:
    settings = get_settings()
    return AiStatusOut(
        enabled=await config_service.get_ai_enabled(db),
        provider=settings.ai_provider,
        model=settings.ai_model,
        mock=(settings.ai_provider or "mock").lower() == "mock",
        has_key=bool(settings.ai_api_key),
        daily_limit=settings.ai_daily_limit,
        used_today=await used_today(db),
        stages=[stage.value for stage in SUPPORTED_STAGES],
    )


# ---------- 排队与执行 ----------


async def enqueue(
    db: AsyncSession,
    *,
    material: Material,
    trigger: str,
    actor_id: int | None = None,
) -> AiRun | None:
    """建一条待审记录。返回 None 表示这次不需要跑（未启用 / 环节未接入 / 超额）。"""
    settings = get_settings()
    if not await config_service.get_ai_enabled(db):
        return None
    if material.stage not in _SUPPORTED_VALUES:
        return None
    if settings.ai_daily_limit and await used_today(db) >= settings.ai_daily_limit:
        # 上传时静默跳过：学生已经提交成功，不该因为额度提示而以为上传失败
        logger.info("AI 预审已达当日上限 %s，材料 %s 跳过", settings.ai_daily_limit, material.id)
        return None

    run = AiRun(
        material_id=material.id,
        student_id=material.student_id,
        stage=material.stage,
        material_version=material.version,
        status=AiRunStatus.QUEUED.value,
        provider=settings.ai_provider,
        model=settings.ai_model,
        prompt_version=PROMPT_VERSION,
        trigger=trigger,
        triggered_by=actor_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


_RETRY_DELAY_SECONDS = 2


async def _call_with_retry(db, run: AiRun, provider, request, settings):
    """调用模型，遇到"可能自己好"的错误自动重试。

    重试次数与实时错误都落到这一行记录上：
    - 重试成功：错误清空，attempts=2，界面能看出"这次重试过一次才成"；
    - 重试失败：保留最后一次的原始错误，避免只看到"预审失败"却不知道为什么。
    401/402 这类重试也没用的错误不消耗第二次请求，直接抛。
    """
    max_attempts = 1 + max(0, settings.ai_retry_times)
    for attempt in range(1, max_attempts + 1):
        run.attempts = attempt
        try:
            reply = await provider.review(request)
        except AiError as exc:
            if not exc.retryable or attempt >= max_attempts:
                raise
            run.error = f"第 {attempt} 次调用失败（{exc.message}），{_RETRY_DELAY_SECONDS} 秒后自动重试"
            await db.commit()
            logger.warning("AI 预审 run=%s 第 %s 次调用失败：%s", run.id, attempt, exc.message)
            await asyncio.sleep(_RETRY_DELAY_SECONDS)
            continue

        if run.error:
            run.error = None
        return reply

    # 循环里要么 return 要么 raise，这里只是让类型检查安心
    raise AiError("模型调用失败")


async def execute(run_id: int) -> None:
    """后台任务入口。自己开会话，自己收尾，绝不向外抛异常。"""
    settings = get_settings()
    started = time.perf_counter()

    async with SessionLocal() as db:
        run = await db.get(AiRun, run_id)
        if run is None or run.status != AiRunStatus.QUEUED.value:
            return

        run.status = AiRunStatus.RUNNING.value
        run.started_at = _now()
        await db.commit()

        try:
            material = await db.get(Material, run.material_id)
            if material is None:
                raise AiSkipped("材料已被删除，无需再审")

            text = clean(extract_text(material_service.absolute_file(material)))
            truncated = len(text) > settings.ai_max_chars
            if truncated:
                text = text[: settings.ai_max_chars]

            provider = get_provider(settings)
            run.provider = provider.name
            run.model = provider.model

            request = ReviewRequest(
                text=text,
                stage=run.stage,
                title=material.title,
                material_version=run.material_version,
                truncated=truncated,
            )
            reply = await _call_with_retry(db, run, provider, request, settings)
            result = normalize(reply.payload)

            run.status = AiRunStatus.DONE.value
            run.score = result.score
            run.completion = result.completion
            run.summary = result.summary
            run.result = result.model_dump()
            run.raw_response = reply.raw[:20000]  # 原始返回留一份，排查"模型说了什么"时用
            run.tokens_input = reply.tokens_input
            run.tokens_output = reply.tokens_output
        except AiSkipped as exc:
            run.status = AiRunStatus.SKIPPED.value
            run.error = str(exc)
        except (AiError, AppError) as exc:
            run.status = AiRunStatus.FAILED.value
            message = getattr(exc, "message", None) or str(exc)
            if (run.attempts or 1) > 1:
                message = f"{message}（共尝试 {run.attempts} 次）"
            run.error = message
        except Exception:
            # 未预期的错误也要落状态，否则前端会一直转圈
            logger.exception("AI 预审执行失败 run=%s", run_id)
            run.status = AiRunStatus.FAILED.value
            run.error = "预审过程出错，请稍后重试；反复失败请联系管理员查看日志"
        finally:
            run.finished_at = _now()
            run.latency_ms = int((time.perf_counter() - started) * 1000)
            await db.commit()


async def fail_stale_runs() -> int:
    """启动时把上次进程留下的"排队中/审阅中"标成失败。

    BackgroundTasks 活在进程里，进程一重启任务就没了；不清理的话前端会永远轮询。
    """
    async with SessionLocal() as db:
        result = await db.execute(
            update(AiRun)
            .where(AiRun.status.in_([AiRunStatus.QUEUED.value, AiRunStatus.RUNNING.value]))
            .values(
                status=AiRunStatus.FAILED.value,
                error="服务重启，本次预审被中断；可在详情页重新运行",
                finished_at=_now(),
            )
        )
        await db.commit()
        return result.rowcount or 0


# ---------- 查询 ----------


def _base_query() -> Select:
    return (
        select(
            AiRun,
            Student.name,
            Student.sno,
            Material.title,
            Material.file_name,
            User.real_name,
        )
        .join(Student, AiRun.student_id == Student.id)
        .outerjoin(Material, AiRun.material_id == Material.id)
        .outerjoin(User, AiRun.triggered_by == User.id)
    )


def _to_out(row) -> AiRunOut:
    run, student_name, sno, material_title, file_name, trigger_name = row

    result: AiResult | None = None
    if run.result:
        try:
            result = AiResult.model_validate(run.result)
        except ValidationError:
            # 历史数据结构变更时不让整页 500，保留原始 JSON 在库里
            result = None

    try:
        status_label = AI_RUN_STATUS_LABELS[AiRunStatus(run.status)]
    except ValueError:
        status_label = run.status

    return AiRunOut(
        id=run.id,
        material_id=run.material_id,
        student_id=run.student_id,
        student_name=student_name,
        sno=sno,
        stage=Stage(run.stage),
        material_version=run.material_version,
        material_title=material_title,
        file_name=file_name,
        status=run.status,
        status_label=status_label,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        score=run.score,
        completion=run.completion,
        summary=run.summary,
        result=result,
        error=run.error,
        tokens_input=run.tokens_input,
        tokens_output=run.tokens_output,
        latency_ms=run.latency_ms,
        attempts=run.attempts or 1,
        trigger=run.trigger,
        triggered_by_name=trigger_name,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


async def list_runs(
    db: AsyncSession,
    *,
    scope_student_id: int | None = None,
    scope_teacher_id: int | None = None,
    student_id: int | None = None,
    material_id: int | None = None,
    stage: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[AiRunOut], int]:
    conditions = []
    if scope_student_id is not None:
        conditions.append(AiRun.student_id == scope_student_id)
    elif student_id is not None:
        conditions.append(AiRun.student_id == student_id)
    if scope_teacher_id is not None:
        conditions.append(Student.teacher_id == scope_teacher_id)
    if material_id is not None:
        conditions.append(AiRun.material_id == material_id)
    if stage:
        conditions.append(AiRun.stage == stage)
    if status:
        conditions.append(AiRun.status == status)

    count_stmt = select(func.count()).select_from(AiRun).join(Student, AiRun.student_id == Student.id)
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
    total = await db.scalar(count_stmt) or 0

    stmt = _base_query()
    for cond in conditions:
        stmt = stmt.where(cond)
    stmt = stmt.order_by(AiRun.created_at.desc(), AiRun.id.desc()).offset((page - 1) * size).limit(size)

    rows = (await db.execute(stmt)).all()
    return [_to_out(row) for row in rows], total


async def get_run(db: AsyncSession, run_id: int) -> tuple[AiRunOut, int]:
    """返回 (运行记录, 学生 id)：学生 id 给接口层做权限判断。"""
    row = (await db.execute(_base_query().where(AiRun.id == run_id))).first()
    if row is None:
        raise AppError(40410, "预审记录不存在", http_status=404)
    return _to_out(row), row[0].student_id
