"""外部智能审阅服务的 HTTP 客户端。

只负责"怎么和对方说话"，不碰数据库、不碰权限——这样将来换成本地进程调用
（把对方的循环嵌进我们后端）时，只需要替换这一个文件。

对方的三个坑（都实测过）：
1. 证书是 Caddy 自签且 12 小时一换 → 默认跳过校验，正式环境再关；
2. 单任务串行、约 3-4 分钟 → 提交后必须异步轮询，不能同步等；
3. 失败时错误码在 body.error.code 里，HTTP 可能仍是 200 → 要读业务字段而不只看状态码。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import get_settings


class AgentError(Exception):
    """调用外部服务失败。code 尽量保留对方的原始错误码，便于前端区分是否可重试。"""

    def __init__(self, message: str, code: str = "agent_error", retryable: bool = False):
        self.message = message
        self.code = code
        self.retryable = retryable
        super().__init__(message)


@dataclass
class UploadFile:
    path: Path
    name: str
    role: str


def _client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.agent_base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.agent_token}"},
        verify=settings.agent_verify_tls,
        timeout=httpx.Timeout(settings.agent_timeout_seconds, connect=10.0),
    )


def _check(resp: httpx.Response) -> dict:
    """把各种失败翻译成带错误码的 AgentError，调用方只处理一种异常。"""
    if resp.status_code == 401:
        raise AgentError("智能审阅服务拒绝了令牌（401），请检查 AGENT_TOKEN", "unauthorized")
    if resp.status_code == 403:
        raise AgentError("智能审阅服务拒绝访问（403），多为反向代理 Host 配置问题", "forbidden")
    if resp.status_code == 413:
        raise AgentError("材料超出智能审阅服务的体积限制（413）", "too_large")
    if resp.status_code == 429:
        raise AgentError("智能审阅服务队列已满（429），请稍后重试", "queue_full", retryable=True)
    if resp.status_code in (500, 502, 503, 504):
        raise AgentError(f"智能审阅服务暂时不可用（{resp.status_code}）", "upstream_error", retryable=True)
    if resp.status_code >= 400:
        detail = ""
        try:
            detail = (resp.json().get("error") or {}).get("message") or ""
        except Exception:
            detail = resp.text[:200]
        raise AgentError(f"智能审阅服务返回 {resp.status_code}：{detail}", "invalid_request")
    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        raise AgentError(f"智能审阅服务返回了非 JSON 内容：{resp.text[:120]}", "bad_response") from exc


async def submit(files: list[UploadFile], project_id: str) -> dict:
    settings = get_settings()
    handles = []
    try:
        multipart = []
        for f in files:
            fh = open(f.path, "rb")  # noqa: SIM115 - 需要在请求期间保持打开
            handles.append(fh)
            multipart.append(("files", (f.name, fh, "application/octet-stream")))
        data = {
            "project_id": project_id,
            # roles 与上传顺序一一对应，对方按它决定用哪套规则
            "roles": "[" + ",".join(f'"{f.role}"' for f in files) + "]",
        }
        async with _client() as client:
            resp = await client.post("/reviews", files=multipart, data=data)
        return _check(resp)
    finally:
        for fh in handles:
            fh.close()


async def get_status(review_id: str) -> dict:
    async with _client() as client:
        resp = await client.get(f"/reviews/{review_id}")
    return _check(resp)


async def get_result(review_id: str) -> dict:
    async with _client() as client:
        resp = await client.get(f"/reviews/{review_id}/result")
    if resp.status_code == 202:
        raise AgentError("任务尚未完成，暂时没有结果", "not_ready", retryable=True)
    if resp.status_code == 409:
        detail = ""
        try:
            detail = json_error(resp.json())
        except Exception:
            detail = resp.text[:200]
        raise AgentError(f"审阅失败：{detail or '409'}", "task_failed")
    return _check(resp)


def json_error(payload: dict) -> str:
    err = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict):
        return err.get("message") or err.get("code") or ""
    return str(err or "")


async def poll_until_done(review_id: str, *, timeout_minutes: int | None = None) -> dict:
    """轮询到终态。返回最后一次状态响应。

    对方串行处理，一份材料约 3-4 分钟；超时设置得比它宽一点，
    但必须有个上限，否则一个卡死的任务会让后台任务永远挂着。
    """
    settings = get_settings()
    limit = (timeout_minutes or settings.agent_max_wait_minutes) * 60
    waited = 0
    while waited <= limit:
        state = await get_status(review_id)
        status = state.get("status")
        if status in ("completed", "failed"):
            return state
        await asyncio.sleep(settings.agent_poll_interval)
        waited += settings.agent_poll_interval
    raise AgentError(
        f"等待审阅超时（超过 {timeout_minutes or settings.agent_max_wait_minutes} 分钟）",
        "timeout",
        retryable=True,
    )
