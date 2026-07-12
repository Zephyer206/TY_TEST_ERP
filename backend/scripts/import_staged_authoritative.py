#!/usr/bin/env python3
"""
Phase 3: Import staged VALID rows to formal tables
Implements authoritative design from data-model.md
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
from collections import defaultdict

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import psycopg2
import psycopg2.extras
from urllib.parse import urlparse


def get_db_config():
    """Get database config from settings - NO PASSWORD FALLBACK."""
    try:
        from app.core.config import settings
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured in settings")

        db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        parsed = urlparse(db_url)

        if not parsed.hostname or not parsed.password:
            raise ValueError("DATABASE_URL must include host and password")

        config = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'stamping_system',
            'user': parsed.username or 'postgres',
            'password': parsed.password
        }
        print(f"[INFO] Database: {config['host']}:{config['port']}/{config['database']}")
        return config
    except Exception as e:
        print(f"[ERROR] Could not load database configuration: {e}")
        print("[ERROR] Please configure DATABASE_URL in backend/.env")
        raise


def normalize_customer_name(name: str) -> str:
    """Normalize customer name for matching."""
    if not name:
        return ''
    # Remove whitespace, convert to lowercase
    normalized = name.strip().lower()
    # Remove common suffixes for matching
    normalized = re.sub(r'有限公司|股份有限公司|（.+?）|\(.+?\)', '', normalized)
    normalized = normalized.strip()
    return normalized


def normalize_internal_name(name: str) -> str:
    """Normalize internal part name for matching."""
    if not name:
        return ''
    return name.strip().lower()


def create_part_fingerprint(tooling_number: str, internal_name: str,
                            material: Optional[str], thickness: Optional[float],
                            width: Optional[float], pitch: Optional[float],
                            position: Optional[str]) -> str:
    """
    Create fingerprint for part matching.
    Format: tooling_number|internal_name|material|T|W|P|position
    """
    parts = [
        tooling_number or '',
        normalize_internal_name(internal_name),
        (material or '').strip().lower(),
        str(thickness) if thickness else '',
        str(width) if width else '',
        str(pitch) if pitch else '',
        (position or '').strip().upper()
    ]
    return '|'.join(parts)


def get_or_create_customer(cur, customer_name: str, customer_code: Optional[str] = None) -> int:
    """
    Get existing customer or create new one.
    Returns customer_id.
    """
    if not customer_name:
        raise ValueError("Customer name required")

    normalized = normalize_customer_name(customer_name)

    # Try exact match first
    cur.execute("""
        SELECT id FROM customers
        WHERE LOWER(TRIM(name)) = %s
    """, (customer_name.strip().lower(),))

    result = cur.fetchone()
    if result:
        return result[0]

    # Try normalized match
    cur.execute("""
        SELECT id, name FROM customers
    """)

    for row in cur.fetchall():
        existing_id, existing_name = row
        if normalize_customer_name(existing_name) == normalized:
            return existing_id

    # Create new customer
    cur.execute("""
        INSERT INTO customers (name, customer_code, created_at)
        VALUES (%s, %s, NOW())
        RETURNING id
    """, (customer_name.strip(), customer_code))

    customer_id = cur.fetchone()[0]
    print(f"  [NEW] Customer: {customer_name} (id={customer_id})")
    return customer_id


def get_or_create_part(cur, internal_name: str, fingerprint: str,
                       material: Optional[str] = None,
                       thickness: Optional[float] = None,
                       width: Optional[float] = None,
                       pitch: Optional[float] = None,
                       position: Optional[str] = None,
                       gross_weight: Optional[float] = None,
                       net_weight: Optional[float] = None) -> int:
    """
    Get existing part by fingerprint or create new one.
    Returns part_id.

    IMPORTANT: internal_part_no and part_number must remain NULL.
    """
    if not internal_name:
        raise ValueError("Internal name required")

    # Check for existing part with same fingerprint
    # Use actual column names from parts table
    cur.execute("""
        SELECT id FROM parts
        WHERE internal_name = %s
              AND COALESCE(material_name, '') = %s
              AND COALESCE(thickness, 0) = %s
              AND COALESCE(width, 0) = %s
              AND COALESCE(pitch, 0) = %s
              AND COALESCE(part_position, '') = %s
    """, (internal_name.strip(), material or '', thickness or 0,
          width or 0, pitch or 0, position or ''))

    result = cur.fetchone()
    if result:
        return result[0]

    # Create new part - internal_part_no and part_number remain NULL
    # Use actual column names from parts table
    cur.execute("""
        INSERT INTO parts (
            internal_name, material_name, thickness, width, pitch, part_position,
            gross_weight, net_weight, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
    """, (internal_name.strip(), material, thickness, width, pitch,
          position, gross_weight, net_weight))

    part_id = cur.fetchone()[0]
    print(f"  [NEW] Part: {internal_name} (id={part_id})")
    return part_id


def get_or_create_tooling(cur, tooling_number: str, mold_type: Optional[str],
                          is_continuous: bool, process_step_count: Optional[int],
                          cavity_count: Optional[int]) -> int:
    """
    Get existing tooling or create new one.
    Returns tooling_id.
    """
    if not tooling_number:
        raise ValueError("Tooling number required")

    # Check for existing tooling using tooling_no (NOT NULL column)
    cur.execute("""
        SELECT id FROM tooling
        WHERE tooling_no = %s
    """, (tooling_number.strip(),))

    result = cur.fetchone()
    if result:
        return result[0]

    # Create new tooling
    # Use tooling_no (NOT NULL) and set required fields with defaults
    cur.execute("""
        INSERT INTO tooling (
            tooling_no, mold_type, is_continuous,
            process_step_count, cavity_count,
            mold_status, status, shot_count, is_deleted,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
    """, (tooling_number.strip(),
          mold_type or 'Unknown',  # mold_type is NOT NULL
          is_continuous,
          process_step_count,
          cavity_count or 0,  # cavity_count is NOT NULL
          'active',  # mold_status is NOT NULL
          'active',  # status is NOT NULL
          0,  # shot_count is NOT NULL
          False))  # is_deleted is NOT NULL

    tooling_id = cur.fetchone()[0]
    print(f"  [NEW] Tooling: {tooling_number} (id={tooling_id}, continuous={is_continuous}, steps={process_step_count})")
    return tooling_id


def create_or_update_alias(cur, customer_id: int, part_id: int,
                           customer_part_no: Optional[str],
                           customer_part_name: Optional[str] = None,
                           revision: str = 'A') -> Optional[int]:
    """
    Create or update customer part alias.
    Returns alias_id or None if no customer_part_no.
    """
    if not customer_part_no:
        return None

    # Check for existing alias
    cur.execute("""
        SELECT id FROM part_customer_aliases
        WHERE customer_id = %s AND part_id = %s
              AND customer_part_no = %s AND revision = %s
    """, (customer_id, part_id, customer_part_no.strip(), revision))

    result = cur.fetchone()
    if result:
        return result[0]

    # Create new alias
    cur.execute("""
        INSERT INTO part_customer_aliases (
            customer_id, part_id, customer_part_no,
            customer_part_name, revision, created_at
        )
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id
    """, (customer_id, part_id, customer_part_no.strip(),
          customer_part_name, revision))

    alias_id = cur.fetchone()[0]
    return alias_id


def link_tooling_part(cur, tooling_id: int, part_id: int):
    """Create tooling-part relationship if not exists."""
    cur.execute("""
        SELECT 1 FROM tooling_parts
        WHERE tooling_id = %s AND part_id = %s
    """, (tooling_id, part_id))

    if not cur.fetchone():
        cur.execute("""
            INSERT INTO tooling_parts (tooling_id, part_id, created_at)
            VALUES (%s, %s, NOW())
        """, (tooling_id, part_id))


def link_tooling_customer(cur, tooling_id: int, customer_id: int):
    """Create tooling-customer relationship if not exists."""
    cur.execute("""
        SELECT 1 FROM tooling_customer_links
        WHERE tooling_id = %s AND customer_id = %s
    """, (tooling_id, customer_id))

    if not cur.fetchone():
        cur.execute("""
            INSERT INTO tooling_customer_links (tooling_id, customer_id, created_at)
            VALUES (%s, %s, NOW())
        """, (tooling_id, customer_id))


def create_tooling_steps(cur, tooling_id: int, step_count: int):
    """Create tooling steps for non-continuous molds."""
    if step_count <= 0:
        return

    # Check if steps already exist
    cur.execute("""
        SELECT COUNT(*) FROM tooling_steps
        WHERE tooling_id = %s
    """, (tooling_id,))

    existing = cur.fetchone()[0]
    if existing > 0:
        return  # Steps already created

    # Create steps
    for step_number in range(1, step_count + 1):
        cur.execute("""
            INSERT INTO tooling_steps (
                tooling_id, step_number, step_name, created_at
            )
            VALUES (%s, %s, %s, NOW())
        """, (tooling_id, step_number, f"Step {step_number}"))


def process_valid_rows(conn, batch_id: int):
    """
    Process all VALID rows from batch and import to formal tables.
    Uses SAVEPOINT for each row to avoid rollback of successful imports.
    """
    cur = conn.cursor()

    # Get all VALID rows
    cur.execute("""
        SELECT id, source_sheet, source_row,
               parsed_customer_name, parsed_customer_part_no, parsed_customer_part_name,
               parsed_tooling_number, parsed_internal_name,
               parsed_mold_type, parsed_is_continuous, parsed_process_step_count,
               parsed_cavity_count, parsed_material,
               parsed_thickness, parsed_width, parsed_pitch,
               parsed_gross_weight, parsed_net_weight, parsed_position
        FROM excel_import_rows
        WHERE batch_id = %s AND validation_status = 'VALID'
        ORDER BY id
    """, (batch_id,))

    # Get column names
    column_names = [desc[0] for desc in cur.description]

    valid_rows = cur.fetchall()
    total = len(valid_rows)

    print(f"\n[INFO] Processing {total} VALID rows...")

    imported = 0
    errors = 0
    no_alias = 0

    for idx, row_tuple in enumerate(valid_rows, 1):
        # Convert tuple to dict using column names
        row = dict(zip(column_names, row_tuple))
        row_id = row['id']

        # Print progress every 500 rows
        if idx % 500 == 0:
            print(f"  [{idx}/{total}] Imported: {imported}, Errors: {errors}")

        try:
            # Start savepoint for this row
            cur.execute(f"SAVEPOINT row_{row_id}")

            # 1. Get or create customer
            customer_id = get_or_create_customer(
                cur,
                row['parsed_customer_name']
            )

            # 2. Create part fingerprint
            fingerprint = create_part_fingerprint(
                row['parsed_tooling_number'],
                row['parsed_internal_name'],
                row.get('parsed_material'),
                row.get('parsed_thickness'),
                row.get('parsed_width'),
                row.get('parsed_pitch'),
                row.get('parsed_position')
            )

            # 3. Get or create part
            part_id = get_or_create_part(
                cur,
                row['parsed_internal_name'],
                fingerprint,
                row.get('parsed_material'),
                row.get('parsed_thickness'),
                row.get('parsed_width'),
                row.get('parsed_pitch'),
                row.get('parsed_position'),
                row.get('parsed_gross_weight'),
                row.get('parsed_net_weight')
            )

            # 4. Get or create tooling
            tooling_id = get_or_create_tooling(
                cur,
                row['parsed_tooling_number'],
                row.get('parsed_mold_type'),
                row['parsed_is_continuous'],
                row.get('parsed_process_step_count'),
                row.get('parsed_cavity_count')
            )

            # 5. Create customer part alias (if has customer_part_no)
            alias_id = None
            if row.get('parsed_customer_part_no'):
                alias_id = create_or_update_alias(
                    cur,
                    customer_id,
                    part_id,
                    row['parsed_customer_part_no'],
                    row.get('parsed_customer_part_name')
                )
            else:
                no_alias += 1

            # 6. Link tooling to part
            link_tooling_part(cur, tooling_id, part_id)

            # 7. Link tooling to customer
            link_tooling_customer(cur, tooling_id, customer_id)

            # 8. Create tooling steps for non-continuous molds
            if not row['parsed_is_continuous'] and row.get('parsed_process_step_count'):
                create_tooling_steps(cur, tooling_id, row['parsed_process_step_count'])

            # 9. Update staged row to IMPORTED
            cur.execute("""
                UPDATE excel_import_rows
                SET validation_status = 'IMPORTED',
                    resolved_customer_id = %s,
                    resolved_part_id = %s,
                    resolved_tooling_id = %s,
                    resolved_alias_id = %s
                WHERE id = %s
            """, (customer_id, part_id, tooling_id, alias_id, row_id))

            # Release savepoint
            cur.execute(f"RELEASE SAVEPOINT row_{row_id}")

            imported += 1

        except Exception as e:
            # Rollback to savepoint
            cur.execute(f"ROLLBACK TO SAVEPOINT row_{row_id}")
            cur.execute(f"RELEASE SAVEPOINT row_{row_id}")

            # Get detailed error message
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            if not error_msg or error_msg == ": " or len(error_msg) < 5:
                error_msg = traceback.format_exc()[:500]
            else:
                error_msg = error_msg[:500]

            cur.execute("""
                UPDATE excel_import_rows
                SET validation_status = 'ERROR',
                    validation_errors = %s
                WHERE id = %s
            """, (error_msg, row_id))

            errors += 1
            if errors <= 10:  # Only print first 10 errors
                print(f"  [ERROR] Row {row['source_sheet']}:{row['source_row']} - {error_msg[:150]}")

        # Commit every 100 rows
        if idx % 100 == 0:
            conn.commit()

    # Final commit
    conn.commit()
    cur.close()

    print(f"\n[SUMMARY]")
    print(f"  Total VALID rows: {total}")
    print(f"  Imported: {imported}")
    print(f"  Errors: {errors}")
    print(f"  No customer part number: {no_alias}")

    return imported, errors, no_alias


def print_statistics(conn, batch_id: int):
    """Print import statistics."""
    cur = conn.cursor()

    print(f"\n{'='*70}")
    print(f"IMPORT STATISTICS")
    print(f"{'='*70}")

    # Status counts
    cur.execute("""
        SELECT validation_status, COUNT(*)
        FROM excel_import_rows
        WHERE batch_id = %s
        GROUP BY validation_status
        ORDER BY validation_status
    """, (batch_id,))

    print("\nStaged rows status:")
    for status, count in cur.fetchall():
        print(f"  {status}: {count}")

    # Table counts
    print("\nFormal table counts:")
    tables = ['customers', 'parts', 'tooling', 'part_customer_aliases',
              'tooling_parts', 'tooling_customer_links', 'tooling_steps']

    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table}: {count}")

    cur.close()


def main():
    """Main entry point."""
    print("="*70)
    print("Phase 3: Import Staged Data to Formal Tables")
    print("="*70)

    # Get database config
    try:
        db_config = get_db_config()
    except Exception as e:
        print(f"[FATAL] {e}")
        return 1

    # Connect to database
    conn = psycopg2.connect(**db_config)

    try:
        # Get latest batch
        cur = conn.cursor()
        cur.execute("SELECT id FROM import_batches ORDER BY id DESC LIMIT 1")
        result = cur.fetchone()
        if not result:
            print("[ERROR] No batches found")
            return 1

        batch_id = result[0]
        print(f"\n[INFO] Processing batch {batch_id}")
        cur.close()

        # Process VALID rows
        imported, errors, no_alias = process_valid_rows(conn, batch_id)

        # Print statistics
        print_statistics(conn, batch_id)

        print(f"\n[SUCCESS] Import completed")
        print(f"  Imported: {imported}")
        print(f"  Errors: {errors}")
        print(f"  Rows without customer part number: {no_alias}")

        return 0

    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
