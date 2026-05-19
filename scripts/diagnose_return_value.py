"""
diagnose_return_value.py
=========================
打印 upsert_treatment 内部原始返回值。
"""

import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

import psycopg2
from psycopg2.extras import RealDictCursor
import time

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432",
}

unique_name = f"DiagTest_{int(time.time())}"

# ── 直接模拟 upsert_treatment 内部逻辑，打印中间值 ───────
print(f"Test name: {unique_name}")

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    INSERT INTO treatment_dicts (name, calc_mode, rate, unit)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (name) DO UPDATE SET
        calc_mode = EXCLUDED.calc_mode,
        rate      = EXCLUDED.rate,
        unit      = EXCLUDED.unit
    RETURNING id, name, calc_mode, rate, unit
""", (unique_name, "manual", 7.77, "Yuan/Pc"))

row = cur.fetchone()
print(f"\n[1] cur.fetchone() raw value: {repr(row)}")
print(f"[2] type(row): {type(row)}")

conn.commit()
print(f"[3] committed")

conn.close()

# ── 模拟 dict(row) 转换 ──────────────────────────────────
conn2 = psycopg2.connect(**DB_CONFIG)
cur2 = conn2.cursor(cursor_factory=RealDictCursor)
cur2.execute("SELECT id, name, calc_mode, rate, unit FROM treatment_dicts WHERE name = %s", (unique_name,))
row2 = cur2.fetchone()
print(f"\n[4] New connection fetch: {repr(row2)}")
if row2:
    d = dict(row2)
    print(f"[5] dict(row): {d}")
    print(f"[6] d['id']: {d['id']}, d['rate']: {d['rate']}, type: {type(d['rate'])}")
conn2.close()

print("\n=== Done ===")
