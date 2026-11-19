"""阶段审核记录。

一次审核一行，只增不改：
- APPROVE：from_stage → to_stage（最后一个环节通过后学生状态变 ARCHIVED）
- RETURN：from_stage = to_stage，学生仍停在原环节，等修改后重交

material_version 记录审核时该生在该环节的最新版本，
以后材料被删或替换，也能知道当时看的是第几版。
"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import STAGE_ORDER

_STAGE_VALUES = ", ".join(f"'{stage.value}'" for stage in STAGE_ORDER)


class StageReview(Base, TimestampMixin):
    __tablename__ = "stage_reviews"
    __table_args__ = (
        CheckConstraint(f"stage IN ({_STAGE_VALUES})", name="ck_stage_reviews_stage"),
        CheckConstraint(f"from_stage IN ({_STAGE_VALUES})", name="ck_stage_reviews_from"),
        CheckConstraint(f"to_stage IN ({_STAGE_VALUES})", name="ck_stage_reviews_to"),
        CheckConstraint("action IN ('APPROVE', 'RETURN')", name="ck_stage_reviews_action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    from_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    material_version: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
