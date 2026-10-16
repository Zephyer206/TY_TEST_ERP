"""Add shipping order workflow tables."""

from alembic import op
import sqlalchemy as sa

revision = "20260822_shipping_orders"
down_revision = "20260821_gaibo_pending_ibi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipping_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_no", sa.String(40), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False, server_default="formal"),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("temporary_customer_name", sa.String(200), nullable=True),
        sa.Column("po_no", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_modified_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("order_no", name="uq_shipping_orders_order_no"),
    )
    op.create_index("ix_shipping_orders_status", "shipping_orders", ["status"])
    op.create_index("ix_shipping_orders_created_by", "shipping_orders", ["created_by"])
    op.create_index("ix_shipping_orders_customer_id", "shipping_orders", ["customer_id"])
    op.create_index("ix_shipping_orders_po_no", "shipping_orders", ["po_no"])
    op.create_index("ix_shipping_orders_status_created", "shipping_orders", ["status", "created_at"])
    op.create_index("ix_shipping_orders_customer_po", "shipping_orders", ["customer_id", "po_no"])
    op.create_index("ix_shipping_orders_draft_cleanup", "shipping_orders", ["status", "last_modified_at"])

    op.create_table(
        "shipping_order_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("shipping_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id"), nullable=True),
        sa.Column("part_customer_alias_id", sa.Integer(), sa.ForeignKey("part_customer_aliases.id"), nullable=True),
        sa.Column("customer_part_no_snapshot", sa.String(150), nullable=False),
        sa.Column("part_name_snapshot", sa.String(200), nullable=False),
        sa.Column("ordered_qty", sa.Integer(), nullable=False),
        sa.Column("planned_ship_date", sa.Date(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("status", sa.String(60), nullable=False, server_default="draft"),
        sa.Column("cancelled_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_shipping_order_lines_order_id", "shipping_order_lines", ["order_id"])
    op.create_index("ix_shipping_order_lines_order_status", "shipping_order_lines", ["order_id", "status"])
    op.create_index("ix_shipping_order_lines_alias", "shipping_order_lines", ["part_customer_alias_id"])
    op.create_index("ix_shipping_order_lines_planned_date", "shipping_order_lines", ["planned_ship_date"])
    op.create_index("ix_shipping_order_lines_part_id", "shipping_order_lines", ["part_id"])

    op.create_table(
        "shipping_label_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_line_id", sa.Integer(), sa.ForeignKey("shipping_order_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.UniqueConstraint("order_line_id", name="uq_shipping_label_line"),
    )
    op.create_table(
        "shipping_cancellation_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_line_id", sa.Integer(), sa.ForeignKey("shipping_order_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cancel_qty", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("business_confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("business_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("label_confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("label_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_shipping_cancellation_consents_line", "shipping_cancellation_consents", ["order_line_id"])
    op.create_table(
        "shipping_shipments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shipment_no", sa.String(40), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("shipping_orders.id"), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("production_batch_no", sa.String(100), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.UniqueConstraint("shipment_no", name="uq_shipping_shipments_no"),
    )
    op.create_index("ix_shipping_shipments_order_id", "shipping_shipments", ["order_id"])
    op.create_table(
        "shipping_shipment_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shipment_id", sa.Integer(), sa.ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_line_id", sa.Integer(), sa.ForeignKey("shipping_order_lines.id"), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
    )
    op.create_index("ix_shipping_shipment_lines_shipment_id", "shipping_shipment_lines", ["shipment_id"])
    op.create_index("ix_shipping_shipment_lines_order_line_id", "shipping_shipment_lines", ["order_line_id"])
    op.create_table(
        "shipping_logistics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shipment_id", sa.Integer(), sa.ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("carrier_name", sa.String(100), nullable=True),
        sa.Column("tracking_no", sa.String(150), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_shipping_logistics_shipment_id", "shipping_logistics", ["shipment_id"])


def downgrade() -> None:
    op.drop_table("shipping_logistics")
    op.drop_table("shipping_shipment_lines")
    op.drop_table("shipping_shipments")
    op.drop_table("shipping_cancellation_consents")
    op.drop_table("shipping_label_confirmations")
    op.drop_table("shipping_order_lines")
    op.drop_table("shipping_orders")
