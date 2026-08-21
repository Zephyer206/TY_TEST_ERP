"""Harden canonical relationships and quarantine unresolved legacy part identity data."""

from alembic import op
import sqlalchemy as sa


revision = "20260809_spec_database_hardening"
down_revision = "20260809_spec_database_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy part identity values have no customer mapping in the current
    # database. Keep them queryable as review work items; do not guess a
    # customer or write them into part_customer_aliases.
    op.create_table(
        "part_identity_migration_issues",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "part_id",
            sa.Integer(),
            sa.ForeignKey("parts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("issue_type", sa.String(50), nullable=False),
        sa.Column("source_column", sa.String(50), nullable=True),
        sa.Column("source_value", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_review"),
        sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_part_identity_migration_issues_part_id",
        "part_identity_migration_issues",
        ["part_id"],
    )
    op.create_index(
        "ix_part_identity_migration_issues_status",
        "part_identity_migration_issues",
        ["status", "detected_at"],
    )
    op.execute(
        """
        INSERT INTO part_identity_migration_issues
            (part_id, issue_type, source_column, source_value, snapshot)
        SELECT p.id,
               'legacy_identity_without_customer',
               v.source_column,
               v.source_value,
               json_build_object(
                   'part_id', p.id,
                   'customer_id', p.customer_id,
                   'internal_name', p.internal_name,
                   'part_number', p.part_number,
                   'internal_part_no', p.internal_part_no,
                   'customer_product_no', p.customer_product_no,
                   'customer_product_name', p.customer_product_name
               )
        FROM parts p
        CROSS JOIN LATERAL (
            VALUES
                ('part_number', NULLIF(BTRIM(p.part_number), '')),
                ('internal_part_no', NULLIF(BTRIM(p.internal_part_no), '')),
                ('customer_product_no', NULLIF(BTRIM(p.customer_product_no), '')),
                ('customer_product_name', NULLIF(BTRIM(p.customer_product_name), ''))
        ) AS v(source_column, source_value)
        WHERE p.customer_id IS NULL
          AND v.source_value IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO part_identity_migration_issues
            (part_id, issue_type, source_column, source_value, snapshot)
        SELECT p.id,
               'missing_internal_name',
               'internal_name',
               NULL,
               json_build_object('part_id', p.id, 'internal_name', p.internal_name)
        FROM parts p
        WHERE NULLIF(BTRIM(p.internal_name), '') IS NULL
        """
    )

    # These are NOT VALID checks: legacy rows remain available for review, but
    # new inserts/updates cannot introduce the same invalid state.
    op.execute(
        """
        ALTER TABLE parts
        ADD CONSTRAINT ck_parts_internal_name_nonempty
        CHECK (is_deleted OR NULLIF(BTRIM(internal_name), '') IS NOT NULL)
        NOT VALID
        """
    )
    op.execute(
        """
        ALTER TABLE part_customer_aliases
        ADD CONSTRAINT ck_part_customer_aliases_customer_part_no_nonempty
        CHECK (
            data_quality_status = 'pending_review'
            OR NULLIF(BTRIM(customer_part_no), '') IS NOT NULL
        )
        NOT VALID
        """
    )

    op.create_unique_constraint(
        "uq_tooling_steps_tooling_step_no",
        "tooling_steps",
        ["tooling_id", "step_no"],
    )
    op.execute(
        """
        ALTER TABLE part_display_group_defs
        ADD CONSTRAINT ck_part_display_group_type
        CHECK (group_type IN ('left_right', 'shared_source'))
        NOT VALID
        """
    )
    op.execute(
        """
        ALTER TABLE shared_field_group_members
        ADD CONSTRAINT ck_shared_field_group_member_target
        CHECK (part_id IS NOT NULL OR tooling_id IS NOT NULL)
        NOT VALID
        """
    )

    # Resolved import references are nullable by design, but when present they
    # must point to real business records.
    op.create_foreign_key(
        "fk_excel_import_rows_resolved_customer",
        "excel_import_rows",
        "customers",
        ["resolved_customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_excel_import_rows_resolved_part",
        "excel_import_rows",
        "parts",
        ["resolved_part_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_excel_import_rows_resolved_tooling",
        "excel_import_rows",
        "tooling",
        ["resolved_tooling_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_excel_import_rows_resolved_alias",
        "excel_import_rows",
        "part_customer_aliases",
        ["resolved_alias_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_excel_import_rows_resolved_alias", "excel_import_rows", type_="foreignkey")
    op.drop_constraint("fk_excel_import_rows_resolved_tooling", "excel_import_rows", type_="foreignkey")
    op.drop_constraint("fk_excel_import_rows_resolved_part", "excel_import_rows", type_="foreignkey")
    op.drop_constraint("fk_excel_import_rows_resolved_customer", "excel_import_rows", type_="foreignkey")
    op.drop_constraint("ck_shared_field_group_member_target", "shared_field_group_members", type_="check")
    op.drop_constraint("ck_part_display_group_type", "part_display_group_defs", type_="check")
    op.drop_constraint("uq_tooling_steps_tooling_step_no", "tooling_steps", type_="unique")
    op.drop_constraint(
        "ck_part_customer_aliases_customer_part_no_nonempty",
        "part_customer_aliases",
        type_="check",
    )
    op.drop_constraint("ck_parts_internal_name_nonempty", "parts", type_="check")
    op.drop_index("ix_part_identity_migration_issues_status", table_name="part_identity_migration_issues")
    op.drop_index("ix_part_identity_migration_issues_part_id", table_name="part_identity_migration_issues")
    op.drop_table("part_identity_migration_issues")
