from alembic import op
import sqlalchemy as sa


revision = "20261125_0004"
down_revision = "20261119_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduler_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "event_type", name="uq_scheduler_event_task_type"),
    )
    op.create_index(op.f("ix_scheduler_events_id"), "scheduler_events", ["id"], unique=False)
    op.create_index(op.f("ix_scheduler_events_task_id"), "scheduler_events", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scheduler_events_task_id"), table_name="scheduler_events")
    op.drop_index(op.f("ix_scheduler_events_id"), table_name="scheduler_events")
    op.drop_table("scheduler_events")
