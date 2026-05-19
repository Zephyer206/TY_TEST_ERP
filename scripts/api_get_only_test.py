"""
api_get_only_test.py
====================
只测 GET，查清楚它到底在查什么。
"""

from urllib.request import urlopen, Request, HTTPCookieProcessor, build_opener
from urllib.parse import urlencode
import json

BASE = "http://localhost:8000"

# ── 不登录直接 GET ───────────────────────────────────────
print("=== GET without login ===")
req = Request(f"{BASE}/api/dict/treatments")
req.add_header("Content-Type", "application/json")
try:
    resp = urlopen(req, timeout=10)
    body = resp.read().decode("utf-8")
    print(f"Status: {resp.status}")
    print(f"Body: {body[:500]}")
except Exception as e:
    if hasattr(e, "read"):
        err = e.read().decode("utf-8")
        print(f"HTTPError code={e.code}: {err[:300]}")
    else:
        print(f"Error: {e}")

# ── 登录后再 GET ─────────────────────────────────────────
print("\n=== GET with login cookie ===")
opener = build_opener(HTTPCookieProcessor())

# 登录
login_body = urlencode({"username": "admin", "password": "123456"}).encode("utf-8")
login_req = Request(f"{BASE}/login", data=login_body)
login_req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    lr = opener.open(login_req, timeout=10)
    print(f"Login status: {lr.status}")
    print(f"Cookies after login: {dict(opener.cookiejar)}")
except Exception as e:
    if hasattr(e, "read"):
        print(f"Login error: {e.read().decode()[:200]}")
    else:
        print(f"Login error: {e}")

# GET with cookie
get_req = Request(f"{BASE}/api/dict/treatments")
get_req.add_header("Content-Type", "application/json")
try:
    gr = opener.open(get_req, timeout=10)
    body = gr.read().decode("utf-8")
    data = json.loads(body)
    print(f"GET status: {gr.status}")
    print(f"GET code: {data.get('code')}")
    print(f"GET data count: {len(data.get('data', []))}")
    print(f"First 3: {data.get('data', [])[:3]}")
except Exception as e:
    if hasattr(e, "read"):
        err = e.read().decode("utf-8")
        print(f"GET Error code={e.code if hasattr(e,'code') else '?'}: {err[:300]}")
    else:
        print(f"GET Error: {e}")

# ── 直接用 requests 库测试（如果安装的话）─────────────────
print("\n=== Attempting with requests library ===")
try:
    import requests
    s = requests.Session()
    r_login = s.post(f"{BASE}/login", data={"username": "admin", "password": "123456"})
    print(f"requests login: {r_login.status_code}, cookies: {dict(s.cookies)}")
    r_get = s.get(f"{BASE}/api/dict/treatments")
    print(f"requests GET: {r_get.status_code}, code={r_get.json().get('code')}, count={len(r_get.json().get('data',[]))}")
    print(f"Full GET body: {r_get.text[:400]}")
except ImportError:
    print("requests not installed, skipping")
except Exception as e:
    print(f"requests error: {e}")
