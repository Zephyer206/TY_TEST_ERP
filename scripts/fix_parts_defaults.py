# -*- coding: utf-8 -*-
"""修复迁移遗留问题：设置 parts.version/part_status 默认值，回填旧数据"""
import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system', user='postgres',
    password='thehaoshi5DE', host='localhost', port='5432'
)
conn.autocommit = True
cur = conn.cursor()

print("=== 1. 补充 parts.version 默认值为 V1.0 ===")
cur.execute("""
    ALTER TABLE parts
    ALTER COLUMN version SET DEFAULT 'V1.0';
""")
cur.execute("""
    UPDATE parts SET version = 'V1.0' WHERE version IS NULL;
""")
cur.execute("SELECT COUNT(*), COUNT(version) FROM parts")
total, with_ver = cur.fetchone()
print(f"  parts 表总行数={total}, 有 version 值={with_ver}")

print()
print("=== 2. 补充 parts.part_status 默认值为 ACTIVE ===")
cur.execute("""
    ALTER TABLE parts
    ALTER COLUMN part_status SET DEFAULT 'ACTIVE';
""")
cur.execute("""
    UPDATE parts SET part_status = 'ACTIVE' WHERE part_status IS NULL;
""")
cur.execute("SELECT COUNT(*), COUNT(part_status) FROM parts")
total2, with_st = cur.fetchone()
print(f"  parts 表总行数={total2}, 有 part_status 值={with_st}")

print()
print("=== 3. 验证联合唯一约束 ===")
cur.execute("""
    SELECT part_number, version, COUNT(*) as cnt
    FROM parts
    GROUP BY part_number, version
    HAVING COUNT(*) > 1;
""")
dups = cur.fetchall()
if not dups:
    print("  联合唯一约束正常：无重复 (part_number, version)")
else:
    print(f"  WARNING: 发现重复组合: {dups}")

print()
print("=== 4. 最终 parts 表字段快照 ===")
cur.execute("""
    SELECT column_name, column_default, is_nullable
    FROM information_schema.columns
    WHERE table_name='parts' AND column_name IN ('version', 'part_status')
    ORDER BY column_name
""")
for r in cur.fetchall():
    print(f"  {r[0]}: default={r[1]}, nullable={r[2]}")

print()
print("=== 5. 再次抽样验证 parts 数据 ===")
cur.execute("SELECT id, part_number, version, part_status FROM parts LIMIT 5")
for r in cur.fetchall():
    print(f"  id={r[0]} part={r[1]} version={r[2]} status={r[3]}")

conn.close()
print()
print("全部完成。")
