#!/usr/bin/env python3
"""Check actual database schema to find tooling table."""

import os

import psycopg2

DB_HOST = os.environ["ZEPHYR_DB_HOST"]
DB_PORT = int(os.environ.get("ZEPHYR_DB_PORT", "5432"))
DB_NAME = os.environ.get("ZEPHYR_DB_NAME", "stamping_system")
DB_USER = os.environ.get("ZEPHYR_DB_USER", "postgres")
DB_PASSWORD = os.environ["ZEPHYR_DB_PASSWORD"]

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Find tables with 'tooling' or 'mold' in name
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND (table_name LIKE '%tooling%' OR table_name LIKE '%mold%')
    ORDER BY table_name
""")

print("=== Tooling/Mold Related Tables ===")
for row in cur.fetchall():
    table_name = row[0]
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    print(f"{table_name}: {count} rows")

# Check for customers table
cur.execute("SELECT COUNT(*) FROM customers")
customers_count = cur.fetchone()[0]
print(f"\ncustomers: {customers_count} rows")

cur.close()
conn.close()
