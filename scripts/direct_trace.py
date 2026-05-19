"""
direct_trace.py
==============
直接在 db_service.py 的 upsert_treatment 函数里加一行追踪文件写入，
绕过所有 import 问题，直接确认返回值。
"""

import sys, os, time
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

TRACE_FILE = r"c:\Users\Administrator\Desktop\Cloud-Stamping\scripts\upsert_trace.log"

# ── 直接 patch upsert_treatment 来追踪 ───────────────────────
import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432",
}

def traced_upsert(name, calc_mode, rate, unit):
    ts = time.strftime("%H:%M:%S")
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] START upsert_treatment({name}, {calc_mode}, {rate}, {unit})\n")

    # 直接内联 upsert_treatment 逻辑
    # Step 1: _ensure_treatment_dicts_table (简化版，直接查)
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Step 2: INSERT
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] EXECUTING INSERT...\n")

    cur.execute("""
        INSERT INTO treatment_dicts (name, calc_mode, rate, unit)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            calc_mode = EXCLUDED.calc_mode,
            rate      = EXCLUDED.rate,
            unit      = EXCLUDED.unit
        RETURNING id, name, calc_mode, rate, unit
    """, (name, calc_mode, float(rate), unit))

    row = cur.fetchone()
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] cur.fetchone() = {repr(row)}\n")
        f.write(f"[{ts}] type(row) = {type(row)}\n")

    conn.commit()
    conn.close()

    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] committed\n")

    # Step 3: 构造返回值
    result = {"code": 0, "data": dict(row)}
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] result = {repr(result)}\n")

    return result

# ── 运行 ───────────────────────────────────────────────────
name = f"DirectTrace_{int(time.time())}"
print(f"Running traced upsert: {name}")
result = traced_upsert(name, "manual", 3.33, "Yuan/Pc")
print(f"Result: code={result.get('code')}, data={result.get('data')}")

# ── 验证 ───────────────────────────────────────────────────
from app.services.db_service import get_all_treatments
rows = get_all_treatments()
found = [r for r in rows if r["name"] == name]
print(f"Verification: {'FOUND' if found else 'NOT FOUND'}, total rows={len(rows)}")

print(f"\nTrace file: {TRACE_FILE}")
with open(TRACE_FILE, "r", encoding="utf-8") as f:
    print(f.read())
