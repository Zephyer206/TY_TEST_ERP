#!/usr/bin/env python3
"""Fix remaining migration issues"""

import psycopg2

conn = psycopg2.connect(
    host="124.222.29.229", port=5432, database="stamping_system",
    user="postgres", password="thehaoshi5DE"
)

cur = conn.cursor()

print("Fixing customers table...")
# Check and add missing columns
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'customers' AND column_name = 'short_name'
""")
if not cur.fetchone():
    cur.execute("""
        ALTER TABLE customers
        ADD COLUMN short_name VARCHAR(100),
        ADD COLUMN contact_person VARCHAR(100),
        ADD COLUMN contact_phone VARCHAR(50),
        ADD COLUMN contact_email VARCHAR(100),
        ADD COLUMN address TEXT,
        ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    """)
    print("  [OK] Added missing columns to customers")
else:
    print("  [SKIP] customers already has target columns")

conn.commit()

print("Fixing parts table...")
# Make part_number nullable
cur.execute("""
    SELECT is_nullable FROM information_schema.columns
    WHERE table_name = 'parts' AND column_name = 'part_number'
""")
if cur.fetchone()[0] == 'NO':
    cur.execute("ALTER TABLE parts ALTER COLUMN part_number DROP NOT NULL")
    print("  [OK] Made parts.part_number nullable")
else:
    print("  [SKIP] parts.part_number already nullable")

# Add is_deleted if missing
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'parts' AND column_name = 'is_deleted'
""")
if not cur.fetchone():
    cur.execute("ALTER TABLE parts ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE")
    print("  [OK] Added parts.is_deleted")
else:
    print("  [SKIP] parts.is_deleted already exists")

conn.commit()

print("\nVerifying fixes...")
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'customers' AND column_name IN ('customer_code', 'is_active', 'updated_at')
""")
customer_cols = [row[0] for row in cur.fetchall()]
print(f"  customers has: {customer_cols}")

cur.execute("""
    SELECT column_name, is_nullable FROM information_schema.columns
    WHERE table_name = 'parts' AND column_name IN ('part_number', 'is_deleted')
""")
parts_cols = cur.fetchall()
print(f"  parts columns: {parts_cols}")

cur.close()
conn.close()

print("\n[OK] Migration fixes complete")
