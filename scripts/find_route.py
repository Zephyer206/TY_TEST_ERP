"""
find_route.py — 搜索项目中所有包含 treatments 相关路由的 .py 文件
用法：python scripts/find_route.py
"""
import re, os

ROOT = r'C:\Users\Administrator\Desktop\Cloud-Stamping'

patterns = [
    r'@api_router\.get.*treatments',
    r'@router\.get.*treatments',
    r'"/api/dict/treatments"',
    r'"/api/treatments',
]

for root, dirs, files in os.walk(ROOT):
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = fh.read().split('\n')
            for i, line in enumerate(lines, 1):
                for pat in patterns:
                    if re.search(pat, line, re.IGNORECASE):
                        print(f'{path}:{i}: {line.strip()}')
        except Exception:
            pass
