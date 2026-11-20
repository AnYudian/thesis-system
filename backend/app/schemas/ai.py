"""AI 预审的接口模型。

result 里的结构是"给前端直接渲染"的形状，所以在这里就定死字段：
模型输出再自由，落库前也要经过这一层校验，避免前端到处写兜底。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    """前端据此决定显不显示 AI 区块、要不要提示"演示模式"。

    文档里的示例值是当前真实配置的形状，别拿它当响应值——
    enabled 会随管理员开关变化，used_today 每天从 0 开始涨。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "provider": "deepseek",
                "model": "deepseek-flash",
                "mock": False,
                "has_key": True,
                "daily_limit": 30,
                "used_today": 3,
                "stages": ["PROPOSAL"],
            }
        }
    )

    enabled: bool = Field(description="管理员开关 + .env 默认值的最终结果；关闭后不再自动预审")
    provider: str = Field(description="mock / deepseek，由 AI_PROVIDER 决定")
    model: str = Field(description="真实模型名，例如 deepseek-flash；mock 时为 mock-reviewer-v1")
    mock: bool = Field(description="true 表示离线演示，不调用真实模型")
    has_key: bool = Field(description="是否配置了 API Key（只回布尔值，不回 key 本身）")
    daily_limit: int = Field(description="每日预审上限，0 表示不限")
    used_today: int = Field(description="今天已发起的预审次数（含教师重跑）")
    stages: list[str] = Field(description="已接入 AI 的环节，目前只有 PROPOSAL")


class AiRunCreate(BaseModel):
    material_id: int
