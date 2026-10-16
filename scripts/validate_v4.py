# -*- coding: utf-8 -*-
"""阶段二迁移后验证"""
import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres',
                         password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost', port='5432')
conn.autocommit = True
cur = conn.cursor()

print("=" * 55)
print("  阶段二迁移验证 (molds / bom_routings / sample_tasks)")
print("=" * 55)

tables = ['molds', 'bom_routings', 'sample_tasks']
for t in tables:
    cur.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{t}' ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    print(f"\n[{t}] {len(cols)} 列:")
    for c in cols:
        print(f"    {c}")

# 检查索引
print("\n[索引检查]")
for t in tables:
    cur.execute(f"""
        SELECT indexname, indexdef FROM pg_indexes
        WHERE tablename = '{t}'
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")

# 检查约束
print("\n[约束检查]")
for t in tables:
    cur.execute(f"""
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint WHERE conrelid = '{t}'::regclass
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")

# 检查外键
print("\n[外键检查]")
for t in tables:
    cur.execute(f"""
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = '{t}'::regclass AND contype = 'f'
    """)
    for r in cur.fetchall():
        print(f"  FK {r[0]}: {r[1]}")

print("\n" + "=" * 55)
print("  验证完毕")
print("=" * 55)
conn.close()
