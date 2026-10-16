import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# 检查 production_plans 表
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'production_plans' ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print('=== production_plans 表字段 ===')
for c in cols:
    print(f'  {c[0]}: {c[1]}')

# 检查有哪些表引用了 parts.id
cur.execute("""
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND kcu.column_name = 'part_id'
      AND tc.table_schema = 'public';
""")
fks = cur.fetchall()
print('\n=== 引用 parts.part_id 的外键 ===')
for f in fks:
    print(f'  {f[0]}.{f[1]}')

# 检查 plan_machines 表
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'plan_machines' ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print('\n=== plan_machines 表字段 ===')
for c in cols:
    print(f'  {c[0]}: {c[1]}')

conn.close()
