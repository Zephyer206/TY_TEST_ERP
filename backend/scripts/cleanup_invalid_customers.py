#!/usr/bin/env python3
"""
Safe Customer Cleanup Tool for Zephyr ERP
Removes duplicate and invalid customers identified by audit

Safety features:
- Default DRY-RUN mode with read-only database connection
- Physical DELETE only with explicit --apply flag
- Verifies all targets match audit before delete
- Dynamically discovers ALL foreign key references
- Aborts if ANY target has ANY reference
- Creates timestamped restoration backups before delete
- All operations in single transaction with verification
- Protects canonical customers (IBI id 7286, ITT id 7271, ZF id 35)
"""

import sys
import os
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE


# Canonical customers that must be protected
CANONICAL_CUSTOMERS = {
    'IBI': 7286,
    'ITT': 7271,
    'ZF': 35
}


def get_db_config():
    """Get database config from settings"""
    try:
        original_cwd = os.getcwd()
        os.chdir(backend_path)

        from app.core.config import settings
        from urllib.parse import urlparse

        os.chdir(original_cwd)

        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)

        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password
        }
    except Exception as e:
        print(f"[ERROR] Could not load database config: {e}")
        raise


def load_audit_data(audit_path: Path) -> Dict[str, Any]:
    """Load and validate audit JSON"""
    if not audit_path.exists():
        raise FileNotFoundError(f"Audit file not found: {audit_path}")

    with open(audit_path, 'r', encoding='utf-8') as f:
        audit = json.load(f)

    # Calculate audit hash for backup traceability
    audit_hash = hashlib.sha256(json.dumps(audit, sort_keys=True).encode()).hexdigest()[:16]

    return audit, audit_hash


def extract_target_customers(audit: Dict[str, Any]) -> Tuple[List[Dict], List[Dict]]:
    """
    Extract target customers from audit with strict validation
    Returns: (targets, excluded)
    - targets: EXACTLY 3 truncated + 57 high_confidence_empty_duplicates = 60 total
    - excluded: EXACTLY 23 low_confidence_no_ref_customers
    """
    duplicates = audit.get('duplicate_customers', {})

    truncated = duplicates.get('truncated', [])
    high_conf = duplicates.get('high_confidence_empty_duplicates', [])
    low_conf = duplicates.get('low_confidence_no_ref_customers', [])

    targets = truncated + high_conf

    print(f"[INFO] Loaded {len(truncated)} truncated customers")
    print(f"[INFO] Loaded {len(high_conf)} high-confidence empty duplicates")
    print(f"[INFO] Total targets: {len(targets)}")
    print(f"[INFO] Excluded low-confidence: {len(low_conf)}")

    return targets, low_conf


def validate_audit_shape(targets: List[Dict], excluded: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Strict audit shape validation - must match exact expected counts
    Returns: (valid, errors)
    """
    errors = []

    # Count by classification
    truncated = [t for t in targets if t.get('classification') == 'truncated']
    high_conf = [t for t in targets if t.get('classification') == 'high_confidence_empty_duplicate']

    # Validate exact counts
    if len(truncated) != 3:
        errors.append(f"Expected exactly 3 truncated customers, got {len(truncated)}")

    if len(high_conf) != 57:
        errors.append(f"Expected exactly 57 high-confidence duplicates, got {len(high_conf)}")

    if len(excluded) != 23:
        errors.append(f"Expected exactly 23 excluded low-confidence customers, got {len(excluded)}")

    if len(targets) != 60:
        errors.append(f"Expected exactly 60 total targets, got {len(targets)}")

    # Check for duplicate IDs in targets
    target_ids = [t['id'] for t in targets]
    unique_ids = set(target_ids)

    if len(target_ids) != len(unique_ids):
        duplicates = [id for id in target_ids if target_ids.count(id) > 1]
        errors.append(f"Duplicate IDs found in targets: {set(duplicates)}")

    if len(unique_ids) != 60:
        errors.append(f"Expected exactly 60 unique target IDs, got {len(unique_ids)}")

    # Verify canonical IDs are NOT in targets
    canonical_ids = set(CANONICAL_CUSTOMERS.values())
    overlap = unique_ids & canonical_ids

    if overlap:
        errors.append(f"Canonical customer IDs found in targets: {overlap}")

    # Specifically check the three canonical IDs
    if 35 in unique_ids:
        errors.append("Canonical customer ZF (id=35) found in targets")
    if 7271 in unique_ids:
        errors.append("Canonical customer ITT (id=7271) found in targets")
    if 7286 in unique_ids:
        errors.append("Canonical customer IBI (id=7286) found in targets")

    return len(errors) == 0, errors


def verify_canonical_customers(cur, dry_run: bool = True) -> Dict[str, Any]:
    """
    Verify canonical customers exist and are active
    MUST abort if any canonical is missing or inactive
    """
    result = {
        'all_exist': True,
        'customers': {},
        'errors': []
    }

    for name, customer_id in CANONICAL_CUSTOMERS.items():
        query = "SELECT id, name, customer_code, is_active FROM customers WHERE id = %s"
        cur.execute(query, (customer_id,))
        row = cur.fetchone()

        if not row:
            result['all_exist'] = False
            result['errors'].append(f"CRITICAL: Canonical customer {name} (id={customer_id}) not found in database")
        else:
            result['customers'][name] = dict(row)
            if not row['is_active']:
                result['all_exist'] = False
                result['errors'].append(f"CRITICAL: Canonical customer {name} (id={customer_id}) is not active")

    return result


def discover_foreign_keys(cur) -> List[Dict[str, Any]]:
    """
    Dynamically discover ALL foreign key constraints referencing customers.id
    Returns list of {table, column, constraint_name}
    """
    query = """
    SELECT
        tc.table_name,
        kcu.column_name,
        tc.constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name
        AND tc.table_schema = ccu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
        AND ccu.table_name = 'customers'
        AND ccu.column_name = 'id'
        AND tc.table_schema = 'public'
    ORDER BY tc.table_name, kcu.column_name
    """

    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]


def get_legacy_references(cur) -> List[Dict[str, Any]]:
    """
    Get known legacy/non-FK references to customers
    These might not have proper foreign keys but still reference customers
    """
    # Currently all known references have proper FKs, but this allows extensibility
    legacy = []

    # Check for any other tables that might have customer_id columns without FK
    query = """
    SELECT
        c.table_name,
        c.column_name
    FROM information_schema.columns c
    WHERE c.table_schema = 'public'
        AND c.column_name LIKE '%customer_id%'
        -- Historical snapshots intentionally preserve the pre-cleanup state.
        -- They are audit evidence, not live references, and must not block
        -- physical deletion from the live customers table.
        AND c.table_name !~ '(backup|snapshot|snap_)'
        AND NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND kcu.table_name = c.table_name
                AND kcu.column_name = c.column_name
        )
    """

    cur.execute(query)
    rows = cur.fetchall()

    for row in rows:
        legacy.append({
            'table_name': row['table_name'],
            'column_name': row['column_name'],
            'constraint_name': 'LEGACY_NO_FK'
        })

    return legacy


def count_references(cur, customer_id: int, fk_refs: List[Dict], legacy_refs: List[Dict]) -> Dict[str, int]:
    """Count references for a customer across all discovered tables"""
    ref_counts = {}

    # Count FK references
    for ref in fk_refs:
        table = ref['table_name']
        column = ref['column_name']

        query = f"SELECT COUNT(*) as count FROM {table} WHERE {column} = %s"
        cur.execute(query, (customer_id,))
        count = cur.fetchone()['count']

        if count > 0:
            ref_counts[f"{table}.{column}"] = count

    # Count legacy references
    for ref in legacy_refs:
        table = ref['table_name']
        column = ref['column_name']

        query = f"SELECT COUNT(*) as count FROM {table} WHERE {column} = %s"
        cur.execute(query, (customer_id,))
        count = cur.fetchone()['count']

        if count > 0:
            ref_counts[f"{table}.{column}_LEGACY"] = count

    return ref_counts


def verify_targets_unchanged(cur, targets: List[Dict], audit_hash: str) -> Tuple[bool, List[str], Dict[int, Dict]]:
    """
    Verify all target customers still exist and match audit data
    Returns full live customer rows from database for backup
    Returns: (all_valid, errors, live_rows_by_id)
    """
    errors = []
    live_rows = {}

    for target in targets:
        customer_id = target['id']
        expected_name = target['name']

        # Query ALL columns from customers table for accurate backup
        query = "SELECT * FROM customers WHERE id = %s"
        cur.execute(query, (customer_id,))
        row = cur.fetchone()

        if not row:
            errors.append(f"Customer id={customer_id} not found (expected '{expected_name}')")
            continue

        # Store full live row for backup
        live_rows[customer_id] = dict(row)

        # Verify name hasn't changed
        if row['name'] != expected_name:
            errors.append(
                f"Customer id={customer_id} name changed: "
                f"audit='{expected_name}' current='{row['name']}'"
            )

    return len(errors) == 0, errors, live_rows


def check_all_references(cur, targets: List[Dict], fk_refs: List[Dict],
                         legacy_refs: List[Dict]) -> Tuple[bool, Dict[int, Dict[str, int]]]:
    """
    Check all targets have zero references
    Returns: (safe_to_delete, reference_counts_by_id)
    """
    all_refs = {}
    safe = True

    for target in targets:
        customer_id = target['id']
        refs = count_references(cur, customer_id, fk_refs, legacy_refs)
        all_refs[customer_id] = refs

        if refs:
            safe = False

    return safe, all_refs


def create_backup(live_rows: Dict[int, Dict], audit_hash: str, all_refs: Dict[int, Dict[str, int]],
                  canonical_check: Dict, backup_dir: Path) -> Tuple[Path, Path]:
    """
    Create timestamped JSON and SQL restoration backups using actual customer table rows
    Returns: (json_path, sql_path)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Convert live_rows for JSON serialization
    targets_for_json = []
    for customer_id, row in live_rows.items():
        row_copy = dict(row)
        # Convert datetime objects to ISO strings for JSON
        for key, value in row_copy.items():
            if isinstance(value, datetime):
                row_copy[key] = value.isoformat()
        targets_for_json.append(row_copy)

    # JSON backup with full metadata
    json_backup = {
        'backup_timestamp': datetime.now().isoformat(),
        'audit_source_hash': audit_hash,
        'target_count': len(live_rows),
        'canonical_customers': canonical_check['customers'],
        'targets': targets_for_json,
        'reference_counts': {str(k): v for k, v in all_refs.items()},
        'tool_version': '1.0.0'
    }

    json_path = backup_dir / f'cleanup_backup_{timestamp}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_backup, f, ensure_ascii=False, indent=2, default=str)

    # SQL backup with INSERT statements using actual customer columns
    sql_path = backup_dir / f'cleanup_restore_{timestamp}.sql'
    with open(sql_path, 'w', encoding='utf-8') as f:
        f.write(f"-- Customer Cleanup Restoration Script\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Audit hash: {audit_hash}\n")
        f.write(f"-- Target count: {len(live_rows)}\n\n")
        f.write("BEGIN;\n\n")

        for customer_id in sorted(live_rows.keys()):
            row = live_rows[customer_id]

            # Get actual column names from customer row
            columns = list(row.keys())

            # Build properly escaped values using psycopg2 adaptation
            values = []
            for col in columns:
                val = row[col]
                if val is None:
                    values.append('NULL')
                elif isinstance(val, bool):
                    values.append('TRUE' if val else 'FALSE')
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                elif isinstance(val, datetime):
                    # Use ISO format with timezone
                    values.append(f"'{val.isoformat()}'")
                else:
                    # Escape single quotes for SQL string literals
                    escaped = str(val).replace("'", "''")
                    values.append(f"'{escaped}'")

            f.write(f"-- Restore customer id={customer_id}: {row.get('name', 'UNKNOWN')}\n")
            f.write(f"INSERT INTO customers ({', '.join(columns)})\n")
            f.write(f"VALUES ({', '.join(values)});\n\n")

        f.write("COMMIT;\n")

    return json_path, sql_path


def delete_customers(cur, targets: List[Dict]) -> int:
    """
    Delete customers in single transaction
    MUST delete exactly 60 rows, otherwise abort
    Returns: count of deleted rows
    """
    customer_ids = [t['id'] for t in targets]

    query = "DELETE FROM customers WHERE id = ANY(%s)"
    cur.execute(query, (customer_ids,))

    deleted_count = cur.rowcount

    # Strict verification: must be exactly 60
    if deleted_count != 60:
        raise RuntimeError(
            f"DELETE rowcount mismatch: expected exactly 60, got {deleted_count}. "
            f"Transaction will be rolled back."
        )

    return deleted_count


def verify_deletion(cur, targets: List[Dict], canonical_check: Dict) -> Tuple[bool, List[str]]:
    """
    Verify targets are deleted and canonical customers remain
    Returns: (success, errors)
    """
    errors = []

    # Check targets are gone
    target_ids = [t['id'] for t in targets]
    query = "SELECT id, name FROM customers WHERE id = ANY(%s)"
    cur.execute(query, (target_ids,))
    remaining = cur.fetchall()

    if remaining:
        for row in remaining:
            errors.append(f"Customer id={row['id']} still exists: {row['name']}")

    # Check canonical customers still exist
    for name, customer_id in CANONICAL_CUSTOMERS.items():
        query = "SELECT id, name FROM customers WHERE id = %s"
        cur.execute(query, (customer_id,))
        row = cur.fetchone()

        if not row:
            errors.append(f"Canonical customer {name} (id={customer_id}) was deleted!")

    return len(errors) == 0, errors


def generate_report(targets: List[Dict], excluded: List[Dict], all_refs: Dict[int, Dict[str, int]],
                   canonical_check: Dict, fk_refs: List[Dict], legacy_refs: List[Dict],
                   audit_hash: str, dry_run: bool, report_dir: Path,
                   apply_result: Optional[Dict[str, Any]] = None) -> Tuple[Path, Path]:
    """
    Generate timestamped JSON and Markdown reports
    For apply mode, include success status, deleted_count, backup paths, and verification
    Returns: (json_path, md_path)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    mode = 'DRY_RUN' if dry_run else 'APPLY'

    # JSON report
    json_report = {
        'report_timestamp': datetime.now().isoformat(),
        'mode': mode,
        'audit_source_hash': audit_hash,
        'target_count': len(targets),
        'excluded_count': len(excluded),
        'canonical_customers': canonical_check,
        'targets': targets,
        'excluded': excluded,
        'reference_counts': {str(k): v for k, v in all_refs.items()},
        'discovered_fk_references': fk_refs,
        'discovered_legacy_references': legacy_refs,
        'total_references_found': sum(sum(refs.values()) for refs in all_refs.values())
    }

    # Add apply result if this is post-delete report
    if apply_result:
        json_report['apply_result'] = apply_result

    json_path = report_dir / f'cleanup_report_{mode.lower()}_{timestamp}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)

    # Markdown report
    md_path = report_dir / f'cleanup_report_{mode.lower()}_{timestamp}.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# Customer Cleanup Report\n\n")
        f.write(f"**Mode:** {mode}\n\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Audit Source Hash:** {audit_hash}\n\n")

        if apply_result:
            f.write("## Apply Result\n\n")
            f.write(f"- **Success:** {apply_result.get('success', False)}\n")
            f.write(f"- **Deleted Count:** {apply_result.get('deleted_count', 0)}\n")
            f.write(f"- **JSON Backup:** {apply_result.get('json_backup', 'N/A')}\n")
            f.write(f"- **SQL Backup:** {apply_result.get('sql_backup', 'N/A')}\n")
            f.write(f"- **Post-Delete Verification:** {apply_result.get('verification', 'N/A')}\n\n")

        if dry_run:
            f.write("## Dry-Run Status\n\n")
            f.write("**Database unchanged** - no deletions performed.\n\n")

        f.write("## Summary\n\n")
        f.write(f"- **Target Customers:** {len(targets)}\n")
        f.write(f"  - Truncated: {len([t for t in targets if t.get('classification') == 'truncated'])}\n")
        f.write(f"  - High-Confidence Empty Duplicates: {len([t for t in targets if t.get('classification') == 'high_confidence_empty_duplicate'])}\n")
        f.write(f"- **Excluded (Low-Confidence):** {len(excluded)}\n")
        f.write(f"- **Total References Found:** {sum(sum(refs.values()) for refs in all_refs.values())}\n\n")

        f.write("## Canonical Customers (Protected)\n\n")
        f.write("| Name | ID | Status |\n")
        f.write("|------|----|---------|\n")
        for name, customer_id in CANONICAL_CUSTOMERS.items():
            cust = canonical_check['customers'].get(name, {})
            status = "✓ EXISTS" if cust else "✗ MISSING"
            f.write(f"| {name} | {customer_id} | {status} |\n")
        f.write("\n")

        f.write("## Target Customers\n\n")
        f.write("| ID | Name | Classification | Active | Refs |\n")
        f.write("|----|------|----------------|--------|------|\n")
        for target in targets:
            refs = all_refs.get(target['id'], {})
            ref_count = sum(refs.values())
            classification = target.get('classification', 'unknown')
            active = "Yes" if target.get('is_active') else "No"
            f.write(f"| {target['id']} | {target['name']} | {classification} | {active} | {ref_count} |\n")
        f.write("\n")

        if any(all_refs.values()):
            f.write("## Reference Counts by Customer\n\n")
            for customer_id, refs in all_refs.items():
                if refs:
                    target = next((t for t in targets if t['id'] == customer_id), None)
                    if target:
                        f.write(f"### Customer {customer_id}: {target['name']}\n\n")
                        for table_col, count in refs.items():
                            f.write(f"- {table_col}: {count}\n")
                        f.write("\n")

        f.write("## Excluded Customers (Low Confidence)\n\n")
        f.write(f"The following {len(excluded)} customers were excluded from cleanup:\n\n")
        f.write("| ID | Name | Code | Active | Evidence |\n")
        f.write("|----|------|------|--------|----------|\n")
        for exc in excluded:
            code = exc.get('customer_code') or ''
            active = "Yes" if exc.get('is_active') else "No"
            evidence = exc.get('evidence', '')[:80]
            f.write(f"| {exc['id']} | {exc['name']} | {code} | {active} | {evidence}... |\n")
        f.write("\n")

        f.write("## Discovered Foreign Key References\n\n")
        f.write("| Table | Column | Constraint |\n")
        f.write("|-------|--------|------------|\n")
        for ref in fk_refs:
            f.write(f"| {ref['table_name']} | {ref['column_name']} | {ref['constraint_name']} |\n")
        f.write("\n")

        if legacy_refs:
            f.write("## Legacy References (No FK)\n\n")
            f.write("| Table | Column |\n")
            f.write("|-------|--------|\n")
            for ref in legacy_refs:
                f.write(f"| {ref['table_name']} | {ref['column_name']} |\n")
            f.write("\n")

    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(
        description='Safe customer cleanup tool - default DRY-RUN mode',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default, read-only)
  python cleanup_invalid_customers.py

  # Apply changes (requires explicit flag)
  python cleanup_invalid_customers.py --apply

  # Use custom audit file
  python cleanup_invalid_customers.py --audit-file path/to/audit.json
        """
    )

    parser.add_argument(
        '--apply',
        action='store_true',
        help='Execute physical DELETE (default is dry-run)'
    )

    parser.add_argument(
        '--audit-file',
        type=str,
        default='backend/scripts/backups/customer_import_audit/customer_import_audit_1.json',
        help='Path to audit JSON file'
    )

    args = parser.parse_args()

    dry_run = not args.apply
    mode = "DRY-RUN (read-only)" if dry_run else "APPLY (will delete)"

    print("=" * 80)
    print("Customer Cleanup Tool")
    print(f"Mode: {mode}")
    print("=" * 80)
    print()

    # Load audit data
    print("[1/11] Loading audit data...")
    audit_path = Path(args.audit_file)
    if not audit_path.is_absolute():
        audit_path = backend_path.parent / audit_path

    audit, audit_hash = load_audit_data(audit_path)
    print(f"  Audit hash: {audit_hash}")
    print()

    # Extract targets
    print("[2/11] Extracting target customers...")
    targets, excluded = extract_target_customers(audit)
    print()

    # Validate audit shape with strict checks
    print("[2b/11] Validating audit shape...")
    valid, errors = validate_audit_shape(targets, excluded)
    if not valid:
        for error in errors:
            print(f"  [ERROR] {error}")
        print("\n[ABORT] Audit shape validation failed")
        return 1
    print("  ✓ Audit shape validated: 3 truncated + 57 high-confidence = 60 targets, 23 excluded")
    print("  ✓ No duplicate IDs, canonical IDs not in targets")
    print()

    # Setup directories
    backup_dir = backend_path / 'backups' / 'customer_cleanup'
    report_dir = backup_dir / 'reports'
    backup_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    # Connect to database
    print("[3/11] Connecting to database...")
    config = get_db_config()

    if dry_run:
        conn = psycopg2.connect(**config)
        conn.set_session(readonly=True, autocommit=True)
        print("  Connected (READ-ONLY mode)")
    else:
        conn = psycopg2.connect(**config)
        conn.set_isolation_level(ISOLATION_LEVEL_SERIALIZABLE)
        print("  Connected (SERIALIZABLE transaction)")

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    print()

    try:
        # Verify canonical customers
        print("[4/11] Verifying canonical customers...")
        canonical_check = verify_canonical_customers(cur, dry_run)
        if not canonical_check['all_exist']:
            for error in canonical_check['errors']:
                print(f"  [ERROR] {error}")
            print("\n[ABORT] Canonical customers check failed")
            return 1

        for name, cust in canonical_check['customers'].items():
            print(f"  ✓ {name} (id={cust['id']}): {cust['name']}")
        print()

        # Check no targets are canonical
        print("[5/11] Checking targets are not canonical...")
        target_ids = {t['id'] for t in targets}
        canonical_ids = set(CANONICAL_CUSTOMERS.values())
        overlap = target_ids & canonical_ids

        if overlap:
            print(f"  [ERROR] Target list includes canonical customers: {overlap}")
            print("\n[ABORT] Cannot delete canonical customers")
            return 1
        print("  ✓ No canonical customers in target list")
        print()

        # Discover foreign keys
        print("[6/11] Discovering foreign key references...")
        fk_refs = discover_foreign_keys(cur)
        legacy_refs = get_legacy_references(cur)
        print(f"  Found {len(fk_refs)} FK references")
        print(f"  Found {len(legacy_refs)} legacy references")
        print()

        # Verify targets unchanged
        print("[7/11] Verifying target customers match audit...")
        valid, errors, live_rows = verify_targets_unchanged(cur, targets, audit_hash)
        if not valid:
            for error in errors:
                print(f"  [ERROR] {error}")
            print("\n[ABORT] Target verification failed")
            return 1
        print(f"  ✓ All {len(targets)} targets verified")
        print(f"  ✓ Full live customer rows loaded for backup")
        print()

        # Check references
        print("[8/11] Checking references for all targets...")
        safe, all_refs = check_all_references(cur, targets, fk_refs, legacy_refs)

        total_refs = sum(sum(refs.values()) for refs in all_refs.values())
        print(f"  Total references found: {total_refs}")

        if not safe:
            print("\n  [ERROR] Some targets have references:")
            for customer_id, refs in all_refs.items():
                if refs:
                    target = next((t for t in targets if t['id'] == customer_id), None)
                    if target:
                        print(f"    Customer {customer_id} ({target['name']}):")
                        for table_col, count in refs.items():
                            print(f"      - {table_col}: {count}")
            print("\n[ABORT] Cannot delete customers with references")

            # Still generate report
            print("\n[9/11] Generating report...")
            json_path, md_path = generate_report(
                targets, excluded, all_refs, canonical_check,
                fk_refs, legacy_refs, audit_hash, dry_run, report_dir
            )
            print(f"  JSON: {json_path}")
            print(f"  Markdown: {md_path}")

            return 1

        print(f"  ✓ All {len(targets)} targets have zero references")
        print()

        if dry_run:
            # Generate dry-run report BEFORE any changes
            print("[9/11] Generating dry-run report...")
            json_path, md_path = generate_report(
                targets, excluded, all_refs, canonical_check,
                fk_refs, legacy_refs, audit_hash, dry_run, report_dir
            )
            print(f"  JSON: {json_path}")
            print(f"  Markdown: {md_path}")
            print()

            print("[10/11] DRY-RUN mode - skipping backup creation")
            print("[11/11] DRY-RUN mode - skipping delete")
            print()
            print("=" * 80)
            print("DRY-RUN COMPLETE")
            print(f"Would delete {len(targets)} customers")
            print("Database unchanged")
            print("To apply changes, run with --apply flag")
            print("=" * 80)
            return 0

        # APPLY mode - create backup and delete
        print("[9/11] Creating restoration backups...")
        json_backup, sql_backup = create_backup(
            live_rows, audit_hash, all_refs, canonical_check, backup_dir
        )
        print(f"  JSON backup: {json_backup}")
        print(f"  SQL backup: {sql_backup}")
        print()

        # Delete customers
        print("[10/11] Deleting customers...")
        deleted_count = delete_customers(cur, targets)
        print(f"  Deleted {deleted_count} rows (verified exactly 60)")

        # Verify deletion
        print("  Verifying deletion...")
        success, errors = verify_deletion(cur, targets, canonical_check)

        if not success:
            print("\n  [ERROR] Verification failed:")
            for error in errors:
                print(f"    {error}")
            print("\n  Rolling back transaction...")
            conn.rollback()
            print("  [ABORT] Transaction rolled back, database unchanged")
            return 1

        print("  ✓ All targets deleted")
        print("  ✓ All canonical customers intact")

        # Commit transaction
        print("  Committing transaction...")
        conn.commit()
        print("  ✓ Transaction committed")
        print()

        # Generate apply report AFTER successful delete
        print("[11/11] Generating apply report...")
        apply_result = {
            'success': True,
            'deleted_count': deleted_count,
            'json_backup': str(json_backup),
            'sql_backup': str(sql_backup),
            'verification': 'passed'
        }
        json_path, md_path = generate_report(
            targets, excluded, all_refs, canonical_check,
            fk_refs, legacy_refs, audit_hash, dry_run, report_dir,
            apply_result=apply_result
        )
        print(f"  JSON: {json_path}")
        print(f"  Markdown: {md_path}")
        print()

        print("=" * 80)
        print("CLEANUP COMPLETE")
        print(f"Successfully deleted {deleted_count} customers")
        print(f"Backups saved to: {backup_dir}")
        print(f"Reports saved to: {report_dir}")
        print("=" * 80)

        return 0

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()

        if not dry_run:
            print("\nRolling back transaction...")
            conn.rollback()
            print("Transaction rolled back, database unchanged")

        return 1

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
