"""Drop legacy mold summary columns from parts.

The authoritative mold number and mold type now come from tooling joined
through tooling_parts.  Keeping text copies on parts risks diverging data.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260804_drop_part_mold"
down_revision = "20260730_explicit_part_grouping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE parts DROP COLUMN IF EXISTS mold_number")
    op.execute("ALTER TABLE parts DROP COLUMN IF EXISTS mold_type")


def downgrade() -> None:
    op.add_column("parts", sa.Column("mold_number", sa.String(length=50), nullable=True))
    op.add_column("parts", sa.Column("mold_type", sa.String(length=50), nullable=True))
