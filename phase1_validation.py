#!/usr/bin/env python3
"""
Phase 1 Validation - Comprehensive checks for authoritative schema migration
"""

import sys
import os
from pathlib import Path

# Add backend to path for model imports and config
sys.path.insert(0, str(Path(__file__).parent / "backend"))

import psycopg2
from urllib.parse import urlparse

def get_db_config():
    """Get database config from settings or environment."""
    try:
        from app.core.config import settings
        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'stamping_system',
            'user': parsed.username or 'postgres',
            'password': parsed.password or 'postgres'
        }
    except Exception as e:
        print(f"[WARNING] Could not load settings: {e}")
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/stamping_system')
        parsed = urlparse(db_url)
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'stamping_system',
            'user': parsed.username or 'postgres',
            'password': parsed.password or 'postgres'
        }

def connect_db():
    config = get_db_config()
    for attempt in range(1, 4):
        try:
            conn = psycopg2.connect(**config, connect_timeout=10)
            conn.set_session(autocommit=False)
            return conn, config
        except Exception as e:
            print(f"[ERROR] Connection attempt {attempt}/3: {e}")
            if attempt < 3:
                import time
                time.sleep(2)
            else:
                raise

def validate_orm_models():
    """Check that all ORM models can be imported."""
    print("\n[VALIDATION 1] ORM Model Imports")
    errors = []

    try:
        from app.models import (
            Customer, Part, Tooling, ToolingStep, ToolingPart,
            ToolingCustomerLink, PartCustomerAlias,
            ImportBatch, ExcelImportRow
        )
        print("  [OK] All Phase 1 models imported successfully")
        return True, []
    except Exception as e:
        errors.append(f"Model import failed: {e}")
        print(f"  [FAIL] {e}")
        return False, errors

def validate_database_structure(conn):
    """Check that database structure matches target design."""
    print("\n[VALIDATION 2] Database Structure")

    cur = conn.cursor()
    issues = []

    # Check customers table
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'customers'
        AND column_name IN ('customer_code', 'is_active', 'updated_at', 'short_name')
    """)
    customer_cols = [row[0] for row in cur.fetchall()]
    if len(customer_cols) == 4:
        print("  [OK] customers table has target columns")
    else:
        issues.append(f"customers table missing columns: expected 4, found {len(customer_cols)}")
        print(f"  [FAIL] customers table incomplete")

    # Check parts table
    cur.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'part_number'
    """)
    part_number_nullable = cur.fetchone()
    if part_number_nullable and part_number_nullable[0] == 'YES':
        print("  [OK] parts.part_number is nullable")
    else:
        issues.append("parts.part_number not nullable")
        print("  [FAIL] parts.part_number should be nullable")

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name IN ('is_deleted', 'internal_part_no')
    """)
    parts_cols = [row[0] for row in cur.fetchall()]
    if len(parts_cols) == 2:
        print("  [OK] parts table has is_deleted and internal_part_no")
    else:
        issues.append(f"parts missing columns: {2 - len(parts_cols)}")
        print(f"  [FAIL] parts table missing columns")

    # Check tooling table
    cur.execute("""
        SELECT column_name, data_type, is_nullable FROM information_schema.columns
        WHERE table_name = 'tooling' AND column_name IN (
            'tooling_number', 'is_continuous', 'cavity_count', 'process_step_count',
            'status', 'shot_count', 'is_deleted'
        )
    """)
    tooling_cols = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

    expected_tooling = ['tooling_number', 'is_continuous', 'cavity_count', 'process_step_count',
                        'status', 'shot_count', 'is_deleted']
    if all(col in tooling_cols for col in expected_tooling):
        print("  [OK] tooling table has all target columns")

        # Check is_continuous distribution
        cur.execute("SELECT is_continuous, COUNT(*) FROM tooling GROUP BY is_continuous")
        is_cont_dist = dict(cur.fetchall())
        true_count = is_cont_dist.get(True, 0)
        false_count = is_cont_dist.get(False, 0)
        if true_count > 0 and false_count > 0:
            print(f"  [OK] is_continuous correctly backfilled ({true_count} continuous, {false_count} non-continuous)")
        else:
            issues.append(f"is_continuous not properly backfilled: {is_cont_dist}")
            print(f"  [FAIL] is_continuous distribution incorrect")
    else:
        missing = [col for col in expected_tooling if col not in tooling_cols]
        issues.append(f"tooling missing columns: {missing}")
        print(f"  [FAIL] tooling table incomplete")

    # Check tooling_number NULL count
    cur.execute("SELECT COUNT(*) FROM tooling WHERE tooling_number IS NULL")
    null_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tooling")
    total_count = cur.fetchone()[0]
    if null_count > 0:
        print(f"  [INFO] tooling_number has {null_count}/{total_count} NULL (compatibility period, Phase 2 will resolve)")
    else:
        print(f"  [OK] All tooling rows have tooling_number")

    # Check excel_import_rows has parsed_is_continuous and parsed_position
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'excel_import_rows'
        AND column_name IN ('parsed_is_continuous', 'parsed_position')
    """)
    parsed_cols = [row[0] for row in cur.fetchall()]
    if len(parsed_cols) == 2:
        print("  [OK] excel_import_rows has parsed_is_continuous and parsed_position")
    else:
        issues.append(f"excel_import_rows missing parsed columns: {2 - len(parsed_cols)}")
        print(f"  [FAIL] excel_import_rows missing parsed fields")

    # Check relationship tables exist
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name IN ('tooling_steps', 'tooling_customer_links')
    """)
    if cur.fetchone()[0] == 2:
        print("  [OK] tooling_steps and tooling_customer_links tables exist")
    else:
        issues.append("relationship tables missing")
        print("  [FAIL] relationship tables incomplete")

    # Check part_customer_aliases structure
    cur.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'part_customer_aliases' AND column_name = 'customer_id'
    """)
    result = cur.fetchone()
    if result and result[0] == 'NO':
        print("  [OK] part_customer_aliases.customer_id is NOT NULL")
    else:
        issues.append("part_customer_aliases.customer_id should be NOT NULL")
        print("  [FAIL] part_customer_aliases.customer_id nullable")

    # Check part_customer_aliases unique constraint
    cur.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'part_customer_aliases'
        AND indexname = 'idx_part_customer_alias_unique'
    """)
    if cur.fetchone():
        print("  [OK] part_customer_aliases has target unique constraint")
    else:
        issues.append("part_customer_aliases missing idx_part_customer_alias_unique")
        print("  [FAIL] part_customer_aliases unique constraint missing")

    # Check tooling_parts NOT NULL and unique constraint
    cur.execute("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'tooling_parts' AND column_name IN ('tooling_id', 'part_id')
    """)
    tooling_parts_nullable = [row[0] for row in cur.fetchall()]
    if all(n == 'NO' for n in tooling_parts_nullable):
        print("  [OK] tooling_parts.tooling_id and part_id are NOT NULL")
    else:
        issues.append("tooling_parts tooling_id/part_id should be NOT NULL")
        print("  [FAIL] tooling_parts NOT NULL constraints missing")

    cur.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'tooling_parts' AND indexname = 'idx_tooling_parts_unique'
    """)
    if cur.fetchone():
        print("  [OK] tooling_parts has target unique constraint")
    else:
        issues.append("tooling_parts missing idx_tooling_parts_unique")
        print("  [FAIL] tooling_parts unique constraint missing")

    cur.close()
    return len(issues) == 0, issues

def validate_constraints(conn):
    """Check foreign keys and unique constraints."""
    print("\n[VALIDATION 3] Constraints and Indexes")

    cur = conn.cursor()
    issues = []

    # Check tooling_number unique index
    cur.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'tooling' AND indexname = 'idx_tooling_number'
    """)
    if cur.fetchone():
        print("  [OK] tooling.tooling_number unique index exists")
    else:
        issues.append("idx_tooling_number missing")
        print("  [FAIL] idx_tooling_number missing")

    # Check foreign keys on tooling_parts
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.table_constraints
        WHERE table_name = 'tooling_parts' AND constraint_type = 'FOREIGN KEY'
    """)
    fk_count = cur.fetchone()[0]
    if fk_count >= 2:
        print(f"  [OK] tooling_parts has {fk_count} foreign keys")
    else:
        issues.append(f"tooling_parts has only {fk_count} foreign keys")
        print(f"  [FAIL] tooling_parts foreign keys incomplete")

    # Check orphans
    cur.execute("""
        SELECT COUNT(*) FROM tooling_parts tp
        LEFT JOIN tooling t ON tp.tooling_id = t.id
        WHERE t.id IS NULL
    """)
    orphan_tooling = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM tooling_parts tp
        LEFT JOIN parts p ON tp.part_id = p.id
        WHERE p.id IS NULL
    """)
    orphan_parts = cur.fetchone()[0]

    if orphan_tooling == 0 and orphan_parts == 0:
        print("  [OK] No orphan records in tooling_parts")
    else:
        issues.append(f"Orphan records: {orphan_tooling} tooling, {orphan_parts} parts")
        print(f"  [FAIL] Orphan records found")

    cur.close()
    return len(issues) == 0, issues

def main():
    print("="*70)
    print("PHASE 1 COMPREHENSIVE VALIDATION")
    print("="*70)

    from datetime import datetime
    start_time = datetime.now()
    all_passed = True

    # Test 1: ORM models
    orm_passed, orm_errors = validate_orm_models()
    all_passed = all_passed and orm_passed

    # Test 2 & 3: Database structure
    try:
        conn, config = connect_db()
        print(f"\n[OK] Connected to {config['host']}:{config['port']}/{config['database']}")

        db_passed, db_issues = validate_database_structure(conn)
        all_passed = all_passed and db_passed

        constraint_passed, constraint_issues = validate_constraints(conn)
        all_passed = all_passed and constraint_passed

        conn.close()
    except Exception as e:
        print(f"\n[FAIL] Database validation error: {e}")
        all_passed = False

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print(f"Duration: {duration:.1f}s")
    print(f"Result: {'PASSED' if all_passed else 'FAILED'}")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
