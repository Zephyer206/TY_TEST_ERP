#!/usr/bin/env python3
"""
Phase 3: Import staged VALID rows to formal tables (Recovery Version)
- Uses correct column names (tooling_number, not tooling_no)
- NO table truncation or deletion
- Small batch testing first
- Better error handling
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import psycopg2
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
    normalized = name.strip().lower()
    normalized = re.sub(r'有限公司|股份有限公司|（.+?）|\(.+?\)', '', normalized)
    return normalized.strip()


def get_or_create_customer(cur, customer_name: str) -> int:
    """Get existing customer or create new one."""
    if not customer_name:
        raise ValueError("Customer name required")

    # Try exact match first
    cur.execute("""
        SELECT id FROM customers
        WHERE LOWER(TRIM(name)) = %s
    """, (customer_name.strip().lower(),))

    result = cur.fetchone()
    if result:
        return result[0]

    # Try normalized match
    normalized = normalize_customer_name(customer_name)
    cur.execute("SELECT id, name FROM customers")

    for row in cur.fetchall():
        existing_id, existing_name = row
        if normalize_customer_name(existing_name) == normalized:
            return existing_id

    # Create new customer
    cur.execute("""
        INSERT INTO customers (name, created_at)
        VALUES (%s, NOW())
        RETURNING id
    """, (customer_name.strip(),))

    customer_id = cur.fetchone()[0]
    print(f"  [NEW] Customer: {customer_name} (id={customer_id})")
    return customer_id


def get_or_create_part(cur, internal_name: str,
                       tooling_number: str,
                       material: Optional[str] = None,
                       thickness: Optional[float] = None,
                       width: Optional[float] = None,
                       pitch: Optional[float] = None,
                       position: Optional[str] = None,
                       gross_weight: Optional[float] = None,
                       net_weight: Optional[float] = None) -> int:
    """
    Get existing part or create new one.
    Uses tooling_number + part attributes as fingerprint.
    """
    if not internal_name:
        raise ValueError("Internal name required")
    if not tooling_number:
        raise ValueError("Tooling number required for part fingerprint")

    # Strategy 1: Check via tooling_parts -> tooling.tooling_number + part attributes
    cur.execute("""
        SELECT p.id FROM parts p
        JOIN tooling_parts tp ON tp.part_id = p.id
        JOIN tooling t ON t.id = tp.tooling_id
        WHERE t.tooling_number = %s
              AND p.internal_name = %s
              AND COALESCE(p.material_name, '') = %s
              AND COALESCE(p.thickness, 0) = %s
              AND COALESCE(p.width, 0) = %s
              AND COALESCE(p.pitch, 0) = %s
              AND COALESCE(p.part_position, '') = %s
        LIMIT 1
    """, (tooling_number.strip(), internal_name.strip(), material or '',
          thickness or 0, width or 0, pitch or 0, position or ''))

    result = cur.fetchone()
    if result:
        return result[0]

    # Strategy 2: Check old parts via mold_number (compatibility)
    cur.execute("""
        SELECT id FROM parts
        WHERE mold_number = %s
              AND internal_name = %s
              AND COALESCE(material_name, '') = %s
              AND COALESCE(thickness, 0) = %s
              AND COALESCE(width, 0) = %s
              AND COALESCE(pitch, 0) = %s
              AND COALESCE(part_position, '') = %s
        LIMIT 1
    """, (tooling_number.strip(), internal_name.strip(), material or '',
          thickness or 0, width or 0, pitch or 0, position or ''))

    result = cur.fetchone()
    if result:
        return result[0]

    # Strategy 3: Create new part - internal_part_no and part_number remain NULL
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
    Uses tooling_number as authoritative field.
    """
    if not tooling_number:
        raise ValueError("Tooling number required")

    # Check for existing tooling using tooling_number (authoritative)
    cur.execute("""
        SELECT id FROM tooling
        WHERE tooling_number = %s
    """, (tooling_number.strip(),))

    result = cur.fetchone()
    if result:
        return result[0]

    # Create new tooling
    # Use tooling_number as primary, also set tooling_no for compatibility
    cur.execute("""
        INSERT INTO tooling (
            tooling_number, tooling_no, mold_type, is_continuous,
            process_step_count, cavity_count,
            mold_status, status, shot_count, is_deleted,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
    """, (tooling_number.strip(),
          tooling_number.strip(),  # Also set tooling_no for compatibility
          mold_type or 'Unknown',
          is_continuous,
          process_step_count,
          cavity_count or 0,
          'active',
          'active',
          0,
          False))

    tooling_id = cur.fetchone()[0]
    print(f"  [NEW] Tooling: {tooling_number} (id={tooling_id}, continuous={is_continuous}, steps={process_step_count})")
    return tooling_id


def create_or_update_alias(cur, customer_id: int, part_id: int,
                           customer_part_no: Optional[str],
                           customer_part_name: Optional[str] = None) -> Optional[int]:
    """Create or update customer part alias. If duplicate, return existing."""
    if not customer_part_no:
        return None

    # Check for existing alias with same customer_id + customer_part_no
    # This matches the unique constraint idx_part_customer_alias_unique
    cur.execute("""
        SELECT id, part_id FROM part_customer_aliases
        WHERE customer_id = %s AND customer_part_no = %s
    """, (customer_id, customer_part_no.strip()))

    result = cur.fetchone()
    if result:
        existing_id, existing_part_id = result
        # If it points to the same part, just return the existing id
        if existing_part_id == part_id:
            return existing_id
        # If it points to a different part, this is a conflict
        # For now, skip creating (could log this as a warning)
        print(f"  [SKIP] Alias {customer_part_no} already exists for customer {customer_id} with different part")
        return existing_id

    # Create new alias (customer_name can be NULL now)
    try:
        cur.execute("""
            INSERT INTO part_customer_aliases (
                customer_id, part_id, customer_part_no,
                customer_part_name, revision, created_at
            )
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (customer_id, part_id, customer_part_no.strip(),
              customer_part_name, 'A'))

        alias_id = cur.fetchone()[0]
        return alias_id
    except Exception as e:
        # If insert fails due to race condition, fetch again
        if 'idx_part_customer_alias_unique' in str(e):
            cur.execute("""
                SELECT id FROM part_customer_aliases
                WHERE customer_id = %s AND customer_part_no = %s
            """, (customer_id, customer_part_no.strip()))
            result = cur.fetchone()
            if result:
                return result[0]
        # Re-raise if it's a different error
        raise


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
        return

    # Create steps using correct column names (step_no, not step_number)
    for step_number in range(1, step_count + 1):
        cur.execute("""
            INSERT INTO tooling_steps (
                tooling_id, step_no, step_name, sequence, created_at
            )
            VALUES (%s, %s, %s, %s, NOW())
        """, (tooling_id, step_number, f"Step {step_number}", step_number))


def process_single_row(cur, row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Process a single row.
    Returns: (success, error_message)
    """
    row_id = row['id']

    try:
        # Start savepoint
        cur.execute(f"SAVEPOINT row_{row_id}")

        # 1. Get or create customer
        customer_id = get_or_create_customer(cur, row['parsed_customer_name'])

        # 2. Get or create tooling first (needed for part fingerprint)
        tooling_id = get_or_create_tooling(
            cur,
            row['parsed_tooling_number'],
            row.get('parsed_mold_type'),
            row['parsed_is_continuous'],
            row.get('parsed_process_step_count'),
            row.get('parsed_cavity_count')
        )

        # 3. Get or create part (with tooling_number in fingerprint)
        part_id = get_or_create_part(
            cur,
            row['parsed_internal_name'],
            row['parsed_tooling_number'],  # Add tooling_number for fingerprint
            row.get('parsed_material'),
            row.get('parsed_thickness'),
            row.get('parsed_width'),
            row.get('parsed_pitch'),
            row.get('parsed_position'),
            row.get('parsed_gross_weight'),
            row.get('parsed_net_weight')
        )

        # 4. Create customer part alias (if has customer_part_no)
        alias_id = None
        if row.get('parsed_customer_part_no'):
            alias_id = create_or_update_alias(
                cur,
                customer_id,
                part_id,
                row['parsed_customer_part_no'],
                row.get('parsed_customer_part_name')
            )

        # 5. Link tooling to part
        link_tooling_part(cur, tooling_id, part_id)

        # 6. Link tooling to customer
        link_tooling_customer(cur, tooling_id, customer_id)

        # 7. Create tooling steps for non-continuous molds
        if not row['parsed_is_continuous'] and row.get('parsed_process_step_count'):
            create_tooling_steps(cur, tooling_id, row['parsed_process_step_count'])

        # 8. Update staged row to IMPORTED
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

        return True, None

    except Exception as e:
        # Rollback to savepoint
        cur.execute(f"ROLLBACK TO SAVEPOINT row_{row_id}")
        cur.execute(f"RELEASE SAVEPOINT row_{row_id}")

        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        if not error_msg or len(error_msg) < 10:
            error_msg = traceback.format_exc()[:500]
        else:
            error_msg = error_msg[:500]

        return False, error_msg


def process_valid_rows(conn, batch_id: int, test_mode: bool = False, limit: Optional[int] = None):
    """
    Process VALID rows from batch.

    Args:
        test_mode: If True, only process first 20 rows for testing
        limit: Max rows to process (None = all)
    """
    cur = conn.cursor()

    # Get VALID rows
    query = """
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
    """

    if test_mode:
        query += " LIMIT 20"
    elif limit:
        query += f" LIMIT {limit}"

    cur.execute(query, (batch_id,))

    # Get column names
    column_names = [desc[0] for desc in cur.description]
    valid_rows = cur.fetchall()
    total = len(valid_rows)

    mode_str = "TEST MODE (20 rows)" if test_mode else f"{total} rows"
    print(f"\n[INFO] Processing {mode_str}...")

    imported = 0
    errors = 0
    error_types = {}

    for idx, row_tuple in enumerate(valid_rows, 1):
        # Convert tuple to dict
        row = dict(zip(column_names, row_tuple))
        row_id = row['id']

        # Process row
        success, error_msg = process_single_row(cur, row)

        if success:
            imported += 1
        else:
            errors += 1

            # Track error types
            error_type = error_msg.split(':')[0] if error_msg else 'Unknown'
            error_types[error_type] = error_types.get(error_type, 0) + 1

            # Mark as error
            cur.execute("""
                UPDATE excel_import_rows
                SET validation_status = 'ERROR',
                    validation_errors = %s
                WHERE id = %s
            """, (error_msg, row_id))

            # Print first 10 errors
            if errors <= 10:
                print(f"  [ERROR] Row {row['source_sheet']}:{row['source_row']} - {error_msg[:100]}")

            # Stop if same SYSTEM error type appears > 5 times
            # Exclude business constraint errors like UniqueViolation
            system_error_types = {k: v for k, v in error_types.items()
                                 if k not in ['UniqueViolation']}
            if any(count > 5 for count in system_error_types.values()):
                print(f"\n[STOP] Same system error type appeared >5 times: {system_error_types}")
                print(f"[STOP] Stopping to avoid mass errors. Fix the issue and re-run.")
                break

        # Commit every 100 rows
        if idx % 100 == 0:
            conn.commit()
            print(f"  [{idx}/{total}] Imported: {imported}, Errors: {errors}")

    # Final commit
    conn.commit()
    cur.close()

    print(f"\n[SUMMARY]")
    print(f"  Total processed: {imported + errors}")
    print(f"  Imported: {imported}")
    print(f"  Errors: {errors}")
    if error_types:
        print(f"  Error types: {error_types}")

    return imported, errors


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
    print("Phase 3: Import Staged Data to Formal Tables (Recovery)")
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

        # Check if test mode requested
        import sys
        test_mode = '--test' in sys.argv

        if test_mode:
            print("\n[TEST MODE] Processing 20 rows for validation...")
            imported, errors = process_valid_rows(conn, batch_id, test_mode=True)

            if errors > 0:
                print(f"\n[WARNING] Test mode found {errors} errors. Fix before full run.")
                return 1
            else:
                print(f"\n[SUCCESS] Test mode passed! Ready for full import.")
        else:
            # Full import
            imported, errors = process_valid_rows(conn, batch_id, test_mode=False)

        # Print statistics
        print_statistics(conn, batch_id)

        if errors > 0:
            print(f"\n[PARTIAL] Import completed with {errors} errors")
            return 1
        else:
            print(f"\n[SUCCESS] Import completed successfully")
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
