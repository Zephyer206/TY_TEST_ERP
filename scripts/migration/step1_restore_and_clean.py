#!/usr/bin/env python3
"""
Step 1: Restore from backup and clean incorrect data
"""

import os

import psycopg2

DB_HOST = os.environ.get("ZEPHYR_DB_HOST", "")
DB_PORT = int(os.environ.get("ZEPHYR_DB_PORT", "5432"))
DB_NAME = os.environ.get("ZEPHYR_DB_NAME", "stamping_system")
DB_USER = os.environ.get("ZEPHYR_DB_USER", "postgres")
DB_PASSWORD = os.environ.get("ZEPHYR_DB_PASSWORD", "")

if not DB_HOST or not DB_PASSWORD:
    raise RuntimeError("Set ZEPHYR_DB_HOST and ZEPHYR_DB_PASSWORD before running this migration")

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

def restore_and_clean():
    """Restore from backup and clean incorrect imported data."""
    print("="*70)
    print("STEP 1: RESTORE FROM BACKUP AND CLEAN")
    print("="*70)

    conn = connect_db()
    print(f"\n[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}\n")

    cur = conn.cursor()

    # 1. Delete IMPORT_* parts created in last failed run
    print("=== Cleaning IMPORT_* parts ===")
    cur.execute("SELECT COUNT(*) FROM parts WHERE part_number LIKE 'IMPORT_%'")
    import_count = cur.fetchone()[0]
    print(f"Found {import_count} IMPORT_* parts to delete")

    if import_count > 0:
        cur.execute("""
            DELETE FROM part_customer_aliases
            WHERE part_id IN (SELECT id FROM parts WHERE part_number LIKE 'IMPORT_%')
        """)
        deleted_aliases = cur.rowcount
        print(f"  Deleted {deleted_aliases} aliases linked to IMPORT_* parts")

        cur.execute("""
            DELETE FROM tooling_parts
            WHERE part_id IN (SELECT id FROM parts WHERE part_number LIKE 'IMPORT_%')
        """)
        deleted_tooling_parts = cur.rowcount
        print(f"  Deleted {deleted_tooling_parts} tooling_parts links")

        cur.execute("DELETE FROM parts WHERE part_number LIKE 'IMPORT_%'")
        deleted_parts = cur.rowcount
        print(f"  Deleted {deleted_parts} IMPORT_* parts")

    # 2. Restore parts from backup (only if we deleted many)
    cur.execute("SELECT COUNT(*) FROM parts")
    current_parts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parts_backup_20260712_085755")
    backup_parts = cur.fetchone()[0]

    print(f"\nParts count: current={current_parts}, backup={backup_parts}")

    if current_parts < backup_parts:
        print("[WARNING] Current parts less than backup, but keeping current state")
        print("          (backup had old incorrect structure)")

    # 3. Clean incorrect tooling_customer_links and part_customer_aliases
    print("\n=== Cleaning incorrect relationship data ===")

    cur.execute("DELETE FROM tooling_customer_links WHERE created_at > '2026-07-12 09:00:00'")
    deleted_tcl = cur.rowcount
    print(f"Deleted {deleted_tcl} recent tooling_customer_links")

    cur.execute("DELETE FROM part_customer_aliases WHERE created_at > '2026-07-12 09:00:00'")
    deleted_pca = cur.rowcount
    print(f"Deleted {deleted_pca} recent part_customer_aliases")

    cur.execute("DELETE FROM tooling_parts WHERE created_at > '2026-07-12 09:00:00'")
    deleted_tp = cur.rowcount
    print(f"Deleted {deleted_tp} recent tooling_parts")

    # 4. Reset is_continuous for all tooling (will be re-set correctly)
    # Set to false as default since column is NOT NULL
    cur.execute("UPDATE tooling SET is_continuous = false WHERE is_continuous = true")
    reset_continuous = cur.rowcount
    print(f"\nReset is_continuous to false for {reset_continuous} tooling records")

    # 5. Clear and reset import batch
    print("\n=== Resetting import batch ===")
    cur.execute("DELETE FROM excel_import_rows WHERE batch_id = 1")
    deleted_rows = cur.rowcount
    print(f"Deleted {deleted_rows} staging rows")

    cur.execute("DELETE FROM import_batches WHERE id = 1")
    deleted_batches = cur.rowcount
    print(f"Deleted {deleted_batches} import batches")

    conn.commit()

    # 6. Show final state
    print("\n=== Final State After Cleanup ===")
    cur.execute("SELECT COUNT(*) FROM customers")
    print(f"customers: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM parts")
    print(f"parts: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM tooling")
    print(f"tooling: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM tooling_parts")
    print(f"tooling_parts: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM part_customer_aliases")
    print(f"part_customer_aliases: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM tooling_customer_links")
    print(f"tooling_customer_links: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM tooling_steps")
    print(f"tooling_steps: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM import_batches")
    print(f"import_batches: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM excel_import_rows")
    print(f"excel_import_rows: {cur.fetchone()[0]}")

    cur.close()
    conn.close()

    print("\n[OK] Cleanup completed")

if __name__ == "__main__":
    restore_and_clean()
