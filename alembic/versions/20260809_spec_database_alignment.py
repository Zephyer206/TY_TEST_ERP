"""Stage the database toward the authoritative ERP data model.

This migration deliberately does not infer customer-part ownership. Historical
rows with missing or conflicting customer part numbers are retained and marked
for review; only confirmed rows participate in the new business-key index.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_spec_database_alignment"
down_revision = "20260804_drop_part_mold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep an immutable copy of the legacy values before the UI/API stops using
    # these compatibility columns.  The columns remain for this staged rollout.
    op.create_table(
        "part_legacy_identifier_archive",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_column", sa.String(50), nullable=False),
        sa.Column("source_value", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("part_id", "source_column", "source_value", name="uq_part_legacy_identifier_snapshot"),
    )
    op.create_index(
        "ix_part_legacy_identifier_archive_part_id",
        "part_legacy_identifier_archive",
        ["part_id"],
    )
    op.execute(
        """
        INSERT INTO part_legacy_identifier_archive (part_id, source_column, source_value)
        SELECT id, source_column, source_value
        FROM (
            SELECT id, 'part_number' AS source_column, NULLIF(BTRIM(part_number), '') AS source_value FROM parts
            UNION ALL
            SELECT id, 'internal_part_no', NULLIF(BTRIM(internal_part_no), '') FROM parts
            UNION ALL
            SELECT id, 'customer_product_no', NULLIF(BTRIM(customer_product_no), '') FROM parts
            UNION ALL
            SELECT id, 'customer_product_name', NULLIF(BTRIM(customer_product_name), '') FROM parts
        ) legacy
        WHERE source_value IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    # Add an explicit review state instead of deleting or inventing customer
    # part numbers. Existing bad rows remain queryable for reconciliation.
    op.add_column(
        "part_customer_aliases",
        sa.Column("data_quality_status", sa.String(20), nullable=False, server_default="approved"),
    )
    op.add_column(
        "part_customer_aliases",
        sa.Column("data_quality_reason", sa.Text(), nullable=True),
    )
    op.create_table(
        "part_customer_alias_issues",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("alias_id", sa.Integer(), sa.ForeignKey("part_customer_aliases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_type", sa.String(50), nullable=False),
        sa.Column("issue_key", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_part_customer_alias_issues_alias_id", "part_customer_alias_issues", ["alias_id"])

    op.execute(
        """
        INSERT INTO part_customer_alias_issues (alias_id, issue_type, issue_key, snapshot)
        SELECT a.id,
               CASE
                 WHEN NULLIF(BTRIM(a.customer_part_no), '') IS NULL THEN 'missing_customer_part_no'
                 ELSE 'duplicate_customer_part_key'
               END,
               CONCAT(a.customer_id, '|', COALESCE(BTRIM(a.customer_part_no), '<missing>'), '|', a.revision),
               TO_JSON(a)
        FROM part_customer_aliases a
        WHERE NULLIF(BTRIM(a.customer_part_no), '') IS NULL
           OR EXISTS (
                SELECT 1
                FROM part_customer_aliases d
                WHERE d.customer_id = a.customer_id
                  AND COALESCE(BTRIM(d.customer_part_no), '') = COALESCE(BTRIM(a.customer_part_no), '')
                  AND d.revision = a.revision
                GROUP BY d.customer_id, COALESCE(BTRIM(d.customer_part_no), ''), d.revision
                HAVING COUNT(*) > 1
           )
        """
    )
    op.execute(
        """
        UPDATE part_customer_aliases a
        SET data_quality_status = 'pending_review',
            data_quality_reason = CASE
              WHEN NULLIF(BTRIM(a.customer_part_no), '') IS NULL THEN 'missing_customer_part_no'
              ELSE 'duplicate_customer_part_key'
            END
        WHERE NULLIF(BTRIM(a.customer_part_no), '') IS NULL
           OR EXISTS (
                SELECT 1
                FROM part_customer_aliases d
                WHERE d.customer_id = a.customer_id
                  AND COALESCE(BTRIM(d.customer_part_no), '') = COALESCE(BTRIM(a.customer_part_no), '')
                  AND d.revision = a.revision
                GROUP BY d.customer_id, COALESCE(BTRIM(d.customer_part_no), ''), d.revision
                HAVING COUNT(*) > 1
           )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_part_customer_aliases_confirmed_key
        ON part_customer_aliases (customer_id, BTRIM(customer_part_no), revision)
        WHERE data_quality_status = 'approved'
          AND NULLIF(BTRIM(customer_part_no), '') IS NOT NULL
        """
    )

    # tooling_no is the populated historical source and tooling_number is the
    # authoritative spec field. The audit proved this backfill is one-to-one.
    op.create_table(
        "tooling_number_backfill_audit",
        sa.Column("tooling_id", sa.Integer(), sa.ForeignKey("tooling.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("old_tooling_number", sa.String(100), nullable=True),
        sa.Column("old_tooling_no", sa.String(50), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        """
        INSERT INTO tooling_number_backfill_audit (tooling_id, old_tooling_number, old_tooling_no)
        SELECT id, tooling_number, tooling_no
        FROM tooling
        WHERE NULLIF(BTRIM(tooling_number), '') IS NULL
          AND NULLIF(BTRIM(tooling_no), '') IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE tooling
        SET tooling_number = BTRIM(tooling_no)
        WHERE NULLIF(BTRIM(tooling_number), '') IS NULL
          AND NULLIF(BTRIM(tooling_no), '') IS NOT NULL
        """
    )
    op.alter_column("tooling", "tooling_number", existing_type=sa.String(length=100), nullable=False)
    op.create_unique_constraint(
        "uq_tooling_parts_business_key",
        "tooling_parts",
        ["tooling_id", "part_id", "position"],
    )
    op.create_unique_constraint(
        "uq_tooling_customer_links_business_key",
        "tooling_customer_links",
        ["tooling_id", "customer_id", "relation_type"],
    )
    # PostgreSQL UNIQUE constraints treat NULL positions as distinct. This
    # expression index closes that loophole while preserving nullable display
    # position semantics in the table.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_tooling_parts_business_key_normalized
        ON tooling_parts (tooling_id, part_id, COALESCE(position, ''))
        """
    )

    op.execute("COMMENT ON COLUMN parts.part_number IS 'DEPRECATED compatibility field; customer part numbers belong in part_customer_aliases.customer_part_no'")
    op.execute("COMMENT ON COLUMN parts.customer_product_no IS 'DEPRECATED compatibility field; use part_customer_aliases.customer_part_no'")
    op.execute("COMMENT ON COLUMN parts.customer_product_name IS 'DEPRECATED compatibility field; use part_customer_aliases.customer_part_name'")
    op.execute("COMMENT ON COLUMN parts.internal_part_no IS 'Reserved internal identifier; no user-visible number is generated'")
    op.execute("COMMENT ON COLUMN tooling.tooling_no IS 'DEPRECATED compatibility field; tooling_number is authoritative'")


def downgrade() -> None:
    op.drop_index("uq_tooling_parts_business_key_normalized", table_name="tooling_parts")
    op.drop_constraint("uq_tooling_customer_links_business_key", "tooling_customer_links", type_="unique")
    op.drop_constraint("uq_tooling_parts_business_key", "tooling_parts", type_="unique")
    op.execute(
        """
        UPDATE tooling t
        SET tooling_number = a.old_tooling_number
        FROM tooling_number_backfill_audit a
        WHERE a.tooling_id = t.id
        """
    )
    op.alter_column("tooling", "tooling_number", existing_type=sa.String(length=100), nullable=True)
    op.drop_table("tooling_number_backfill_audit")
    op.drop_index("uq_part_customer_aliases_confirmed_key", table_name="part_customer_aliases")
    op.drop_index("ix_part_customer_alias_issues_alias_id", table_name="part_customer_alias_issues")
    op.drop_table("part_customer_alias_issues")
    op.drop_column("part_customer_aliases", "data_quality_reason")
    op.drop_column("part_customer_aliases", "data_quality_status")
    op.drop_index("ix_part_legacy_identifier_archive_part_id", table_name="part_legacy_identifier_archive")
    op.drop_table("part_legacy_identifier_archive")
