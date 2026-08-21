"""Add customer-scoped archive column configuration and package extra data."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_gaibo_customer_columns"
down_revision = "20260818_gaibo_archive_views"
branch_labels = None
depends_on = None


def _jsonb(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.add_column("gaibo_customer_workspaces", _jsonb("default_view_config"))
    op.add_column(
        "gaibo_customer_workspaces",
        sa.Column("column_config_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column("gaibo_installation_packages", _jsonb("extra_data"))


def downgrade() -> None:
    op.drop_column("gaibo_installation_packages", "extra_data")
    op.drop_column("gaibo_customer_workspaces", "column_config_version")
    op.drop_column("gaibo_customer_workspaces", "default_view_config")
