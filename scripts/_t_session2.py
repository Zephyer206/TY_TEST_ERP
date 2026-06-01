# -*- coding: utf-8 -*-
"""详细测试 API 认证问题"""
import urllib.request, urllib.parse, http.cookiejar, json

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# 先拿 login 页面的 CSRF token
resp = opener.open('http://127.0.0.1:8000/login', timeout=5)
print("Cookies after login page:", [(c.name, c.value[:20]) for c in jar])

# POST 登录 - 用 form data
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/login', data=data, method='POST')
req.add_header('Content-Type', 'application/x-www-form-urlencoded')
try:
    resp = opener.open(req, timeout=10)
    print("Login status:", resp.status, "URL:", resp.url)
    print("Cookies after login:", [(c.name, c.value[:20]) for c in jar])
except Exception as e:
    print("Login error:", e)

# 测试一个简单的 API
for path in ['/api/boss/customers', '/api/me', '/api/users']:
    jar2 = http.cookiejar.CookieJar()
    opener2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar2))
    opener2.open('http://127.0.0.1:8000/login', timeout=5)
    data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
    req = urllib.request.Request('http://127.0.0.1:8000/login', data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        opener2.open(req, timeout=10)
    except Exception as e:
        print(f"Login for {path} error:", e)
        continue
    try:
        req2 = urllib.request.Request(f'http://127.0.0.1:8000{path}')
        resp2 = opener2.open(req2, timeout=10)
        body = resp2.read(300)
        print(f"{path} -> {resp2.status}: {body[:200]}")
    except Exception as e:
        print(f"{path} -> ERROR: {e}")
