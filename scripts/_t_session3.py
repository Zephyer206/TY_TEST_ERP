# -*- coding: utf-8 -*-
"""检查登录逻辑和 session cookie"""
import urllib.request, urllib.parse, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# 拿 login 页面
resp = opener.open('http://127.0.0.1:8000/login', timeout=5)
print("Login page status:", resp.status)
print("Cookies from login page:", [(c.name, c.value[:30]) for c in jar])

# 尝试登录
data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request('http://127.0.0.1:8000/login', data=data)
try:
    resp = opener.open(req, timeout=10)
    print("\nAfter login POST:")
    print("  Status:", resp.status, "URL:", resp.url)
    print("  Cookies:", [(c.name, c.value[:30]) for c in jar])
    print("  Headers:", dict(resp.headers))
    body = resp.read(500)
    print("  Body:", body[:300])
except Exception as e:
    print("Login error:", e)
