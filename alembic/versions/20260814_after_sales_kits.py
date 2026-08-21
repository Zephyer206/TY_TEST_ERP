"""Add after-sales installation kit archives.

Revision ID: 20260814_after_sales_kits
Revises: 20260812_left_right_pair_plans
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260814_after_sales_kits"
down_revision = "20260812_left_right_pair_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "after_sales_installation_kits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_item_no", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=40), server_default="installation_kit", nullable=False),
        sa.Column("fmg_code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("d_code", sa.String(length=100), nullable=True),
        sa.Column("tianyue_pn", sa.String(length=100), nullable=True),
        sa.Column("ibi_spec", sa.Text(), nullable=True),
        sa.Column("internal_kit_spec", sa.Text(), nullable=True),
        sa.Column("drawing_status", sa.String(length=300), nullable=True),
        sa.Column("sample_status", sa.String(length=300), nullable=True),
        sa.Column("ppap_status", sa.String(length=300), nullable=True),
        sa.Column("price", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("source_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_file_name", sa.String(length=300), nullable=True),
        sa.Column("source_sheet", sa.String(length=100), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fmg_code", name="uq_after_sales_installation_kits_fmg_code"),
    )
    op.create_index("ix_after_sales_installation_kits_fmg_code", "after_sales_installation_kits", ["fmg_code"])
    op.create_index("ix_after_sales_installation_kits_priority", "after_sales_installation_kits", ["priority"])
    op.create_index("ix_after_sales_installation_kits_d_code", "after_sales_installation_kits", ["d_code"])
    op.create_index("ix_after_sales_installation_kits_tianyue_pn", "after_sales_installation_kits", ["tianyue_pn"])
    op.create_index("ix_after_sales_installation_kits_is_active", "after_sales_installation_kits", ["is_active"])

    op.create_table(
        "after_sales_kit_components",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kit_id", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=20), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("part_number", sa.String(length=200), nullable=True),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["kit_id"], ["after_sales_installation_kits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_after_sales_kit_components_kit_id", "after_sales_kit_components", ["kit_id"])
    op.create_index("ix_after_sales_kit_components_source_kind", "after_sales_kit_components", ["source_kind"])

    op.create_table(
        "after_sales_kit_change_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kit_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_file_name", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["kit_id"], ["after_sales_installation_kits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_after_sales_kit_change_logs_kit_id", "after_sales_kit_change_logs", ["kit_id"])
    op.create_index("ix_after_sales_kit_change_logs_created_at", "after_sales_kit_change_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_after_sales_kit_change_logs_created_at", table_name="after_sales_kit_change_logs")
    op.drop_index("ix_after_sales_kit_change_logs_kit_id", table_name="after_sales_kit_change_logs")
    op.drop_table("after_sales_kit_change_logs")
    op.drop_index("ix_after_sales_kit_components_source_kind", table_name="after_sales_kit_components")
    op.drop_index("ix_after_sales_kit_components_kit_id", table_name="after_sales_kit_components")
    op.drop_table("after_sales_kit_components")
    op.drop_index("ix_after_sales_installation_kits_is_active", table_name="after_sales_installation_kits")
    op.drop_index("ix_after_sales_installation_kits_tianyue_pn", table_name="after_sales_installation_kits")
    op.drop_index("ix_after_sales_installation_kits_d_code", table_name="after_sales_installation_kits")
    op.drop_index("ix_after_sales_installation_kits_priority", table_name="after_sales_installation_kits")
    op.drop_index("ix_after_sales_installation_kits_fmg_code", table_name="after_sales_installation_kits")
    op.drop_table("after_sales_installation_kits")
