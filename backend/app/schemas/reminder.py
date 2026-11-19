"""催交提醒的出入参。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Stage


class ReminderIn(BaseModel):
    content: str | None = Field(default=None, max_length=200, description="不填用系统默认话术")


class ReminderOut(BaseModel):
    id: int
    student_id: int
    sno: str
    student_name: str
    teacher_name: str | None = None
    stage: Stage
    content: str
    created_at: datetime
    read_at: datetime | None = None


class ReminderList(BaseModel):
    items: list[ReminderOut]
    unread: int
