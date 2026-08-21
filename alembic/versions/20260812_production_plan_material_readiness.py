"""Add material-readiness and TWP snapshots to production plans.

Revision ID: 20260812_plan_material_readiness
Revises: 20260809_retire_legacy_columns
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_plan_material_readiness"
down_revision = "20260809_retire_legacy_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_plans",
        sa.Column("is_urgent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "production_plans",
        sa.Column("material_status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column("production_plans", sa.Column("material_confirmed_qty", sa.Integer(), nullable=True))
    op.add_column("production_plans", sa.Column("material_confirmed_by", sa.Integer(), nullable=True))
    op.add_column("production_plans", sa.Column("material_confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("production_plans", sa.Column("material_confirmation_note", sa.Text(), nullable=True))
    op.add_column(
        "production_plans",
        sa.Column("material_calculation_mode", sa.String(length=16), nullable=False, server_default="manual"),
    )
    op.add_column("production_plans", sa.Column("twp_source_spec_id", sa.Integer(), nullable=True))
    op.add_column("production_plans", sa.Column("twp_value", sa.String(length=100), nullable=True))
    op.add_column("production_plans", sa.Column("twp_thickness", sa.Numeric(10, 3), nullable=True))
    op.add_column("production_plans", sa.Column("twp_width", sa.Numeric(10, 3), nullable=True))
    op.add_column("production_plans", sa.Column("twp_pitch", sa.Numeric(10, 3), nullable=True))
    op.add_column("production_plans", sa.Column("twp_cavity_count", sa.Integer(), nullable=True))
    op.add_column(
        "production_plans",
        sa.Column("twp_manual_override", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("production_plans", sa.Column("material_name_snapshot", sa.String(length=100), nullable=True))
    op.add_column("production_plans", sa.Column("material_density_snapshot", sa.Numeric(10, 4), nullable=True))
    op.add_column("production_plans", sa.Column("cancellation_reason", sa.Text(), nullable=True))

    op.create_foreign_key(
        "fk_production_plans_twp_source_spec",
        "production_plans",
        "part_tooling_specs",
        ["twp_source_spec_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_production_plans_material_status", "production_plans", ["material_status"])
    op.create_index("ix_production_plans_twp_source_spec_id", "production_plans", ["twp_source_spec_id"])


def downgrade() -> None:
    op.drop_index("ix_production_plans_twp_source_spec_id", table_name="production_plans")
    op.drop_index("ix_production_plans_material_status", table_name="production_plans")
    op.drop_constraint("fk_production_plans_twp_source_spec", "production_plans", type_="foreignkey")
    op.drop_column("production_plans", "cancellation_reason")
    op.drop_column("production_plans", "material_density_snapshot")
    op.drop_column("production_plans", "material_name_snapshot")
    op.drop_column("production_plans", "twp_manual_override")
    op.drop_column("production_plans", "twp_cavity_count")
    op.drop_column("production_plans", "twp_pitch")
    op.drop_column("production_plans", "twp_width")
    op.drop_column("production_plans", "twp_thickness")
    op.drop_column("production_plans", "twp_value")
    op.drop_column("production_plans", "twp_source_spec_id")
    op.drop_column("production_plans", "material_calculation_mode")
    op.drop_column("production_plans", "material_confirmation_note")
    op.drop_column("production_plans", "material_confirmed_at")
    op.drop_column("production_plans", "material_confirmed_by")
    op.drop_column("production_plans", "material_confirmed_qty")
    op.drop_column("production_plans", "material_status")
    op.drop_column("production_plans", "is_urgent")
