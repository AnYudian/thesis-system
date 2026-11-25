"""ai_runs attempts

Revision ID: 8c77a74104f4
Revises: dfe5459c9a20
Create Date: 2026-11-20 10:53:55.016187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c77a74104f4'
down_revision: Union[str, Sequence[str], None] = 'dfe5459c9a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """记录实际调用模型的次数（1 = 一次成功，>1 = 自动重试过）。"""
    op.add_column(
        "ai_runs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("ai_runs", "attempts")
