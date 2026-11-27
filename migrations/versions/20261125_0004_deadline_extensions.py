"""Add one-time task deadline extension audit records.

Revision ID: 20261125_0004
Revises: 20261125_0003
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20261125_0004"
down_revision = "20261125_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deadline_extensions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("extended_by_user_id", sa.Integer(), nullable=False),
        sa.Column("original_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extended_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["extended_by_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("task_id", name="uq_deadline_extensions_task_id"),
    )
    op.create_index(
        "ix_deadline_extensions_id",
        "deadline_extensions",
        ["id"],
    )


def downgrade() -> None:
    op.drop_index("ix_deadline_extensions_id", table_name="deadline_extensions")
    op.drop_table("deadline_extensions")
