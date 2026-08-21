"""Add per-pair component status annotations for after-sales kits.

Revision ID: 20260815_after_sales_component_annotations
Revises: 20260814_after_sales_kits
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260815_kit_component_status"
down_revision = "20260814_after_sales_kits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "after_sales_kit_component_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kit_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["kit_id"], ["after_sales_installation_kits.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kit_id", "sequence", name="uq_after_sales_kit_component_annotation_pair"
        ),
    )
    op.create_index(
        "ix_after_sales_kit_component_annotations_kit_id",
        "after_sales_kit_component_annotations",
        ["kit_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_after_sales_kit_component_annotations_kit_id",
        table_name="after_sales_kit_component_annotations",
    )
    op.drop_table("after_sales_kit_component_annotations")
