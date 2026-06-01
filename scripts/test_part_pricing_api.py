"""
测试零件报价 API - 验证 Cookie 认证问题
使用 requests 库更好地处理 Cookie
"""
import subprocess, time, sys

# 先检查服务器是否在运行
import urllib.request
try:
    r = urllib.request.urlopen("http://localhost:8000/", timeout=3)
    print(f"服务器状态: {r.status}")
except Exception as e:
    print(f"服务器未运行: {e}")
    print("请先启动服务器: py main.py")
    sys.exit(1)

# 使用 requests（如果有的话）
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("requests 库未安装，将使用 urllib（Cookie 处理较弱）")

def test_with_requests():
    import requests
    s = requests.Session()
    BASE = "http://localhost:8000"

    # 1. 登录
    r = s.post(f"{BASE}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
    print(f"登录: {r.status_code}")
    print(f"Cookie after login: {dict(s.cookies)}")

    # 2. SSR 页面
    r2 = s.get(f"{BASE}/sales/parts/pricing")
    print(f"\nSSR /sales/parts/pricing: {r2.status_code}")
    html = r2.text

    # 3. 检查 parts 数据
    import re
    count_match = re.search(r'(\d+)\s*件', html)
    if count_match:
        print(f"页面显示: {count_match.group(0)}")

    # 检查是否有内容
    if '<div class="list-card"' in html:
        print("✓ 页面包含卡片元素")
    else:
        print("✗ 页面没有卡片元素！")
        # 看看有没有空的 parts
        if 'empty-state' in html:
            print("  -> 页面显示 empty-state（无数据）")
        # 打印 body 区域
        body_match = re.search(r'<div class="content">(.*?)</div>\s*<button', html, re.DOTALL)
        if body_match:
            print(f"  -> 内容区域前100字符: {body_match.group(1)[:200].strip()}")

    # 4. API 调用
    r3 = s.get(f"{BASE}/api/part/1")
    print(f"\nAPI /api/part/1: {r3.status_code}")
    if r3.status_code == 200:
        data = r3.json()
        print(f"  code={data.get('code')}, message={data.get('message')}")
        if data.get("code") == 200:
            part = data["data"].get("part", {})
            print(f"  零件号: {part.get('part_number', '?')}")
    else:
        print(f"  失败: {r3.text[:200]}")


def test_with_urllib():
    import urllib.request, urllib.parse, http.cookiejar, urllib.error
    BASE = "http://localhost:8000"

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 手动处理重定向以捕获所有 Cookie
    class FollowRedirectsHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            new_req = urllib.request.Request(newurl, data=req.data, headers=req.headers, method=req.method)
            return new_req

    opener2 = urllib.request.build_opener(FollowRedirectsHandler(), urllib.request.HTTPCookieProcessor(cj))

    # 1. 登录
    login_data = urllib.parse.urlencode({"username": "admin", "password": "admin123"}).encode()
    try:
        resp = opener2.open(urllib.request.Request(f"{BASE}/login", data=login_data, method="POST"), timeout=10)
        print(f"登录: {resp.status}")
    except Exception as e:
        print(f"登录失败: {e}")
        return

    print(f"Cookie jar: {[c.name for c in cj]}")

    # 2. SSR 页面
    try:
        resp2 = opener2.open(urllib.request.Request(f"{BASE}/sales/parts/pricing"), timeout=10)
        print(f"\nSSR 页面: {resp2.status}")
        html = resp2.read().decode("utf-8")
        import re
        count_match = re.search(r'(\d+)\s*件', html)
        if count_match:
            print(f"页面显示: {count_match.group(0)}")
        if '<div class="list-card"' in html:
            print("✓ 有卡片")
        else:
            print("✗ 没有卡片")
            if 'empty-state' in html:
                print("  -> 显示 empty-state")
    except Exception as e:
        print(f"SSR 失败: {e}")

    # 3. API
    try:
        resp3 = opener2.open(urllib.request.Request(f"{BASE}/api/part/1"), timeout=10)
        print(f"\nAPI /api/part/1: {resp3.status}")
    except urllib.error.HTTPError as e:
        print(f"\nAPI /api/part/1: HTTP {e.code}")
        print(f"  响应: {e.read().decode()[:200]}")
    except Exception as e:
        print(f"\nAPI /api/part/1: {e}")


if HAS_REQUESTS:
    test_with_requests()
else:
    test_with_urllib()
