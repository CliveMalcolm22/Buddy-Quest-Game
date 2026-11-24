"""Add task completion tracking and link point events to tasks.

Revision ID: 20261125_0003
Revises: 20261117_0002
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20261125_0003"
down_revision = "20261117_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    with op.batch_alter_table("point_events") as batch_op:
        batch_op.add_column(
            sa.Column("task_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_point_events_task_id_tasks",
            "tasks",
            ["task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_point_events_task_id",
            ["task_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("point_events") as batch_op:
        batch_op.drop_index("ix_point_events_task_id")
        batch_op.drop_constraint(
            "fk_point_events_task_id_tasks",
            type_="foreignkey",
        )
        batch_op.drop_column("task_id")

    op.drop_column("tasks", "completed_at")
