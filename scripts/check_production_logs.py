import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='thehaoshi5DE',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# 检查 production_logs 表结构
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'production_logs' ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print('=== production_logs 表字段 ===')
for c in cols:
    print(f'  {c[0]}: {c[1]}')

# 检查 sf_production_logs 和 production_logs 的关系
cur.execute("""
    SELECT 1 FROM sf_production_logs sfp
    JOIN production_logs pl ON sfp.work_order_id = pl.id
    WHERE pl.part_id = 158
    LIMIT 1;
""")
rel = cur.fetchone()
print(f'\nsf_production_logs 和 production_logs 关联: {"有" if rel else "无"}')

conn.close()
