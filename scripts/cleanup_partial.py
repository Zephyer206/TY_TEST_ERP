# -*- coding: utf-8 -*-
"""清理残留表"""
import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres',
                        password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost', port='5432')
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name IN ('molds','bom_routings','sample_tasks')")
existing = [r[0] for r in cur.fetchall()]
print("现有表:", existing)

for t in ['sample_tasks', 'bom_routings', 'molds']:
    if t in existing:
        cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
        print(f"DROP IF EXISTS {t} — OK")

# 清理残留索引
for idx in ['idx_molds_number', 'idx_molds_status', 'idx_molds_part_id',
            'idx_bom_part_seq', 'idx_bom_mold_id',
            'idx_sample_part_id', 'idx_sample_status']:
    cur.execute(f"DROP INDEX IF EXISTS {idx} CASCADE")
    print(f"DROP INDEX IF EXISTS {idx} — OK")

conn.close()
print("清理完成")
