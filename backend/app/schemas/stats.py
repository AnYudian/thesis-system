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


class ReportOut(BaseModel):
    summary: ReportSummary
    stages: list[StageReportRow]
    teachers: list[TeacherReportRow]
    activity: list[ActivityPoint]
