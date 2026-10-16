# -*- coding: utf-8 -*-
"""迁移：为 prices 表添加 material_cost 字段"""
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', port='5432')
cur = conn.cursor()

# 1. 添加 material_cost 列（如果不存在）
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='prices' AND column_name='material_cost'
""")
if cur.fetchone():
    print("material_cost 列已存在，跳过")
else:
    cur.execute("""
        ALTER TABLE prices
        ADD COLUMN material_cost numeric(12,6)
    """)
    print("已添加 material_cost 列")

# 2. 用 net_weight * material_unit_price 回填已有行的 material_cost
cur.execute("""
    UPDATE prices
    SET material_cost = round((net_weight * material_unit_price)::numeric, 6)
    WHERE net_weight IS NOT NULL
      AND material_unit_price IS NOT NULL
      AND material_cost IS NULL
""")
updated = cur.rowcount
print(f"回填了 {updated} 条 material_cost")

conn.commit()
conn.close()
print("迁移完成")
