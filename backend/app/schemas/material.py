"""材料的出入参。"""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Stage


class MaterialOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    sno: str
    stage: Stage
    title: str
    version: int
    file_name: str
    file_size: int
    content_type: str | None = None
    note: str | None = None
    uploader_name: str | None = None
    created_at: datetime


class MaterialPage(BaseModel):
    items: list[MaterialOut]
    total: int
    page: int
    size: int
