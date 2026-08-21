"""Add before/after values and actor metadata for editable after-sales fields.

The legacy installation-kit tables remain in place during the gaibo migration
observation window. These columns make the current FMG dossier fully editable
without losing the existing import history.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_after_sales_editable"
down_revision = "20260815_kit_component_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "after_sales_kit_change_logs",
        sa.Column(
            "change_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "after_sales_kit_change_logs",
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_after_sales_kit_change_logs_actor_user_id",
        "after_sales_kit_change_logs",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_after_sales_kit_change_logs_actor_user_id",
        table_name="after_sales_kit_change_logs",
    )
    op.drop_column("after_sales_kit_change_logs", "actor_user_id")
    op.drop_column("after_sales_kit_change_logs", "change_data")
