"""Retire denormalized part/tooling identity columns after canonical migration."""

from alembic import op
import sqlalchemy as sa


revision = "20260809_retire_legacy_columns"
down_revision = "20260809_spec_database_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fail closed if the immutable snapshots expected by the migration are
    # missing. This prevents an accidental destructive drop on an unprepared DB.
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('part_legacy_identifier_archive') IS NULL
             OR to_regclass('part_identity_migration_issues') IS NULL
             OR to_regclass('tooling_number_backfill_audit') IS NULL THEN
            RAISE EXCEPTION 'Canonical identity archives are required before retiring legacy columns';
          END IF;
        END $$;
        """
    )

    for column in ("part_number", "internal_part_no", "customer_product_no", "customer_product_name", "customer_id"):
        op.drop_column("parts", column)
    for column in ("tooling_no", "customer_id", "customer_product_no", "customer_product_name", "name"):
        op.drop_column("tooling", column)


def downgrade() -> None:
    op.add_column("parts", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.add_column("parts", sa.Column("customer_product_name", sa.String(length=200), nullable=True))
    op.add_column("parts", sa.Column("customer_product_no", sa.String(length=100), nullable=True))
    op.add_column("parts", sa.Column("internal_part_no", sa.String(length=100), nullable=True))
    op.add_column("parts", sa.Column("part_number", sa.String(length=50), nullable=True))
    op.create_index("ix_parts_customer_id", "parts", ["customer_id"])
    op.create_index("ix_parts_internal_part_no", "parts", ["internal_part_no"])
    op.create_index("ix_parts_customer_product_no", "parts", ["customer_product_no"])
    op.create_index("ix_parts_part_number", "parts", ["part_number"])

    op.add_column("tooling", sa.Column("name", sa.String(length=200), nullable=True))
    op.add_column("tooling", sa.Column("customer_product_name", sa.String(length=200), nullable=True))
    op.add_column("tooling", sa.Column("customer_product_no", sa.String(length=100), nullable=True))
    op.add_column("tooling", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.add_column("tooling", sa.Column("tooling_no", sa.String(length=50), nullable=True))
    op.create_index("ix_tooling_tooling_no", "tooling", ["tooling_no"])

    # Restore only archived values; no new inference is performed.
    op.execute(
        """
        UPDATE parts p
        SET part_number = a.source_value
        FROM part_legacy_identifier_archive a
        WHERE a.part_id = p.id AND a.source_column = 'part_number'
        """
    )
    op.execute(
        """
        UPDATE parts p
        SET internal_part_no = a.source_value
        FROM part_legacy_identifier_archive a
        WHERE a.part_id = p.id AND a.source_column = 'internal_part_no'
        """
    )
    op.execute(
        """
        UPDATE parts p
        SET customer_product_no = a.source_value
        FROM part_legacy_identifier_archive a
        WHERE a.part_id = p.id AND a.source_column = 'customer_product_no'
        """
    )
    op.execute(
        """
        UPDATE parts p
        SET customer_product_name = a.source_value
        FROM part_legacy_identifier_archive a
        WHERE a.part_id = p.id AND a.source_column = 'customer_product_name'
        """
    )
    op.execute(
        """
        UPDATE tooling t
        SET tooling_no = a.old_tooling_no
        FROM tooling_number_backfill_audit a
        WHERE a.tooling_id = t.id
        """
    )
