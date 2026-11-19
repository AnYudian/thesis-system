"""催交提醒。

教师发现学生在当前环节迟迟没交（或退回后没重交）时，点一下「催交」生成一条提醒。
本系统没有短信 / 微信通道，提醒就留在系统里：学生下次进工作台或材料页能看到，
教师和管理员也能追溯「什么时候催过谁、催的是哪个环节」。

不塞进审计日志的原因：学生端要按人读取并标记已读，日志是给管理员事后查的，
用途不同，混在一起会让日志变脏。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import STAGE_ORDER

_STAGE_VALUES = ", ".join(f"'{stage.value}'" for stage in STAGE_ORDER)


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint(f"stage IN ({_STAGE_VALUES})", name="ck_reminders_stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 谁催的：学生换导师后历史提醒仍要显示当时的教师
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    stage: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 学生点「我知道了」时写入；未读的才在工作台上提示
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
