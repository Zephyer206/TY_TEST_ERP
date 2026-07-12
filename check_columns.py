#!/usr/bin/env python3
"""Quick check of actual database columns"""

import psycopg2

conn = psycopg2.connect(
    host="124.222.29.229", port=5432, database="stamping_system",
    user="postgres", password="thehaoshi5DE"
)

cur = conn.cursor()

print("CUSTOMERS columns:")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'customers'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:30} {row[1]:20} nullable={row[2]}")

print("\nPARTS columns (key ones):")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'parts' AND column_name IN ('part_number', 'internal_part_no', 'is_deleted', 'thickness')
    ORDER BY column_name
""")
for row in cur.fetchall():
    print(f"  {row[0]:30} {row[1]:20} nullable={row[2]}")

print("\nTOOLING columns (key ones):")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'tooling' AND column_name IN ('tooling_number', 'cavity_count', 'is_continuous', 'process_step_count')
    ORDER BY column_name
""")
for row in cur.fetchall():
    print(f"  {row[0]:30} {row[1]:20} nullable={row[2]}")

cur.close()
conn.close()
