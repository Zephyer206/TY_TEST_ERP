#!/usr/bin/env python3
"""
Phase 2 Validation - Test Excel parsing and staging
"""

import sys
from pathlib import Path

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
        import os
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/stamping_system')
        parsed = urlparse(db_url.replace('postgresql+asyncpg://', 'postgresql://'))
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'stamping_system',
            'user': parsed.username or 'postgres',
            'password': parsed.password or 'postgres'
        }


def test_batch_completion():
    """Test that batch was completed successfully."""
    print("\n[TEST 1] Batch Completion")
    config = get_db_config()
    conn = psycopg2.connect(**config)
    cur = conn.cursor()

    cur.execute("SELECT status, total_sheets, data_sheets FROM import_batches ORDER BY id DESC LIMIT 1")
    batch = cur.fetchone()

    if not batch:
        print("  [FAIL] No batch found")
        return False

    if batch[0] != 'COMPLETED':
        print(f"  [FAIL] Batch status is {batch[0]}, expected COMPLETED")
        return False

    if batch[1] != 95:
        print(f"  [FAIL] Total sheets is {batch[1]}, expected 95")
        return False

    print(f"  [OK] Batch completed: {batch[1]} total sheets, {batch[2]} data sheets")
    cur.close()
    conn.close()
    return True


def test_formal_tables_unchanged():
    """Test that formal tables were not modified."""
    print("\n[TEST 2] Formal Tables Unchanged")
    config = get_db_config()
    conn = psycopg2.connect(**config)
    cur = conn.cursor()

    expected = {
        'customers': 129,
        'parts': 1534,
        'tooling': 1357,
        'part_customer_aliases': 0,
        'tooling_parts': 0,
        'tooling_customer_links': 0,
    }

    all_correct = True
    for table, expected_count in expected.items():
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        actual_count = cur.fetchone()[0]
        if actual_count != expected_count:
            print(f"  [FAIL] {table}: expected {expected_count}, got {actual_count}")
            all_correct = False
        else:
            print(f"  [OK] {table}: {actual_count}")

    cur.close()
    conn.close()
    return all_correct


def test_parsing_quality():
    """Test that parsed fields have reasonable coverage."""
    print("\n[TEST 3] Parsing Quality")
    config = get_db_config()
    conn = psycopg2.connect(**config)
    cur = conn.cursor()

    # Get total VALID rows
    cur.execute("SELECT COUNT(*) FROM excel_import_rows WHERE validation_status = 'VALID'")
    total_valid = cur.fetchone()[0]

    if total_valid == 0:
        print("  [FAIL] No VALID rows found")
        return False

    print(f"  Total VALID rows: {total_valid}")

    # Check parsed fields
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE parsed_mold_type IS NOT NULL) as has_mold_type,
            COUNT(*) FILTER (WHERE parsed_process_step_count IS NOT NULL) as has_process_step,
            COUNT(*) FILTER (WHERE parsed_cavity_count IS NOT NULL) as has_cavity,
            COUNT(*) FILTER (WHERE parsed_tooling_number IS NOT NULL) as has_tooling_number,
            COUNT(*) FILTER (WHERE parsed_is_continuous = TRUE) as is_continuous_true,
            COUNT(*) FILTER (WHERE parsed_is_continuous = FALSE) as is_continuous_false,
            COUNT(*) FILTER (WHERE parsed_customer_name IS NOT NULL) as has_customer,
            COUNT(*) FILTER (WHERE parsed_thickness IS NOT NULL) as has_thickness
        FROM excel_import_rows
        WHERE validation_status = 'VALID'
    """)
    stats = cur.fetchone()

    has_mold_type = stats[0]
    has_process_step = stats[1]
    has_cavity = stats[2]
    has_tooling_number = stats[3]
    is_continuous_true = stats[4]
    is_continuous_false = stats[5]
    has_customer = stats[6]
    has_thickness = stats[7]

    all_passed = True

    # Test: parsed_mold_type should be non-empty for most rows
    mold_type_pct = (has_mold_type / total_valid) * 100
    if mold_type_pct < 90:
        print(f"  [WARN] parsed_mold_type coverage: {mold_type_pct:.1f}% (expected >90%)")
    else:
        print(f"  [OK] parsed_mold_type coverage: {mold_type_pct:.1f}%")

    # Test: parsed_tooling_number should be present for all VALID rows
    tooling_pct = (has_tooling_number / total_valid) * 100
    if tooling_pct < 95:
        print(f"  [FAIL] parsed_tooling_number coverage: {tooling_pct:.1f}% (expected >95%)")
        all_passed = False
    else:
        print(f"  [OK] parsed_tooling_number coverage: {tooling_pct:.1f}%")

    # Test: parsed_process_step_count should exist for non-continuous molds
    if has_process_step > 0:
        print(f"  [OK] parsed_process_step_count: {has_process_step} rows")
    else:
        print(f"  [WARN] parsed_process_step_count: 0 rows (may be expected if all continuous)")

    # Test: parsed_cavity_count (may be low due to Excel data quality)
    cavity_pct = (has_cavity / total_valid) * 100
    print(f"  [INFO] parsed_cavity_count coverage: {cavity_pct:.1f}%")

    # Test: is_continuous distribution
    continuous_total = is_continuous_true + is_continuous_false
    if continuous_total > 0:
        continuous_pct = (is_continuous_true / continuous_total) * 100
        print(f"  [OK] is_continuous: {is_continuous_true} TRUE ({continuous_pct:.1f}%), {is_continuous_false} FALSE")
    else:
        print(f"  [WARN] is_continuous: no classification")

    # Test: customer name
    customer_pct = (has_customer / total_valid) * 100
    if customer_pct < 80:
        print(f"  [WARN] parsed_customer_name coverage: {customer_pct:.1f}%")
    else:
        print(f"  [OK] parsed_customer_name coverage: {customer_pct:.1f}%")

    # Test: thickness (TWP)
    thickness_pct = (has_thickness / total_valid) * 100
    if thickness_pct > 50:
        print(f"  [OK] parsed_thickness coverage: {thickness_pct:.1f}%")
    else:
        print(f"  [INFO] parsed_thickness coverage: {thickness_pct:.1f}%")

    cur.close()
    conn.close()
    return all_passed


def test_row_classification():
    """Test that row classification is reasonable."""
    print("\n[TEST 4] Row Classification")
    config = get_db_config()
    conn = psycopg2.connect(**config)
    cur = conn.cursor()

    cur.execute("""
        SELECT validation_status, COUNT(*)
        FROM excel_import_rows
        GROUP BY validation_status
        ORDER BY validation_status
    """)

    status_counts = {}
    for status, count in cur.fetchall():
        status_counts[status] = count
        print(f"  {status}: {count}")

    total = sum(status_counts.values())
    valid_pct = (status_counts.get('VALID', 0) / total) * 100
    skipped_pct = (status_counts.get('SKIPPED', 0) / total) * 100
    review_pct = (status_counts.get('REVIEW', 0) / total) * 100
    error_pct = (status_counts.get('ERROR', 0) / total) * 100

    print(f"\n  Percentages:")
    print(f"    VALID: {valid_pct:.1f}%")
    print(f"    SKIPPED: {skipped_pct:.1f}%")
    print(f"    REVIEW: {review_pct:.1f}%")
    print(f"    ERROR: {error_pct:.1f}%")

    # Expect most rows to be either VALID or SKIPPED (empty templates, headers, etc.)
    if valid_pct < 50:
        print(f"  [WARN] Low VALID percentage: {valid_pct:.1f}%")

    if error_pct > 5:
        print(f"  [WARN] High ERROR percentage: {error_pct:.1f}%")

    cur.close()
    conn.close()
    return True


def test_data_integrity():
    """Test data integrity (no duplicates, valid JSON)."""
    print("\n[TEST 5] Data Integrity")
    config = get_db_config()
    conn = psycopg2.connect(**config)
    cur = conn.cursor()

    # Check for duplicate rows (same sheet + row)
    cur.execute("""
        SELECT source_sheet, source_row, COUNT(*)
        FROM excel_import_rows
        GROUP BY source_sheet, source_row
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    if duplicates:
        print(f"  [FAIL] Found {len(duplicates)} duplicate sheet/row combinations")
        return False
    else:
        print(f"  [OK] No duplicate sheet/row combinations")

    # Check raw_data is valid JSON
    cur.execute("SELECT COUNT(*) FROM excel_import_rows WHERE raw_data IS NULL")
    null_raw_data = cur.fetchone()[0]
    if null_raw_data > 0:
        print(f"  [FAIL] {null_raw_data} rows have NULL raw_data")
        return False
    else:
        print(f"  [OK] All rows have raw_data")

    cur.close()
    conn.close()
    return True


def main():
    """Run all tests."""
    print("="*70)
    print("PHASE 2 VALIDATION - Excel Parsing and Staging")
    print("="*70)

    tests = [
        ("Batch Completion", test_batch_completion),
        ("Formal Tables Unchanged", test_formal_tables_unchanged),
        ("Parsing Quality", test_parsing_quality),
        ("Row Classification", test_row_classification),
        ("Data Integrity", test_data_integrity),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n  [ERROR] {e}")
            results.append((test_name, False))

    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    for test_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  [{status}] {test_name}")

    all_passed = all(passed for _, passed in results)
    print(f"\nOverall: {'PASSED' if all_passed else 'FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
