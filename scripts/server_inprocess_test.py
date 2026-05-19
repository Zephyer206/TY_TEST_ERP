"""
server_inprocess_test.py
========================
在 FastAPI 服务器进程内直接 import db_service，打印真实返回值，
绕过所有 HTTP 层，精确确认 get_all_treatments() 在服务器环境下的行为。
"""

import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

TRACE = r"c:\Users\Administrator\Desktop\Cloud-Stamping\scripts\_server_test.log"

def trace(msg):
    with open(TRACE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ── Step 1: 模拟 sales.py 的 import ────────────────────────
trace("=== In-process test ===")
trace(f"sys.path[0]: {sys.path[0]}")

# 模拟 sales.py 里的导入顺序
trace("Importing app.services.db_service...")
import app.services.db_service as dbs
trace(f"dbs module id: {id(dbs)}")
trace(f"dbs.get_all_treatments id: {id(dbs.get_all_treatments)}")

# ── Step 2: 直接调用 ───────────────────────────────────────
trace("Calling dbs.get_all_treatments()...")
result = dbs.get_all_treatments()
trace(f"Result type: {type(result)}")
trace(f"Result length: {len(result)}")
trace(f"Result first item: {result[0] if result else 'EMPTY'}")

# ── Step 3: 模拟 list_treatments 路由逻辑 ─────────────────
trace("Simulating list_treatments logic...")
trace(f"get_all_treatments returned: {result}")
if result is None:
    trace("WARNING: get_all_treatments returned None!")
elif len(result) == 0:
    trace("WARNING: get_all_treatments returned empty list!")
else:
    trace(f"OK: got {len(result)} rows")

# ── Step 4: 检查 _ensure_treatment_dicts_table ────────────
trace("Calling _ensure_treatment_dicts_table() directly...")
dbs._ensure_treatment_dicts_table()
trace("Done. Now calling get_all_treatments() again...")
result2 = dbs.get_all_treatments()
trace(f"Result2 length: {len(result2)}")

# ── Step 5: 读回 TRACE 文件并打印 ─────────────────────────
with open(TRACE, "r", encoding="utf-8") as f:
    print(f.read())
