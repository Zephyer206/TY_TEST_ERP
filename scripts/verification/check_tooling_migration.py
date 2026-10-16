#!/usr/bin/env python3
"""Check tooling_number migration status"""

import os

import psycopg2

conn = psycopg2.connect(
    host=os.environ["ZEPHYR_DB_HOST"],
    port=int(os.environ.get("ZEPHYR_DB_PORT", "5432")),
    database=os.environ.get("ZEPHYR_DB_NAME", "stamping_system"),
    user=os.environ.get("ZEPHYR_DB_USER", "postgres"),
    password=os.environ["ZEPHYR_DB_PASSWORD"],
)

cur = conn.cursor()

print("Tooling number migration status:")
cur.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(tooling_no) as has_tooling_no,
        COUNT(tooling_number) as has_tooling_number,
        COUNT(*) FILTER (WHERE tooling_no IS NOT NULL AND tooling_number IS NULL) as need_migration,
        COUNT(*) FILTER (WHERE tooling_no IS NOT NULL AND tooling_number IS NOT NULL
                         AND tooling_no != tooling_number) as mismatch
    FROM tooling
""")
row = cur.fetchone()
print(f"  Total: {row[0]}")
print(f"  Has tooling_no: {row[1]}")
print(f"  Has tooling_number: {row[2]}")
print(f"  Need migration: {row[3]}")
print(f"  Mismatch: {row[4]}")

# Check for duplicates in tooling_no that need migration
cur.execute("""
    SELECT tooling_no, COUNT(*)
    FROM tooling
    WHERE tooling_no IS NOT NULL AND tooling_number IS NULL
    GROUP BY tooling_no
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 5
""")
dups = cur.fetchall()
if dups:
    print(f"\nDuplicates in tooling_no (need migration): {len(dups)}")
    for dup, count in dups:
        print(f"  {dup}: {count} rows")

# Check if index exists
cur.execute("""
    SELECT indexname FROM pg_indexes
    WHERE tablename = 'tooling' AND indexname = 'idx_tooling_number'
""")
if cur.fetchone():
    print("\nidx_tooling_number index exists")
else:
    print("\nidx_tooling_number index NOT exists")

cur.close()
conn.close()
