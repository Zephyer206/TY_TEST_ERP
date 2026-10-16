"""Unify customer-facing part records and add part BOM.

Revision ID: 20260914_unify_parts
Revises: 20260822_shipping_orders
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_unify_parts"
down_revision = "20260822_shipping_orders"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    part_columns = _columns(inspector, "parts")

    additions = (
        ("customer_id", sa.Column("customer_id", sa.Integer(), nullable=True)),
        ("internal_part_no", sa.Column("internal_part_no", sa.String(100), nullable=True)),
        ("customer_part_no", sa.Column("customer_part_no", sa.String(150), nullable=True)),
        ("customer_part_name", sa.Column("customer_part_name", sa.String(200), nullable=True)),
        ("process_type", sa.Column("process_type", sa.String(100), nullable=True)),
        ("process_description", sa.Column("process_description", sa.Text(), nullable=True)),
        ("parent_part_id", sa.Column("parent_part_id", sa.Integer(), nullable=True)),
    )
    for name, column in additions:
        if name not in part_columns:
            op.add_column("parts", column)

    inspector = sa.inspect(bind)
    foreign_keys = inspector.get_foreign_keys("parts")
    customer_fk = next(
        (fk for fk in foreign_keys if fk.get("constrained_columns") == ["customer_id"]),
        None,
    )
    if customer_fk and customer_fk.get("referred_table") != "customers":
        bind.execute(sa.text("UPDATE parts SET customer_id = NULL WHERE customer_id IS NOT NULL"))
        op.drop_constraint(customer_fk["name"], "parts", type_="foreignkey")
        customer_fk = None
    if not customer_fk:
        op.create_foreign_key(
            "fk_parts_customer_id_customers",
            "parts",
            "customers",
            ["customer_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    foreign_keys = sa.inspect(bind).get_foreign_keys("parts")
    if not any(fk.get("constrained_columns") == ["parent_part_id"] for fk in foreign_keys):
        op.create_foreign_key(
            "fk_parts_parent_part_id",
            "parts",
            "parts",
            ["parent_part_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    indexes = _indexes(sa.inspect(bind), "parts")
    for name, columns in (
        ("ix_parts_customer_id", ["customer_id"]),
        ("ix_parts_internal_part_no", ["internal_part_no"]),
        ("ix_parts_customer_part_no", ["customer_part_no"]),
        ("ix_parts_parent_part_id", ["parent_part_id"]),
    ):
        if name not in indexes:
            op.create_index(name, "parts", columns)

    tables = set(sa.inspect(bind).get_table_names())
    if "part_customer_aliases" in tables:
        bind.execute(
            sa.text(
                """
                WITH single_alias AS (
                    SELECT part_id,
                           MIN(customer_id) AS customer_id,
                           MIN(customer_part_no) AS customer_part_no,
                           MIN(customer_part_name) AS customer_part_name
                    FROM part_customer_aliases
                    WHERE is_active = TRUE
                    GROUP BY part_id
                    HAVING COUNT(*) = 1
                )
                UPDATE parts AS p
                   SET customer_id = COALESCE(p.customer_id, a.customer_id),
                       customer_part_no = COALESCE(p.customer_part_no, a.customer_part_no),
                       customer_part_name = COALESCE(p.customer_part_name, a.customer_part_name)
                  FROM single_alias AS a
                 WHERE p.id = a.part_id
                """
            )
        )

    if "part_BOM" not in tables:
        op.create_table(
            "part_BOM",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("parent_part_id", sa.Integer(), nullable=False),
            sa.Column("component_part_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
            sa.Column("unit", sa.String(30), nullable=False, server_default="个"),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("revision", sa.String(50), nullable=False, server_default="V1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("quantity > 0", name="ck_part_bom_quantity_positive"),
            sa.CheckConstraint("parent_part_id <> component_part_id", name="ck_part_bom_no_self_reference"),
            sa.ForeignKeyConstraint(["parent_part_id"], ["parts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["component_part_id"], ["parts.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint(
                "parent_part_id",
                "component_part_id",
                "revision",
                name="uq_part_bom_component_revision",
            ),
        )
        op.create_index("ix_part_BOM_parent_part_id", "part_BOM", ["parent_part_id"])
        op.create_index("ix_part_BOM_component_part_id", "part_BOM", ["component_part_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "part_BOM" in tables:
        op.drop_table("part_BOM")

    columns = _columns(sa.inspect(bind), "parts")
    for column_name in (
        "parent_part_id",
        "process_description",
        "process_type",
        "customer_part_name",
        "customer_part_no",
        "internal_part_no",
    ):
        if column_name in columns:
            op.drop_column("parts", column_name)
