"""指导记录的出入参。

列表项带学生与教师姓名：管理员详情页、教师工作台都要直接展示，
不让前端再按 id 逐条查人。
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import GuidanceMethod, Stage


class GuidanceOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    sno: str
    teacher_id: int | None = None
    teacher_name: str | None = None
    stage: Stage
    method: GuidanceMethod
    happened_at: datetime
    content: str
    evidence_name: str | None = None
    evidence_size: int | None = None
    evidence_type: str | None = None
    created_at: datetime


class GuidancePage(BaseModel):
    items: list[GuidanceOut]
    total: int
    page: int
    size: int


class GuidanceSummary(BaseModel):
    """详情页与教师工作台的进度用：按环节计数 + 中期硬性要求。"""

    total: int
    by_stage: dict[str, int]
    midterm_count: int
    midterm_required: int
