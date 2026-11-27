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
from pathlib import Path

from app.services.agent_client import AgentError, UploadFile

logger = logging.getLogger(__name__)

# 对方的核查状态是中文，直接映射成计数，避免前端自己去字符串匹配
FAILED_LABELS = {"需修改", "不通过"}
PENDING_LABELS = {"待确认", "待核验"}

# 错误码 → 用户能看懂、能行动的提示。原始信息留在日志里，界面不抛技术黑话
FRIENDLY_ERRORS = {
    "model_unavailable": "智能审阅的模型服务暂时不可用，请稍后重试；反复出现请联系管理员",
    "review_failed": "审阅未完成，服务方未给出具体原因，请稍后重试",
    "invalid_request": "提交被服务方拒绝，请检查材料格式后重试",
    "queue_full": "审阅队列已满，请稍后重试",
    "timeout": "等待审阅超时，可稍后在列表中查看结果",
    "unauthorized": "智能审阅服务鉴权失败，请联系管理员检查令牌",
    "forbidden": "智能审阅服务拒绝访问，请联系管理员检查反向代理配置",
    "too_large": "材料超出体积限制，请减少文件后重试",
    "material_missing": "材料文件缺失，请重新上传后再发起审阅",
    "bad_response": "智能审阅服务返回了无法识别的内容，请稍后重试",
    "upstream_error": "智能审阅服务暂时不可用，请稍后重试",
}


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
        if item.material_id:
            material = await db.get(Material, item.material_id)
            rel_path = material.stored_path if material else None
        else:
            # 生成件（指导记录导出）没有 materials 行，用明细里记的路径
            material = None
            rel_path = item.stored_path
        if not rel_path or not (settings.upload_path / rel_path).exists():
            review.status = AiRunStatus.FAILED.value
            review.error = f"材料文件缺失：{item.file_name}"
            review.error_code = "material_missing"
            await db.commit()
            return review
        files.append(
            UploadFile(path=settings.upload_path / rel_path, name=item.file_name, role=item.role or None)
        )

    review.status = AiRunStatus.RUNNING.value
    review.error = None
    review.error_code = None
    review.submitted_at = _now()
    await db.commit()

    try:
        try:
            submitted = await agent_client.submit(files, review.project_id)
        except AgentError as exc:
            # 服务方拒绝某个格式时是整单 400；把不支持的文件剔掉重试一次，
            # 而不是让老师看到"整单失败"却不知道为什么
            allowed = exc.allowed_exts
            if not allowed:
                raise
            dropped = 0
            kept: list[UploadFile] = []
            for item, f in zip(included, files):
                ext = Path(f.name).suffix.lower().lstrip(".")
                if ext in allowed:
                    kept.append(f)
                    continue
                item.included = False
                item.skip_reason = f"服务方不接受 .{ext or '未知'} 格式，已自动跳过"
                dropped += 1
            if dropped == 0:
                raise
            logger.warning("服务方拒绝格式 %s，已跳过 %d 份后重试 review_id=%s", sorted(allowed), dropped, review_id)
            await db.commit()
            if not kept:
                raise AgentError("所有材料格式都不被服务方接受", "invalid_request")
            files = kept
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
        friendly = FRIENDLY_ERRORS.get(exc.code)
        review.error = f"{friendly}（原始：{exc.message}）" if friendly else exc.message
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
