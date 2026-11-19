from datetime import datetime

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
