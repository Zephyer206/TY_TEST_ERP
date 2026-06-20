"""clarify: add work_hours to production_sessions

Revision ID: clarify20260620c
Revises: clarify20260620b
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "clarify20260620c"
down_revision = "clarify20260620b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_sessions",
        sa.Column("work_hours", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("production_sessions", "work_hours")
