"""Check remote PostgreSQL migration status."""

import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        host='124.222.29.229',
        port=5432,
        user='postgres',
        password='thehaoshi5DE',
        database='stamping_system'
    )

    try:
        print('Remote database check:')
        print('='*60)

        # Check data
        rows = await conn.fetch('''
            SELECT id, name, category, primary_category, secondary_category, customer_part_name
            FROM part_name_dict
            LIMIT 5
        ''')

        print(f'\nTotal records: {len(rows)}')
        print('\nSample data:')
        print('-'*60)
        for row in rows:
            print(f"ID {row['id']}:")
            print(f"  Old: name={row['name']}, category={row['category']}")
            print(f"  New: primary={row['primary_category']}, secondary={row['secondary_category']}, customer={row['customer_part_name']}")

        # Check if migration is complete
        null_count = await conn.fetchval('SELECT COUNT(*) FROM part_name_dict WHERE primary_category IS NULL')
        print(f"\nRecords with NULL primary_category: {null_count}")

        if null_count == 0:
            print('\nStatus: Migration COMPLETE')
        else:
            print('\nStatus: Migration INCOMPLETE - need to migrate data')

    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
