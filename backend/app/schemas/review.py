"""阶段审核的出入参。"""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ReviewAction, Stage


class ReviewIn(BaseModel):
    action: ReviewAction
    comment: str | None = Field(default=None, max_length=500, description="退回时必须填写原因")


class ReviewOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    sno: str
    teacher_name: str | None = None
    stage: Stage
    action: ReviewAction
    from_stage: Stage
    to_stage: Stage
    material_version: int | None = None
    comment: str | None = None
    reviewer_name: str | None = None
    created_at: datetime


class ReviewPage(BaseModel):
    items: list[ReviewOut]
    total: int
    page: int
    size: int


class PendingItem(BaseModel):
    """教师待办列表的一行：学生当前停在哪、交了几版材料、上次说了什么。"""

    student_id: int
    sno: str
    name: str
    teacher_name: str | None = None
    stage: Stage
    material_count: int
    latest_material_at: datetime | None = None
    latest_version: int | None = None
    last_action: ReviewAction | None = None
    last_comment: str | None = None
    last_reviewed_at: datetime | None = None
    # 当前环节的指导记录数；中期检查要求满「参数配置」里的次数才允许通过
    guidance_count: int = 0
    guidance_required: int = 0
    # 当前环节的截止日期（管理员在参数配置里设），过了就算逾期
    stage_deadline: date | None = None
    stage_overdue: bool = False
    # 最近一次催交时间：列表里提示"什么时候催过"，避免老师隔天重复催
    last_reminded_at: datetime | None = None


class ReviewResult(BaseModel):
    """审核结果：带上更新后的环节，前端不用再查一次。"""

    review: ReviewOut
    current_stage: Stage
    status: str
