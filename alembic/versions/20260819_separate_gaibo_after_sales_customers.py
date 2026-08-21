"""Separate after-sales customer master data from the ERP customer table."""

from alembic import op
import sqlalchemy as sa


revision = "20260819_gaibo_afsc"
down_revision = "20260818_gaibo_customer_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gaibo_after_sales_customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("migration_workspace_id", sa.Integer(), nullable=True, unique=True),
        sa.UniqueConstraint("name", name="uq_gaibo_after_sales_customer_name"),
    )
    op.create_index("ix_gaibo_after_sales_customers_name", "gaibo_after_sales_customers", ["name"])
    op.create_index("ix_gaibo_after_sales_customers_is_active", "gaibo_after_sales_customers", ["is_active"])

    op.add_column("gaibo_customer_workspaces", sa.Column("after_sales_customer_id", sa.Integer(), nullable=True))
    op.execute(
        """
        INSERT INTO gaibo_after_sales_customers (name, is_active, created_at, updated_at, migration_workspace_id)
        SELECT display_name, is_active, created_at, updated_at, id
        FROM gaibo_customer_workspaces
        """
    )
    op.execute(
        """
        UPDATE gaibo_customer_workspaces AS workspace
        SET after_sales_customer_id = customer.id
        FROM gaibo_after_sales_customers AS customer
        WHERE customer.migration_workspace_id = workspace.id
        """
    )
    op.alter_column("gaibo_customer_workspaces", "after_sales_customer_id", nullable=False)
    op.create_foreign_key(
        "fk_gaibo_workspace_after_sales_customer",
        "gaibo_customer_workspaces",
        "gaibo_after_sales_customers",
        ["after_sales_customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_gaibo_customer_workspaces_after_sales_customer_id", "gaibo_customer_workspaces", ["after_sales_customer_id"])
    op.drop_constraint("uq_gaibo_workspace_customer", "gaibo_customer_workspaces", type_="unique")
    op.create_unique_constraint("uq_gaibo_workspace_after_sales_customer", "gaibo_customer_workspaces", ["after_sales_customer_id"])
    op.drop_constraint("gaibo_customer_workspaces_customer_id_fkey", "gaibo_customer_workspaces", type_="foreignkey")
    op.drop_column("gaibo_customer_workspaces", "customer_id")
    op.drop_column("gaibo_after_sales_customers", "migration_workspace_id")


def downgrade() -> None:
    raise RuntimeError(
        "The after-sales customer split is intentionally one-way; restore from a database backup instead."
    )
