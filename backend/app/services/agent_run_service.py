"""提交 → 轮询 → 落库。

为什么单独一个模块：HTTP 交互（agent_client）和"我们怎么记这笔账"（本文件）分开，
将来对方换成同步接口或本地进程，只改 client，状态机与落库不用动。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.agent_review import AgentReview
from app.models.enums import AiRunStatus
from app.models.material import Material
from app.services import agent_client
from app.services.agent_client import AgentError, UploadFile

logger = logging.getLogger(__name__)

# 对方的核查状态是中文，直接映射成计数，避免前端自己去字符串匹配
FAILED_LABELS = {"需修改", "不通过"}
PENDING_LABELS = {"待确认", "待核验"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _count_checks(result: dict) -> tuple[int, int, int]:
    checks = result.get("checks") or []
    failed = sum(1 for c in checks if str(c.get("status")) in FAILED_LABELS)
    pending = sum(1 for c in checks if str(c.get("status")) in PENDING_LABELS)
    return len(checks), failed, pending


async def run(db: AsyncSession, review_id: int) -> AgentReview:
    review = await db.get(AgentReview, review_id)
    if review is None:
        raise AgentError("审阅记录不存在", "not_found")

    included = [i for i in review.items if i.included]
    if not included:
        review.status = AiRunStatus.SKIPPED.value
        review.error = "没有可送审的材料"
        await db.commit()
        return review

    settings = get_settings()
    files: list[UploadFile] = []
    for item in included:
        material = await db.get(Material, item.material_id) if item.material_id else None
        if material is None:
            review.status = AiRunStatus.FAILED.value
            review.error = f"材料不存在：{item.file_name}"
            review.error_code = "material_missing"
            await db.commit()
            return review
        files.append(
            UploadFile(path=settings.upload_path / material.stored_path, name=item.file_name, role=item.role)
        )

    review.status = AiRunStatus.RUNNING.value
    review.error = None
    review.error_code = None
    review.submitted_at = _now()
    await db.commit()

    try:
        submitted = await agent_client.submit(files, review.project_id)
        review.external_id = submitted.get("review_id")
        review.external_db_status = submitted.get("database_status")
        await db.commit()

        if not review.external_id:
            raise AgentError("对方没有返回 review_id", "bad_response")

        state = await agent_client.poll_until_done(review.external_id)
        review.started_at = _parse_time(state.get("started_at")) or review.started_at
        review.finished_at = _parse_time(state.get("finished_at"))
        review.external_db_status = state.get("database_status")

        if state.get("status") == "failed":
            err = state.get("error") or {}
            raise AgentError(
                err.get("message") or "对方判定任务失败",
                err.get("code") or "task_failed",
                retryable=(err.get("code") in {"model_unavailable", "upstream_error"}),
            )

        payload = await agent_client.get_result(review.external_id)
        result = payload.get("result") or {}
        review.result = result
        review.summary = result.get("summary")
        review.review_mode = result.get("review_mode")
        review.model = result.get("model")
        review.simulation_only = result.get("simulation_only")
        review.check_total, review.check_failed, review.check_pending = _count_checks(result)
        review.status = AiRunStatus.DONE.value
        review.finished_at = review.finished_at or _now()
        review.external_db_status = payload.get("database_status") or review.external_db_status
        await db.commit()
    except AgentError as exc:
        logger.warning("智能审阅失败 review_id=%s code=%s: %s", review_id, exc.code, exc.message)
        review.status = AiRunStatus.FAILED.value
        review.error = exc.message
        review.error_code = exc.code
        review.finished_at = _now()
        await db.commit()
    except Exception as exc:  # noqa: BLE001 - 兜底，避免后台任务静默死掉
        logger.exception("智能审阅出现未预期异常 review_id=%s", review_id)
        review.status = AiRunStatus.FAILED.value
        review.error = f"未预期错误：{type(exc).__name__}: {exc}"
        review.error_code = "internal_error"
        review.finished_at = _now()
        await db.commit()
    return review


async def run_in_new_session(review_id: int) -> None:
    """后台任务入口：请求的 session 在响应返回后就关了，必须自己开一个。"""
    async with SessionLocal() as db:
        await run(db, review_id)
