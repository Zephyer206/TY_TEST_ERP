#!/usr/bin/env python3
"""Check detailed status for Phase 1 corrections"""

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

print("="*70)
print("DETAILED STATUS CHECK")
print("="*70)

# Check tooling_number NULLs
print("\n1. tooling_number NULL count:")
cur.execute("SELECT COUNT(*) FROM tooling WHERE tooling_number IS NULL")
null_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM tooling")
total_count = cur.fetchone()[0]
print(f"   NULL: {null_count}/{total_count}")

# Check is_continuous distribution
print("\n2. is_continuous distribution:")
cur.execute("SELECT is_continuous, COUNT(*) FROM tooling GROUP BY is_continuous")
for row in cur.fetchall():
    print(f"   {row[0]}: {row[1]}")

# Check mold_type values
print("\n3. mold_type distribution (top 10):")
cur.execute("SELECT mold_type, COUNT(*) FROM tooling GROUP BY mold_type ORDER BY COUNT(*) DESC LIMIT 10")
for row in cur.fetchall():
    print(f"   {row[0]}: {row[1]}")

# Check excel_import_rows columns
print("\n4. excel_import_rows parsed columns:")
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'excel_import_rows'
    AND column_name LIKE 'parsed_%'
    ORDER BY column_name
""")
parsed_cols = [row[0] for row in cur.fetchall()]
print(f"   Found {len(parsed_cols)} parsed_* columns")
if 'parsed_is_continuous' not in parsed_cols:
    print("   [MISSING] parsed_is_continuous")
if 'parsed_position' not in parsed_cols:
    print("   [MISSING] parsed_position")

# Check part_customer_aliases constraints
print("\n5. part_customer_aliases constraints:")
cur.execute("""
    SELECT constraint_name, constraint_type
    FROM information_schema.table_constraints
    WHERE table_name = 'part_customer_aliases'
""")
for row in cur.fetchall():
    print(f"   {row[0]}: {row[1]}")

cur.execute("""
    SELECT is_nullable FROM information_schema.columns
    WHERE table_name = 'part_customer_aliases' AND column_name = 'customer_id'
""")
result = cur.fetchone()
print(f"   customer_id nullable: {result[0] if result else 'COLUMN NOT FOUND'}")

# Check tooling_parts constraints
print("\n6. tooling_parts structure:")
cur.execute("""
    SELECT column_name, is_nullable FROM information_schema.columns
    WHERE table_name = 'tooling_parts' AND column_name IN ('tooling_id', 'part_id', 'position')
    ORDER BY column_name
""")
for row in cur.fetchall():
    print(f"   {row[0]}: nullable={row[1]}")

cur.execute("""
    SELECT constraint_name FROM information_schema.table_constraints
    WHERE table_name = 'tooling_parts' AND constraint_type = 'UNIQUE'
""")
unique_constraints = cur.fetchall()
print(f"   Unique constraints: {len(unique_constraints)}")
for row in unique_constraints:
    print(f"     - {row[0]}")

cur.close()
conn.close()
