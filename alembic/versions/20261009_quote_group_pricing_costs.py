"""Add editable quote cost components for project quotations."""

from alembic import op
import sqlalchemy as sa

revision = "20261009_qg_pricing_costs"
down_revision = "20261008_qg_material_snap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, precision in (
        ("surface_treatment_fee", "12,4"),
        ("inspection_fee", "12,4"),
        ("packaging_fee", "12,4"),
        ("freight_fee", "12,4"),
        ("management_fee", "12,4"),
        ("profit_margin", "7,4"),
    ):
        op.execute(
            f"ALTER TABLE quote_groups ADD COLUMN IF NOT EXISTS {name} NUMERIC({precision}) NOT NULL DEFAULT 0;"
        )


def downgrade() -> None:
    for name in ("profit_margin", "management_fee", "freight_fee", "packaging_fee", "inspection_fee", "surface_treatment_fee"):
        op.execute(f"ALTER TABLE quote_groups DROP COLUMN IF EXISTS {name};")
