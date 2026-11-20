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
    updated_at: datetime | None = None
    updated_by_name: str | None = None


class ConfigUpdate(BaseModel):
    # 上限 50：再高就不是"过程管理"，而是把老师按在表里凑数了
    midterm_min_guidance: int = Field(ge=1, le=50, description="中期检查通过前要求的最少指导次数")
    stage_deadlines: dict[Stage, date | None] = Field(default_factory=dict)
