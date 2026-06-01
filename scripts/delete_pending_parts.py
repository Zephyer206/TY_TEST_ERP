import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='thehaoshi5DE', host='localhost', port='5432')
conn.autocommit = True
cur = conn.cursor()

# Check all FK references to parts table using pg_catalog
print('=== Checking all FK references to parts ===')
cur.execute("""
    SELECT tc.table_name, tc.constraint_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND kcu.table_name IN (
          SELECT table_name FROM information_schema.tables
          WHERE table_schema = 'public'
            AND table_name NOT IN ('alembic_version', 'pg_stat_statements')
      );
""")
refs = cur.fetchall()
for row in refs:
    print(f'  {row[0]}.{row[2]} -> {row[1]}')

PART_IDS = (175, 176, 177, 178)

# Find and clear referencing FKs dynamically
for tbl, constraint, col in refs:
    try:
        cur.execute(f'SELECT 1 FROM "{tbl}" WHERE "{col}" IN %s LIMIT 1;', (PART_IDS,))
        exists = cur.fetchone() is not None
        if exists:
            cur.execute(f'UPDATE "{tbl}" SET "{col}" = NULL WHERE "{col}" IN %s;', (PART_IDS,))
            print(f'[OK] Cleared {cur.rowcount} rows in {tbl}.{col}')
    except Exception as e:
        print(f'[SKIP] {tbl}.{col}: {e}')

# Now delete parts
print('\n=== Deleting parts ===')
cur.execute("DELETE FROM parts WHERE id IN %s;", (PART_IDS,))
print(f'[OK] Deleted {cur.rowcount} parts: {PART_IDS}')

# Verify
cur.execute("SELECT id, part_number FROM parts ORDER BY id DESC;")
print('\n=== Remaining parts ===')
for row in cur.fetchall():
    print(f'  ID={row[0]}, part_number={row[1]}')

conn.close()
