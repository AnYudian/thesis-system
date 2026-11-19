"""teacher type: 教师分「指导教师 / 评阅教师」

Revision ID: c5d81a4f7e20
Revises: 62f173a997e2
Create Date: 2026-11-19 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d81a4f7e20'
down_revision: Union[str, Sequence[str], None] = '62f173a997e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('teacher_type', sa.String(length=16), nullable=True))
    op.create_check_constraint(
        'ck_users_teacher_type',
        'users',
        "teacher_type IS NULL OR teacher_type IN ('SUPERVISOR', 'REVIEWER')",
    )
    # 存量教师全部按指导教师回填：他们本来就带着学生、在做阶段审核，
    # 不回填的话管理员一编辑旧账号就会被"身份必填"挡住。
    op.execute("UPDATE users SET teacher_type = 'SUPERVISOR' WHERE role = 'TEACHER'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_users_teacher_type', 'users', type_='check')
    op.drop_column('users', 'teacher_type')
