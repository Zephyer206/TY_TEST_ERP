"""Create the customer-first gaibo after-sales archive tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_gaibo_after_sales"
down_revision = "20260817_after_sales_editable"
branch_labels = None
depends_on = None


def _jsonb(name: str, default: str = "'{}'::jsonb") -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text(default),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "gaibo_customer_workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _jsonb("field_labels"),
        _jsonb("extra_field_definitions"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("customer_id", name="uq_gaibo_workspace_customer"),
        sa.UniqueConstraint("slug", name="uq_gaibo_workspace_slug"),
    )
    op.create_index("ix_gaibo_customer_workspaces_customer_id", "gaibo_customer_workspaces", ["customer_id"])
    op.create_index("ix_gaibo_customer_workspaces_slug", "gaibo_customer_workspaces", ["slug"])
    op.create_index("ix_gaibo_customer_workspaces_is_active", "gaibo_customer_workspaces", ["is_active"])

    op.create_table(
        "gaibo_single_parts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tianyue_internal_part_no", sa.String(100), nullable=True),
        sa.Column("name", sa.String(300), nullable=True),
        sa.Column("drawing_reference", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gaibo_single_parts_part_id", "gaibo_single_parts", ["part_id"])
    op.create_index("ix_gaibo_single_parts_internal_no", "gaibo_single_parts", ["tianyue_internal_part_no"])
    op.create_index("ix_gaibo_single_parts_is_active", "gaibo_single_parts", ["is_active"])

    op.create_table(
        "gaibo_customer_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("gaibo_customer_workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("single_part_id", sa.Integer(), sa.ForeignKey("gaibo_single_parts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_part_number", sa.String(200), nullable=False),
        sa.Column("ibi", sa.Text(), nullable=False),
        sa.Column("tianyue_internal_composition", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        _jsonb("extra_data"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "single_part_id", "customer_part_number", name="uq_gaibo_customer_requirement"),
    )
    for name, column in (
        ("workspace_id", "workspace_id"),
        ("single_part_id", "single_part_id"),
        ("customer_part_number", "customer_part_number"),
        ("ibi", "ibi"),
        ("tianyue_internal_composition", "tianyue_internal_composition"),
        ("is_active", "is_active"),
    ):
        op.create_index(f"ix_gaibo_customer_requirements_{name}", "gaibo_customer_requirements", [column])

    op.create_table(
        "gaibo_installation_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("gaibo_customer_workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("package_number", sa.String(200), nullable=False),
        sa.Column("name", sa.String(300), nullable=True),
        sa.Column("price", sa.Numeric(14, 4), nullable=True),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        _jsonb("source_data"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "package_number", name="uq_gaibo_package_number"),
    )
    op.create_index("ix_gaibo_installation_packages_workspace_id", "gaibo_installation_packages", ["workspace_id"])
    op.create_index("ix_gaibo_installation_packages_package_number", "gaibo_installation_packages", ["package_number"])
    op.create_index("ix_gaibo_installation_packages_is_active", "gaibo_installation_packages", ["is_active"])

    op.create_table(
        "gaibo_package_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("gaibo_installation_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("gaibo_customer_requirements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("unlinked_customer_part_number", sa.String(200), nullable=True),
        sa.Column("ibi", sa.Text(), nullable=False),
        sa.Column("tianyue_internal_composition", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), server_default="1", nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("match_state", sa.String(20), server_default="unlinked", nullable=False),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "requirement_id IS NOT NULL OR unlinked_customer_part_number IS NOT NULL",
            name="ck_gaibo_package_item_reference",
        ),
        sa.UniqueConstraint("package_id", "sequence", name="uq_gaibo_package_item_sequence"),
    )
    op.create_index("ix_gaibo_package_items_package_id", "gaibo_package_items", ["package_id"])
    op.create_index("ix_gaibo_package_items_requirement_id", "gaibo_package_items", ["requirement_id"])

    op.create_table(
        "gaibo_drawings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("gaibo_customer_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(30), server_default="not_started", nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.UniqueConstraint("requirement_id", "version", name="uq_gaibo_drawing_version"),
    )
    op.create_index("ix_gaibo_drawings_requirement_id", "gaibo_drawings", ["requirement_id"])

    op.create_table(
        "gaibo_process_routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("gaibo_customer_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.UniqueConstraint("requirement_id", "version", name="uq_gaibo_route_version"),
    )
    op.create_index("ix_gaibo_process_routes_requirement_id", "gaibo_process_routes", ["requirement_id"])
    op.create_index("ix_gaibo_process_routes_is_current", "gaibo_process_routes", ["is_current"])
    op.create_index(
        "uq_gaibo_current_route_per_requirement",
        "gaibo_process_routes",
        ["requirement_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    op.create_table(
        "gaibo_process_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route_id", sa.Integer(), sa.ForeignKey("gaibo_process_routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("operation_name", sa.String(200), nullable=False),
        sa.Column("machine_id", sa.Integer(), sa.ForeignKey("machines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tooling_id", sa.Integer(), sa.ForeignKey("tooling.id", ondelete="SET NULL"), nullable=True),
        _jsonb("key_parameters"),
        _jsonb("quality_checkpoints"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.UniqueConstraint("route_id", "sequence", name="uq_gaibo_process_step_sequence"),
    )
    op.create_index("ix_gaibo_process_steps_route_id", "gaibo_process_steps", ["route_id"])

    op.create_table(
        "gaibo_document_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("gaibo_customer_requirements.id", ondelete="CASCADE"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("gaibo_installation_packages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), server_default="not_started", nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("concluded_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        _jsonb("source_data"),
        sa.CheckConstraint(
            "(requirement_id IS NOT NULL AND package_id IS NULL) OR (requirement_id IS NULL AND package_id IS NOT NULL)",
            name="ck_gaibo_document_owner",
        ),
    )
    op.create_index("ix_gaibo_document_statuses_requirement_id", "gaibo_document_statuses", ["requirement_id"])
    op.create_index("ix_gaibo_document_statuses_package_id", "gaibo_document_statuses", ["package_id"])
    op.create_index("ix_gaibo_document_statuses_type", "gaibo_document_statuses", ["document_type"])

    op.create_table(
        "gaibo_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("gaibo_customer_workspaces.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        _jsonb("changed_fields", "'[]'::jsonb"),
        _jsonb("change_data"),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gaibo_change_logs_workspace_id", "gaibo_change_logs", ["workspace_id"])
    op.create_index("ix_gaibo_change_logs_entity_type", "gaibo_change_logs", ["entity_type"])
    op.create_index("ix_gaibo_change_logs_entity_id", "gaibo_change_logs", ["entity_id"])
    op.create_index("ix_gaibo_change_logs_actor_user_id", "gaibo_change_logs", ["actor_user_id"])
    op.create_index("ix_gaibo_change_logs_created_at", "gaibo_change_logs", ["created_at"])


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_gaibo_change_logs_created_at", "gaibo_change_logs"),
        ("ix_gaibo_change_logs_actor_user_id", "gaibo_change_logs"),
        ("ix_gaibo_change_logs_entity_id", "gaibo_change_logs"),
        ("ix_gaibo_change_logs_entity_type", "gaibo_change_logs"),
        ("ix_gaibo_change_logs_workspace_id", "gaibo_change_logs"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("gaibo_change_logs")
    for index_name, table_name in (
        ("ix_gaibo_document_statuses_type", "gaibo_document_statuses"),
        ("ix_gaibo_document_statuses_package_id", "gaibo_document_statuses"),
        ("ix_gaibo_document_statuses_requirement_id", "gaibo_document_statuses"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("gaibo_document_statuses")
    op.drop_index("ix_gaibo_process_steps_route_id", table_name="gaibo_process_steps")
    op.drop_table("gaibo_process_steps")
    op.drop_index("uq_gaibo_current_route_per_requirement", table_name="gaibo_process_routes")
    op.drop_index("ix_gaibo_process_routes_is_current", table_name="gaibo_process_routes")
    op.drop_index("ix_gaibo_process_routes_requirement_id", table_name="gaibo_process_routes")
    op.drop_table("gaibo_process_routes")
    op.drop_index("ix_gaibo_drawings_requirement_id", table_name="gaibo_drawings")
    op.drop_table("gaibo_drawings")
    op.drop_index("ix_gaibo_package_items_requirement_id", table_name="gaibo_package_items")
    op.drop_index("ix_gaibo_package_items_package_id", table_name="gaibo_package_items")
    op.drop_table("gaibo_package_items")
    for index_name, table_name in (
        ("ix_gaibo_installation_packages_is_active", "gaibo_installation_packages"),
        ("ix_gaibo_installation_packages_package_number", "gaibo_installation_packages"),
        ("ix_gaibo_installation_packages_workspace_id", "gaibo_installation_packages"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("gaibo_installation_packages")
    for name in ("workspace_id", "single_part_id", "customer_part_number", "ibi", "tianyue_internal_composition", "is_active"):
        op.drop_index(f"ix_gaibo_customer_requirements_{name}", table_name="gaibo_customer_requirements")
    op.drop_table("gaibo_customer_requirements")
    for index_name in ("ix_gaibo_single_parts_is_active", "ix_gaibo_single_parts_internal_no", "ix_gaibo_single_parts_part_id"):
        op.drop_index(index_name, table_name="gaibo_single_parts")
    op.drop_table("gaibo_single_parts")
    for index_name in ("ix_gaibo_customer_workspaces_is_active", "ix_gaibo_customer_workspaces_slug", "ix_gaibo_customer_workspaces_customer_id"):
        op.drop_index(index_name, table_name="gaibo_customer_workspaces")
    op.drop_table("gaibo_customer_workspaces")
