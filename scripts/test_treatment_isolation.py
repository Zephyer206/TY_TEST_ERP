"""
test_treatment_isolation.py
=============================
直接端到端测试 upsert_treatment + get_all_treatments 事务隔离。
"""

import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

from app.services.db_service import upsert_treatment, get_all_treatments
import time

def safe_str(obj):
    """Windows GBK safe string representation."""
    return repr(obj)

# ── 测试 1：读取当前所有数据 ────────────────────────────────
print("=== TEST 1: Read current data ===")
rows = get_all_treatments()
print(f"get_all_treatments() returned {len(rows)} rows")
for r in rows:
    print(f"  id={r['id']} name={safe_str(r['name'])} rate={r['rate']} type={type(r['rate']).__name__}")

# ── 测试 2：新增一条带唯一名的记录 ───────────────────────
unique_name = f"TestTreat_{int(time.time())}"
print(f"\n=== TEST 2: Insert '{unique_name}' ===")
try:
    result = upsert_treatment(
        name=unique_name,
        calc_mode="manual",
        rate=9.99,
        unit="Yuan/Pc",
    )
    print(f"upsert_treatment returned: code={result.get('code')}")
    data = result.get("data")
    print(f"  data keys: {list(data.keys()) if data else None}")
    print(f"  rate type: {type(data['rate']).__name__ if data else None}")
    print(f"  rate value: {data['rate'] if data else None}")
except Exception as e:
    print(f"EXCEPTION in upsert_treatment: {type(e).__name__}: {e}")

# ── 测试 3：立即读取，验证能否查到刚插入的数据 ───────────
print(f"\n=== TEST 3: Immediate read (transaction isolation check) ===")
rows_after = get_all_treatments()
print(f"get_all_treatments() returned {len(rows_after)} rows")
found = [r for r in rows_after if r["name"] == unique_name]
if found:
    print(f"OK: Found inserted record id={found[0]['id']} name={found[0]['name']!r}")
    print(f"    rate type: {type(found[0]['rate']).__name__}, value: {found[0]['rate']}")
else:
    print(f"FAIL: Cannot find '{unique_name}' in result")

# ── 测试 4：精确重现前端 POST → GET 序列 ──────────────────
print(f"\n=== TEST 4: Reproduce frontend POST -> GET sequence ===")
test_name = f"Reproduce_{int(time.time())}"
print(f"POST: upsert_treatment('{test_name}', rate=5.55)")
post_result = upsert_treatment(test_name, "net_weight", 5.55, "Yuan/kg")
print(f"  code={post_result.get('code')}, data={post_result.get('data')}")

print(f"GET: get_all_treatments()")
get_result = get_all_treatments()
found_in_get = [r for r in get_result if r["name"] == test_name]
print(f"  Returned {len(get_result)} rows")
if found_in_get:
    print(f"  OK: Found id={found_in_get[0]['id']}, rate={found_in_get[0]['rate']} (type={type(found_in_get[0]['rate']).__name__})")
else:
    print(f"  FAIL: Cannot find '{test_name}'")

# ── 测试 5：检查 Decimal 序列化 ───────────────────────────
print(f"\n=== TEST 5: JSON serialization of Decimal ===")
from fastapi.encoders import jsonable_encoder
test_data = {"code": 0, "data": result.get("data")}
try:
    serialized = jsonable_encoder(test_data)
    import json
    json_str = json.dumps(serialized, ensure_ascii=False)
    print(f"  JSON serialization: OK")
    print(f"  JSON output: {json_str[:200]}")
except Exception as e:
    print(f"  JSON serialization FAILED: {type(e).__name__}: {e}")

print("\n=== DONE ===")
