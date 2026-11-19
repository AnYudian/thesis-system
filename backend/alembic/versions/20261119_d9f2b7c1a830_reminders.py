"""reminders: 教师催交材料提醒

Revision ID: d9f2b7c1a830
Revises: c5d81a4f7e20
Create Date: 2026-11-19 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9f2b7c1a830'
down_revision: Union[str, Sequence[str], None] = 'c5d81a4f7e20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STAGES = "'TOPIC', 'TASK_BOOK', 'PROPOSAL', 'MIDTERM', 'PLAGIARISM', 'THESIS', 'REVIEW', 'DEFENSE', 'ARCHIVE'"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=True),
        sa.Column('stage', sa.String(length=24), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(f'stage IN ({_STAGES})', name='ck_reminders_stage'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reminders_stage'), 'reminders', ['stage'], unique=False)
    op.create_index(op.f('ix_reminders_student_id'), 'reminders', ['student_id'], unique=False)
    op.create_index(op.f('ix_reminders_teacher_id'), 'reminders', ['teacher_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_reminders_teacher_id'), table_name='reminders')
    op.drop_index(op.f('ix_reminders_student_id'), table_name='reminders')
    op.drop_index(op.f('ix_reminders_stage'), table_name='reminders')
    op.drop_table('reminders')
