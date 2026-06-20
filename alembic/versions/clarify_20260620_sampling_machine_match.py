"""clarify: add assigned_machine_id to sample_tasks

Revision ID: clarify20260620
Revises:
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "clarify20260620"
down_revision = "qr003_fix_missing_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sample_tasks",
        sa.Column("assigned_machine_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_sample_tasks_assigned_machine_id",
        "sample_tasks",
        ["assigned_machine_id"],
    )
    op.create_foreign_key(
        "fk_sample_tasks_assigned_machine_id",
        "sample_tasks",
        "machines",
        ["assigned_machine_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_sample_tasks_assigned_machine_id", "sample_tasks", type_="foreignkey")
    op.drop_index("ix_sample_tasks_assigned_machine_id", table_name="sample_tasks")
    op.drop_column("sample_tasks", "assigned_machine_id")
