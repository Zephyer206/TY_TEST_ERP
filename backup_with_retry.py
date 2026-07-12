#!/usr/bin/env python3
"""Database backup with retry logic using psycopg2 (sync driver)."""

import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import sql

# Database connection parameters
DB_HOST = "124.222.29.229"
DB_PORT = 5432
DB_NAME = "stamping_system"
DB_USER = "postgres"
DB_PASSWORD = "thehaoshi5DE"

def connect_with_retry(max_retries=3):
    """Connect to database with retry logic."""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Connection attempt {attempt}/{max_retries}...")
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=10
            )
            print(f"[OK] Connected to {DB_HOST}:{DB_PORT}/{DB_NAME}")
            return conn
        except Exception as e:
            print(f"[ERROR] Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                print(f"Retrying in 2 seconds...")
                time.sleep(2)
            else:
                raise

def backup_database():
    """Create backup of critical tables."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(__file__).parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    backup_file = backup_dir / f"database_backup_{timestamp}.sql"

    # Critical tables to backup
    tables = [
        'customers', 'tooling_customers', 'parts', 'part_customer_aliases',
        'part_customer_alias', 'part_aliases', 'tooling_molds', 'dies',
        'tooling_parts', 'tooling_customer_links', 'quotes',
        'price_accounts', 'price_adjustments', 'material_dict',
        'treatment_dict', 'import_batches', 'excel_import_rows'
    ]

    print(f"\nStarting database backup...")
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Backup file: {backup_file}\n")

    stats = {}

    # Connect with retry
    conn = connect_with_retry(max_retries=3)
    cur = conn.cursor()

    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(f'-- Database Backup {timestamp}\n')
            f.write(f'-- Database: {DB_NAME}\n')
            f.write(f'-- Host: {DB_HOST}:{DB_PORT}\n\n')

            for table in tables:
                try:
                    # Check if table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = %s
                        )
                    """, (table,))

                    exists = cur.fetchone()[0]

                    if not exists:
                        f.write(f'-- Table {table} does not exist, skipping\n\n')
                        stats[table] = 'NOT_EXISTS'
                        print(f"[SKIP] {table} - does not exist")
                        continue

                    # Get row count
                    cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier(table)
                    ))
                    count = cur.fetchone()[0]
                    stats[table] = count

                    # Create backup table
                    backup_table_name = f'{table}_backup_{timestamp}'
                    cur.execute(sql.SQL("CREATE TABLE {} AS SELECT * FROM {}").format(
                        sql.Identifier(backup_table_name),
                        sql.Identifier(table)
                    ))
                    conn.commit()

                    f.write(f'-- Table: {table} ({count} rows) -> {backup_table_name}\n')
                    print(f"[OK] {table}: {count} rows backed up")

                except Exception as e:
                    conn.rollback()
                    f.write(f'-- Error backing up {table}: {str(e)}\n\n')
                    stats[table] = f'ERROR: {str(e)}'
                    print(f"[ERROR] {table}: {e}")

            f.write(f'\n-- Backup completed at {datetime.now()}\n')

        print(f"\n[OK] Backup completed: {backup_file}")

    finally:
        cur.close()
        conn.close()

    return backup_file, stats


if __name__ == "__main__":
    try:
        backup_file, stats = backup_database()

        print("\n=== Backup Summary ===")
        successful = 0
        failed = 0
        not_exists = 0

        for table, result in stats.items():
            if result == 'NOT_EXISTS':
                not_exists += 1
            elif isinstance(result, str) and result.startswith('ERROR'):
                failed += 1
            else:
                successful += 1
                print(f"{table}: {result} rows")

        print(f"\nTotal: {len(stats)} tables")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Not exists: {not_exists}")

        if failed > 0:
            sys.exit(1)

    except Exception as e:
        print(f"\n[FATAL] Backup failed: {e}")
        sys.exit(1)
