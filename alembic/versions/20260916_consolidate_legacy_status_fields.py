"""Consolidate lifecycle state and archive overlapping legacy tooling fields.

The canonical fields are parts.part_status and tooling.status.  Legacy values
are copied to audit tables before being neutralised; columns remain for a
later removal migration after all external consumers have been retired.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260916_consolidate_status"
down_revision = "20260914_unify_parts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "part_legacy_status_archive",
        sa.Column("part_id", sa.Integer(), nullable=False),
        sa.Column("legacy_status", sa.String(50), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "tooling_legacy_fields_archive",
        sa.Column("tooling_id", sa.Integer(), nullable=False),
        sa.Column("mold_status", sa.String(50), nullable=True),
        sa.Column("cavity_status", sa.String(50), nullable=True),
        sa.Column("forming_steps", sa.Integer(), nullable=True),
        sa.Column("mold_count", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    bind.execute(sa.text("""
        INSERT INTO part_legacy_status_archive (part_id, legacy_status)
        SELECT id, status FROM parts
        WHERE status IS NOT NULL
    """))
    bind.execute(sa.text("""
        INSERT INTO tooling_legacy_fields_archive
            (tooling_id, mold_status, cavity_status, forming_steps, mold_count)
        SELECT id, mold_status, cavity_status, forming_steps, mold_count
        FROM tooling
        WHERE mold_status IS NOT NULL
           OR cavity_status IS NOT NULL
           OR forming_steps IS NOT NULL
           OR mold_count IS NOT NULL
    """))

    # Canonicalise the one outlier in the active tooling state values.
    bind.execute(sa.text("UPDATE tooling SET status = 'active' WHERE status = 'AVAILABLE'"))

    # These fields are preserved only in the archive, so no new code can
    # accidentally read two competing lifecycle values.
    bind.execute(sa.text("UPDATE parts SET status = NULL WHERE status IS NOT NULL"))
    bind.execute(sa.text("UPDATE tooling SET mold_status = NULL WHERE mold_status IS NOT NULL"))

    op.execute("COMMENT ON COLUMN parts.status IS 'DEPRECATED: archived by 20260916_consolidate_status; use part_status'" )
    op.execute("COMMENT ON COLUMN tooling.mold_status IS 'DEPRECATED: archived by 20260916_consolidate_status; use status'" )
    op.execute("COMMENT ON COLUMN tooling.cavity_status IS 'DEPRECATED: use cavity_count for 1-out-N; retained for archive compatibility'" )
    op.execute("COMMENT ON COLUMN tooling.forming_steps IS 'DEPRECATED: use process_step_count and tooling_steps'" )
    op.execute("COMMENT ON COLUMN tooling.mold_count IS 'DEPRECATED: no active business consumer; retained for archive compatibility'" )


def downgrade() -> None:
    # Restore only archived values; do not overwrite any later user changes.
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE parts p SET status = a.legacy_status
        FROM part_legacy_status_archive a
        WHERE a.part_id = p.id AND p.status IS NULL
    """))
    bind.execute(sa.text("""
        UPDATE tooling t SET mold_status = a.mold_status
        FROM tooling_legacy_fields_archive a
        WHERE a.tooling_id = t.id AND t.mold_status IS NULL
    """))
    op.drop_table("tooling_legacy_fields_archive")
    op.drop_table("part_legacy_status_archive")
