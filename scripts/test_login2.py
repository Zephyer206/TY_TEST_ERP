"""诊断登录 Cookie 问题"""
import requests, re

BASE = "http://localhost:8000"
s = requests.Session()

# POST 登录，不过 follow_redirects，查看原始响应头
r = s.post(f"{BASE}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=False)
print(f"POST /login: {r.status_code}")
for k, v in r.headers.items():
    k_lower = k.lower()
    if 'ookie' in k_lower or 'ocation' in k_lower or 'et-' in k_lower:
        print(f"  {k}: {v}")

# 跟随重定向
r2 = s.post(f"{BASE}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
print(f"\nPOST+redirect /login: {r2.status_code}")
print(f"Cookies after redirect: {dict(s.cookies)}")

# 访问 SSR 页面
r3 = s.get(f"{BASE}/sales/parts/pricing")
print(f"\nSSR 页面: {r3.status_code}")
html = r3.text
count = re.search(r'(\d+)\s*件', html)
print(f"显示: {count.group(0) if count else '未找到'}")
if '<div class="list-card"' in html:
    print("有卡片")
else:
    print("无卡片")
    # 打印 content 区域
    m = re.search(r'<div class="content">(.*?)</div>\s*<button', html, re.DOTALL)
    if m:
        content = m.group(1).strip()
        print(f"内容: {content[:300]}")

# 访问 API（直接带 Cookie jar 中的 cookie）
r4 = s.get(f"{BASE}/api/part/1")
print(f"\nAPI /api/part/1: {r4.status_code} - {r4.text[:200]}")
