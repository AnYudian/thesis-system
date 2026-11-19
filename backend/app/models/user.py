"""用户表。

role 用 VARCHAR + CHECK 约束而不是 PostgreSQL 原生 enum：
后者改枚举值需要 ALTER TYPE，迁移麻烦；本期角色稳定但后续可能加"教研室/评阅"。
"""

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'TEACHER', 'STUDENT')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    # 教师档案：学院、专业、手机号、QQ。教师要用它联系学生，所以由业务层要求必填；
    # 数据库层面仍允许为空——历史账号和管理员账号都不需要这几项，加 NOT NULL 会挡住迁移。
    college: Mapped[str | None] = mapped_column(String(100))
    major: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    qq: Mapped[str | None] = mapped_column(String(30))
