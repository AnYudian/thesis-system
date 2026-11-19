"""操作日志的出入参。"""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Role


class LogOut(BaseModel):
    id: int
    user_id: int | None = None
    username: str | None = None
    real_name: str | None = None
    role: Role | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    detail: dict | None = None
    created_at: datetime


class LogPage(BaseModel):
    items: list[LogOut]
    total: int
    page: int
    size: int
