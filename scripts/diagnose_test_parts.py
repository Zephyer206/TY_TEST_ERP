import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# 查 parts 表结构
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'parts' ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print('=== parts 表字段 ===')
for c in cols:
    print(f'  {c[0]}: {c[1]}')

# 查 quotes 表结构
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'quotes' ORDER BY ordinal_position;
""")
qcols = cur.fetchall()
print('\n=== quotes 表字段 ===')
for c in qcols:
    print(f'  {c[0]}: {c[1]}')

# 查找 TEST 零件
cur.execute('''
    SELECT id, part_number, internal_name, status
    FROM parts
    WHERE LOWER(part_number) LIKE '%test%' OR LOWER(internal_name) LIKE '%test%'
    ORDER BY id DESC
    LIMIT 20;
''')
parts = cur.fetchall()
print('\n=== TEST 零件列表 ===')
for p in parts:
    print(f'  part_id={p[0]}, part_number={p[1]!r}, name={p[2]!r}, status={p[3]}')

# 查 dies 表结构
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'dies' ORDER BY ordinal_position;
""")
die_cols = [c[0] for c in cur.fetchall()]
print(f'\n=== dies 表字段 ===')
print('  ' + ', '.join(die_cols))

# 查 die_parts 表结构
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'die_parts' ORDER BY ordinal_position;
""")
dp_cols = [c[0] for c in cur.fetchall()]
print(f'\n=== die_parts 表字段 ===')
print('  ' + ', '.join(dp_cols))

for p in parts:
    pid = p[0]
    # 查关联的 quotes（所有状态）
    cur.execute('''
        SELECT id, approval_status, is_deleted, quote_serial
        FROM quotes
        WHERE part_id = %s
        ORDER BY id;
    ''', (pid,))
    quotes = cur.fetchall()
    print(f'\n  零件 {p[1]} (id={pid}) 的报价单:')
    for q in quotes:
        print(f'    quote_id={q[0]}, status={q[1]}, is_deleted={q[2]}, serial={q[3]}')

    # 查关联的 die_parts / dies
    cur.execute('''
        SELECT dp.id, dp.die_id, d.mold_number
        FROM die_parts dp
        JOIN dies d ON dp.die_id = d.id
        WHERE dp.part_id = %s;
    ''', (pid,))
    dies = cur.fetchall()
    print(f'  模具关联: {dies}')

    # 查库存
    cur.execute('SELECT COUNT(*) FROM finished_inventory WHERE part_id = %s;', (pid,))
    fi = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM remnant_inventory WHERE part_id = %s;', (pid,))
    ri = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM production_logs WHERE part_id = %s;', (pid,))
    pl = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM part_aliases WHERE internal_part_id = %s;', (pid,))
    pa = cur.fetchone()[0]
    print(f'  库存 finished_inventory={fi}, remnant_inventory={ri}')
    print(f'  报工 production_logs={pl}, 别名 part_aliases={pa}')

conn.close()
