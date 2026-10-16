#!/usr/bin/env python3
"""
Complete database migration and Excel import execution script.
Executes all phases: ORM fixes, migration, Excel import, validation.
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import psycopg2
from psycopg2 import sql
import xlrd

# Database connection parameters
DB_HOST = os.environ["ZEPHYR_DB_HOST"]
DB_PORT = int(os.environ.get("ZEPHYR_DB_PORT", "5432"))
DB_NAME = os.environ.get("ZEPHYR_DB_NAME", "stamping_system")
DB_USER = os.environ.get("ZEPHYR_DB_USER", "postgres")
DB_PASSWORD = os.environ["ZEPHYR_DB_PASSWORD"]

EXCEL_FILE = "excel/五金模具及产品清单表.xls"

def connect_db():
    """Connect to database with retry."""
    for attempt in range(1, 4):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=10
            )
            return conn
        except Exception as e:
            print(f"[ERROR] Connection attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(2)
            else:
                raise

def get_table_counts(conn) -> Dict[str, int]:
    """Get row counts for all business tables."""
    conn.rollback()  # Clear any previous transaction state
    cur = conn.cursor()
    tables = ['customers', 'parts', 'tooling', 'part_customer_aliases',
              'tooling_parts', 'tooling_steps', 'tooling_customer_links',
              'quotes', 'price_accounts', 'price_adjustments',
              'import_batches', 'excel_import_rows']

    counts = {}
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]
            conn.commit()
        except:
            conn.rollback()
            counts[table] = 'NOT_EXISTS'

    cur.close()
    return counts

def phase1_create_missing_tables(conn):
    """Phase 1: Create missing tables for staging and relationships."""
    print("\n=== PHASE 1: Create Missing Tables ===")
    conn.rollback()  # Clear any previous transaction state
    cur = conn.cursor()

    # Create import_batches if not exists
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
    print("[OK] import_batches table ready")

    # Create excel_import_rows if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS excel_import_rows (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER NOT NULL REFERENCES import_batches(id),
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
            parsed_process_step_count INTEGER,
            parsed_cavity_count INTEGER,
            parsed_material VARCHAR(100),
            parsed_thickness NUMERIC(10,3),
            parsed_width NUMERIC(10,3),
            parsed_pitch NUMERIC(10,3),
            parsed_gross_weight NUMERIC(12,3),
            parsed_net_weight NUMERIC(12,3),

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
    print("[OK] excel_import_rows table ready")

    # Create tooling_steps if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tooling_steps (
            id SERIAL PRIMARY KEY,
            tooling_id INTEGER NOT NULL REFERENCES tooling(id),
            step_no INTEGER NOT NULL,
            step_code VARCHAR(50),
            step_name VARCHAR(200),
            operation_type VARCHAR(100),
            sequence INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(tooling_id, step_no)
        )
    """)
    print("[OK] tooling_steps table ready")

    # Create tooling_customer_links if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tooling_customer_links (
            id SERIAL PRIMARY KEY,
            tooling_id INTEGER NOT NULL REFERENCES tooling(id),
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            relation_type VARCHAR(30) NOT NULL DEFAULT 'user',
            is_owner BOOLEAN NOT NULL DEFAULT FALSE,
            valid_from DATE,
            valid_to DATE,
            remark TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(tooling_id, customer_id, relation_type)
        )
    """)
    print("[OK] tooling_customer_links table ready")

    # Add customer_code to customers if missing
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'customers' AND column_name = 'customer_code'
    """)
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE customers
            ADD COLUMN customer_code VARCHAR(20) UNIQUE
        """)
        print("[OK] Added customer_code to customers")

    # Add fields to tooling if missing
    tooling_fields = [
        ('process_step_count', 'INTEGER'),
        ('is_continuous', 'BOOLEAN NOT NULL DEFAULT TRUE'),
    ]

    for field_name, field_type in tooling_fields:
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tooling' AND column_name = '{field_name}'
        """)
        if not cur.fetchone():
            cur.execute(f"ALTER TABLE tooling ADD COLUMN {field_name} {field_type}")
            print(f"[OK] Added {field_name} to tooling")

    # Add fields to parts if missing
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'internal_part_no'
    """)
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE parts
            ADD COLUMN internal_part_no VARCHAR(100) UNIQUE
        """)
        print("[OK] Added internal_part_no to parts")

    conn.commit()
    cur.close()
    print("[OK] Phase 1 completed\n")

def phase2_import_excel(conn) -> Dict:
    """Phase 2: Import Excel file to staging tables."""
    print("=== PHASE 2: Import Excel to Staging ===")

    if not Path(EXCEL_FILE).exists():
        print(f"[ERROR] Excel file not found: {EXCEL_FILE}")
        return {'status': 'ERROR', 'message': 'File not found'}

    # Calculate file hash
    with open(EXCEL_FILE, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
        file_size = Path(EXCEL_FILE).stat().st_size

    print(f"File: {EXCEL_FILE}")
    print(f"Size: {file_size} bytes")
    print(f"SHA256: {file_hash}")

    # Open Excel file
    workbook = xlrd.open_workbook(EXCEL_FILE, formatting_info=False)

    cur = conn.cursor()

    # Create batch record
    cur.execute("""
        INSERT INTO import_batches (file_name, file_hash, file_size, total_sheets, imported_by, started_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id
    """, (EXCEL_FILE, file_hash, file_size, workbook.nsheets, 'claude_code'))

    batch_id = cur.fetchone()[0]
    conn.commit()

    print(f"[OK] Created import batch #{batch_id}")

    stats = {
        'batch_id': batch_id,
        'total_sheets': workbook.nsheets,
        'data_sheets': 0,
        'skipped_sheets': 0,
        'total_rows': 0,
        'valid_rows': 0,
        'failed_rows': 0,
        'sheets': {}
    }

    # Special sheets to skip or handle differently
    special_sheets = ['客户名称代号', '五金模具进度一览表']

    for sheet_idx in range(workbook.nsheets):
        sheet = workbook.sheet_by_index(sheet_idx)
        sheet_name = sheet.name

        print(f"\n[Sheet {sheet_idx + 1}/{workbook.nsheets}] {sheet_name}")

        if sheet_name in special_sheets:
            print(f"  [SKIP] Special sheet - will process separately")
            stats['skipped_sheets'] += 1
            stats['sheets'][sheet_name] = {'type': 'special', 'rows': sheet.nrows}
            continue

        if sheet.nrows < 2:
            print(f"  [SKIP] Empty sheet")
            stats['skipped_sheets'] += 1
            continue

        # Find header row (look for key columns)
        header_row_idx = None
        for row_idx in range(min(5, sheet.nrows)):
            row_values = [str(cell.value).strip() for cell in sheet.row(row_idx)]
            if any('本厂产品' in val for val in row_values):
                header_row_idx = row_idx
                break

        if header_row_idx is None:
            print(f"  [SKIP] No header row found")
            stats['skipped_sheets'] += 1
            continue

        # Parse header
        headers = [str(cell.value).strip() for cell in sheet.row(header_row_idx)]
        print(f"  Header at row {header_row_idx + 1}")

        # Map header positions
        header_map = {}
        for idx, header in enumerate(headers):
            if '本厂产品编号' in header or header == '产品编号':
                header_map['tooling_number'] = idx
            elif '本厂产品名称' in header:
                header_map['internal_name'] = idx
            elif '原图产品编号' in header or '客户产品编号' in header:
                header_map['customer_part_no'] = idx
            elif '原图产品名称' in header:
                header_map['customer_part_name'] = idx
            elif '模具类型' in header:
                header_map['mold_type'] = idx
            elif '材质' in header or header == '材料':
                header_map['material'] = idx

        sheet_stats = {'data_rows': 0, 'skipped_rows': 0, 'imported_rows': 0}

        # Process data rows
        for row_idx in range(header_row_idx + 1, sheet.nrows):
            stats['total_rows'] += 1
            row_values = [cell.value for cell in sheet.row(row_idx)]

            # Skip empty rows
            if all(str(v).strip() == '' for v in row_values):
                sheet_stats['skipped_rows'] += 1
                continue

            # Parse row data
            raw_data = {headers[i]: str(row_values[i]) if i < len(row_values) else ''
                       for i in range(len(headers))}

            # Extract key fields
            tooling_number = row_values[header_map.get('tooling_number', -1)] if 'tooling_number' in header_map else ''
            internal_name = row_values[header_map.get('internal_name', -1)] if 'internal_name' in header_map else ''
            customer_part_no = row_values[header_map.get('customer_part_no', -1)] if 'customer_part_no' in header_map else ''

            tooling_number = str(tooling_number).strip()
            internal_name = str(internal_name).strip()
            customer_part_no = str(customer_part_no).strip()

            # Skip header duplicates and template rows
            if ('本厂产品' in internal_name or '产品名称' in internal_name or
                internal_name in ['', '合计', '小计', '返回目录'] or
                tooling_number in ['', '编号']):
                sheet_stats['skipped_rows'] += 1
                continue

            # Basic validation
            validation_status = 'VALID'
            validation_errors = []

            if not tooling_number and not customer_part_no:
                validation_status = 'FAILED'
                validation_errors.append('No tooling number or customer part number')

            # Insert to staging
            cur.execute("""
                INSERT INTO excel_import_rows (
                    batch_id, source_sheet, source_row, raw_data,
                    parsed_tooling_number, parsed_internal_name, parsed_customer_part_no,
                    validation_status, validation_errors
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                batch_id, sheet_name, row_idx + 1, json.dumps(raw_data, ensure_ascii=False),
                tooling_number or None, internal_name or None, customer_part_no or None,
                validation_status, '; '.join(validation_errors) if validation_errors else None
            ))

            if validation_status == 'VALID':
                stats['valid_rows'] += 1
                sheet_stats['imported_rows'] += 1
            else:
                stats['failed_rows'] += 1

            sheet_stats['data_rows'] += 1

        stats['data_sheets'] += 1
        stats['sheets'][sheet_name] = sheet_stats
        print(f"  Data rows: {sheet_stats['data_rows']}, Imported: {sheet_stats['imported_rows']}, Skipped: {sheet_stats['skipped_rows']}")

    # Update batch statistics
    cur.execute("""
        UPDATE import_batches
        SET data_sheets = %s, total_rows = %s, valid_rows = %s, failed_rows = %s,
            status = 'STAGED', completed_at = NOW()
        WHERE id = %s
    """, (stats['data_sheets'], stats['total_rows'], stats['valid_rows'], stats['failed_rows'], batch_id))

    conn.commit()
    cur.close()

    print(f"\n[OK] Phase 2 completed")
    print(f"  Total sheets: {stats['total_sheets']}")
    print(f"  Data sheets: {stats['data_sheets']}")
    print(f"  Total rows: {stats['total_rows']}")
    print(f"  Valid rows: {stats['valid_rows']}")
    print(f"  Failed rows: {stats['failed_rows']}\n")

    return stats

def phase3_process_staging_to_production(conn, batch_id: int):
    """Phase 3: Process staging data into production tables."""
    print("=== PHASE 3: Process Staging to Production ===")

    cur = conn.cursor()

    # Get valid rows from staging
    cur.execute("""
        SELECT id, parsed_customer_part_no, parsed_internal_name, parsed_tooling_number,
               source_sheet, source_row
        FROM excel_import_rows
        WHERE batch_id = %s AND validation_status = 'VALID'
        ORDER BY id
    """, (batch_id,))

    rows = cur.fetchall()
    print(f"Processing {len(rows)} valid rows...")

    stats = {
        'customers_created': 0,
        'parts_created': 0,
        'tooling_linked': 0,
        'aliases_created': 0,
        'errors': 0
    }

    # Extract customer name from sheet name
    customer_name_map = {}

    for row_id, customer_part_no, internal_name, tooling_number, sheet_name, source_row in rows:
        try:
            # Parse customer name from sheet (e.g., "ZF产品" -> "ZF")
            customer_name = sheet_name
            if '产品' in customer_name:
                customer_name = customer_name.replace('产品', '').strip()

            # Find or create customer
            customer_id = customer_name_map.get(customer_name)
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

                customer_name_map[customer_name] = customer_id

            # Find or create part by internal_name
            if internal_name:
                cur.execute("SELECT id FROM parts WHERE internal_name = %s LIMIT 1", (internal_name,))
                result = cur.fetchone()
                if result:
                    part_id = result[0]
                else:
                    # Create new part (part_number can be customer_part_no for now)
                    part_number = customer_part_no if customer_part_no else f"P{row_id}"
                    cur.execute("""
                        INSERT INTO parts (part_number, internal_name, created_at)
                        VALUES (%s, %s, NOW())
                        RETURNING id
                    """, (part_number, internal_name))
                    part_id = cur.fetchone()[0]
                    stats['parts_created'] += 1
            else:
                part_id = None

            # Link to tooling if tooling_number exists
            tooling_id = None
            if tooling_number:
                cur.execute("SELECT id FROM tooling WHERE tooling_number = %s", (tooling_number,))
                result = cur.fetchone()
                if result:
                    tooling_id = result[0]

                    # Create tooling_parts relationship if both exist
                    if part_id:
                        cur.execute("""
                            INSERT INTO tooling_parts (tooling_id, part_id, created_at)
                            VALUES (%s, %s, NOW())
                            ON CONFLICT DO NOTHING
                        """, (tooling_id, part_id))
                        stats['tooling_linked'] += 1

            # Create part_customer_alias if we have customer and part
            if customer_id and part_id and customer_part_no:
                cur.execute("""
                    INSERT INTO part_customer_aliases (part_id, customer_name, customer_part_no, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (part_id, customer_name, customer_part_no) DO NOTHING
                """, (part_id, customer_name, customer_part_no))
                if cur.rowcount > 0:
                    stats['aliases_created'] += 1

            # Update staging row with resolved IDs
            cur.execute("""
                UPDATE excel_import_rows
                SET resolved_customer_id = %s, resolved_part_id = %s,
                    resolved_tooling_id = %s, validation_status = 'IMPORTED'
                WHERE id = %s
            """, (customer_id, part_id, tooling_id, row_id))

            conn.commit()

        except Exception as e:
            conn.rollback()
            stats['errors'] += 1
            cur.execute("""
                UPDATE excel_import_rows
                SET validation_status = 'ERROR',
                    validation_errors = %s
                WHERE id = %s
            """, (str(e), row_id))
            conn.commit()

    cur.close()

    print(f"[OK] Phase 3 completed")
    print(f"  Customers created: {stats['customers_created']}")
    print(f"  Parts created: {stats['parts_created']}")
    print(f"  Tooling links: {stats['tooling_linked']}")
    print(f"  Aliases created: {stats['aliases_created']}")
    print(f"  Errors: {stats['errors']}\n")

    return stats

def phase4_validate(conn) -> Dict:
    """Phase 4: Validate imported data."""
    print("=== PHASE 4: Validation ===")

    cur = conn.cursor()

    validation = {}

    # Check for orphaned foreign keys
    cur.execute("""
        SELECT COUNT(*) FROM parts p
        LEFT JOIN customers c ON p.customer_id = c.id
        WHERE p.customer_id IS NOT NULL AND c.id IS NULL
    """)
    validation['orphaned_parts_customer'] = cur.fetchone()[0]

    # Check for duplicate customer part numbers
    cur.execute("""
        SELECT customer_name, customer_part_no, COUNT(*)
        FROM part_customer_aliases
        GROUP BY customer_name, customer_part_no
        HAVING COUNT(*) > 1
    """)
    validation['duplicate_aliases'] = cur.fetchall()

    # Check tooling_parts relationships
    cur.execute("SELECT COUNT(*) FROM tooling_parts")
    validation['tooling_parts_count'] = cur.fetchone()[0]

    # Sample traces
    cur.execute("""
        SELECT e.source_sheet, e.source_row, e.parsed_internal_name,
               e.resolved_customer_id, e.resolved_part_id, e.resolved_tooling_id,
               p.part_number, c.name
        FROM excel_import_rows e
        LEFT JOIN parts p ON e.resolved_part_id = p.id
        LEFT JOIN customers c ON e.resolved_customer_id = c.id
        WHERE e.validation_status = 'IMPORTED'
        ORDER BY e.id
        LIMIT 10
    """)
    validation['sample_traces'] = cur.fetchall()

    cur.close()

    print(f"[OK] Validation completed")
    print(f"  Orphaned parts: {validation['orphaned_parts_customer']}")
    print(f"  Duplicate aliases: {len(validation['duplicate_aliases'])}")
    print(f"  Tooling-parts links: {validation['tooling_parts_count']}")
    print(f"  Sample traces: {len(validation['sample_traces'])}\n")

    return validation

def main():
    """Execute complete migration and import."""
    start_time = datetime.now()

    print("="*60)
    print("DATABASE MIGRATION AND EXCEL IMPORT")
    print(f"Started: {start_time}")
    print("="*60)

    try:
        # Connect
        print("\nConnecting to database...")
        conn = connect_db()
        print(f"[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}\n")

        # Initial counts
        print("=== Initial State ===")
        before_counts = get_table_counts(conn)
        for table, count in before_counts.items():
            print(f"  {table}: {count}")

        # Phase 1: Create tables
        phase1_create_missing_tables(conn)

        # Phase 2: Import Excel
        import_stats = phase2_import_excel(conn)

        # Phase 3: Process to production
        if import_stats.get('valid_rows', 0) > 0:
            process_stats = phase3_process_staging_to_production(conn, import_stats['batch_id'])
        else:
            print("[WARN] No valid rows to process")
            process_stats = {}

        # Phase 4: Validate
        validation = phase4_validate(conn)

        # Final counts
        print("=== Final State ===")
        after_counts = get_table_counts(conn)
        for table, count in after_counts.items():
            before = before_counts.get(table, 'N/A')
            print(f"  {table}: {before} -> {count}")

        conn.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "="*60)
        print(f"EXECUTION COMPLETED")
        print(f"Duration: {duration:.1f} seconds")
        print("="*60)

        # Write results
        result = {
            'status': 'COMPLETED',
            'started_at': start_time.isoformat(),
            'completed_at': end_time.isoformat(),
            'duration_seconds': duration,
            'database': f"{DB_HOST}:{DB_PORT}/{DB_NAME}",
            'before_counts': before_counts,
            'after_counts': after_counts,
            'import_stats': import_stats,
            'process_stats': process_stats,
            'validation': {
                'orphaned_parts_customer': validation.get('orphaned_parts_customer'),
                'duplicate_aliases_count': len(validation.get('duplicate_aliases', [])),
                'tooling_parts_count': validation.get('tooling_parts_count'),
                'sample_traces_count': len(validation.get('sample_traces', []))
            }
        }

        return result

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'FAILED', 'error': str(e)}

if __name__ == "__main__":
    result = main()

    # Save result
    with open('migration_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    sys.exit(0 if result.get('status') == 'COMPLETED' else 1)
