"""学生档案。

学生与登录账号解耦：管理员可以先导入学生名单（还没有账号），
后续再为学生开通账号，所以 user_id 允许为空且唯一。
current_stage 记录学生当前所处的流程节点，管理员看板的阶段分布直接按它统计。
"""

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import STAGE_ORDER, Stage, StudentStatus

_STAGE_VALUES = ", ".join(f"'{stage.value}'" for stage in STAGE_ORDER)
_STATUS_VALUES = ", ".join(f"'{status.value}'" for status in StudentStatus)


class Student(Base, TimestampMixin):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint(f"current_stage IN ({_STAGE_VALUES})", name="ck_students_current_stage"),
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_students_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, index=True
    )
    sno: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    major: Mapped[str] = mapped_column(String(100), nullable=False)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False)
    grade: Mapped[str] = mapped_column(String(10), nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    current_stage: Mapped[str] = mapped_column(
        String(24), nullable=False, default=Stage.TOPIC.value, server_default=Stage.TOPIC.value, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=StudentStatus.ACTIVE.value, server_default=StudentStatus.ACTIVE.value
    )
