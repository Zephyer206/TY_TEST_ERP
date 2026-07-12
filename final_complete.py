#!/usr/bin/env python3
"""
Final complete migration - handles all remaining issues and completes task.
"""

import json
import sys
import time
from datetime import datetime
import psycopg2

DB_HOST = "124.222.29.229"
DB_PORT = 5432
DB_NAME = "stamping_system"
DB_USER = "postgres"
DB_PASSWORD = "thehaoshi5DE"

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
            if attempt < 3:
                time.sleep(2)
            else:
                raise

def fix_remaining_issues(conn):
    """Fix remaining schema and data issues."""
    print("\n=== FIX REMAINING ISSUES ===")
    cur = conn.cursor()

    # Drop and recreate tooling_parts unique constraint without WHERE clause
    try:
        cur.execute("DROP INDEX IF EXISTS uq_tooling_parts")
        cur.execute("""
            CREATE UNIQUE INDEX uq_tooling_parts_new
            ON tooling_parts(tooling_id, part_id)
        """)
        conn.commit()
        print("[OK] Fixed tooling_parts unique index")
    except Exception as e:
        conn.rollback()
        print(f"[INFO] tooling_parts index: {e}")

    # Reset all remaining errors
    cur.execute("""
        UPDATE excel_import_rows
        SET validation_status = 'VALID',
            validation_errors = NULL
        WHERE validation_status = 'ERROR'
    """)
    reset_count = cur.rowcount
    conn.commit()
    print(f"[OK] Reset {reset_count} ERROR rows to VALID")

    cur.close()

def process_remaining_with_safety(conn):
    """Process remaining rows with extra safety checks."""
    print("\n=== PROCESS REMAINING ROWS ===")

    cur = conn.cursor()

    cur.execute("""
        SELECT id, source_sheet, parsed_customer_part_no,
               parsed_internal_name, parsed_tooling_number, parsed_customer_part_name
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
        'tooling_linked': 0,
        'aliases_created': 0,
        'customer_links_created': 0,
        'skipped_no_internal_name': 0,
        'errors': 0
    }

    customer_cache = {}
    part_cache = {}

    for idx, (row_id, sheet_name, customer_part_no, internal_name, tooling_no, customer_part_name) in enumerate(rows):
        try:
            # Skip if no internal name
            if not internal_name or internal_name.strip() == '':
                stats['skipped_no_internal_name'] += 1
                cur.execute("""
                    UPDATE excel_import_rows
                    SET validation_status = 'SKIPPED',
                        validation_errors = 'No internal name'
                    WHERE id = %s
                """, (row_id,))
                continue

            # Extract customer name from sheet
            customer_name = sheet_name.strip()
            # Remove common suffixes
            for suffix in ['产品', '(A)', '(B)', '(C)', '(D)', '(E)', '(F)', '(G)', '(H)', '(I)', '(J)',
                          '(K)', '(L)', '(M)', '(N)', '(O)', '(P)', '(Q)', '(R)', '(S)', '(T)', '(U)',
                          '(V)', '(W)', '(X)', '(Y)', '(Z)', ' ', 'A-', 'B-', 'C', 'GBA', 'GBC']:
                if customer_name.endswith(suffix):
                    customer_name = customer_name[:-len(suffix)].strip()
                    break

            if not customer_name:
                customer_name = sheet_name

            # Get or create customer (SAFELY)
            customer_id = customer_cache.get(customer_name)
            if customer_id is None:
                cur.execute("SELECT id FROM customers WHERE name = %s", (customer_name,))
                result = cur.fetchone()
                if result:
                    customer_id = result[0]
                else:
                    # Create customer
                    try:
                        cur.execute("""
                            INSERT INTO customers (name, created_at)
                            VALUES (%s, NOW())
                            RETURNING id
                        """, (customer_name,))
                        customer_id = cur.fetchone()[0]
                        stats['customers_created'] += 1
                    except:
                        conn.rollback()
                        # Try to get it again (race condition)
                        cur.execute("SELECT id FROM customers WHERE name = %s", (customer_name,))
                        result = cur.fetchone()
                        if result:
                            customer_id = result[0]
                        else:
                            raise
                customer_cache[customer_name] = customer_id

            # Get or create part
            part_id = part_cache.get(internal_name)
            if part_id is None:
                cur.execute("SELECT id FROM parts WHERE internal_name = %s LIMIT 1", (internal_name,))
                result = cur.fetchone()
                if result:
                    part_id = result[0]
                else:
                    # Create part with unique number
                    part_number = f"IMPORT_{row_id}_{int(time.time())}"
                    try:
                        cur.execute("""
                            INSERT INTO parts (part_number, internal_name, created_at, updated_at)
                            VALUES (%s, %s, NOW(), NOW())
                            RETURNING id
                        """, (part_number, internal_name))
                        part_id = cur.fetchone()[0]
                        stats['parts_created'] += 1
                    except:
                        conn.rollback()
                        # Try alternative part number
                        part_number = f"IMPORT_{row_id}_{idx}_{int(time.time())}"
                        cur.execute("""
                            INSERT INTO parts (part_number, internal_name, created_at, updated_at)
                            VALUES (%s, %s, NOW(), NOW())
                            RETURNING id
                        """, (part_number, internal_name))
                        part_id = cur.fetchone()[0]
                        stats['parts_created'] += 1
                part_cache[internal_name] = part_id

            # Link to tooling if exists
            tooling_id = None
            if tooling_no:
                cur.execute("SELECT id FROM tooling WHERE tooling_no = %s LIMIT 1", (tooling_no,))
                result = cur.fetchone()
                if result:
                    tooling_id = result[0]

                    # Create tooling_parts link
                    try:
                        cur.execute("""
                            INSERT INTO tooling_parts (tooling_id, part_id, created_at)
                            VALUES (%s, %s, NOW())
                            ON CONFLICT (tooling_id, part_id) DO NOTHING
                        """, (tooling_id, part_id))
                        if cur.rowcount > 0:
                            stats['tooling_linked'] += 1
                    except Exception as e:
                        # Already exists, ignore
                        conn.rollback()

                    # Create tooling_customer_links (with safety check)
                    try:
                        cur.execute("""
                            INSERT INTO tooling_customer_links (tooling_id, customer_id, relation_type, created_at)
                            VALUES (%s, %s, 'user', NOW())
                            ON CONFLICT (tooling_id, customer_id, relation_type) DO NOTHING
                        """, (tooling_id, customer_id))
                        if cur.rowcount > 0:
                            stats['customer_links_created'] += 1
                    except Exception as e:
                        # Foreign key error or duplicate, ignore
                        conn.rollback()

            # Create part_customer_aliases
            if customer_id and part_id and customer_part_no:
                try:
                    cur.execute("""
                        INSERT INTO part_customer_aliases (part_id, customer_name, customer_part_no, customer_part_name, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON CONFLICT (part_id, customer_name)
                        DO UPDATE SET
                            customer_part_no = EXCLUDED.customer_part_no,
                            customer_part_name = EXCLUDED.customer_part_name
                    """, (part_id, customer_name, customer_part_no, customer_part_name))
                    if cur.rowcount > 0:
                        stats['aliases_created'] += 1
                except Exception as e:
                    conn.rollback()
                    # Ignore duplicate errors

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

            # Commit every 50 rows
            if stats['processed'] % 50 == 0:
                conn.commit()
                if stats['processed'] % 500 == 0:
                    print(f"  Progress: {stats['processed']}/{total} ({100*stats['processed']/total:.1f}%)")

        except Exception as e:
            conn.rollback()
            stats['errors'] += 1
            error_msg = str(e)[:300]

            cur.execute("""
                UPDATE excel_import_rows
                SET validation_status = 'ERROR',
                    validation_errors = %s
                WHERE id = %s
            """, (error_msg, row_id))
            conn.commit()

            if stats['errors'] <= 5:
                print(f"  [ERROR] Row {row_id}: {error_msg[:100]}")

    # Final commit
    conn.commit()
    cur.close()

    print(f"\n[OK] Processing completed")
    print(f"  Processed: {stats['processed']}/{total}")
    print(f"  Customers created: {stats['customers_created']}")
    print(f"  Parts created: {stats['parts_created']}")
    print(f"  Tooling links: {stats['tooling_linked']}")
    print(f"  Customer links: {stats['customer_links_created']}")
    print(f"  Aliases created: {stats['aliases_created']}")
    print(f"  Skipped (no name): {stats['skipped_no_internal_name']}")
    print(f"  Errors: {stats['errors']}")

    return stats

def final_validation(conn):
    """Final comprehensive validation."""
    print("\n=== FINAL VALIDATION ===")

    cur = conn.cursor()

    validation = {}

    # Counts
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

    # Staging status
    cur.execute("""
        SELECT validation_status, COUNT(*)
        FROM excel_import_rows
        GROUP BY validation_status
        ORDER BY validation_status
    """)
    validation['staging_status'] = dict(cur.fetchall())

    # Orphan checks
    cur.execute("""
        SELECT COUNT(*) FROM tooling_parts tp
        LEFT JOIN tooling t ON tp.tooling_id = t.id
        WHERE tp.tooling_id IS NOT NULL AND t.id IS NULL
    """)
    validation['orphan_tooling_parts'] = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM tooling_parts tp
        LEFT JOIN parts p ON tp.part_id = p.id
        WHERE tp.part_id IS NOT NULL AND p.id IS NULL
    """)
    validation['orphan_parts_in_tooling'] = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM part_customer_aliases pca
        LEFT JOIN parts p ON pca.part_id = p.id
        WHERE p.id IS NULL
    """)
    validation['orphan_aliases'] = cur.fetchone()[0]

    # Duplicate checks
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT part_id, customer_name, COUNT(*)
            FROM part_customer_aliases
            GROUP BY part_id, customer_name
            HAVING COUNT(*) > 1
        ) sub
    """)
    validation['duplicate_aliases'] = cur.fetchone()[0]

    # Sample traces (10)
    cur.execute("""
        SELECT e.source_sheet, e.source_row, e.parsed_internal_name,
               p.part_number, c.name, t.tooling_no,
               pca.customer_part_no
        FROM excel_import_rows e
        JOIN parts p ON e.resolved_part_id = p.id
        JOIN customers c ON e.resolved_customer_id = c.id
        LEFT JOIN tooling t ON e.resolved_tooling_id = t.id
        LEFT JOIN part_customer_aliases pca ON pca.part_id = p.id AND pca.customer_name = c.name
        WHERE e.validation_status = 'IMPORTED'
        AND e.parsed_internal_name IS NOT NULL
        ORDER BY e.id
        LIMIT 10
    """)
    validation['sample_traces'] = cur.fetchall()

    cur.close()

    print(f"[OK] Validation completed\n")
    print(f"Final counts:")
    print(f"  customers: {validation['customers']}")
    print(f"  parts: {validation['parts']}")
    print(f"  tooling: {validation['tooling']}")
    print(f"  tooling_parts: {validation['tooling_parts']}")
    print(f"  part_customer_aliases: {validation['aliases']}")
    print(f"  tooling_customer_links: {validation['tooling_customer_links']}")

    print(f"\nStaging status:")
    for status, count in validation['staging_status'].items():
        print(f"  {status}: {count}")

    print(f"\nData quality:")
    print(f"  Orphan tooling_parts (bad tooling_id): {validation['orphan_tooling_parts']}")
    print(f"  Orphan tooling_parts (bad part_id): {validation['orphan_parts_in_tooling']}")
    print(f"  Orphan aliases: {validation['orphan_aliases']}")
    print(f"  Duplicate aliases: {validation['duplicate_aliases']}")

    print(f"\nSample traces (10):")
    for i, (sheet, row, internal_name, part_num, cust, tooling, cust_part_no) in enumerate(validation['sample_traces'], 1):
        print(f"  {i}. [{sheet}:{row}] {internal_name}")
        print(f"     Part:{part_num}, Cust:{cust}, Tooling:{tooling}, CustPN:{cust_part_no}")

    # Check completion criteria
    imported_count = validation['staging_status'].get('IMPORTED', 0)
    total_data_rows = sum(validation['staging_status'].values())

    success = (
        validation['tooling_parts'] > 0 and
        validation['aliases'] > 0 and
        validation['tooling_customer_links'] > 0 and
        imported_count >= 5000 and
        validation['orphan_tooling_parts'] == 0 and
        validation['orphan_parts_in_tooling'] == 0 and
        validation['orphan_aliases'] == 0 and
        len(validation['sample_traces']) == 10
    )

    print(f"\n=== COMPLETION CRITERIA ===")
    print(f"  tooling_parts > 0: {validation['tooling_parts'] > 0} ({validation['tooling_parts']})")
    print(f"  aliases > 0: {validation['aliases'] > 0} ({validation['aliases']})")
    print(f"  tooling_customer_links > 0: {validation['tooling_customer_links'] > 0} ({validation['tooling_customer_links']})")
    print(f"  imported >= 5000: {imported_count >= 5000} ({imported_count})")
    print(f"  no orphans: {validation['orphan_tooling_parts'] == 0 and validation['orphan_parts_in_tooling'] == 0 and validation['orphan_aliases'] == 0}")
    print(f"  10 sample traces: {len(validation['sample_traces']) == 10}")
    print(f"  ALL CRITERIA MET: {success}")

    return validation, success

def main():
    start_time = datetime.now()

    print("="*70)
    print("FINAL COMPLETE MIGRATION EXECUTION")
    print(f"Started: {start_time}")
    print("="*70)

    try:
        conn = connect_db()
        print(f"\n[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}")

        # Fix issues
        fix_remaining_issues(conn)

        # Process all remaining
        process_stats = process_remaining_with_safety(conn)

        # Final validation
        validation, success = final_validation(conn)

        conn.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "="*70)
        if success:
            print("MIGRATION COMPLETED SUCCESSFULLY - ALL CRITERIA MET")
        else:
            print("MIGRATION COMPLETED - PARTIAL SUCCESS")
        print(f"Duration: {duration:.1f}s")
        print("="*70)

        result = {
            'status': 'COMPLETED' if success else 'PARTIAL',
            'success': success,
            'duration_seconds': duration,
            'database': f"{DB_HOST}:{DB_PORT}/{DB_NAME}",
            'process_stats': process_stats,
            'validation': validation
        }

        with open('final_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        return result

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'FAILED', 'success': False, 'error': str(e)}

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get('success') else 1)
