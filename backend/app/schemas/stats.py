from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import Stage


class StageCount(BaseModel):
    stage: Stage
    label: str
    count: int
    ai_capable: bool


class RecentLogin(BaseModel):
    id: int
    username: str
    real_name: str | None = None
    role: str
    created_at: datetime


class OverviewOut(BaseModel):
    students_total: int
    teachers_total: int
    in_progress: int
    archived: int
    materials_total: int
    stages: list[StageCount]
    recent_logins: list[RecentLogin]


class ReportSummary(BaseModel):
    """报表顶部指标。通过率 / 平均时长在样本为 0 时返回 None，前端显示“—”。"""

    students_total: int
    in_progress: int
    archived: int
    teachers_total: int
    materials_total: int
    reviews_total: int
    approved: int
    returned: int
    approve_rate: float | None = None
    avg_review_hours: float | None = None


class StageReportRow(BaseModel):
    stage: Stage
    label: str
    students: int
    materials: int
    reviews: int
    approved: int
    returned: int


class TeacherReportRow(BaseModel):
    teacher_id: int | None = None
    name: str
    students: int
    active: int
    archived: int
    materials: int
    reviews: int
    approve_rate: float | None = None
    last_reviewed_at: datetime | None = None


class ActivityPoint(BaseModel):
    date: date
    materials: int
    approvals: int
    returns: int


class GuidanceStats(BaseModel):
    """指导记录：总量、方式结构、中期达标情况。"""

    total: int
    meet: int
    online: int
    evidence: int
    students_with_guidance: int
    midterm_total: int
    midterm_required: int
    midterm_reached: int


class DistributionItem(BaseModel):
    """专业 / 班级 / 年级的人数分布，name 为展示名。"""

    name: str
    count: int


class DeadlineRow(BaseModel):
    """某环节的截止与逾期情况：只统计当前停在该环节的学生。"""

    stage: Stage
    label: str
    deadline: date | None = None
    students: int
    overdue: int


class ReportOut(BaseModel):
    summary: ReportSummary
    stages: list[StageReportRow]
    teachers: list[TeacherReportRow]
    activity: list[ActivityPoint]
    guidance: GuidanceStats
    majors: list[DistributionItem]
    classes: list[DistributionItem]
    grades: list[DistributionItem]
    deadlines: list[DeadlineRow]
