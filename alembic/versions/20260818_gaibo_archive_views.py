"""Add gaibo archive display fields and user view preferences."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_gaibo_archive_views"
down_revision = "20260818_gaibo_doc_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gaibo_installation_packages", sa.Column("priority", sa.Integer(), nullable=True))
    op.add_column("gaibo_installation_packages", sa.Column("d_code", sa.String(100), nullable=True))
    op.add_column("gaibo_installation_packages", sa.Column("tianyue_pn", sa.String(100), nullable=True))
    op.create_index("ix_gaibo_installation_packages_priority", "gaibo_installation_packages", ["priority"])
    op.create_index("ix_gaibo_installation_packages_d_code", "gaibo_installation_packages", ["d_code"])
    op.create_index("ix_gaibo_installation_packages_tianyue_pn", "gaibo_installation_packages", ["tianyue_pn"])

    op.execute(
        """
        UPDATE gaibo_installation_packages AS package
        SET priority = legacy.priority,
            d_code = legacy.d_code,
            tianyue_pn = legacy.tianyue_pn
        FROM after_sales_installation_kits AS legacy
        WHERE legacy.fmg_code = package.package_number
        """
    )

    op.create_table(
        "gaibo_view_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("view_key", sa.String(100), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "view_key", name="uq_gaibo_view_preference_user_key"),
    )
    op.create_index("ix_gaibo_view_preferences_user_id", "gaibo_view_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_gaibo_view_preferences_user_id", table_name="gaibo_view_preferences")
    op.drop_table("gaibo_view_preferences")
    op.drop_index("ix_gaibo_installation_packages_tianyue_pn", table_name="gaibo_installation_packages")
    op.drop_index("ix_gaibo_installation_packages_d_code", table_name="gaibo_installation_packages")
    op.drop_index("ix_gaibo_installation_packages_priority", table_name="gaibo_installation_packages")
    op.drop_column("gaibo_installation_packages", "tianyue_pn")
    op.drop_column("gaibo_installation_packages", "d_code")
    op.drop_column("gaibo_installation_packages", "priority")
