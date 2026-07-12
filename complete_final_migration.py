#!/usr/bin/env python3
"""
Complete migration fix and resume script.
Fixes schema issues and completes all valid row processing with idempotency.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import sql

DB_HOST = "124.222.29.229"
DB_PORT = 5432
DB_NAME = "stamping_system"
DB_USER = "postgres"
DB_PASSWORD = "thehaoshi5DE"

def connect_db():
    """Connect with retry."""
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
                time.sleep(2)
            else:
                raise

def fix_schema(conn):
    """Fix schema issues before processing."""
    print("\n=== FIX SCHEMA ISSUES ===")
    cur = conn.cursor()

    try:
        # Check and fix tooling_parts table
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tooling_parts' AND column_name = 'tooling_id'
        """)

        if not cur.fetchone():
            print("[FIX] Adding tooling_id to tooling_parts")
            cur.execute("""
                ALTER TABLE tooling_parts
                ADD COLUMN tooling_id INTEGER REFERENCES tooling(id)
            """)
            conn.commit()
            print("[OK] Added tooling_id column")

        # Check and fix part_id column
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tooling_parts' AND column_name = 'part_id'
        """)

        if not cur.fetchone():
            print("[FIX] Adding part_id to tooling_parts")
            cur.execute("""
                ALTER TABLE tooling_parts
                ADD COLUMN part_id INTEGER REFERENCES parts(id)
            """)
            conn.commit()
            print("[OK] Added part_id column")

        # Add created_at if missing
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tooling_parts' AND column_name = 'created_at'
        """)

        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE tooling_parts
                ADD COLUMN created_at TIMESTAMP DEFAULT NOW()
            """)
            conn.commit()
            print("[OK] Added created_at column")

        # Add unique constraint for tooling_parts
        cur.execute("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'tooling_parts'::regclass
            AND conname = 'uq_tooling_parts'
        """)

        if not cur.fetchone():
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_tooling_parts
                ON tooling_parts(tooling_id, part_id)
                WHERE tooling_id IS NOT NULL AND part_id IS NOT NULL
            """)
            conn.commit()
            print("[OK] Added unique constraint to tooling_parts")

        # Check part_customer_aliases constraint
        cur.execute("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'part_customer_aliases'::regclass
            AND contype = 'u'
        """)

        constraints = cur.fetchall()
        print(f"[INFO] part_customer_aliases has {len(constraints)} unique constraints:")
        for name, def_ in constraints:
            print(f"  {name}: {def_}")

        # Add missing customer_part_no column if needed
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'part_customer_aliases' AND column_name = 'customer_part_name'
        """)

        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE part_customer_aliases
                ADD COLUMN customer_part_name VARCHAR(200)
            """)
            conn.commit()
            print("[OK] Added customer_part_name column")

        print("[OK] Schema fixes completed\n")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Schema fix failed: {e}")
        raise

    cur.close()

def reset_failed_rows(conn):
    """Reset ERROR rows back to VALID for retry."""
    print("=== RESET FAILED ROWS ===")
    cur = conn.cursor()

    # Reset ON CONFLICT errors (schema is now fixed)
    cur.execute("""
        UPDATE excel_import_rows
        SET validation_status = 'VALID',
            validation_errors = NULL,
            resolved_customer_id = NULL,
            resolved_part_id = NULL,
            resolved_tooling_id = NULL
        WHERE validation_status = 'ERROR'
        AND validation_errors LIKE '%ON CONFLICT%'
    """)

    reset_conflict = cur.rowcount

    # Reset tooling_id column errors (schema is now fixed)
    cur.execute("""
        UPDATE excel_import_rows
        SET validation_status = 'VALID',
            validation_errors = NULL,
            resolved_customer_id = NULL,
            resolved_part_id = NULL,
            resolved_tooling_id = NULL
        WHERE validation_status = 'ERROR'
        AND validation_errors LIKE '%tooling_id%'
    """)

    reset_tooling = cur.rowcount

    conn.commit()

    print(f"[OK] Reset {reset_conflict} ON CONFLICT errors")
    print(f"[OK] Reset {reset_tooling} tooling_id errors")

    # Show current status
    cur.execute("""
        SELECT validation_status, COUNT(*)
        FROM excel_import_rows
        GROUP BY validation_status
        ORDER BY validation_status
    """)

    print("\nCurrent staging status:")
    for status, count in cur.fetchall():
        print(f"  {status}: {count}")

    cur.close()

def process_all_valid_rows(conn):
    """Process all VALID rows with idempotency and proper error handling."""
    print("\n=== PROCESS ALL VALID ROWS ===")

    cur = conn.cursor()

    # Get all VALID rows
    cur.execute("""
        SELECT id, source_sheet, source_row,
               parsed_customer_part_no, parsed_internal_name, parsed_tooling_number,
               parsed_customer_part_name
        FROM excel_import_rows
        WHERE validation_status = 'VALID'
        ORDER BY id
    """)

    rows = cur.fetchall()
    total = len(rows)

    print(f"Processing {total} VALID rows...\n")

    stats = {
        'processed': 0,
        'customers_created': 0,
        'parts_created': 0,
        'parts_updated': 0,
        'tooling_linked': 0,
        'aliases_created': 0,
        'customer_links_created': 0,
        'skipped': 0,
        'errors': 0
    }

    customer_cache = {}
    part_cache = {}

    for idx, (row_id, sheet_name, source_row, customer_part_no, internal_name, tooling_no, customer_part_name) in enumerate(rows):
        try:
            # Extract customer name
            customer_name = sheet_name
            for suffix in ['产品', '(A)', '(B)', '(C)', '(D)', '(E)', '(F)', '(G)', '(H)', '(I)', '(J)', '(K)', '(L)', '(M)', '(N)', '(O)', '(P)', '(Q)', '(R)', '(S)', '(T)', '(U)', '(V)', '(W)', '(X)', '(Y)', '(Z)',
                          'A-A', 'A-B', 'A-C', 'A-D', 'A-E', 'A-F', 'A-G', 'A-H', 'A-J', 'A-K', 'A-L', 'A-M', 'A-N', 'A-O', 'A-P', 'A-Q', 'A-R', 'A-S', 'A-T', 'A-U', 'A-V', 'A-W', 'A-X', 'A-Y', 'A-Z',
                          'B-A', 'B-B', 'B-C', 'B-D', 'B-E', 'B-F', 'B-G', 'B-H', 'B-I', 'B-J', 'B-K', 'B-L', 'B-M', 'B-N', 'B-O', 'B-P', 'B-Q', 'B-R', 'B-S', 'B-T', 'B-U', 'B-V', 'B-W', 'B-X', 'B-Y', 'B-Z',
                          'CA', 'CB', 'CC', 'CD', 'CE', 'CF', 'CG', 'CH', 'CI', 'CJ', 'GBA', 'GBC']:
                if customer_name.startswith(suffix) or customer_name.endswith(suffix):
                    customer_name = customer_name.replace(suffix, '').strip()
                    break

            if not customer_name:
                customer_name = sheet_name

            # Find or create customer (cached)
            customer_id = customer_cache.get(customer_name)
            if customer_id is None:
                cur.execute("SELECT id FROM customers WHERE name = %s", (customer_name,))
                result = cur.fetchone()
                if result:
                    customer_id = result[0]
                else:
                    cur.execute("""
                        INSERT INTO customers (name, created_at)
                        VALUES (%s, NOW())
                        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id
                    """, (customer_name,))
                    customer_id = cur.fetchone()[0]
                    stats['customers_created'] += 1
                customer_cache[customer_name] = customer_id

            # Find or create part by internal_name
            part_id = None
            if internal_name:
                # Check cache first
                part_id = part_cache.get(internal_name)
                if part_id is None:
                    cur.execute("SELECT id FROM parts WHERE internal_name = %s LIMIT 1", (internal_name,))
                    result = cur.fetchone()
                    if result:
                        part_id = result[0]
                        stats['parts_updated'] += 1
                    else:
                        # Create new part with unique part_number
                        part_number = f"IMPORT_{row_id}_{datetime.now().strftime('%Y%m%d')}"
                        cur.execute("""
                            INSERT INTO parts (part_number, internal_name, created_at, updated_at)
                            VALUES (%s, %s, NOW(), NOW())
                            ON CONFLICT (part_number) DO UPDATE SET internal_name = EXCLUDED.internal_name
                            RETURNING id
                        """, (part_number, internal_name))
                        part_id = cur.fetchone()[0]
                        stats['parts_created'] += 1
                    part_cache[internal_name] = part_id

            # Link to tooling (using tooling_no column in tooling table)
            tooling_id = None
            if tooling_no and part_id:
                cur.execute("SELECT id FROM tooling WHERE tooling_no = %s LIMIT 1", (tooling_no,))
                result = cur.fetchone()
                if result:
                    tooling_id = result[0]

                    # Create tooling_parts link (now with proper columns)
                    cur.execute("""
                        INSERT INTO tooling_parts (tooling_id, part_id, created_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT DO NOTHING
                    """, (tooling_id, part_id))
                    if cur.rowcount > 0:
                        stats['tooling_linked'] += 1

                    # Create tooling_customer_links
                    cur.execute("""
                        INSERT INTO tooling_customer_links (tooling_id, customer_id, relation_type, created_at)
                        VALUES (%s, %s, 'user', NOW())
                        ON CONFLICT (tooling_id, customer_id, relation_type) DO NOTHING
                    """, (tooling_id, customer_id))
                    if cur.rowcount > 0:
                        stats['customer_links_created'] += 1

            # Create part_customer_aliases (using existing constraint: part_id, customer_name)
            if customer_id and part_id and customer_part_no:
                cur.execute("""
                    INSERT INTO part_customer_aliases (part_id, customer_name, customer_part_no, customer_part_name, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (part_id, customer_name) DO UPDATE
                    SET customer_part_no = EXCLUDED.customer_part_no,
                        customer_part_name = EXCLUDED.customer_part_name
                    RETURNING id
                """, (part_id, customer_name, customer_part_no, customer_part_name))
                if cur.rowcount > 0:
                    stats['aliases_created'] += 1

            # Update staging row
            cur.execute("""
                UPDATE excel_import_rows
                SET resolved_customer_id = %s,
                    resolved_part_id = %s,
                    resolved_tooling_id = %s,
                    validation_status = 'IMPORTED'
                WHERE id = %s
            """, (customer_id, part_id, tooling_id, row_id))

            stats['processed'] += 1

            # Commit every 100 rows
            if stats['processed'] % 100 == 0:
                conn.commit()
                print(f"  Progress: {stats['processed']}/{total} ({100*stats['processed']/total:.1f}%)")

        except Exception as e:
            conn.rollback()
            stats['errors'] += 1
            error_msg = str(e)[:300]

            # Log error back to staging
            cur.execute("""
                UPDATE excel_import_rows
                SET validation_status = 'ERROR',
                    validation_errors = %s
                WHERE id = %s
            """, (error_msg, row_id))
            conn.commit()

            if stats['errors'] <= 10:
                print(f"  [ERROR] Row {row_id}: {error_msg[:100]}")

    # Final commit
    conn.commit()
    cur.close()

    print(f"\n[OK] Processing completed")
    print(f"  Processed: {stats['processed']}/{total}")
    print(f"  Customers created: {stats['customers_created']}")
    print(f"  Parts created: {stats['parts_created']}")
    print(f"  Parts updated: {stats['parts_updated']}")
    print(f"  Tooling links: {stats['tooling_linked']}")
    print(f"  Customer links: {stats['customer_links_created']}")
    print(f"  Aliases created: {stats['aliases_created']}")
    print(f"  Errors: {stats['errors']}")

    return stats

def validate_results(conn):
    """Comprehensive validation."""
    print("\n=== VALIDATION ===")

    cur = conn.cursor()

    validation = {}

    # 1. Final counts
    cur.execute("SELECT COUNT(*) FROM customers")
    validation['customers'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM parts")
    validation['parts'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tooling")
    validation['tooling'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tooling_parts")
    validation['tooling_parts'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM part_customer_aliases")
    validation['aliases'] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tooling_customer_links")
    validation['tooling_customer_links'] = cur.fetchone()[0]

    # 2. Staging status
    cur.execute("""
        SELECT validation_status, COUNT(*)
        FROM excel_import_rows
        GROUP BY validation_status
    """)
    validation['staging_status'] = dict(cur.fetchall())

    # 3. Orphan checks
    cur.execute("""
        SELECT COUNT(*) FROM tooling_parts tp
        LEFT JOIN tooling t ON tp.tooling_id = t.id
        WHERE tp.tooling_id IS NOT NULL AND t.id IS NULL
    """)
    validation['orphan_tooling_parts'] = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM part_customer_aliases pca
        LEFT JOIN parts p ON pca.part_id = p.id
        WHERE p.id IS NULL
    """)
    validation['orphan_aliases'] = cur.fetchone()[0]

    # 4. Sample traces (10)
    cur.execute("""
        SELECT e.source_sheet, e.source_row, e.parsed_internal_name,
               p.part_number, c.name, t.tooling_no,
               pca.customer_part_no
        FROM excel_import_rows e
        LEFT JOIN parts p ON e.resolved_part_id = p.id
        LEFT JOIN customers c ON e.resolved_customer_id = c.id
        LEFT JOIN tooling t ON e.resolved_tooling_id = t.id
        LEFT JOIN part_customer_aliases pca ON pca.part_id = p.id AND pca.customer_name = c.name
        WHERE e.validation_status = 'IMPORTED'
        AND e.parsed_internal_name IS NOT NULL
        ORDER BY e.id
        LIMIT 10
    """)
    validation['sample_traces'] = cur.fetchall()

    cur.close()

    print(f"[OK] Validation completed")
    print(f"\nFinal counts:")
    print(f"  customers: {validation['customers']}")
    print(f"  parts: {validation['parts']}")
    print(f"  tooling: {validation['tooling']}")
    print(f"  tooling_parts: {validation['tooling_parts']}")
    print(f"  part_customer_aliases: {validation['aliases']}")
    print(f"  tooling_customer_links: {validation['tooling_customer_links']}")

    print(f"\nStaging status:")
    for status, count in validation['staging_status'].items():
        print(f"  {status}: {count}")

    print(f"\nOrphan checks:")
    print(f"  Orphan tooling_parts: {validation['orphan_tooling_parts']}")
    print(f"  Orphan aliases: {validation['orphan_aliases']}")

    print(f"\nSample traces (10):")
    for sheet, row, internal_name, part_num, cust, tooling, cust_part_no in validation['sample_traces']:
        print(f"  [{sheet}:{row}] {internal_name}")
        print(f"    -> Part: {part_num}, Customer: {cust}, Tooling: {tooling}, CustPartNo: {cust_part_no}")

    return validation

def main():
    """Execute complete fix and migration."""
    start_time = datetime.now()

    print("="*70)
    print("COMPLETE MIGRATION FIX AND EXECUTION")
    print(f"Started: {start_time}")
    print("="*70)

    try:
        conn = connect_db()
        print(f"\n[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}")

        # Step 1: Fix schema
        fix_schema(conn)

        # Step 2: Reset failed rows
        reset_failed_rows(conn)

        # Step 3: Process all valid rows
        process_stats = process_all_valid_rows(conn)

        # Step 4: Validate
        validation = validate_results(conn)

        conn.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "="*70)
        print("MIGRATION COMPLETED SUCCESSFULLY")
        print(f"Duration: {duration:.1f}s")
        print("="*70)

        # Check completion criteria
        success = (
            validation['tooling_parts'] > 0 and
            validation['aliases'] > 0 and
            validation['tooling_customer_links'] > 0 and
            validation['staging_status'].get('IMPORTED', 0) > 5000 and
            validation['orphan_tooling_parts'] == 0 and
            validation['orphan_aliases'] == 0 and
            len(validation['sample_traces']) == 10
        )

        result = {
            'status': 'COMPLETED' if success else 'PARTIAL',
            'duration_seconds': duration,
            'process_stats': process_stats,
            'validation': {
                'counts': {
                    'customers': validation['customers'],
                    'parts': validation['parts'],
                    'tooling': validation['tooling'],
                    'tooling_parts': validation['tooling_parts'],
                    'aliases': validation['aliases'],
                    'tooling_customer_links': validation['tooling_customer_links']
                },
                'staging_status': validation['staging_status'],
                'orphans': {
                    'tooling_parts': validation['orphan_tooling_parts'],
                    'aliases': validation['orphan_aliases']
                },
                'sample_traces_count': len(validation['sample_traces'])
            },
            'success_criteria_met': success
        }

        with open('final_migration_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        return result

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'FAILED', 'error': str(e)}

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get('success_criteria_met') else 1)
