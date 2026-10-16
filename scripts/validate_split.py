# -*- coding: utf-8 -*-
"""迁移后验证脚本"""
import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system', user='postgres',
    password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost', port='5432'
)
conn.autocommit = True
cur = conn.cursor()

print("=== 验证1: quotes 表行数 ===")
cur.execute("SELECT COUNT(*) FROM quotes")
print(f"quotes 行数: {cur.fetchone()[0]}")

print()
print("=== 验证2: parts 表现有字段 ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='parts' ORDER BY column_name")
for r in cur.fetchall():
    print(f"  {r[0]}")

print()
print("=== 验证3: quotes 表字段 ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='quotes' ORDER BY column_name")
for r in cur.fetchall():
    print(f"  {r[0]}")

print()
print("=== 验证4: 抽样检查 quotes 数据 ===")
cur.execute("""
    SELECT q.id, q.quote_serial, q.approval_status, q.final_price, p.part_number
    FROM quotes q JOIN parts p ON q.part_id = p.id
    LIMIT 5
""")
for r in cur.fetchall():
    print(f"  id={r[0]} serial={r[1]} status={r[2]} price={r[3]} part={r[4]}")

print()
print("=== 验证5: parts.version / part_status 字段值 ===")
cur.execute("SELECT id, part_number, version, part_status FROM parts LIMIT 5")
for r in cur.fetchall():
    print(f"  id={r[0]} part_number={r[1]} version={r[2]} status={r[3]}")

conn.close()
