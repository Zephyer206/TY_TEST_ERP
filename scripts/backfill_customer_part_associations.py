"""
Customer-Part Association Backfill Script (Stage 2)

Business Requirements:
- Source: excel_import_rows with validation_status='IMPORTED' and both resolved_part_id and resolved_customer_id present
- When parsed_customer_part_no is NULL or empty, create association with customer_part_no=NULL
- Never duplicate: skip if customer_id+part_id association already exists
- Never overwrite existing customer_part_no values
- Never fabricate any customer, part, customer_part_no, or tooling relationships
- Idempotent: can be run multiple times safely
- Auditable: log all operations with counts

Safety:
- Wrapped in transaction
- Read-only validation queries before modification
- Detailed logging for audit trail
- No credentials exposed in output
"""

import psycopg2
from datetime import datetime
import sys
from pathlib import Path
from sqlalchemy.engine import make_url

# Add backend directory to path to use its configuration
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import settings


def get_db_connection():
    """Get database connection using application configuration"""
    # Parse async SQLAlchemy URL and convert to psycopg2 format
    # settings.DATABASE_URL format: postgresql+asyncpg://user:password@host:port/dbname
    # psycopg2 needs: postgresql://user:password@host:port/dbname

    url = make_url(settings.DATABASE_URL)

    # Build psycopg2-compatible connection string
    # Use postgresql driver instead of postgresql+asyncpg
    psycopg2_url = url.set(drivername="postgresql")

    return psycopg2.connect(str(psycopg2_url))


def validate_source_data(cur):
    """Validate source data before backfill"""
    print("\n=== Source Data Validation ===")

    # Count eligible rows
    cur.execute("""
        SELECT COUNT(*) as eligible_count
        FROM excel_import_rows
        WHERE validation_status = 'IMPORTED'
          AND resolved_part_id IS NOT NULL
          AND resolved_customer_id IS NOT NULL
    """)
    eligible_count = cur.fetchone()[0]
    print(f"Eligible excel_import_rows: {eligible_count}")

    # Count by customer_part_no status
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE parsed_customer_part_no IS NULL OR TRIM(parsed_customer_part_no) = '') as null_or_empty,
            COUNT(*) FILTER (WHERE parsed_customer_part_no IS NOT NULL AND TRIM(parsed_customer_part_no) != '') as has_value,
            COUNT(DISTINCT resolved_part_id) as distinct_parts,
            COUNT(DISTINCT resolved_customer_id) as distinct_customers
        FROM excel_import_rows
        WHERE validation_status = 'IMPORTED'
          AND resolved_part_id IS NOT NULL
          AND resolved_customer_id IS NOT NULL
    """)
    row = cur.fetchone()
    print(f"  - NULL or empty customer_part_no: {row[0]}")
    print(f"  - Has customer_part_no value: {row[1]}")
    print(f"  - Distinct parts: {row[2]}")
    print(f"  - Distinct customers: {row[3]}")

    # Count existing associations
    cur.execute("SELECT COUNT(*) FROM part_customer_aliases")
    existing_count = cur.fetchone()[0]
    print(f"Existing part_customer_aliases: {existing_count}")

    return eligible_count, existing_count


def check_existing_associations(cur):
    """Check for existing associations that match our source data"""
    print("\n=== Checking Existing Associations ===")

    cur.execute("""
        SELECT COUNT(DISTINCT (e.resolved_customer_id, e.resolved_part_id))
        FROM excel_import_rows e
        INNER JOIN part_customer_aliases pca
            ON pca.customer_id = e.resolved_customer_id
            AND pca.part_id = e.resolved_part_id
        WHERE e.validation_status = 'IMPORTED'
          AND e.resolved_part_id IS NOT NULL
          AND e.resolved_customer_id IS NOT NULL
    """)
    overlap_count = cur.fetchone()[0]
    print(f"Customer-part pairs already in aliases table: {overlap_count}")

    return overlap_count


def backfill_associations(cur, dry_run=False):
    """
    Backfill customer-part associations from excel_import_rows

    Rules:
    1. Only use IMPORTED rows with both resolved_part_id and resolved_customer_id
    2. Create association with customer_part_no=NULL when parsed_customer_part_no is empty
    3. Skip if association (customer_id, part_id) already exists
    4. Never modify existing associations
    """
    print(f"\n=== Backfill Associations ({'DRY RUN' if dry_run else 'EXECUTING'}) ===")

    stats = {
        'processed': 0,
        'created': 0,
        'skipped_existing': 0,
        'skipped_invalid': 0,
        'errors': 0
    }

    # Get all eligible rows
    cur.execute("""
        SELECT
            id,
            resolved_customer_id,
            resolved_part_id,
            parsed_customer_part_no
        FROM excel_import_rows
        WHERE validation_status = 'IMPORTED'
          AND resolved_part_id IS NOT NULL
          AND resolved_customer_id IS NOT NULL
        ORDER BY id
    """)
    import_rows = cur.fetchall()

    print(f"Processing {len(import_rows)} eligible rows...")

    # Track unique (customer_id, part_id) pairs we've seen in this run
    seen_pairs = set()

    # Get existing associations to avoid duplicates
    cur.execute("""
        SELECT customer_id, part_id
        FROM part_customer_aliases
    """)
    existing_pairs = set(cur.fetchall())
    print(f"Found {len(existing_pairs)} existing (customer_id, part_id) pairs")

    for row in import_rows:
        row_id, customer_id, part_id, parsed_customer_part_no = row
        stats['processed'] += 1

        pair_key = (customer_id, part_id)

        # Skip if we've already processed this pair in this run
        if pair_key in seen_pairs:
            stats['skipped_existing'] += 1
            continue

        # Skip if association already exists in database
        if pair_key in existing_pairs:
            stats['skipped_existing'] += 1
            seen_pairs.add(pair_key)
            continue

        # Determine customer_part_no value
        customer_part_no = parsed_customer_part_no
        if customer_part_no is not None:
            customer_part_no = customer_part_no.strip()
            if customer_part_no == '':
                customer_part_no = None

        # Create new association
        if not dry_run:
            try:
                now = datetime.now()
                cur.execute("""
                    INSERT INTO part_customer_aliases
                        (part_id, customer_id, customer_part_no, revision, is_active, remark, created_at, updated_at)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    part_id,
                    customer_id,
                    customer_part_no,
                    '',  # revision - empty string since NOT NULL
                    True,  # is_active
                    f"Backfilled from excel_import_rows on {now.date()}",
                    now,  # created_at
                    now   # updated_at
                ))
                stats['created'] += 1
                seen_pairs.add(pair_key)

                if stats['created'] % 100 == 0:
                    print(f"  Progress: {stats['created']} associations created...")

            except Exception as e:
                stats['errors'] += 1
                print(f"  ERROR creating association for customer={customer_id}, part={part_id}: {e}")
        else:
            stats['created'] += 1
            seen_pairs.add(pair_key)

    return stats


def verify_backfill(cur, before_count):
    """Verify backfill results"""
    print("\n=== Verification ===")

    # Count after backfill
    cur.execute("SELECT COUNT(*) FROM part_customer_aliases")
    after_count = cur.fetchone()[0]
    print(f"Associations after backfill: {after_count}")
    print(f"Net change: +{after_count - before_count}")

    # Count NULL customer_part_no
    cur.execute("SELECT COUNT(*) FROM part_customer_aliases WHERE customer_part_no IS NULL")
    null_count = cur.fetchone()[0]
    print(f"Associations with NULL customer_part_no: {null_count}")

    # Verify no duplicates
    cur.execute("""
        SELECT customer_id, part_id, COUNT(*)
        FROM part_customer_aliases
        GROUP BY customer_id, part_id
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    if duplicates:
        print(f"WARNING: Found {len(duplicates)} duplicate (customer_id, part_id) pairs!")
        for dup in duplicates[:5]:
            print(f"  customer_id={dup[0]}, part_id={dup[1]}, count={dup[2]}")
    else:
        print("No duplicate (customer_id, part_id) pairs found")

    return after_count


def run_acceptance_queries(cur):
    """Run acceptance test queries"""
    print("\n=== Acceptance Test Queries ===")

    # Query 1: Distinct parts with customer associations
    cur.execute("""
        SELECT COUNT(DISTINCT part_id) as parts_with_customers
        FROM part_customer_aliases
    """)
    parts_with_customers = cur.fetchone()[0]
    print(f"1. Distinct parts with customer associations: {parts_with_customers}")

    # Query 2: Total parts
    cur.execute("SELECT COUNT(*) FROM parts")
    total_parts = cur.fetchone()[0]
    print(f"2. Total parts in database: {total_parts}")

    # Query 3: Distinct parts in tooling_parts
    cur.execute("""
        SELECT COUNT(DISTINCT part_id) as tooling_parts
        FROM tooling_parts
        WHERE part_id IS NOT NULL
    """)
    tooling_parts = cur.fetchone()[0]
    print(f"3. Distinct parts in tooling_parts: {tooling_parts}")

    # Query 4: IMPORTED parts without customer associations
    cur.execute("""
        SELECT COUNT(DISTINCT e.resolved_part_id) as parts_without_associations
        FROM excel_import_rows e
        WHERE e.validation_status = 'IMPORTED'
          AND e.resolved_part_id IS NOT NULL
          AND e.resolved_customer_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM part_customer_aliases pca
              WHERE pca.part_id = e.resolved_part_id
                AND pca.customer_id = e.resolved_customer_id
          )
    """)
    parts_without = cur.fetchone()[0]
    print(f"4. IMPORTED parts without customer associations: {parts_without}")

    return {
        'parts_with_customers': parts_with_customers,
        'total_parts': total_parts,
        'tooling_parts': tooling_parts,
        'parts_without_associations': parts_without
    }


def main():
    """Main execution function"""
    print("=" * 60)
    print("Customer-Part Association Backfill (Stage 2)")
    print("=" * 60)
    print(f"Start time: {datetime.now()}")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # Step 1: Validate source data
            eligible_count, before_count = validate_source_data(cur)

            # Step 2: Check existing associations
            overlap_count = check_existing_associations(cur)

            # Step 3: Dry run
            print("\n--- DRY RUN ---")
            dry_stats = backfill_associations(cur, dry_run=True)
            print(f"\nDry run results:")
            print(f"  Processed: {dry_stats['processed']}")
            print(f"  Would create: {dry_stats['created']}")
            print(f"  Would skip (existing): {dry_stats['skipped_existing']}")
            print(f"  Would skip (invalid): {dry_stats['skipped_invalid']}")

            # Step 4: Execute backfill
            print("\n--- EXECUTING BACKFILL ---")
            stats = backfill_associations(cur, dry_run=False)
            print(f"\nBackfill results:")
            print(f"  Processed: {stats['processed']}")
            print(f"  Created: {stats['created']}")
            print(f"  Skipped (existing): {stats['skipped_existing']}")
            print(f"  Skipped (invalid): {stats['skipped_invalid']}")
            print(f"  Errors: {stats['errors']}")

            # Step 5: Commit transaction
            conn.commit()
            print("\nTransaction committed successfully")

        # Step 6: Verify results (new cursor after commit)
        with conn.cursor() as cur:
            after_count = verify_backfill(cur, before_count)

            # Step 7: Run acceptance queries
            acceptance_results = run_acceptance_queries(cur)

        print("\n" + "=" * 60)
        print("BACKFILL COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"End time: {datetime.now()}")

    except Exception as e:
        print(f"\nERROR: {e}")
        conn.rollback()
        print("Transaction rolled back")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
