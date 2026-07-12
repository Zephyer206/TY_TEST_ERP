#!/usr/bin/env python3
"""
Migration 008: Authoritative Schema - Phase 1 Complete Migration
Implements the authoritative design from specs/001-erp-system-architecture/data-model.md
Uses direct psycopg2 connection from settings
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import settings to get DATABASE_URL
try:
    from app.core.config import settings
    # Parse DATABASE_URL to get connection params
    db_url = settings.DATABASE_URL
    # Convert asyncpg URL to standard postgres URL
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
except Exception as e:
    print(f"[WARNING] Could not load settings: {e}")
    print("[INFO] Using environment variables instead")
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/stamping_system')

import psycopg2
from urllib.parse import urlparse

def get_connection():
    """Get database connection from settings or environment."""
    parsed = urlparse(db_url)
    return psycopg2.connect(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/') if parsed.path else 'stamping_system',
        user=parsed.username or 'postgres',
        password=parsed.password or 'postgres'
    )

def migrate():
    """Execute Phase 1 authoritative schema migration."""

    print("="*70)
    print("Migration 008: Authoritative Schema (Phase 1)")
    print("="*70)

    conn = get_connection()
    conn.set_session(autocommit=False)
    cur = conn.cursor()

    try:
        # Step 1: customers table
        print("\n[STEP 1] Enhancing customers table...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='customers' AND column_name='customer_code') THEN
                    ALTER TABLE customers ADD COLUMN customer_code VARCHAR(20);
                    CREATE UNIQUE INDEX idx_customers_code ON customers(customer_code)
                        WHERE customer_code IS NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='customers' AND column_name='short_name') THEN
                    ALTER TABLE customers
                        ADD COLUMN short_name VARCHAR(100),
                        ADD COLUMN contact_person VARCHAR(100),
                        ADD COLUMN contact_phone VARCHAR(50),
                        ADD COLUMN contact_email VARCHAR(100),
                        ADD COLUMN address TEXT,
                        ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW();
                END IF;
            END $$;
        """)
        conn.commit()
        print("  [OK] customers table enhanced")

        # Step 2: parts table
        print("\n[STEP 2] Modifying parts table...")
        cur.execute("""
            DO $$
            BEGIN
                ALTER TABLE parts ALTER COLUMN part_number DROP NOT NULL;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='parts' AND column_name='internal_part_no') THEN
                    ALTER TABLE parts ADD COLUMN internal_part_no VARCHAR(100);
                    CREATE INDEX idx_parts_internal_no ON parts(internal_part_no)
                        WHERE internal_part_no IS NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='parts' AND column_name='is_deleted') THEN
                    ALTER TABLE parts ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;

                COMMENT ON COLUMN parts.customer_id IS 'DEPRECATED: Use part_customer_aliases instead';
            END $$;
        """)
        conn.commit()
        print("  [OK] parts table modified")

        # Step 3: tooling table
        print("\n[STEP 3] Enhancing tooling table...")

        # Add columns
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='tooling_number') THEN
                    ALTER TABLE tooling ADD COLUMN tooling_number VARCHAR(100);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='tooling_name') THEN
                    ALTER TABLE tooling ADD COLUMN tooling_name VARCHAR(200);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='process_step_count') THEN
                    ALTER TABLE tooling ADD COLUMN process_step_count INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='status') THEN
                    ALTER TABLE tooling ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'DRAFT';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='shot_count') THEN
                    ALTER TABLE tooling ADD COLUMN shot_count BIGINT NOT NULL DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='max_shot_count') THEN
                    ALTER TABLE tooling ADD COLUMN max_shot_count BIGINT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='last_maintenance_at') THEN
                    ALTER TABLE tooling ADD COLUMN last_maintenance_at TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='tooling' AND column_name='is_deleted') THEN
                    ALTER TABLE tooling ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;
        """)

        # Migrate tooling_no to tooling_number (only safe values)
        cur.execute("""
            SELECT COUNT(*) FROM tooling
            WHERE tooling_no IS NOT NULL AND tooling_number IS NULL
        """)
        need_migration = cur.fetchone()[0]

        if need_migration > 0:
            cur.execute("""
                WITH unique_tooling_no AS (
                    SELECT tooling_no
                    FROM tooling
                    WHERE tooling_no IS NOT NULL AND tooling_number IS NULL
                    GROUP BY tooling_no
                    HAVING COUNT(*) = 1
                ),
                non_conflicting AS (
                    SELECT u.tooling_no
                    FROM unique_tooling_no u
                    WHERE NOT EXISTS (
                        SELECT 1 FROM tooling t
                        WHERE t.tooling_number = u.tooling_no
                    )
                )
                UPDATE tooling t
                SET tooling_number = t.tooling_no
                FROM non_conflicting nc
                WHERE t.tooling_no = nc.tooling_no AND t.tooling_number IS NULL
            """)
            print("  [INFO] Migrated unique, non-conflicting tooling_no values")

        # Create index
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tooling_number
            ON tooling(tooling_number) WHERE tooling_number IS NOT NULL
        """)

        # Ensure mold_type is NOT NULL
        cur.execute("""
            UPDATE tooling SET mold_type = 'unknown'
            WHERE mold_type IS NULL OR mold_type = '';
        """)
        cur.execute("ALTER TABLE tooling ALTER COLUMN mold_type SET NOT NULL")
        cur.execute("ALTER TABLE tooling ALTER COLUMN mold_type SET DEFAULT 'unknown'")

        # Convert cavity_count to INTEGER if needed
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name='tooling' AND column_name='cavity_count'
        """)
        if cur.fetchone()[0] != 'integer':
            cur.execute("""
                ALTER TABLE tooling
                ALTER COLUMN cavity_count TYPE INTEGER
                USING CASE
                    WHEN cavity_count ~ '^[0-9]+$' THEN cavity_count::INTEGER
                    ELSE 1
                END
            """)

        cur.execute("ALTER TABLE tooling ALTER COLUMN cavity_count SET NOT NULL")
        cur.execute("ALTER TABLE tooling ALTER COLUMN cavity_count SET DEFAULT 1")

        # Backfill is_continuous based on mold_type
        cur.execute("""
            UPDATE tooling
            SET is_continuous = CASE
                WHEN mold_type LIKE '%连续模%' OR mold_type LIKE '%连续%' THEN TRUE
                ELSE FALSE
            END
        """)

        cur.execute("COMMENT ON COLUMN tooling.customer_id IS 'DEPRECATED: Use tooling_customer_links instead'")

        conn.commit()
        print("  [OK] tooling table enhanced")

        # Step 4: tooling_steps
        print("\n[STEP 4] Creating tooling_steps table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tooling_steps (
                id SERIAL PRIMARY KEY,
                tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
                step_no INTEGER NOT NULL,
                step_code VARCHAR(50),
                step_name VARCHAR(200),
                operation_type VARCHAR(100),
                sequence INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(tooling_id, step_no)
            );
            CREATE INDEX IF NOT EXISTS idx_tooling_steps_tooling ON tooling_steps(tooling_id);
        """)
        conn.commit()
        print("  [OK] tooling_steps table created")

        # Step 5: tooling_parts corrections
        print("\n[STEP 5] Correcting tooling_parts table...")
        cur.execute("SELECT COUNT(*) FROM tooling_parts")
        count = cur.fetchone()[0]

        if count == 0:
            cur.execute("""
                DO $$
                BEGIN
                    ALTER TABLE tooling_parts ALTER COLUMN tooling_id SET NOT NULL;
                    ALTER TABLE tooling_parts ALTER COLUMN part_id SET NOT NULL;

                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                  WHERE table_name='tooling_parts' AND column_name='position') THEN
                        ALTER TABLE tooling_parts ADD COLUMN position VARCHAR(20);
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                  WHERE table_name='tooling_parts' AND column_name='sequence') THEN
                        ALTER TABLE tooling_parts ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                  WHERE table_name='tooling_parts' AND column_name='is_primary') THEN
                        ALTER TABLE tooling_parts ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT TRUE;
                    END IF;

                    DROP INDEX IF EXISTS tooling_parts_tooling_id_part_id_key;
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_tooling_parts_unique
                    ON tooling_parts(tooling_id, part_id, COALESCE(position, ''));
                END $$;
            """)
            conn.commit()
            print("  [OK] tooling_parts table corrected")
        else:
            print(f"  [SKIP] tooling_parts has {count} rows")

        # Step 6: tooling_customer_links
        print("\n[STEP 6] Creating tooling_customer_links table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tooling_customer_links (
                id SERIAL PRIMARY KEY,
                tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
                customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                relation_type VARCHAR(30) NOT NULL DEFAULT 'user',
                is_owner BOOLEAN NOT NULL DEFAULT FALSE,
                valid_from DATE,
                valid_to DATE,
                remark TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(tooling_id, customer_id, relation_type)
            );
            CREATE INDEX IF NOT EXISTS idx_tooling_customer_links_tooling
                ON tooling_customer_links(tooling_id);
            CREATE INDEX IF NOT EXISTS idx_tooling_customer_links_customer
                ON tooling_customer_links(customer_id);
        """)
        conn.commit()
        print("  [OK] tooling_customer_links table created")

        # Step 7: part_customer_aliases corrections
        print("\n[STEP 7] Correcting part_customer_aliases table...")
        cur.execute("SELECT COUNT(*) FROM part_customer_aliases")
        count = cur.fetchone()[0]

        if count == 0:
            cur.execute("""
                DO $$
                BEGIN
                    ALTER TABLE part_customer_aliases
                        DROP CONSTRAINT IF EXISTS uq_part_customer;

                    ALTER TABLE part_customer_aliases
                        ALTER COLUMN customer_id SET NOT NULL;

                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                  WHERE table_name='part_customer_aliases' AND column_name='revision') THEN
                        ALTER TABLE part_customer_aliases
                            ADD COLUMN revision VARCHAR(50) NOT NULL DEFAULT '';
                    END IF;

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_part_customer_alias_unique
                    ON part_customer_aliases(customer_id, customer_part_no, revision);

                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                  WHERE table_name='part_customer_aliases' AND column_name='vehicle_model') THEN
                        ALTER TABLE part_customer_aliases
                            ADD COLUMN vehicle_model VARCHAR(100),
                            ADD COLUMN remark TEXT,
                            ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
                            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW();
                    END IF;
                END $$;
            """)
            conn.commit()
            print("  [OK] part_customer_aliases table corrected")
        else:
            print(f"  [SKIP] part_customer_aliases has {count} rows")

        # Step 8: excel_import_rows enhancements
        print("\n[STEP 8] Enhancing excel_import_rows table...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='excel_import_rows' AND column_name='parsed_is_continuous') THEN
                    ALTER TABLE excel_import_rows ADD COLUMN parsed_is_continuous BOOLEAN;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                              WHERE table_name='excel_import_rows' AND column_name='parsed_position') THEN
                    ALTER TABLE excel_import_rows ADD COLUMN parsed_position VARCHAR(20);
                END IF;
            END $$;
        """)
        conn.commit()
        print("  [OK] excel_import_rows table enhanced")

        print("\n" + "="*70)
        print("Migration 008 completed successfully")
        print("="*70)

        cur.close()
        conn.close()
        return 0

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Run migration."""
    try:
        return migrate()
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
