import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='thehaoshi5DE', host='localhost', port='5432')
conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)

print('=== quotes 表字段 ===')
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'quotes' ORDER BY ordinal_position;")
for r in cur.fetchall():
    print(f'  {r["column_name"]}: {r["data_type"]}')

print('\n=== quotes 示例（最新1条） ===')
cur.execute("SELECT * FROM quotes ORDER BY id DESC LIMIT 1;")
row = cur.fetchone()
if row:
    for k, v in row.items():
        print(f'  {k}: {v}')

print('\n=== production_plans 字段 ===')
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'production_plans' ORDER BY ordinal_position;")
for r in cur.fetchall():
    print(f'  {r["column_name"]}')

print('\n=== molds 表字段 ===')
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'molds' ORDER BY ordinal_position;")
for r in cur.fetchall():
    print(f'  {r["column_name"]}')

print('\n=== mold_parts 表字段 ===')
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'mold_parts' ORDER BY ordinal_position;")
for r in cur.fetchall():
    print(f'  {r["column_name"]}')

conn.close()
