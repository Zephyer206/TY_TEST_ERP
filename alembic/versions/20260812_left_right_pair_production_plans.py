"""Store one-output-pair production plans as a shared manufacturing demand.

Revision ID: 20260812_left_right_pair_plans
Revises: 20260812_plan_material_readiness
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_left_right_pair_plans"
down_revision = "20260812_plan_material_readiness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_plans", sa.Column("paired_part_id", sa.Integer(), nullable=True))
    op.add_column(
        "production_plans",
        sa.Column("is_left_right_pair", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("production_plans", sa.Column("paired_customer_part_no_snapshot", sa.String(length=200), nullable=True))
    op.add_column("production_plans", sa.Column("paired_part_name_snapshot", sa.String(length=200), nullable=True))
    op.create_foreign_key(
        "fk_production_plans_paired_part",
        "production_plans",
        "parts",
        ["paired_part_id"],
        ["id"],
    )
    op.create_index("ix_production_plans_paired_part_id", "production_plans", ["paired_part_id"])


def downgrade() -> None:
    op.drop_index("ix_production_plans_paired_part_id", table_name="production_plans")
    op.drop_constraint("fk_production_plans_paired_part", "production_plans", type_="foreignkey")
    op.drop_column("production_plans", "paired_part_name_snapshot")
    op.drop_column("production_plans", "paired_customer_part_no_snapshot")
    op.drop_column("production_plans", "is_left_right_pair")
    op.drop_column("production_plans", "paired_part_id")
