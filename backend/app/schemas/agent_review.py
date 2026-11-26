"""按环节智能审阅的请求 / 响应模型。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Stage


class AgentReviewItemOut(BaseModel):
    material_id: int | None
    stage: str
    material_version: int | None
    file_name: str
    file_size: int
    role: str
    included: bool
    skip_reason: str | None


class AgentReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    stage: str
    project_id: str
    status: str
    external_id: str | None
    external_db_status: str | None
    review_mode: str | None
    model: str | None
    simulation_only: bool | None
    summary: str | None
    check_total: int
    check_failed: int
    check_pending: int
    error: str | None
    error_code: str | None
    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    items: list[AgentReviewItemOut] = Field(default_factory=list)


class AgentReviewDetail(AgentReviewOut):
    # 原始返回整体给前端：对方字段还在变，前端用 .get() 取，我们不做二次裁剪
    result: dict | None = None


class AgentReviewPage(BaseModel):
    items: list[AgentReviewOut]
    total: int
    page: int
    size: int


class PackageFileOut(BaseModel):
    material_id: int | None
    stage: str
    material_version: int
    file_name: str
    file_size: int
    # 证据类文件由对方自动分类，role 为空
    role: str | None
    included: bool
    skip_reason: str | None
    generated: bool = False


class PackagePreview(BaseModel):
    student_id: int
    stage: str
    project_id: str
    total_files: int
    missing_stages: list[str]
    warnings: list[str]
    files: list[PackageFileOut]


class AgentReviewCreate(BaseModel):
    student_id: int = Field(ge=1)
    stage: Stage
    trigger: Literal["AUTO", "MANUAL"] = "MANUAL"
