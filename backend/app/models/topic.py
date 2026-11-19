"""课题（选题）建档。

一名学生一个课题，所以 student_id 唯一。
指导教师不在这里重复存：学生档案上的 teacher_id 就是指导教师，
两处都存以后必然出现"改了学生导师、课题还挂在旧导师名下"的脏数据。
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 学生档案删除时课题随之删除，不留孤儿记录
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    academic_year: Mapped[str] = mapped_column(
        String(9), nullable=False, default="2026", server_default="2026"
    )
