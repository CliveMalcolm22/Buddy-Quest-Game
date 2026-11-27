"""Add habit tracking.

Revision ID: 20261125_0005
Revises: 20261125_0004
"""

from alembic import op
import sqlalchemy as sa


revision = "20261125_0005"
down_revision = "20261125_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "habits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="daily"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_habits_id", "habits", ["id"])
    op.create_index("ix_habits_user_id", "habits", ["user_id"])

    op.create_table(
        "habit_completions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("habit_id", sa.Integer(), nullable=False),
        sa.Column("completion_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["habit_id"], ["habits.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "habit_id",
            "completion_date",
            name="uq_habit_completion_date",
        ),
    )
    op.create_index("ix_habit_completions_id", "habit_completions", ["id"])
    op.create_index(
        "ix_habit_completions_habit_id",
        "habit_completions",
        ["habit_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_habit_completions_habit_id", table_name="habit_completions")
    op.drop_index("ix_habit_completions_id", table_name="habit_completions")
    op.drop_table("habit_completions")
    op.drop_index("ix_habits_user_id", table_name="habits")
    op.drop_index("ix_habits_id", table_name="habits")
    op.drop_table("habits")
