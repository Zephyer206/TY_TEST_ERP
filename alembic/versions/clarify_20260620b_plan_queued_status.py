"""clarify: add queued status to production_plans

Revision ID: clarify20260620b
Revises: clarify20260620
Create Date: 2026-06-20
"""
from alembic import op

revision = "clarify20260620b"
down_revision = "clarify20260620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: add new enum value (irreversible in PG < 14 without recreate)
    op.execute("ALTER TYPE planstatus ADD VALUE IF NOT EXISTS 'queued' AFTER 'planned'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL without table recreation
    pass
