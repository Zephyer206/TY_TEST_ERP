"""
route_probe.py
==============
探测服务器实际注册的路由，验证 /api/dict/treatments 到底映射到哪里。
"""

import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

from urllib.request import urlopen, Request, HTTPCookieProcessor, build_opener
from urllib.parse import urlencode
import json

BASE = "http://localhost:8000"
opener = build_opener(HTTPCookieProcessor())

def login():
    body = urlencode({"username": "admin", "password": "123456"}).encode()
    req = Request(f"{BASE}/login", data=body)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    opener.open(req, timeout=10)

def get(path):
    req = Request(f"{BASE}{path}")
    req.add_header("Content-Type", "application/json")
    resp = opener.open(req, timeout=10)
    return resp.status, json.loads(resp.read().decode())

def get_raw(path):
    req = Request(f"{BASE}{path}")
    resp = opener.open(req, timeout=10)
    return resp.status, resp.read().decode()

# ── 1. 登录 ─────────────────────────────────────────────
login()
print("Logged in.")

# ── 2. 测试所有可能的路径变体 ──────────────────────────
paths_to_test = [
    "/api/dict/treatments",           # 正常路径（有 prefix）
    "/dict/treatments",               # 无 prefix
    "/api/api/dict/treatments",       # 双重 prefix
    "/treatments",                    # 最短
    "/api/dict/treatment",            # 单数
]
print("\n=== Route probe ===")
for path in paths_to_test:
    try:
        status, body = get(path)
        data_len = len(body.get("data", [])) if isinstance(body, dict) else -1
        print(f"  {path:40s} -> {status}, data_count={data_len}")
    except Exception as e:
        code = e.code if hasattr(e, "code") else "?"
        if hasattr(e, "read"):
            err = e.read().decode()[:80]
        else:
            err = str(e)[:80]
        print(f"  {path:40s} -> ERROR {code}: {err}")

# ── 3. 直接 import main.py 的 app，打印所有已注册路由 ──
print("\n=== Registered routes from main.py ===")
try:
    import main as main_module
    app = main_module.app
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            methods = getattr(route, "methods", {"GET"})
            routes.append(f"  {list(methods)} {route.path}")
    routes.sort()
    for r in routes:
        print(r)
except Exception as e:
    print(f"  Error reading main.py: {e}")

# ── 4. 打印 sales.py 注册到哪个 router ─────────────────
print("\n=== sales.py api_router details ===")
try:
    from app.api import sales as sales_module
    router = sales_module.api_router
    print(f"  prefix: {router.prefix}")
    print(f"  tags: {router.tags}")
    for route in router.routes:
        if hasattr(route, "path"):
            methods = getattr(route, "methods", {"GET"})
            print(f"  {list(methods)} {router.prefix}{route.path}")
except Exception as e:
    print(f"  Error: {e}")

# ── 5. 确认 main.py 是否正确包含了 sales api_router ──────
print("\n=== Check main.py includes sales router ===")
with open(r"c:\Users\Administrator\Desktop\Cloud-Stamping\main.py", "r", encoding="utf-8") as f:
    main_content = f.read()
    for line in main_content.split("\n"):
        if "sales" in line.lower() or "api_router" in line:
            print(f"  {line.strip()}")
