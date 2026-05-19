"""
db_check6.py — db_service 模块路径 + 函数对象身份验证
用法：python scripts/db_check6.py
"""
import sys, os
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')
os.chdir(r'C:\Users\Administrator\Desktop\Cloud-Stamping')

import app.services.db_service as dbs
import importlib

print('=== DB_CONFIG ===')
print(dbs.DB_CONFIG)

print()
print('=== get_all_treatments() ===')
result = dbs.get_all_treatments()
print(f'返回 {len(result)} 条')
for r in result:
    print(' ', r)

print()
print('=== 模块路径 ===')
mod = importlib.import_module('app.services.db_service')
print('Module path:', mod.__file__)
print('get_all_treatments id:', id(mod.get_all_treatments))
