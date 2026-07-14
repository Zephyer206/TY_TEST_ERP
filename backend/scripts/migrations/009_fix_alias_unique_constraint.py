#!/usr/bin/env python3
"""
Migration 009: Fix part_customer_aliases UNIQUE constraint to include part_id

Root Cause:
- Current UNIQUE(customer_id, customer_part_no, revision) prevents same customer_part_no
  from mapping to different internal parts
- Business requirement: left/right parts can share same customer part number
- Result: 490 legitimate aliases were not created, affecting 41 customers

Design Decision (from specs/001-erp-system-architecture/data-model.md):
- Line 136 states: UNIQUE(customer_id, customer_part_no, revision)
- However, this conflicts with the business reality shown in Excel data
- Same customer part number DOES map to multiple internal parts (left/right variants)

Fix:
- Drop existing idx_part_customer_alias_unique
- Create new UNIQUE constraint including part_id: (customer_id, part_id, customer_part_no, revision)
- This allows multiple internal parts to share same customer_part_no under same customer

Impact:
- Enables creation of 490 missing aliases in Phase 2
- Fixes data integrity for 41 affected customers
- Aligns database with actual business requirements

Execution: Phase 1 of customer import integrity repair
Date: 2026-07-13
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

import psycopg2
import psycopg2.extras
from urllib.parse import urlparse


def get_db_config():
    """Get database config from settings."""
    try:
        # Change to backend directory to load settings
        import os
        from urllib.parse import urlparse

        # Read .env file directly
        env_path = backend_path / '.env'
        if not env_path.exists():
            raise ValueError(f".env file not found at {env_path}")

        db_url = None
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.split('=', 1)[1].strip()
                    break

        if not db_url:
            raise ValueError("DATABASE_URL not found in .env")

        db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
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
        import traceback
        traceback.print_exc()
        raise


def main():
    print("=" * 80)
    print("Migration 009: Fix part_customer_aliases UNIQUE constraint")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    config = get_db_config()
    conn = psycopg2.connect(**config)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Step 1: Check current state
        print("[STEP 1] Checking current indexes...")
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'part_customer_aliases'
              AND indexname = 'idx_part_customer_alias_unique'
        """)
        current_index = cur.fetchone()

        if current_index:
            print(f"  Current index found: {current_index[0]}")
            print(f"  Definition: {current_index[1]}")
        else:
            print("  [WARNING] idx_part_customer_alias_unique not found")

        # Step 2: Count current aliases
        cur.execute("SELECT COUNT(*) FROM part_customer_aliases")
        alias_count = cur.fetchone()[0]
        print(f"  Current alias count: {alias_count}")
        print()

        # Step 3: Check for conflicts (same customer_part_no, different part_id)
        print("[STEP 2] Analyzing potential conflicts...")
        cur.execute("""
            SELECT
                customer_id,
                customer_part_no,
                revision,
                COUNT(DISTINCT part_id) as part_count,
                array_agg(DISTINCT part_id ORDER BY part_id) as part_ids
            FROM part_customer_aliases
            WHERE is_active = true
            GROUP BY customer_id, customer_part_no, revision
            HAVING COUNT(DISTINCT part_id) > 1
            ORDER BY part_count DESC
            LIMIT 10
        """)
        conflicts = cur.fetchall()

        if conflicts:
            print(f"  Found {len(conflicts)} existing multi-part mappings (will be preserved):")
            for row in conflicts:
                print(f"    Customer {row[0]}, part_no '{row[1]}', rev '{row[2]}': {row[3]} parts {row[4]}")
        else:
            print("  No multi-part mappings exist yet (expected - current index prevents them)")
        print()

        # Step 4: Create backup of current state
        print("[STEP 3] Creating backup...")
        backup_file = f"backups/alias_index_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        os.makedirs("backups", exist_ok=True)

        cur.execute("""
            SELECT
                id, part_id, customer_id, customer_part_no,
                customer_part_name, revision, is_active
            FROM part_customer_aliases
            ORDER BY id
        """)
        aliases = cur.fetchall()

        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(f"-- Backup of part_customer_aliases before index fix\n")
            f.write(f"-- Created: {datetime.now()}\n")
            f.write(f"-- Total rows: {len(aliases)}\n\n")
            for alias in aliases:
                f.write(f"-- ID {alias[0]}: part={alias[1]}, customer={alias[2]}, "
                       f"part_no='{alias[3]}', rev='{alias[5]}'\n")

        print(f"  Backup saved to: {backup_file}")
        print(f"  Backed up {len(aliases)} rows")
        print()

        # Step 5: Drop old index
        print("[STEP 4] Dropping old UNIQUE index...")
        cur.execute("DROP INDEX IF EXISTS idx_part_customer_alias_unique CASCADE")
        print("  [OK] Old index dropped")
        print()

        # Step 6: Create new index with part_id
        print("[STEP 5] Creating new UNIQUE index with part_id...")
        cur.execute("""
            CREATE UNIQUE INDEX idx_part_customer_alias_unique
            ON part_customer_aliases(customer_id, part_id, customer_part_no, revision)
            WHERE is_active = true
        """)
        print("  [OK] New index created: UNIQUE(customer_id, part_id, customer_part_no, revision)")
        print()

        # Step 7: Verify new index
        print("[STEP 6] Verifying new index...")
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'part_customer_aliases'
              AND indexname = 'idx_part_customer_alias_unique'
        """)
        new_index = cur.fetchone()

        if new_index:
            print(f"  New index verified: {new_index[0]}")
            print(f"  Definition: {new_index[1]}")
        else:
            raise Exception("New index not found after creation")
        print()

        # Commit transaction
        print("[STEP 7] Committing changes...")
        conn.commit()
        print("  [OK] Transaction committed")
        print()

        # Final report
        print("=" * 80)
        print("MIGRATION 009 COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("Changes:")
        print("  - Dropped: UNIQUE(customer_id, customer_part_no, revision)")
        print("  - Created: UNIQUE(customer_id, part_id, customer_part_no, revision)")
        print()
        print("Impact:")
        print("  - Same customer_part_no can now map to multiple internal parts")
        print("  - Phase 2 can proceed to create 490 missing aliases")
        print("  - No existing data was modified (index-only change)")
        print()
        print(f"Backup: {backup_file}")
        print()

    except Exception as e:
        print()
        print("[ERROR] Migration failed:", str(e))
        print("Rolling back transaction...")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
