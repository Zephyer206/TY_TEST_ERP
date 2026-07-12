#!/usr/bin/env python3
"""
Complete database migration and Excel import - CORRECTED VERSION
Fixed to use actual database schema (tooling_no, not tooling_number)
"""

import json
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import psycopg2
from psycopg2 import sql
import xlrd

# Database connection
DB_HOST = "124.222.29.229"
DB_PORT = 5432
DB_NAME = "stamping_system"
DB_USER = "postgres"
DB_PASSWORD = "thehaoshi5DE"

EXCEL_FILE = "excel/五金模具及产品清单表.xls"

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

def execute_full_migration():
    """Execute complete migration with proper error handling."""
    start_time = datetime.now()

    print("="*70)
    print("COMPLETE DATABASE MIGRATION AND EXCEL IMPORT")
    print(f"Started: {start_time}")
    print("="*70)

    conn = connect_db()
    print(f"\n[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}\n")

    cur = conn.cursor()

    # Get initial counts
    print("=== INITIAL STATE ===")
    cur.execute("SELECT COUNT(*) FROM customers")
    customers_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parts")
    parts_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tooling")
    tooling_before = cur.fetchone()[0]
    print(f"customers: {customers_before}")
    print(f"parts: {parts_before}")
    print(f"tooling: {tooling_before}")

    # PHASE 1: Import Excel to staging (already done)
    cur.execute("SELECT COUNT(*) FROM import_batches")
    if cur.fetchone()[0] > 0:
        print("\n[INFO] Excel already imported to staging, using existing batch")
        cur.execute("SELECT id, valid_rows FROM import_batches ORDER BY id DESC LIMIT 1")
        batch_id, valid_rows = cur.fetchone()
        print(f"Batch ID: {batch_id}, Valid rows: {valid_rows}")
    else:
        print("\n[ERROR] No import batch found. Run phase 2 import first.")
        return {'status': 'FAILED', 'error': 'No staging data'}

    # PHASE 2: Process staging to production (FIXED)
    print("\n=== PHASE 2: Process Staging to Production (CORRECTED) ===")

    cur.execute("""
        SELECT id, source_sheet, source_row,
               parsed_customer_part_no, parsed_internal_name, parsed_tooling_number
        FROM excel_import_rows
        WHERE batch_id = %s AND validation_status = 'VALID'
        ORDER BY id
    """, (batch_id,))

    rows = cur.fetchall()
    print(f"Processing {len(rows)} valid rows...\n")

    stats = {
        'customers_created': 0,
        'parts_created': 0,
        'parts_updated': 0,
        'tooling_linked': 0,
        'aliases_created': 0,
        'customer_links_created': 0,
        'processed': 0,
        'errors': 0
    }

    customer_cache = {}
    part_cache = {}

    for row_id, sheet_name, source_row, customer_part_no, internal_name, tooling_no in rows:
        try:
            # Extract customer name from sheet
            customer_name = sheet_name
            for suffix in ['产品', '(A)', '(B)', '(C)', '(D)', '(E)', '(F)', '(G)', '(H)', '(I)', '(J)', '(K)', '(L)', '(M)', '(N)', '(O)', '(P)', '(Q)', '(R)', '(S)', '(T)', '(U)', '(V)', '(W)', '(X)', '(Y)', '(Z)']:
                if suffix in customer_name:
                    customer_name = customer_name.replace(suffix, '').strip()

            # Find or create customer
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
                        RETURNING id
                    """, (customer_name,))
                    customer_id = cur.fetchone()[0]
                    stats['customers_created'] += 1
                customer_cache[customer_name] = customer_id

            # Find or create part by internal_name
            part_id = None
            if internal_name:
                part_id = part_cache.get(internal_name)
                if part_id is None:
                    cur.execute("SELECT id FROM parts WHERE internal_name = %s LIMIT 1", (internal_name,))
                    result = cur.fetchone()
                    if result:
                        part_id = result[0]
                        stats['parts_updated'] += 1
                    else:
                        # Create new part - use auto-generated part_number
                        part_number = f"IMPORT_{row_id}_{batch_id}"
                        cur.execute("""
                            INSERT INTO parts (part_number, internal_name, created_at, updated_at)
                            VALUES (%s, %s, NOW(), NOW())
                            RETURNING id
                        """, (part_number, internal_name))
                        part_id = cur.fetchone()[0]
                        stats['parts_created'] += 1
                    part_cache[internal_name] = part_id

            # Link to tooling using actual column name tooling_no
            tooling_id = None
            if tooling_no and part_id:
                cur.execute("SELECT id FROM tooling WHERE tooling_no = %s", (tooling_no,))
                result = cur.fetchone()
                if result:
                    tooling_id = result[0]

                    # Create tooling_parts link
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
                        ON CONFLICT DO NOTHING
                    """, (tooling_id, customer_id))
                    if cur.rowcount > 0:
                        stats['customer_links_created'] += 1

            # Create part_customer_aliases
            if customer_id and part_id and customer_part_no:
                cur.execute("""
                    INSERT INTO part_customer_aliases (part_id, customer_name, customer_part_no, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (part_id, customer_name, customer_part_no) DO NOTHING
                """, (part_id, customer_name, customer_part_no))
                if cur.rowcount > 0:
                    stats['aliases_created'] += 1

            # Update staging row
            cur.execute("""
                UPDATE excel_import_rows
                SET resolved_customer_id = %s, resolved_part_id = %s,
                    resolved_tooling_id = %s, validation_status = 'IMPORTED'
                WHERE id = %s
            """, (customer_id, part_id, tooling_id, row_id))

            stats['processed'] += 1

            if stats['processed'] % 500 == 0:
                conn.commit()
                print(f"  Processed {stats['processed']}/{len(rows)} rows...")

        except Exception as e:
            conn.rollback()
            stats['errors'] += 1
            error_msg = str(e)[:200]
            cur.execute("""
                UPDATE excel_import_rows
                SET validation_status = 'ERROR', validation_errors = %s
                WHERE id = %s
            """, (error_msg, row_id))
            conn.commit()
            if stats['errors'] <= 5:
                print(f"  [ERROR] Row {row_id}: {error_msg}")

    conn.commit()

    print(f"\n[OK] Phase 2 completed")
    print(f"  Processed: {stats['processed']}/{len(rows)}")
    print(f"  Customers created: {stats['customers_created']}")
    print(f"  Parts created: {stats['parts_created']}")
    print(f"  Parts updated: {stats['parts_updated']}")
    print(f"  Tooling links: {stats['tooling_linked']}")
    print(f"  Customer links: {stats['customer_links_created']}")
    print(f"  Aliases created: {stats['aliases_created']}")
    print(f"  Errors: {stats['errors']}")

    # PHASE 3: Validation
    print("\n=== PHASE 3: Validation ===")

    cur.execute("SELECT COUNT(*) FROM customers")
    customers_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parts")
    parts_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tooling_parts")
    tooling_parts_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM part_customer_aliases")
    aliases_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tooling_customer_links")
    tooling_customer_links_count = cur.fetchone()[0]

    # Sample traces
    cur.execute("""
        SELECT e.source_sheet, e.source_row, e.parsed_internal_name,
               p.part_number, c.name, t.tooling_no
        FROM excel_import_rows e
        LEFT JOIN parts p ON e.resolved_part_id = p.id
        LEFT JOIN customers c ON e.resolved_customer_id = c.id
        LEFT JOIN tooling t ON e.resolved_tooling_id = t.id
        WHERE e.validation_status = 'IMPORTED'
        ORDER BY e.id
        LIMIT 10
    """)
    sample_traces = cur.fetchall()

    print(f"[OK] Validation completed")
    print(f"  Customers: {customers_before} -> {customers_after} (+{customers_after - customers_before})")
    print(f"  Parts: {parts_before} -> {parts_after} (+{parts_after - parts_before})")
    print(f"  Tooling-Parts links: {tooling_parts_count}")
    print(f"  Part-Customer aliases: {aliases_count}")
    print(f"  Tooling-Customer links: {tooling_customer_links_count}")

    print(f"\n=== Sample Traces (10) ===")
    for sheet, row, internal_name, part_num, cust, tooling in sample_traces[:10]:
        print(f"  [{sheet}:{row}] {internal_name} -> Part:{part_num}, Customer:{cust}, Tooling:{tooling}")

    cur.close()
    conn.close()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "="*70)
    print(f"MIGRATION COMPLETED SUCCESSFULLY")
    print(f"Duration: {duration:.1f}s")
    print("="*70)

    result = {
        'status': 'COMPLETED',
        'duration_seconds': duration,
        'before': {
            'customers': customers_before,
            'parts': parts_before,
            'tooling': tooling_before
        },
        'after': {
            'customers': customers_after,
            'parts': parts_after,
            'tooling': tooling_before,
            'tooling_parts': tooling_parts_count,
            'aliases': aliases_count,
            'tooling_customer_links': tooling_customer_links_count
        },
        'stats': stats,
        'sample_traces': len(sample_traces)
    }

    return result

if __name__ == "__main__":
    try:
        result = execute_full_migration()

        with open('final_migration_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        sys.exit(0 if result.get('status') == 'COMPLETED' else 1)

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
