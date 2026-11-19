"""指导记录。

中期检查有一条硬性要求：教师对学生的指导不少于 10 次。光有一个计数不够，
事后检查要能回答"哪一天、什么方式、聊了什么、有没有证据"，所以每次沟通
单独成行，证据文件（截图/PDF）存相对路径。

stage 不锁死在中期：开题、定稿同样需要留痕，做成通用表以后不用再改结构。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import STAGE_ORDER, GuidanceMethod

_STAGE_VALUES = ", ".join(f"'{stage.value}'" for stage in STAGE_ORDER)
_METHOD_VALUES = ", ".join(f"'{method.value}'" for method in GuidanceMethod)


class GuidanceRecord(Base, TimestampMixin):
    __tablename__ = "guidance_records"
    __table_args__ = (
        CheckConstraint(f"stage IN ({_STAGE_VALUES})", name="ck_guidance_records_stage"),
        CheckConstraint(f"method IN ({_METHOD_VALUES})", name="ck_guidance_records_method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 记录归属于哪位教师：学生后来换导师，历史记录仍应显示当时是谁指导的
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    stage: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 证据可以为空（口头沟通也可能没截图），但上传了就保留原始文件名供下载
    evidence_name: Mapped[str | None] = mapped_column(String(255))
    evidence_path: Mapped[str | None] = mapped_column(String(500))
    evidence_size: Mapped[int | None] = mapped_column(Integer)
    evidence_type: Mapped[str | None] = mapped_column(String(120))
