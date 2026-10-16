"""
db_check2.py — 调用 get_all_treatments() 并对比 psycopg2 直查结果
用法：python scripts/db_check2.py
"""
import sys
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')

from app.services.db_service import get_all_treatments, _ensure_treatment_dicts_table
import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    'dbname': 'stamping_system',
    'user': 'postgres',
    'password': '__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
    'host': 'localhost',
    'port': '5432'
}

print('=== 直接调用 get_all_treatments() ===')
result = get_all_treatments()
print('返回类型:', type(result))
print('返回长度:', len(result))
print('返回数据:')
for r in result:
    print(' ', dict(r))

print()
print('=== 直接用 psycopg2 执行相同 SQL ===')
with psycopg2.connect(**DB) as conn:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, name, calc_mode, rate, unit
            FROM treatment_dicts
            WHERE is_active = TRUE
            ORDER BY id
        """)
        rows = cur.fetchall()
        print('fetchall rows:', rows)
        print('len:', len(rows))

print()
print('=== 检查连接参数 ===')
print('host:', DB['host'])
print('dbname:', DB['dbname'])
print('user:', DB['user'])
