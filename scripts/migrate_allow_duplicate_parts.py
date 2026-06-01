import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='thehaoshi5DE', host='localhost', port='5432')
conn.autocommit = True
cur = conn.cursor()

print('=== Step 1: Add remark column ===')
# Check if column already exists
cur.execute("""
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'parts' AND column_name = 'remark';
""")
if cur.fetchone():
    print('[SKIP] remark column already exists')
else:
    cur.execute("""
        ALTER TABLE parts
        ADD COLUMN remark VARCHAR(200) NOT NULL DEFAULT '';
    """)
    print('[OK] Added remark column')

print('\n=== Step 2: Set remark from internal_name for existing rows ===')
cur.execute("""
    UPDATE parts SET remark = COALESCE(internal_name, '')
    WHERE remark = '';
""")
print(f'[OK] Updated {cur.rowcount} rows')

print('\n=== Step 3: Drop unique constraint on part_number ===')
# Check if constraint exists
cur.execute("""
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'parts' AND constraint_name = 'parts_part_number_key';
""")
if cur.fetchone():
    cur.execute("ALTER TABLE parts DROP CONSTRAINT parts_part_number_key;")
    print('[OK] Dropped parts_part_number_key')
else:
    print('[SKIP] parts_part_number_key already removed')

print('\n=== Step 4: Verify constraints ===')
cur.execute("""
    SELECT constraint_name, constraint_type
    FROM information_schema.table_constraints
    WHERE table_name = 'parts' AND constraint_type IN ('UNIQUE', 'PRIMARY KEY')
    ORDER BY constraint_type, constraint_name;
""")
print('Current unique constraints:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

print('\n=== Step 5: Verify remark column ===')
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'parts' AND column_name = 'remark';
""")
row = cur.fetchone()
print(f'  {row[0]}: {row[1]}, nullable={row[2]}, default={row[3]}')

conn.close()
print('\n[ALL DONE] Migration completed successfully')
