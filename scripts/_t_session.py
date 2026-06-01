# -*- coding: utf-8 -*-
"""模拟登录并测试 boss API"""
import urllib.request, urllib.parse, http.cookiejar, json

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# 1. 访问 login 拿 session
opener.open('http://127.0.0.1:8000/login', timeout=5)
print("Step 1: Visited login page")

# 2. POST 登录
try:
    data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
    req = urllib.request.Request('http://127.0.0.1:8000/login', data=data, method='POST')
    resp = opener.open(req, timeout=10)
    print("Step 2: Login POST, status:", resp.status)
except Exception as e:
    print("Login error:", e)

# 3. 测试 boss/customers
for path in ['/api/boss/customers', '/api/boss/price-cards/55', '/boss/price-cards/55']:
    try:
        req = urllib.request.Request(f'http://127.0.0.1:8000{path}')
        resp = opener.open(req, timeout=15)
        body = resp.read(500)
        print(f"\n{path} -> status:{resp.status}")
        print(body[:300])
    except Exception as e:
        print(f"\n{path} -> ERROR: {e}")
