"""AI 预审的接口模型。

result 里的结构是"给前端直接渲染"的形状，所以在这里就定死字段：
模型输出再自由，落库前也要经过这一层校验，避免前端到处写兜底。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Stage


class AiDimension(BaseModel):
    """一个评分维度。score 是 0..max_score 的原始分，前端换算成百分比画条。"""

    key: str
    label: str
    score: float
    max_score: float = 5
    comment: str | None = None


class AiIssue(BaseModel):
    """一条问题。quote 是原文片段，老师不用再翻回去找位置。"""

    level: Literal["MAJOR", "MINOR", "INFO"] = "MINOR"
    title: str
    quote: str | None = None
    suggestion: str | None = None


class AiResult(BaseModel):
    score: float = Field(ge=0, le=100)
    completion: int = Field(ge=0, le=100)
    summary: str
    dimensions: list[AiDimension] = []
    issues: list[AiIssue] = []
    suggestions: list[str] = []


class AiRunOut(BaseModel):
    id: int
    material_id: int
    student_id: int
    student_name: str | None = None
    sno: str | None = None
    stage: Stage
    material_version: int
    material_title: str | None = None
    file_name: str | None = None

    status: str
    status_label: str
    provider: str
    model: str
    prompt_version: str

    score: float | None = None
    completion: int | None = None
    summary: str | None = None
    result: AiResult | None = None
    error: str | None = None

    tokens_input: int | None = None
    tokens_output: int | None = None
    latency_ms: int | None = None
    attempts: int = 1

    trigger: str
    triggered_by_name: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AiRunPage(BaseModel):
    items: list[AiRunOut]
    total: int
    page: int
    size: int


class AiStatusOut(BaseModel):
    """前端据此决定显不显示 AI 区块、要不要提示"演示模式"。"""

    enabled: bool
    provider: str
    model: str
    mock: bool
    has_key: bool
    daily_limit: int
    used_today: int
    stages: list[str]


class AiRunCreate(BaseModel):
    material_id: int
