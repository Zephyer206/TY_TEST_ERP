"""
trace_upsert.py
===============
在 upsert_treatment 内部加追踪，打印每一步返回值。
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

def trace_upsert_treatment(name, calc_mode, rate, unit):
    """带追踪的 upsert_treatment。"""
    unique_name = f"TraceTest_{int(time.time())}"

    print(f"[TRACE] Calling _ensure_treatment_dicts_table()")
    # 直接内联 ensure 逻辑（避免重入问题）
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print(f"[TRACE] Connection opened, executing INSERT...")
    cur.execute(f"""
        INSERT INTO treatment_dicts (name, calc_mode, rate, unit)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            calc_mode = EXCLUDED.calc_mode,
            rate      = EXCLUDED.rate,
            unit      = EXCLUDED.unit
        RETURNING id, name, calc_mode, rate, unit
    """, (unique_name, calc_mode, float(rate), unit))

    print(f"[TRACE] Executed. Now calling cur.fetchone()...")
    row = cur.fetchone()
    print(f"[TRACE] cur.fetchone() = {repr(row)}")
    print(f"[TRACE] type(row) = {type(row)}")

    print(f"[TRACE] Now calling conn.commit()...")
    conn.commit()
    print(f"[TRACE] Committed.")

    print(f"[TRACE] Calling dict(row)...")
    try:
        result = dict(row)
        print(f"[TRACE] dict(row) = {repr(result)}")
    except Exception as e:
        print(f"[TRACE] dict(row) FAILED: {type(e).__name__}: {e}")
        result = None

    conn.close()
    print(f"[TRACE] Connection closed.")
    return result

# ── 运行追踪 ────────────────────────────────────────────────
print("=== TRACE upsert_treatment ===")
result = trace_upsert_treatment("manual", 1.11, "Yuan/Pc")
print(f"\nFinal result: {repr(result)}")
print(f"result.get('code'): {repr(result.get('code')) if result else 'N/A'}")
print(f"result.get('id'): {repr(result.get('id')) if result else 'N/A'}")
print(f"result.get('rate'): {repr(result.get('rate')) if result else 'N/A'}")

# ── 验证数据是否存在 ───────────────────────────────────────
from app.services.db_service import get_all_treatments
print(f"\n=== VERIFY: get_all_treatments() ===")
rows = get_all_treatments()
print(f"Total rows: {len(rows)}")
for r in rows:
    if "TraceTest" in str(r.get("name", "")):
        print(f"  FOUND: {r}")
