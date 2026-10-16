"""
requests_api_test.py
===================
用 requests 库精确测试 HTTP 会话行为。
"""

import sys, os
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:" + __import__("os").environ.get("ZEPHYR_DB_PASSWORD", "") + "@localhost:5432/stamping_system",
)

import requests
import json

BASE = "http://localhost:8000"
s = requests.Session()

print("=== 1. Login ===")
r = s.post(f"{BASE}/login", data={"username": "admin", "password": "123456"}, allow_redirects=True)
print(f"Login: {r.status_code}, Final URL: {r.url}")
print(f"Cookies: {dict(s.cookies)}")

print("\n=== 2. GET /api/dict/treatments ===")
r = s.get(f"{BASE}/api/dict/treatments")
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print(f"Body: {r.text[:500]}")
data = r.json()
print(f"JSON code: {data.get('code')}")
print(f"JSON data count: {len(data.get('data', []))}")
print(f"JSON data[:3]: {data.get('data', [])[:3]}")

print("\n=== 3. POST /api/dict/treatments ===")
import time
test_name = f"RequestsTest_{int(time.time())}"
r = s.post(f"{BASE}/api/dict/treatments", json={
    "name": test_name,
    "calc_mode": "manual",
    "rate": 8.88,
    "unit": "Yuan/Pc",
})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:300]}")
post_data = r.json()
print(f"code: {post_data.get('code')}, data: {post_data.get('data')}")

print("\n=== 4. GET again after POST ===")
r = s.get(f"{BASE}/api/dict/treatments")
print(f"Status: {r.status_code}")
data2 = r.json()
print(f"code: {data2.get('code')}, count: {len(data2.get('data', []))}")
found = [x for x in data2.get("data", []) if x.get("name") == test_name]
print(f"Found '{test_name}': {bool(found)}")
if not found:
    print(f"All names in GET: {[x.get('name') for x in data2.get('data', [])[:5]]}")

print("\n=== 5. Compare with no-session GET ===")
s2 = requests.Session()
r3 = s2.get(f"{BASE}/api/dict/treatments")
print(f"No-session status: {r3.status_code}, body: {r3.text[:100]}")

print("\n=== 6. GET /dashboard (sanity check) ===")
r = s.get(f"{BASE}/dashboard")
print(f"Status: {r.status_code}, url: {r.url}")
