"""
server_side_diagnosis.py
========================
直接在 Python 进程内模拟完整的 FastAPI 请求上下文，
绕过 HTTP 层，彻底排查 list_treatments 的问题。
"""

import sys, os
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")
os.environ["DATABASE_URL"] = "postgresql://postgres:thehaoshi5DE@localhost:5432/stamping_system"

# 直接 import 并调用 db_service（绕过 HTTP）
import psycopg2
from psycopg2.extras import RealDictCursor
import json

DB = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432",
}

print("=" * 60)
print("模拟 list_treatments 路由逻辑（sales.py 第 511-534 行）")
print("=" * 60)

try:
    with psycopg2.connect(
        dbname="stamping_system",
        user="postgres",
        password="thehaoshi5DE",
        host="localhost",
        port="5432"
    ) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, calc_mode, rate, unit FROM treatment_dicts "
                "WHERE is_active = TRUE ORDER BY id"
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d['rate'] = float(d['rate'])
                result.append(d)
            print(f"\n直接 psycopg2 查询结果: {len(result)} 行")
            for r in result[:3]:
                print(f"  {r}")
            print(f"\nJSON 输出预览:")
            print(json.dumps({"code": 200, "data": result}, ensure_ascii=False)[:300])
except Exception as e:
    print(f"查询异常: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("调用 db_service.get_all_treatments()")
print("=" * 60)

from app.services.db_service import get_all_treatments, upsert_treatment
import time

svc_rows = get_all_treatments()
print(f"get_all_treatments() 返回: {len(svc_rows)} 行")
for r in svc_rows[:3]:
    print(f"  {r}")

# 检查 treatment_dicts 表是否有 is_active 字段
print()
print("=" * 60)
print("检查 treatment_dicts 表结构")
print("=" * 60)
conn = psycopg2.connect(**DB)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'treatment_dicts'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:20s} {row[1]:20s} default={row[2]}")
conn.close()

# 检查是否存在另一张表（如 surface_treatments）
print()
print("=" * 60)
print("检查是否存在 surface_treatments 表")
print("=" * 60)
conn2 = psycopg2.connect(**DB)
cur2 = conn2.cursor()
cur2.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    AND (table_name LIKE '%surface%' OR table_name LIKE '%treatment%')
""")
for row in cur2.fetchall():
    print(f"  找到表: {row[0]}")
cur2.execute("SELECT COUNT(*) FROM surface_treatments")
count = cur2.fetchone()[0]
print(f"  surface_treatments 行数: {count}")
conn2.close()

print("\n=== DONE ===")
