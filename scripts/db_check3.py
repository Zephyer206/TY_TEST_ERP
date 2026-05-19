"""
db_check3.py — 环境 + 路由检查
用法：python scripts/db_check3.py
"""
import sys, os
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')

# Check environment
print('=== 环境变量 ===')
for k, v in os.environ.items():
    if any(x in k.lower() for x in ['db', 'postgres', 'pg', 'database', 'host', 'port']):
        print(f'  {k}={v}')

print()
print('=== main.py 前50行 ===')
with open(r'C:\Users\Administrator\Desktop\Cloud-Stamping\main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines[:50], 1):
    print(f'{i:3d}: {line}', end='')
