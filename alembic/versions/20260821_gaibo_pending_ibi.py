"""Preserve installation-kit internal composition when IBI is not supplied."""

from alembic import op
import sqlalchemy as sa


revision = "20260821_gaibo_pending_ibi"
down_revision = "20260819_gaibo_afsc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "gaibo_package_items",
        "ibi",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.drop_constraint(
        "ck_gaibo_package_item_reference",
        "gaibo_package_items",
        type_="check",
    )
    op.create_check_constraint(
        "ck_gaibo_package_item_reference",
        "gaibo_package_items",
        "requirement_id IS NOT NULL OR unlinked_customer_part_number IS NOT NULL OR ibi IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_gaibo_package_item_reference",
        "gaibo_package_items",
        type_="check",
    )
    op.create_check_constraint(
        "ck_gaibo_package_item_reference",
        "gaibo_package_items",
        "requirement_id IS NOT NULL OR unlinked_customer_part_number IS NOT NULL",
    )
    op.alter_column(
        "gaibo_package_items",
        "ibi",
        existing_type=sa.Text(),
        nullable=False,
    )
