"""Create persistent customer inquiry records and uploaded review files."""

from alembic import op
import sqlalchemy as sa


revision = "20261004_customer_inquiries"
down_revision = "20260916_consolidate_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_inquiries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inquiry_no", sa.String(length=50), nullable=False),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id"),
            nullable=False,
        ),
        sa.Column("project_name", sa.String(length=255), nullable=False, server_default="待命名项目"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="报价中"),
        sa.Column("technical_review", sa.String(length=40), nullable=False, server_default="待评审"),
        sa.Column("technical_review_note", sa.Text(), nullable=True),
        sa.Column("owner_name", sa.String(length=100), nullable=False, server_default="待分配"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("inquiry_no", name="uq_customer_inquiries_inquiry_no"),
    )
    op.create_index("ix_customer_inquiries_customer_id", "customer_inquiries", ["customer_id"])
    op.create_index("ix_customer_inquiries_technical_review", "customer_inquiries", ["technical_review"])

    op.create_table(
        "customer_inquiry_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "inquiry_id",
            sa.Integer(),
            sa.ForeignKey("customer_inquiries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("relative_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "ix_customer_inquiry_attachments_inquiry_id",
        "customer_inquiry_attachments",
        ["inquiry_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_customer_inquiry_attachments_inquiry_id", table_name="customer_inquiry_attachments")
    op.drop_table("customer_inquiry_attachments")
    op.drop_index("ix_customer_inquiries_technical_review", table_name="customer_inquiries")
    op.drop_index("ix_customer_inquiries_customer_id", table_name="customer_inquiries")
    op.drop_table("customer_inquiries")
