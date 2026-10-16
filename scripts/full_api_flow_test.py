"""
full_api_flow_test.py
=====================
模拟前端 POST -> GET 完整流程，用 urllib（标准库，无需安装 requests）。
"""

import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

from urllib.request import urlopen, Request, HTTPCookieProcessor, build_opener
from urllib.parse import urlencode
import json
import time

BASE = "http://localhost:8000"

# 带 cookie 的 opener
opener = build_opener(HTTPCookieProcessor())

def api_get(path):
    req = Request(f"{BASE}{path}")
    req.add_header("Content-Type", "application/json")
    try:
        resp = opener.open(req, timeout=10)
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)
    except Exception as e:
        return 0, {"error": str(e)}

def api_post(path, data_dict):
    body_bytes = json.dumps(data_dict).encode("utf-8")
    req = Request(f"{BASE}{path}", data=body_bytes)
    req.add_header("Content-Type", "application/json")
    try:
        resp = opener.open(req, timeout=10)
        resp_body = resp.read().decode("utf-8")
        return resp.status, json.loads(resp_body)
    except Exception as e:
        # HTTPError 会抛出异常，尝试读取错误体
        if hasattr(e, "read"):
            err_body = e.read().decode("utf-8")
            return e.code if hasattr(e, "code") else 0, {"error": str(e), "body": err_body[:500]}
        return 0, {"error": str(e)}

def api_post_form(path, data_dict):
    """模拟 form submit（登录用）"""
    body_bytes = urlencode(data_dict).encode("utf-8")
    req = Request(f"{BASE}{path}", data=body_bytes)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        resp = opener.open(req, timeout=10)
        resp_body = resp.read().decode("utf-8")
        return resp.status, resp_body
    except Exception as e:
        if hasattr(e, "read"):
            err_body = e.read().decode("utf-8")
            return e.code if hasattr(e, "code") else 0, err_body[:200]
        return 0, str(e)

# ── Step 0: 登录拿 cookie ──────────────────────────────────
print("=== Step 0: Login ===")
status, body = api_post_form("/login", {"username": "admin", "password": "123456"})
print(f"Login status={status}, body preview: {body[:100] if isinstance(body,str) else body}")

# ── Step 1: POST 新增记录 ─────────────────────────────────
unique_name = f"APIFlowTest_{int(time.time())}"
print(f"\n=== Step 1: POST '{unique_name}' ===")
status, body = api_post("/api/dict/treatments", {
    "name": unique_name,
    "calc_mode": "manual",
    "rate": 7.77,
    "unit": "Yuan/Pc",
})
print(f"POST status={status}")
print(f"POST body: {body}")

# ── Step 2: GET 查询 ─────────────────────────────────────
print(f"\n=== Step 2: GET immediately after POST ===")
status, body = api_get("/api/dict/treatments")
print(f"GET status={status}, code={body.get('code')}")
data = body.get("data", []) if isinstance(body, dict) else []
print(f"GET data count: {len(data)}")
found = [x for x in data if x.get("name") == unique_name]
if found:
    print(f"  FOUND: {found[0]}")
else:
    print(f"  NOT FOUND in GET result. All names: {[x.get('name') for x in data[:5]]}")
    if data:
        print(f"  First item: {data[0]}")

# ── Step 3: 直接调 db_service ────────────────────────────
print(f"\n=== Step 3: db_service direct call ===")
from app.services.db_service import get_all_treatments
svc_rows = get_all_treatments()
svc_found = [x for x in svc_rows if x.get("name") == unique_name]
print(f"db_service total={len(svc_rows)}, found={bool(svc_found)}")
if svc_found:
    print(f"  {svc_found[0]}")

# ── Step 4: 直查数据库 ───────────────────────────────────
print(f"\n=== Step 4: Direct DB query ===")
import psycopg2
from psycopg2.extras import RealDictCursor
DB = {"dbname": "stamping_system", "user": "postgres", "password": __import__("os").environ.get("ZEPHYR_DB_PASSWORD", ""), "host": "localhost", "port": "5432"}
conn = psycopg2.connect(**DB)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT id, name, calc_mode, rate, unit, is_active FROM treatment_dicts WHERE name = %s", (unique_name,))
db_row = cur.fetchone()
print(f"DB direct: {dict(db_row) if db_row else 'NOT FOUND'}")
conn.close()

print("\n=== SUMMARY ===")
if found:
    print("POST -> GET flow: OK")
else:
    print("POST -> GET flow: FAIL")
    if svc_found:
        print("db_service CAN see the data but GET API cannot.")
        print("ROOT CAUSE: GET API (list_treatments) has a different code path or DB target.")
    else:
        print("db_service also cannot see the data. Data not committed to DB.")
