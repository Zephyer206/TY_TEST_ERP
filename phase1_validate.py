#!/usr/bin/env python3
"""
Phase 1 Validation - Check ORM models can be imported and database structure is correct
"""

import sys
import psycopg2
from datetime import datetime

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
        from backend.app.models.customer import Customer
        print("  [OK] Customer model")
    except Exception as e:
        errors.append(f"Customer: {e}")
        print(f"  [FAIL] Customer model: {e}")

    try:
        from backend.app.models.part import Part
        print("  [OK] Part model")
    except Exception as e:
        errors.append(f"Part: {e}")
        print(f"  [FAIL] Part model: {e}")

    try:
        from backend.app.models.tooling import Tooling, ToolingPart
        print("  [OK] Tooling, ToolingPart models")
    except Exception as e:
        errors.append(f"Tooling: {e}")
        print(f"  [FAIL] Tooling models: {e}")

    try:
        from backend.app.models.tooling_step import ToolingStep
        print("  [OK] ToolingStep model")
    except Exception as e:
        errors.append(f"ToolingStep: {e}")
        print(f"  [FAIL] ToolingStep model: {e}")

    try:
        from backend.app.models.tooling_customer_link import ToolingCustomerLink
        print("  [OK] ToolingCustomerLink model")
    except Exception as e:
        errors.append(f"ToolingCustomerLink: {e}")
        print(f"  [FAIL] ToolingCustomerLink model: {e}")

    try:
        from backend.app.models.part_customer_alias import PartCustomerAlias
        print("  [OK] PartCustomerAlias model")
    except Exception as e:
        errors.append(f"PartCustomerAlias: {e}")
        print(f"  [FAIL] PartCustomerAlias model: {e}")

    try:
        from backend.app.models.excel_import import ImportBatch, ExcelImportRow
        print("  [OK] ImportBatch, ExcelImportRow models")
    except Exception as e:
        errors.append(f"ExcelImport: {e}")
        print(f"  [FAIL] ExcelImport models: {e}")

    return len(errors) == 0, errors

def validate_database_structure(conn):
    """Check that database structure matches target design."""
    print("\n[VALIDATION 2] Database Structure")

    cur = conn.cursor()
    issues = []

    # Check customers table
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'customers' AND column_name IN ('customer_code', 'is_active', 'updated_at')
        ORDER BY column_name
    """)
    customer_cols = cur.fetchall()
    if len(customer_cols) == 3:
        print("  [OK] customers table has target columns")
    else:
        issues.append(f"customers table missing columns, found: {customer_cols}")
        print(f"  [FAIL] customers table structure incomplete")

    # Check parts table
    cur.execute("""
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name IN ('part_number', 'internal_part_no', 'is_deleted')
    """)
    part_cols = {row[0]: row[1] for row in cur.fetchall()}
    if 'part_number' in part_cols and part_cols['part_number'] == 'YES':
        print("  [OK] parts.part_number is nullable")
    else:
        issues.append("parts.part_number not nullable")
        print("  [FAIL] parts.part_number should be nullable")

    if 'is_deleted' in part_cols:
        print("  [OK] parts.is_deleted exists")
    else:
        issues.append("parts.is_deleted missing")
        print("  [FAIL] parts.is_deleted missing")

    # Check tooling table
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'tooling' AND column_name IN (
            'tooling_number', 'is_continuous', 'cavity_count', 'process_step_count',
            'status', 'shot_count', 'is_deleted'
        )
    """)
    tooling_cols = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

    expected_tooling = {
        'tooling_number': ('character varying', 'YES'),
        'is_continuous': ('boolean', 'NO'),
        'cavity_count': ('integer', 'NO'),
        'process_step_count': ('integer', 'YES'),
        'status': ('character varying', 'NO'),
        'shot_count': ('bigint', 'NO'),
        'is_deleted': ('boolean', 'NO')
    }

    for col, (expected_type, expected_nullable) in expected_tooling.items():
        if col not in tooling_cols:
            issues.append(f"tooling.{col} missing")
            print(f"  [FAIL] tooling.{col} missing")
        else:
            actual_type, actual_nullable = tooling_cols[col]
            if actual_nullable != expected_nullable:
                issues.append(f"tooling.{col} nullable mismatch")
                print(f"  [FAIL] tooling.{col} nullable={actual_nullable}, expected={expected_nullable}")

    if all(col in tooling_cols for col in expected_tooling.keys()):
        print("  [OK] tooling table has all target columns")

    # Check tooling_steps table exists
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'tooling_steps'")
    if cur.fetchone()[0] == 1:
        print("  [OK] tooling_steps table exists")
    else:
        issues.append("tooling_steps table missing")
        print("  [FAIL] tooling_steps table missing")

    # Check tooling_customer_links table
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'tooling_customer_links'")
    if cur.fetchone()[0] == 1:
        print("  [OK] tooling_customer_links table exists")
    else:
        issues.append("tooling_customer_links table missing")
        print("  [FAIL] tooling_customer_links table missing")

    # Check part_customer_aliases has customer_id FK
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'part_customer_aliases' AND column_name IN ('customer_id', 'revision')
    """)
    alias_cols = [row[0] for row in cur.fetchall()]
    if 'customer_id' in alias_cols and 'revision' in alias_cols:
        print("  [OK] part_customer_aliases has target columns")
    else:
        issues.append(f"part_customer_aliases missing columns, has: {alias_cols}")
        print(f"  [FAIL] part_customer_aliases structure incomplete")

    # Check import staging tables
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('import_batches', 'excel_import_rows')")
    if cur.fetchone()[0] == 2:
        print("  [OK] import staging tables exist")
    else:
        issues.append("import staging tables incomplete")
        print("  [FAIL] import staging tables incomplete")

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

    cur.close()
    return len(issues) == 0, issues

def main():
    print("="*70)
    print("PHASE 1 VALIDATION")
    print("="*70)

    start_time = datetime.now()
    all_passed = True

    # Test 1: ORM models
    orm_passed, orm_errors = validate_orm_models()
    all_passed = all_passed and orm_passed

    # Test 2 & 3: Database structure
    try:
        conn = connect_db()
        print(f"\n[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}")

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
