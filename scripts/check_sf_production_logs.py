import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# 检查 sf_production_logs 表结构
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'sf_production_logs' ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print('=== sf_production_logs 表字段 ===')
for c in cols:
    print(f'  {c[0]}: {c[1]}')

conn.close()
