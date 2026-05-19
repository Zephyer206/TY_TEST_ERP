"""
deep_inspect.py
===============
深入检查 GET 响应：headers、content-type、完整 body。
"""

import sys, os
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

import requests
import time

BASE = "http://localhost:8000"
s = requests.Session()

# 登录
s.post(f"{BASE}/login", data={"username": "admin", "password": "123456"}, allow_redirects=True)

print("=== Deep inspect GET /api/dict/treatments ===")
r = s.get(f"{BASE}/api/api/dict/treatments")   # double /api
print(f"Path: /api/api/dict/treatments")
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print(f"Body raw: {r.text}")
print(f"Body JSON: {r.json()}")

print()
print("=== Also test single /api ===")
r2 = s.get(f"{BASE}/api/dict/treatments")       # single /api
print(f"Path: /api/dict/treatments")
print(f"Status: {r2.status_code}")
print(f"Body: {r2.text[:200]}")

# 查所有已注册路由
print()
print("=== Import main.app and list all routes ===")
try:
    import main
    app = main.app
    api_routes = []
    for route in app.routes:
        if hasattr(route, "path") and "/dict" in route.path or (hasattr(route, "path") and "/treatment" in route.path):
            methods = list(getattr(route, "methods", {"GET"}))
            api_routes.append(f"  {methods} {route.path}")
    for r in sorted(api_routes):
        print(r)
except Exception as e:
    print(f"Error: {e}")

# 查 sales.py api_router
print()
print("=== Check sales.api_router routes ===")
try:
    from app.api import sales
    for route in sales.api_router.routes:
        if hasattr(route, "path"):
            methods = list(getattr(route, "methods", {"GET"}))
            print(f"  {methods} prefix='{sales.api_router.prefix}' + path='{route.path}' = '/{route.path}'")
except Exception as e:
    print(f"Error: {e}")
