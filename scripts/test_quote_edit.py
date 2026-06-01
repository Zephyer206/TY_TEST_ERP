# 直接请求 quote_edit 页面（无需登录，看路由行为）
import urllib.request
import re

req = urllib.request.Request("http://localhost:8000/sales/quotes/15/edit")
try:
    resp = urllib.request.urlopen(req, timeout=5000)
    html = resp.read().decode("utf-8")
    print(f"Status OK, HTML length: {len(html)}")

    # 提取 quote_data
    m = re.search(r"var q = ({.*?});", html, re.DOTALL)
    if m:
        raw = m.group(1)[:2000]
        print(f"\nquote_data:\n{raw}")
    else:
        print("\n未找到 var q = {...}")

    # 提取材料选项
    m2 = re.search(r'<select[^>]*id="selMaterial"[^>]*>(.*?)</select>', html, re.DOTALL)
    if m2:
        opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>', m2.group(1))
        print(f"\nselMaterial options ({len(opts)}): {opts[:15]}")
    else:
        print("\nselMaterial 未找到")

    # 找 inpT
    for inp_id in ['inpT', 'inpW', 'inpP', 'inpCav', 'inpUtil']:
        m3 = re.search(rf'<input[^>]*id="{inp_id}"[^>]*>', html)
        if m3:
            print(f"\n{inp_id}: {m3.group(0)[:200]}")

except Exception as e:
    print(f"Error: {e}")
