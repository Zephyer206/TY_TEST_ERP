"""Store density and scrap price snapshots on project quote groups."""

from alembic import op


revision = "20261008_qg_material_snap"
down_revision = "20261007_material_library_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE quote_groups ADD COLUMN IF NOT EXISTS material_density NUMERIC(10,4);")
    op.execute("ALTER TABLE quote_groups ADD COLUMN IF NOT EXISTS material_scrap_price NUMERIC(12,4);")


def downgrade() -> None:
    op.execute("ALTER TABLE quote_groups DROP COLUMN IF EXISTS material_scrap_price;")
    op.execute("ALTER TABLE quote_groups DROP COLUMN IF EXISTS material_density;")
