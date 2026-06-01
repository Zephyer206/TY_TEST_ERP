"""直接检查 SSR 页面 HTML 内容"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\Cloud-Stamping")

# 用服务器内置的方式模拟请求（绕过 Cookie）
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# 1. 登录
resp = client.post("/login", data={"username": "admin_mgr_001", "password": "something"})
print(f"登录: {resp.status_code}, location: {resp.headers.get('location', 'none')}")

# 用 session cookie
cookies = resp.cookies
print(f"Cookies set: {dict(cookies)}")

# 2. SSR 页面
resp2 = client.get("/sales/parts/pricing", cookies=cookies)
print(f"\nSSR /sales/parts/pricing: {resp2.status_code}")
html = resp2.text

import re
count = re.search(r'(\d+)\s*件', html)
print(f"显示数量: {count.group(0) if count else '未找到'}")

# 卡片
if '<div class="list-card"' in html:
    print("有 list-card 元素")
else:
    print("没有 list-card")
    if '<div class="empty-state"' in html:
        print("  显示 empty-state")
    if '<div class="content">' in html:
        # 找到 content 开始
        start = html.find('<div class="content">')
        end = html.find('<button class="fab"', start)
        if start >= 0 and end >= 0:
            section = html[start:end]
            print(f"\n--- content 区域 ---\n{section[:500]}\n--- end ---")

# 3. API 调用
resp3 = client.get("/api/part/1", cookies=cookies)
print(f"\nAPI /api/part/1: {resp3.status_code}")
print(f"响应: {resp3.text[:200]}")
