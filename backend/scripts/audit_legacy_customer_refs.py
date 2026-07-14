#!/usr/bin/env python3
"""
STEP 3A1: Raw Live Evidence Collector
Audit all parts referencing legacy invalid customer IDs.
Read-only: no database modifications.
"""

import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Set

import psycopg2
import psycopg2.sql
from psycopg2.extras import RealDictCursor

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


def hard_reject_write_sql(sql: str) -> None:
    """Reject any SQL that could modify the database."""
    write_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'REPLACE', 'MERGE']
    sql_upper = sql.upper()
    for keyword in write_keywords:
        # Scan complete SQL to catch keywords anywhere, not just SELECT with text values
        if f' {keyword} ' in f' {sql_upper} ' or sql_upper.startswith(keyword):
            raise ValueError(f"Write operation rejected: {keyword}")


def json_serializer(obj: Any) -> Any:
    """Safely serialize Decimal and datetime objects for JSON."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def load_audit_manifest(path: str) -> Dict[str, Any]:
    """Load and validate customer_import_audit_1.json."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Validate structure - use actual JSON keys
    assert 'duplicate_customers' in data
    dup_custs = data['duplicate_customers']

    assert 'truncated' in dup_custs
    assert 'high_confidence_empty_duplicates' in dup_custs
    assert 'low_confidence_no_ref_customers' in dup_custs

    truncated = dup_custs['truncated']
    high_conf = dup_custs['high_confidence_empty_duplicates']
    low_conf = dup_custs['low_confidence_no_ref_customers']

    assert len(truncated) == 3, f"Expected 3 truncated, got {len(truncated)}"
    assert len(high_conf) == 57, f"Expected 57 high-confidence, got {len(high_conf)}"
    assert len(low_conf) == 23, f"Expected 23 low-confidence, got {len(low_conf)}"

    # Combine truncated and high_conf as targets
    targets = truncated + high_conf
    target_ids = [c['id'] for c in targets]
    assert len(target_ids) == 60, f"Expected 60 targets, got {len(target_ids)}"
    assert len(set(target_ids)) == 60, "Target IDs not unique"

    # Protected IDs must NOT be in targets
    protected = {35, 7271, 7286}
    for pid in protected:
        assert pid not in target_ids, f"Protected ID {pid} must not be in targets"

    return data


def get_db_config():
    """Get database config from settings"""
    try:
        # Ensure we're in the backend directory for settings to load correctly
        original_cwd = os.getcwd()
        os.chdir(backend_path)

        from app.core.config import settings
        from urllib.parse import urlparse

        os.chdir(original_cwd)

        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)

        config = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password
        }

        print(f"[INFO] DB config: host={config['host']}, port={config['port']}, db={config['database']}")
        return config
    except Exception as e:
        print(f"[ERROR] Could not load database config: {e}")
        import traceback
        traceback.print_exc()
        raise


def connect_readonly() -> psycopg2.extensions.connection:
    """Connect to PostgreSQL with read-only session."""
    config = get_db_config()
    conn = psycopg2.connect(**config)
    conn.set_session(readonly=True, autocommit=True)
    return conn


def get_historical_tables(cursor: psycopg2.extensions.cursor) -> List[str]:
    """Find all historical backup/snapshot tables."""
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND (table_name LIKE '%backup%'
             OR table_name LIKE '%snapshot%'
             OR table_name LIKE '%snap%'
             OR table_name LIKE '%_bak%'
             OR table_name LIKE '%_old%')
        ORDER BY table_name
    """
    hard_reject_write_sql(sql)
    cursor.execute(sql)
    return [row['table_name'] for row in cursor.fetchall()]


def count_historical_customer_refs(cursor: psycopg2.extensions.cursor,
                                   table_name: str,
                                   target_ids: Set[int]) -> int:
    """Count rows in historical table matching target customer IDs."""
    # Check if customer_id column exists
    sql_check = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        AND column_name = 'customer_id'
    """
    hard_reject_write_sql(sql_check)
    cursor.execute(sql_check, (table_name,))

    if not cursor.fetchone():
        return 0

    # Count matching rows using sql.Identifier for table name
    sql_count = psycopg2.sql.SQL("""
        SELECT COUNT(*) AS count
        FROM {table}
        WHERE customer_id = ANY(%s)
    """).format(table=psycopg2.sql.Identifier(table_name))

    hard_reject_write_sql(sql_count.as_string(cursor))
    cursor.execute(sql_count, (list(target_ids),))
    return cursor.fetchone()['count']


def collect_part_evidence(cursor: psycopg2.extensions.cursor,
                          part_id: int,
                          target_ids: Set[int]) -> Dict[str, Any]:
    """Collect all evidence for a single part."""
    evidence = {
        'part': None,
        'invalid_customer': None,
        'part_customer_aliases': [],
        'tooling_parts': [],
        'excel_import_rows': [],
        'duplicate_candidates': []
    }

    # Get full part row
    sql = "SELECT * FROM parts WHERE id = %s"
    hard_reject_write_sql(sql)
    cursor.execute(sql, (part_id,))
    part = cursor.fetchone()
    evidence['part'] = dict(part) if part else None

    if not part:
        return evidence

    # Get invalid customer info
    sql = "SELECT id, name, customer_code, is_active FROM customers WHERE id = %s"
    hard_reject_write_sql(sql)
    cursor.execute(sql, (part['customer_id'],))
    customer = cursor.fetchone()
    evidence['invalid_customer'] = dict(customer) if customer else None

    # Get active part_customer_aliases with customer info
    sql = """
        SELECT pca.*, c.id as alias_customer_id, c.name as customer_name, c.customer_code as customer_code
        FROM part_customer_aliases pca
        JOIN customers c ON pca.customer_id = c.id
        WHERE pca.part_id = %s AND pca.is_active = true
        ORDER BY pca.id
    """
    hard_reject_write_sql(sql)
    cursor.execute(sql, (part_id,))
    evidence['part_customer_aliases'] = [dict(row) for row in cursor.fetchall()]

    # Get tooling_parts with tooling info (ToolingPart has tooling_id/part_id/position, no customer_id)
    sql = """
        SELECT tp.id, tp.tooling_id, tp.part_id, tp.position, tp.sequence, tp.is_primary,
               t.tooling_number, t.tooling_no, t.customer_id as tooling_customer_id
        FROM tooling_parts tp
        JOIN tooling t ON tp.tooling_id = t.id
        WHERE tp.part_id = %s
        ORDER BY tp.id
    """
    hard_reject_write_sql(sql)
    cursor.execute(sql, (part_id,))
    evidence['tooling_parts'] = [dict(row) for row in cursor.fetchall()]

    # Get excel_import_rows
    sql = """
        SELECT * FROM excel_import_rows
        WHERE resolved_part_id = %s
        ORDER BY id
    """
    hard_reject_write_sql(sql)
    cursor.execute(sql, (part_id,))
    evidence['excel_import_rows'] = [dict(row) for row in cursor.fetchall()]

    # Find potential duplicate parts (non-target customer_id)
    duplicates = []

    # By tooling_number
    if evidence['tooling_parts']:
        for tp in evidence['tooling_parts']:
            if tp.get('tooling_number'):
                sql = """
                    SELECT p.*
                    FROM parts p
                    JOIN tooling_parts tp2 ON p.id = tp2.part_id
                    JOIN tooling t ON tp2.tooling_id = t.id
                    WHERE t.tooling_number = %s
                    AND p.id != %s
                    AND p.customer_id NOT IN (SELECT UNNEST(%s::int[]))
                """
                hard_reject_write_sql(sql)
                cursor.execute(sql, (tp['tooling_number'], part_id, list(target_ids)))
                duplicates.extend([dict(row) for row in cursor.fetchall()])

    # By customer_product_no
    if part.get('customer_product_no'):
        sql = """
            SELECT * FROM parts
            WHERE customer_product_no = %s
            AND id != %s
            AND customer_id NOT IN (SELECT UNNEST(%s::int[]))
        """
        hard_reject_write_sql(sql)
        cursor.execute(sql, (part['customer_product_no'], part_id, list(target_ids)))
        duplicates.extend([dict(row) for row in cursor.fetchall()])

    # By exact internal_name + material + dimensions (thickness/width/pitch)
    if part.get('internal_name'):
        sql = """
            SELECT * FROM parts
            WHERE internal_name = %s
            AND COALESCE(material_name, '') = COALESCE(%s, '')
            AND COALESCE(thickness, 0) = COALESCE(%s, 0)
            AND COALESCE(width, 0) = COALESCE(%s, 0)
            AND COALESCE(pitch, 0) = COALESCE(%s, 0)
            AND id != %s
            AND customer_id NOT IN (SELECT UNNEST(%s::int[]))
        """
        hard_reject_write_sql(sql)
        cursor.execute(sql, (
            part['internal_name'],
            part.get('material_name'),
            part.get('thickness'),
            part.get('width'),
            part.get('pitch'),
            part_id,
            list(target_ids)
        ))
        duplicates.extend([dict(row) for row in cursor.fetchall()])

    # Deduplicate by part id
    seen = set()
    unique_duplicates = []
    for dup in duplicates:
        if dup['id'] not in seen:
            seen.add(dup['id'])
            unique_duplicates.append(dup)

    evidence['duplicate_candidates'] = unique_duplicates

    return evidence


def main():
    """Main execution."""
    print("=== STEP 3A1: Raw Live Evidence Collector ===\n")

    # Load and validate manifest using repository-root-relative path
    manifest_path = backend_path / 'scripts' / 'backups' / 'customer_import_audit' / 'customer_import_audit_1.json'

    print(f"Loading manifest: {manifest_path}")
    manifest = load_audit_manifest(str(manifest_path))

    # Extract target IDs from the actual JSON structure
    dup_custs = manifest['duplicate_customers']
    targets = dup_custs['truncated'] + dup_custs['high_confidence_empty_duplicates']
    target_ids = set(c['id'] for c in targets)
    excluded_ids = set(c['id'] for c in dup_custs['low_confidence_no_ref_customers'])

    print(f"✓ Validated: 60 target IDs, 23 excluded IDs")
    print(f"✓ Protected IDs 35/7271/7286 not in targets\n")

    # Connect to database
    print("Connecting to PostgreSQL (read-only)...")
    conn = None
    cursor = None

    try:
        conn = connect_readonly()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("✓ Connected\n")

        # Count affected parts
        sql = "SELECT COUNT(*) AS count FROM parts WHERE customer_id = ANY(%s)"
        hard_reject_write_sql(sql)
        cursor.execute(sql, (list(target_ids),))
        total_parts = cursor.fetchone()['count']
        print(f"Found {total_parts} parts with target customer IDs\n")

        # Collect all affected parts
        sql = "SELECT id FROM parts WHERE customer_id = ANY(%s) ORDER BY id"
        hard_reject_write_sql(sql)
        cursor.execute(sql, (list(target_ids),))
        part_ids = [row['id'] for row in cursor.fetchall()]

        # Verify uniqueness
        assert len(part_ids) == len(set(part_ids)), "Duplicate part IDs found"
        assert len(part_ids) == total_parts, "Part count mismatch"
        print(f"✓ Verified {len(part_ids)} unique part IDs\n")

        # Collect evidence for each part
        print("Collecting evidence...")
        all_evidence = []
        per_customer_counts = {}

        for i, part_id in enumerate(part_ids, 1):
            if i % 100 == 0:
                print(f"  Progress: {i}/{len(part_ids)}")

            evidence = collect_part_evidence(cursor, part_id, target_ids)
            all_evidence.append(evidence)

            # Count per customer
            if evidence['part']:
                cust_id = evidence['part']['customer_id']
                per_customer_counts[cust_id] = per_customer_counts.get(cust_id, 0) + 1

        print(f"✓ Collected evidence for {len(all_evidence)} parts\n")

        # Count historical references
        print("Scanning historical tables...")
        historical_tables = get_historical_tables(cursor)
        historical_counts = {}

        for table in historical_tables:
            count = count_historical_customer_refs(cursor, table, target_ids)
            if count > 0:
                historical_counts[table] = count
                print(f"  {table}: {count} rows")

        if not historical_counts:
            print("  (no historical references found)")
        print()

        # Prepare output using repository-root-relative path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = backend_path / 'scripts' / 'backups' / 'customer_cleanup' / 'legacy_ref_audit'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'raw_evidence_{timestamp}.json'

        output_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'script': 'audit_legacy_customer_refs.py',
                'step': '3A1',
                'database_unchanged': True,
                'manifest_source': str(manifest_path)
            },
            'validation': {
                'target_customers': len(target_ids),
                'excluded_customers': len(excluded_ids),
                'total_parts_affected': len(all_evidence),
                'parts_match_count_query': len(all_evidence) == total_parts
            },
            'per_customer_counts': per_customer_counts,
            'historical_references': historical_counts,
            'evidence': all_evidence
        }

        # Write output
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=json_serializer)

        print(f"✓ Output written: {output_path}")
        print(f"✓ Total parts: {len(all_evidence)}")
        print(f"✓ Per-customer breakdown: {len(per_customer_counts)} customers")
        print(f"✓ Historical tables: {len(historical_counts)} tables with references")
        print(f"✓ Database unchanged: True\n")

    finally:
        # Always close connection
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    main()
