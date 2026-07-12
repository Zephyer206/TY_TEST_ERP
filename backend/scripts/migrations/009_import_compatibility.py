"""
Migration 009: Import Compatibility
Make tables compatible with authoritative design for Phase 3 import.
"""

def upgrade(cur, conn):
    """Apply migration."""
    print("[009] Applying import compatibility fixes...")

    # 1. Make tooling.tooling_number the authoritative field
    # Keep tooling_no for compatibility but allow it to be nullable or same as tooling_number
    print("  [1/4] Fixing tooling.tooling_number...")

    # Make tooling_no nullable if needed (for new inserts using tooling_number)
    cur.execute("""
        ALTER TABLE tooling
        ALTER COLUMN tooling_no DROP NOT NULL
    """)

    # Add unique constraint on tooling_number if not exists
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'tooling_tooling_number_key'
            ) THEN
                ALTER TABLE tooling
                ADD CONSTRAINT tooling_tooling_number_key UNIQUE (tooling_number);
            END IF;
        END $$;
    """)

    # 2. Make part_customer_aliases.customer_name nullable
    # Use customer_id as authoritative
    print("  [2/4] Fixing part_customer_aliases.customer_name...")

    cur.execute("""
        ALTER TABLE part_customer_aliases
        ALTER COLUMN customer_name DROP NOT NULL
    """)

    # 3. Fix tooling_steps column names
    # The real columns are step_no and sequence, not step_number
    print("  [3/4] Checking tooling_steps columns...")

    # Check if step_number exists (wrong name)
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'tooling_steps'
        AND column_name IN ('step_number', 'step_no', 'step_name', 'sequence')
    """)

    existing_cols = [row[0] for row in cur.fetchall()]
    print(f"     Existing columns: {existing_cols}")

    # 4. Add resolved_* columns to excel_import_rows if not exist
    print("  [4/4] Ensuring excel_import_rows has resolved_* columns...")

    for col in ['resolved_customer_id', 'resolved_part_id', 'resolved_tooling_id', 'resolved_alias_id']:
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'excel_import_rows'
                    AND column_name = '{col}'
                ) THEN
                    ALTER TABLE excel_import_rows
                    ADD COLUMN {col} INTEGER;
                END IF;
            END $$;
        """)

    conn.commit()
    print("[009] Migration complete")


def downgrade(cur, conn):
    """Revert migration."""
    print("[009] Reverting import compatibility fixes...")

    # Revert in reverse order
    cur.execute("""
        ALTER TABLE part_customer_aliases
        ALTER COLUMN customer_name SET NOT NULL
    """)

    cur.execute("""
        ALTER TABLE tooling
        ALTER COLUMN tooling_no SET NOT NULL
    """)

    cur.execute("""
        ALTER TABLE tooling
        DROP CONSTRAINT IF EXISTS tooling_tooling_number_key
    """)

    conn.commit()
    print("[009] Revert complete")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    import psycopg2
    from app.core.config import settings
    from urllib.parse import urlparse

    db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    parsed = urlparse(db_url)

    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password
    )

    cur = conn.cursor()

    try:
        upgrade(cur, conn)
        print("\nMigration 009 applied successfully!")
    except Exception as e:
        print(f"\nError: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
