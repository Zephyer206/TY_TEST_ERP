"""Enforce one status row per document type and gaibo owner.

The original gaibo schema enforced exactly one owner, but PostgreSQL treats
NULLs as distinct in a three-column unique constraint.  Two partial unique
indexes model the intended requirement/package ownership explicitly.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_gaibo_doc_unique"
down_revision = "20260818_gaibo_after_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_gaibo_document_requirement_type",
        "gaibo_document_statuses",
        ["requirement_id", "document_type"],
        unique=True,
        postgresql_where=sa.text("requirement_id IS NOT NULL"),
    )
    op.create_index(
        "uq_gaibo_document_package_type",
        "gaibo_document_statuses",
        ["package_id", "document_type"],
        unique=True,
        postgresql_where=sa.text("package_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_gaibo_document_package_type", table_name="gaibo_document_statuses")
    op.drop_index("uq_gaibo_document_requirement_type", table_name="gaibo_document_statuses")
