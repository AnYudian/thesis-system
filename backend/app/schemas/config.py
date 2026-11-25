"""系统参数的出入参。"""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import Stage


class ConfigOut(BaseModel):
    """参数配置页与各端展示共用。

    stage_deadlines 每个环节都给键、没设置的为 null，
    前端不用判断"缺这个键"还是"没配日期"。
    """

    midterm_min_guidance: int
    stage_deadlines: dict[Stage, date | None]
    ai_enabled: bool = False
    # 0 表示不限；默认值来自 .env 的 AI_DAILY_LIMIT
    ai_daily_limit: int = 0
    updated_at: datetime | None = None
    updated_by_name: str | None = None


class AiConfigUpdate(BaseModel):
    """管理员改 AI 预审的运行时配置。

    两项都可选，只改传进来的那一项：开关和次数在同一个卡片里，
    但"调次数"不该顺手把管理员刚关掉的开关又打开。
    """

    enabled: bool | None = Field(default=None, description="是否开启 AI 预审")
    daily_limit: int | None = Field(
        default=None, ge=0, le=200, description="每日预审次数上限，0 表示不限"
    )


class ConfigUpdate(BaseModel):
    # 上限 50：再高就不是"过程管理"，而是把老师按在表里凑数了
    midterm_min_guidance: int = Field(ge=1, le=50, description="中期检查通过前要求的最少指导次数")
    stage_deadlines: dict[Stage, date | None] = Field(default_factory=dict)
