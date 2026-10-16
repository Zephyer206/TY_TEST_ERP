"""Persist project quotation groups and technical review data."""

from alembic import op
import sqlalchemy as sa

revision = "20261006_quote_groups"
down_revision = "20261004_customer_inquiries"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_inquiries", sa.Column("technical_data", sa.JSON(), nullable=True))
    op.create_table(
        "quote_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_no", sa.String(50), nullable=False),
        sa.Column("inquiry_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="待报价"),
        sa.Column("quote_path", sa.String(60), nullable=False, server_default="待确定方案"),
        sa.Column("tooling_type", sa.String(100), nullable=True),
        sa.Column("tooling_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tooling_lead_time", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tooling_life", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("material_name", sa.String(100), nullable=True),
        sa.Column("material_unit_price", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("material_adjustment", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("quote_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["inquiry_id"], ["customer_inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("group_no", name="uq_quote_groups_group_no"),
        sa.UniqueConstraint("inquiry_id", name="uq_quote_groups_inquiry"),
    )
    op.create_index("ix_quote_groups_inquiry_id", "quote_groups", ["inquiry_id"])
    op.create_index("ix_quote_groups_customer_id", "quote_groups", ["customer_id"])
    op.create_table(
        "quote_group_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_group_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("customer_part_no", sa.String(150), nullable=True),
        sa.Column("part_name", sa.String(200), nullable=True),
        sa.Column("pair_key", sa.String(80), nullable=True),
        sa.Column("material_name", sa.String(100), nullable=True),
        sa.Column("thickness", sa.Numeric(10, 4), nullable=True),
        sa.Column("width", sa.Numeric(10, 4), nullable=True),
        sa.Column("pitch", sa.Numeric(10, 4), nullable=True),
        sa.Column("utilization", sa.Numeric(7, 4), nullable=True),
        sa.Column("press_tonnage", sa.Integer(), nullable=True),
        sa.Column("cavity_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tooling_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tooling_lead_time", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("product_price", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("annual_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifecycle_years", sa.Numeric(10, 2), nullable=True),
        sa.Column("technical_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["quote_group_id"], ["quote_groups.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_quote_group_items_group_id", "quote_group_items", ["quote_group_id"])
    op.create_index("ix_quote_group_items_pair_key", "quote_group_items", ["pair_key"])


def downgrade():
    op.drop_table("quote_group_items")
    op.drop_table("quote_groups")
    op.drop_column("customer_inquiries", "technical_data")
