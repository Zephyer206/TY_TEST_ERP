"""
patch_check.py — Monkey-patch db_service 并打印所有 get_all_treatments 调用
用法：python scripts/patch_check.py（会启动 uvicorn）
"""
import sys, os
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')
os.chdir(r'C:\Users\Administrator\Desktop\Cloud-Stamping')

import app.services.db_service as dbs
_orig_get = dbs.get_all_treatments
_orig_upsert = dbs.upsert_treatment

def patched_get():
    print('[PATCH] get_all_treatments() called!', flush=True)
    result = _orig_get()
    print(f'[PATCH] get_all_treatments() returned {len(result)} rows', flush=True)
    return result

def patched_upsert(name, calc_mode, rate, unit='元/件'):
    print(f'[PATCH] upsert_treatment({name!r}, {calc_mode}, {rate}, {unit!r}) called!', flush=True)
    result = _orig_upsert(name, calc_mode, rate, unit)
    print(f'[PATCH] upsert_treatment() returned id={result.get("id")}', flush=True)
    return result

dbs.get_all_treatments = patched_get
dbs.upsert_treatment = patched_upsert
