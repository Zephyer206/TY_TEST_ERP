#!/usr/bin/env python3
"""Database backup script - creates table snapshots before migration."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import text
from app.database import async_session_maker


async def backup_database():
    """Create backup of critical tables."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(__file__).parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    backup_file = backup_dir / f"database_backup_{timestamp}.sql"

    # Critical tables to backup
    tables = [
        'customers', 'tooling_customers', 'parts', 'part_customer_aliases',
        'part_customer_alias', 'part_aliases', 'tooling_molds', 'dies',
        'tooling_parts', 'tooling_customer_links', 'quotes', 'prices',
        'price_accounts', 'price_adjustments', 'material_dict',
        'treatment_dict', 'import_batches', 'excel_import_rows'
    ]

    print(f"Starting database backup...")
    print(f"Database: 124.222.29.229:5432/stamping_system")
    print(f"Backup file: {backup_file}")

    stats = {}

    async with async_session_maker() as session:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(f'-- Database Backup {timestamp}\n')
            f.write(f'-- Database: stamping_system\n')
            f.write(f'-- Host: 124.222.29.229:5432 (Password hidden)\n')
            f.write(f'-- Backup Type: Table snapshots\n\n')

            for table in tables:
                try:
                    # Check if table exists
                    result = await session.execute(
                        text(f"SELECT to_regclass('public.{table}')")
                    )
                    if result.scalar() is None:
                        f.write(f'-- Table {table} does not exist, skipping\n\n')
                        stats[table] = 'NOT_EXISTS'
                        continue

                    # Get row count
                    count_result = await session.execute(
                        text(f'SELECT COUNT(*) FROM "{table}"')
                    )
                    count = count_result.scalar()
                    stats[table] = count

                    # Create backup table
                    backup_table_name = f'{table}_backup_{timestamp}'
                    await session.execute(
                        text(f'CREATE TABLE "{backup_table_name}" AS SELECT * FROM "{table}"')
                    )
                    await session.commit()

                    f.write(f'-- Table: {table} ({count} rows) -> {backup_table_name}\n')
                    print(f"[OK] Backed up {table}: {count} rows")

                except Exception as e:
                    f.write(f'-- Error backing up {table}: {str(e)}\n\n')
                    stats[table] = f'ERROR: {str(e)}'
                    print(f"[ERROR] Error backing up {table}: {e}")

            f.write(f'\n-- Backup completed at {datetime.now()}\n')

        print(f"\n[OK] Backup completed: {backup_file}")
        return backup_file, stats


if __name__ == "__main__":
    backup_file, stats = asyncio.run(backup_database())

    print("\n=== Backup Summary ===")
    for table, count in stats.items():
        print(f"{table}: {count}")
