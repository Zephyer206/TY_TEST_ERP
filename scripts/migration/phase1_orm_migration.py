#!/usr/bin/env python3
"""
Phase 1: ORM and Database Schema Migration
Complete implementation following authoritative design in data-model.md
"""

import os
import sys
import psycopg2
from datetime import datetime
from pathlib import Path

DB_HOST = os.environ["ZEPHYR_DB_HOST"]
DB_PORT = int(os.environ.get("ZEPHYR_DB_PORT", "5432"))
DB_NAME = os.environ.get("ZEPHYR_DB_NAME", "stamping_system")
DB_USER = os.environ.get("ZEPHYR_DB_USER", "postgres")
DB_PASSWORD = os.environ["ZEPHYR_DB_PASSWORD"]

def connect_db():
    for attempt in range(1, 4):
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD, connect_timeout=10
            )
            conn.set_session(autocommit=False)
            return conn
        except Exception as e:
            print(f"[ERROR] Connection attempt {attempt}/3: {e}")
            if attempt < 3:
                import time
                time.sleep(2)
            else:
                raise

def execute_migration_sql(conn):
    """Execute database migration SQL to match authoritative design."""
    print("="*70)
    print("PHASE 1: DATABASE SCHEMA MIGRATION")
    print("="*70)

    cur = conn.cursor()

    # Track changes
    changes = []

    try:
        print("\n[STEP 1] Customers table - add customer_code")
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'customers' AND column_name = 'customer_code'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE customers
                ADD COLUMN customer_code VARCHAR(20),
                ADD COLUMN short_name VARCHAR(100),
                ADD COLUMN contact_person VARCHAR(100),
                ADD COLUMN contact_phone VARCHAR(50),
                ADD COLUMN contact_email VARCHAR(100),
                ADD COLUMN address TEXT,
                ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
                ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            """)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_code ON customers(customer_code) WHERE customer_code IS NOT NULL")
            changes.append("[OK] Added customer_code and related fields to customers")
            print("  [OK] Added customer_code and contact fields")
        else:
            print("  [SKIP] customer_code already exists")

        conn.commit()

        print("\n[STEP 2] Parts table - make part_number nullable, add TWP fields")
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'parts' AND column_name = 'thickness'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE parts
                ALTER COLUMN part_number DROP NOT NULL,
                ADD COLUMN thickness NUMERIC(10,3),
                ADD COLUMN width NUMERIC(10,3),
                ADD COLUMN pitch NUMERIC(10,3),
                ADD COLUMN height NUMERIC(10,3),
                ADD COLUMN gross_weight NUMERIC(12,3),
                ADD COLUMN net_weight NUMERIC(12,3),
                ADD COLUMN part_position VARCHAR(20),
                ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE
            """)
            changes.append("[OK] Modified parts: part_number nullable, added TWP fields")
            print("  [OK] Modified parts table structure")
        else:
            print("  [SKIP] TWP fields already exist")

        # Mark customer_id as deprecated (keep for compatibility)
        cur.execute("COMMENT ON COLUMN parts.customer_id IS 'DEPRECATED: Use part_customer_aliases instead'")

        conn.commit()

        print("\n[STEP 3] Tooling table - add tooling_number and target fields")

        # Check which columns already exist
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tooling' AND column_name IN (
                'tooling_number', 'tooling_name', 'process_step_count',
                'status', 'shot_count', 'max_shot_count', 'last_maintenance_at', 'is_deleted'
            )
        """)
        existing_tooling_cols = set(row[0] for row in cur.fetchall())

        # Add columns individually to avoid duplicate errors
        columns_added = []
        if 'tooling_number' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN tooling_number VARCHAR(100)")
            columns_added.append('tooling_number')
        if 'tooling_name' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN tooling_name VARCHAR(200)")
            columns_added.append('tooling_name')
        if 'process_step_count' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN process_step_count INTEGER")
            columns_added.append('process_step_count')
        if 'status' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'")
            columns_added.append('status')
        if 'shot_count' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN shot_count BIGINT NOT NULL DEFAULT 0")
            columns_added.append('shot_count')
        if 'max_shot_count' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN max_shot_count BIGINT")
            columns_added.append('max_shot_count')
        if 'last_maintenance_at' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN last_maintenance_at TIMESTAMP")
            columns_added.append('last_maintenance_at')
        if 'is_deleted' not in existing_tooling_cols:
            cur.execute("ALTER TABLE tooling ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE")
            columns_added.append('is_deleted')

        if columns_added:
            print(f"  [OK] Added columns: {', '.join(columns_added)}")
            changes.append(f"[OK] Added tooling columns: {', '.join(columns_added)}")
        else:
            print("  [SKIP] All target columns already exist")

        # Copy tooling_no to tooling_number if just added
        if 'tooling_number' in columns_added:
            cur.execute("UPDATE tooling SET tooling_number = tooling_no WHERE tooling_no IS NOT NULL")
            print("  [OK] Migrated tooling_no to tooling_number")

            # Check for duplicates before creating index
            cur.execute("""
                SELECT tooling_number, COUNT(*)
                FROM tooling
                WHERE tooling_number IS NOT NULL
                GROUP BY tooling_number
                HAVING COUNT(*) > 1
            """)
            duplicates = cur.fetchall()
            if duplicates:
                print(f"  [WARNING] Found {len(duplicates)} duplicate tooling_number values, keeping first occurrence")
                for dup_number, count in duplicates:
                    # Keep first, null out others
                    cur.execute("""
                        UPDATE tooling
                        SET tooling_number = NULL
                        WHERE id IN (
                            SELECT id FROM tooling
                            WHERE tooling_number = %s
                            ORDER BY id
                            OFFSET 1
                        )
                    """, (dup_number,))

            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tooling_number ON tooling(tooling_number) WHERE tooling_number IS NOT NULL")
            print("  [OK] Created unique index on tooling_number")

        # Ensure mold_type and is_continuous exist with correct types
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'tooling' AND column_name = 'is_continuous'
        """)
        result = cur.fetchone()
        if not result:
            cur.execute("ALTER TABLE tooling ADD COLUMN is_continuous BOOLEAN NOT NULL DEFAULT FALSE")
            changes.append("[OK] Added is_continuous to tooling")
            print("  [OK] Added is_continuous")

        # Change cavity_count from VARCHAR to INTEGER
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'tooling' AND column_name = 'cavity_count'
        """)
        result = cur.fetchone()
        if result and result[0] != 'integer':
            print("  [INFO] Converting cavity_count from VARCHAR to INTEGER")
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
            changes.append("[OK] Converted cavity_count to INTEGER")
            print("  [OK] Converted cavity_count to INTEGER")

        # Ensure mold_type is NOT NULL
        cur.execute("""
            ALTER TABLE tooling
            ALTER COLUMN mold_type SET NOT NULL,
            ALTER COLUMN mold_type SET DEFAULT 'unknown'
        """)
        cur.execute("UPDATE tooling SET mold_type = 'unknown' WHERE mold_type IS NULL")

        # Mark customer_id as deprecated
        cur.execute("COMMENT ON COLUMN tooling.customer_id IS 'DEPRECATED: Use tooling_customer_links instead'")

        conn.commit()

        print("\n[STEP 4] part_customer_aliases - ensure correct structure")

        # Check if customer_id column exists
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'part_customer_aliases' AND column_name = 'customer_id'
        """)
        has_customer_id_fk = cur.fetchone()

        if not has_customer_id_fk:
            # Add customer_id column
            cur.execute("""
                ALTER TABLE part_customer_aliases
                ADD COLUMN customer_id INTEGER REFERENCES customers(id)
            """)

            # Try to populate from customer_name
            cur.execute("""
                UPDATE part_customer_aliases pca
                SET customer_id = c.id
                FROM customers c
                WHERE pca.customer_name = c.name
            """)

            changes.append("[OK] Added customer_id FK to part_customer_aliases")
            print("  [OK] Added customer_id FK")

        # Add revision column if missing
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'part_customer_aliases' AND column_name = 'revision'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE part_customer_aliases
                ADD COLUMN revision VARCHAR(50) NOT NULL DEFAULT '',
                ADD COLUMN vehicle_model VARCHAR(100),
                ADD COLUMN remark TEXT,
                ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
                ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            """)
            changes.append("[OK] Added revision and other fields to part_customer_aliases")
            print("  [OK] Added revision and related fields")

        conn.commit()

        print("\n[STEP 5] tooling_steps - ensure correct structure")

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
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tooling_steps_tooling ON tooling_steps(tooling_id)")
        changes.append("[OK] Ensured tooling_steps table exists")
        print("  [OK] tooling_steps table ready")

        conn.commit()

        print("\n[STEP 6] tooling_parts - ensure correct structure with proper columns")

        # Check current tooling_parts structure
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tooling_parts'
            ORDER BY ordinal_position
        """)
        existing_cols = [row[0] for row in cur.fetchall()]

        if 'tooling_id' not in existing_cols or 'part_id' not in existing_cols:
            print("  [INFO] tooling_parts needs proper columns")
            # Drop and recreate with correct structure
            cur.execute("DROP TABLE IF EXISTS tooling_parts CASCADE")
            cur.execute("""
                CREATE TABLE tooling_parts (
                    id SERIAL PRIMARY KEY,
                    tooling_id INTEGER NOT NULL REFERENCES tooling(id) ON DELETE CASCADE,
                    part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
                    position VARCHAR(20),
                    sequence INTEGER NOT NULL DEFAULT 0,
                    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(tooling_id, part_id, position)
                )
            """)
            cur.execute("CREATE INDEX idx_tooling_parts_tooling ON tooling_parts(tooling_id)")
            cur.execute("CREATE INDEX idx_tooling_parts_part ON tooling_parts(part_id)")
            changes.append("[OK] Recreated tooling_parts with proper structure")
            print("  [OK] tooling_parts table recreated")
        else:
            # Add missing columns if structure exists
            if 'position' not in existing_cols:
                cur.execute("""
                    ALTER TABLE tooling_parts
                    ADD COLUMN position VARCHAR(20),
                    ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0,
                    ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT TRUE
                """)
                changes.append("[OK] Added position, sequence, is_primary to tooling_parts")
                print("  [OK] Added missing columns to tooling_parts")

        conn.commit()

        print("\n[STEP 7] tooling_customer_links - ensure correct structure")

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
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tooling_customer_links_tooling ON tooling_customer_links(tooling_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tooling_customer_links_customer ON tooling_customer_links(customer_id)")
        changes.append("[OK] Ensured tooling_customer_links table exists")
        print("  [OK] tooling_customer_links table ready")

        conn.commit()

        print("\n[STEP 8] import_batches and excel_import_rows - ensure correct structure")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS import_batches (
                id SERIAL PRIMARY KEY,
                file_name VARCHAR(500) NOT NULL,
                file_hash VARCHAR(64) NOT NULL,
                file_size BIGINT,
                total_sheets INTEGER NOT NULL DEFAULT 0,
                data_sheets INTEGER NOT NULL DEFAULT 0,
                total_rows INTEGER NOT NULL DEFAULT 0,
                valid_rows INTEGER NOT NULL DEFAULT 0,
                failed_rows INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
                imported_by VARCHAR(100),
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS excel_import_rows (
                id SERIAL PRIMARY KEY,
                batch_id INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
                source_sheet VARCHAR(200) NOT NULL,
                source_row INTEGER NOT NULL,
                raw_data JSONB,

                -- Parsed fields
                parsed_customer_name VARCHAR(200),
                parsed_customer_part_no VARCHAR(150),
                parsed_customer_part_name VARCHAR(200),
                parsed_internal_name VARCHAR(200),
                parsed_tooling_number VARCHAR(100),
                parsed_mold_type VARCHAR(50),
                parsed_is_continuous BOOLEAN,
                parsed_process_step_count INTEGER,
                parsed_cavity_count INTEGER,
                parsed_material VARCHAR(100),
                parsed_thickness NUMERIC(10,3),
                parsed_width NUMERIC(10,3),
                parsed_pitch NUMERIC(10,3),
                parsed_gross_weight NUMERIC(12,3),
                parsed_net_weight NUMERIC(12,3),
                parsed_position VARCHAR(20),

                -- Validation
                validation_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
                validation_errors TEXT,

                -- Resolution
                resolved_customer_id INTEGER,
                resolved_part_id INTEGER,
                resolved_tooling_id INTEGER,
                resolved_alias_id INTEGER,

                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_excel_import_rows_batch ON excel_import_rows(batch_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_excel_import_rows_status ON excel_import_rows(validation_status)")
        changes.append("[OK] Ensured import_batches and excel_import_rows tables with all parsed fields")
        print("  [OK] Import staging tables ready")

        conn.commit()

        print("\n[STEP 9] Verify structure")

        # Check table counts
        tables_to_check = [
            'customers', 'parts', 'tooling', 'part_customer_aliases',
            'tooling_steps', 'tooling_parts', 'tooling_customer_links',
            'import_batches', 'excel_import_rows'
        ]

        print("\nTable status:")
        for table in tables_to_check:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table}: {count} rows")

        # Check for orphans
        print("\nOrphan checks:")
        cur.execute("""
            SELECT COUNT(*) FROM tooling_parts tp
            LEFT JOIN tooling t ON tp.tooling_id = t.id
            WHERE tp.tooling_id IS NOT NULL AND t.id IS NULL
        """)
        orphan_tp_tooling = cur.fetchone()[0]
        print(f"  Orphan tooling_parts (bad tooling_id): {orphan_tp_tooling}")

        cur.execute("""
            SELECT COUNT(*) FROM tooling_parts tp
            LEFT JOIN parts p ON tp.part_id = p.id
            WHERE tp.part_id IS NOT NULL AND p.id IS NULL
        """)
        orphan_tp_parts = cur.fetchone()[0]
        print(f"  Orphan tooling_parts (bad part_id): {orphan_tp_parts}")

        cur.execute("""
            SELECT COUNT(*) FROM part_customer_aliases pca
            LEFT JOIN parts p ON pca.part_id = p.id
            WHERE p.id IS NULL
        """)
        orphan_aliases = cur.fetchone()[0]
        print(f"  Orphan part_customer_aliases: {orphan_aliases}")

        success = (orphan_tp_tooling == 0 and orphan_tp_parts == 0 and orphan_aliases == 0)

        print("\n" + "="*70)
        print("MIGRATION COMPLETED")
        print("="*70)

        print("\nChanges applied:")
        for change in changes:
            print(f"  {change}")

        print(f"\nOrphan check: {'PASSED' if success else 'FAILED'}")

        return {
            'success': True,
            'changes': changes,
            'orphan_check_passed': success,
            'table_counts': {table: None for table in tables_to_check}
        }

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

    finally:
        cur.close()

def main():
    print("PHASE 1: ORM AND DATABASE SCHEMA MIGRATION")
    print("Authoritative design: specs/001-erp-system-architecture/data-model.md")
    print()

    start_time = datetime.now()

    try:
        conn = connect_db()
        print(f"[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}\n")

        result = execute_migration_sql(conn)

        conn.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"\nDuration: {duration:.1f}s")

        if result['success'] and result.get('orphan_check_passed'):
            print("\n[OK] PHASE 1 COMPLETE")
            return 0
        else:
            print("\n[FAIL] PHASE 1 INCOMPLETE - see errors above")
            return 1

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
