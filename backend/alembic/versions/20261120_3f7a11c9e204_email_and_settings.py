"""teacher email + system settings

教师档案把 QQ 换成邮箱，并新增系统参数表（中期最少沟通次数、各环节截止日期）。

Revision ID: 3f7a11c9e204
Revises: d9f2b7c1a830
Create Date: 2026-11-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f7a11c9e204'
down_revision: Union[str, Sequence[str], None] = 'd9f2b7c1a830'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('email', sa.String(length=120), nullable=True))
    # 历史教师只有 QQ 号，没法直接转成合法邮箱；按账号生成学校邮箱占位，
    # 管理员在「账号管理」里改成真实邮箱即可（邮箱在业务层仍然必填）。
    op.execute(
        "UPDATE users SET email = username || '@school.edu.cn' "
        "WHERE role = 'TEACHER' AND email IS NULL"
    )
    op.drop_column('users', 'qq')

    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('system_settings')

    op.add_column('users', sa.Column('qq', sa.String(length=30), nullable=True))
    # 回滚时邮箱按账号生成一个数字占位，保证 QQ 的格式校验（5-12 位数字）能通过
    op.execute(
        "UPDATE users SET qq = lpad((1000 + id)::text, 5, '0') "
        "WHERE role = 'TEACHER' AND qq IS NULL"
    )
    op.drop_column('users', 'email')
