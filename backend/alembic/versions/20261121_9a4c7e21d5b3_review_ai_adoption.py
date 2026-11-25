"""stage_reviews 增加 AI 采纳记录

Revision ID: 9a4c7e21d5b3
Revises: 8c77a74104f4
Create Date: 2026-11-21

为什么单独记：
- ai_run_id 回答"这次退回参考了哪一版预审"；
- ai_adopted 存老师勾选采纳的问题原文，用来算 AI 建议采纳率，
  也方便回看"老师当时为什么这么退回"。
两者都允许为空：没开 AI、AI 失败、老师完全没用建议时都是 NULL。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a4c7e21d5b3"
down_revision: Union[str, Sequence[str], None] = "8c77a74104f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stage_reviews", sa.Column("ai_run_id", sa.Integer(), nullable=True))
    op.add_column("stage_reviews", sa.Column("ai_adopted", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_stage_reviews_ai_run_id",
        "stage_reviews",
        "ai_runs",
        ["ai_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_stage_reviews_ai_run_id", "stage_reviews", ["ai_run_id"])


def downgrade() -> None:
    op.drop_index("ix_stage_reviews_ai_run_id", table_name="stage_reviews")
    op.drop_constraint("fk_stage_reviews_ai_run_id", "stage_reviews", type_="foreignkey")
    op.drop_column("stage_reviews", "ai_adopted")
    op.drop_column("stage_reviews", "ai_run_id")
