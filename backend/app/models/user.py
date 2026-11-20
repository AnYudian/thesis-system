"""用户表。

role 用 VARCHAR + CHECK 约束而不是 PostgreSQL 原生 enum：
后者改枚举值需要 ALTER TYPE，迁移麻烦；本期角色稳定但后续可能加"教研室"等角色。
"""

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'TEACHER', 'STUDENT')", name="ck_users_role"),
        # 教师身份只约束教师行；管理员 / 学生留空，避免给无关行填无意义的值
        CheckConstraint(
            "teacher_type IS NULL OR teacher_type IN ('SUPERVISOR', 'REVIEWER')",
            name="ck_users_teacher_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    # 教师分工：SUPERVISOR（指导教师，带学生、做阶段审核）/ REVIEWER（就业老师，仅身份占位）。
    # 导师分配、批量导入、阶段审核都只认 SUPERVISOR，见 student_service。
    teacher_type: Mapped[str | None] = mapped_column(String(16))

    # 教师档案：学院、专业、手机号、邮箱。教师要用它联系学生，所以由业务层要求必填；
    # 数据库层面仍允许为空——历史账号和管理员账号都不需要这几项，加 NOT NULL 会挡住迁移。
    college: Mapped[str | None] = mapped_column(String(100))
    major: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
