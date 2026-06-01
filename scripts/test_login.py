"""测试 API cookie 问题"""
import requests, sys, re

BASE = "http://localhost:8000"

s = requests.Session()

# 1. 直接 POST 登录，不过 follow_redirects
r = s.post(f"{BASE}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=False)
print(f"POST /login: {r.status_code}")
print(f"Headers: {dict(r.headers)}")
print(f"Cookies: {dict(s.cookies)}")
print(f"Content: {r.text[:300]}")

# 2. 如果有 Set-Cookie 头，显示它
for k, v in r.headers.items():
    if 'ookie' in k or 'ocation' in k:
        print(f"  {k}: {v}")

# 3. 尝试带 cookie 访问 API
if s.cookies:
    print(f"\n带 Cookie 访问 /api/part/1:")
    r2 = s.get(f"{BASE}/api/part/1")
    print(f"  {r2.status_code}: {r2.text[:200]}")
else:
    print("\n无法获取 Cookie，尝试直接用已知的 cookie 伪造")
    # 4. 尝试其他用户
    for user, pwd in [("sales", "sales"), ("tech", "tech"), ("test", "test")]:
        r = s.post(f"{BASE}/login", data={"username": user, "password": pwd}, allow_redirects=False)
        print(f"\nPOST /login ({user}/{pwd}): {r.status_code}, Cookies: {dict(s.cookies)}")
        if s.cookies:
            break

# 5. 检查 SSR 页面内容
r3 = s.get(f"{BASE}/sales/parts/pricing")
html = r3.text
count_match = re.search(r'(\d+)\s*件', html)
print(f"\nSSR 页面 (/sales/parts/pricing): {r3.status_code}")
if count_match:
    print(f"显示: {count_match.group(0)}")

# 检查卡片
if '<div class="list-card"' in html:
    print("有 list-card 元素")
else:
    print("没有 list-card 元素")
    # 看看 body 内容
    body = re.search(r'<div class="content">(.*?)(?:<button|<div class="drawer)', html, re.DOTALL)
    if body:
        print(f"内容区域前300: {body.group(1)[:300]}")
    else:
        print("未找到内容区域")

# 6. 直接检查 /api/part/1
print("\n/api/part/1 测试:")
r4 = s.get(f"{BASE}/api/part/1")
print(f"  {r4.status_code}: {r4.text[:200]}")
