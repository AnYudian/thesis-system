"""阶段审核的出入参。"""

from datetime import datetime

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
    # 当前环节的指导记录数；中期检查要求满 10 次才允许通过
    guidance_count: int = 0
    guidance_required: int = 0


class ReviewResult(BaseModel):
    """审核结果：带上更新后的环节，前端不用再查一次。"""

    review: ReviewOut
    current_stage: Stage
    status: str
