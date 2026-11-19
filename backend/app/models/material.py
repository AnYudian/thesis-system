"""阶段材料与版本。

同一学生、同一环节每上传一次就生成一个新版本（v1、v2…），旧版本保留可下载，
这样"改了几稿"本身可追溯，也方便后面接入智能体时对同一篇稿件反复审阅。
"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import STAGE_ORDER

_STAGE_VALUES = ", ".join(f"'{stage.value}'" for stage in STAGE_ORDER)


class Material(Base, TimestampMixin):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint(f"stage IN ({_STAGE_VALUES})", name="ck_materials_stage"),
        # 版本号在同一学生同一环节内自增，唯一约束保证并发下不会出现两个 v2
        UniqueConstraint("student_id", "stage", "version", name="uq_materials_student_stage_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    stage: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # 原始文件名给用户看，磁盘上存的是随机名，避免重名覆盖和中文路径问题
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120))

    note: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
