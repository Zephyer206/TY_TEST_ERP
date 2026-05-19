"""
db_check4.py — verify_user 测试 + 用户列表
用法：python scripts/db_check4.py
"""
import sys
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')

from app.services.db_service import verify_user
import psycopg2

DB = {'dbname': 'stamping_system', 'user': 'postgres', 'password': 'thehaoshi5DE', 'host': 'localhost', 'port': '5432'}

print('=== 测试 verify_user ===')
for pw in ['admin', 'Admin123', 'password', '123456', 'admin12345']:
    u = verify_user('admin', pw)
    print(f'admin/{pw} => {"OK" if u else "FAIL"}')

print()
print('=== 数据库中的用户 ===')
with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id, username, role_level FROM users LIMIT 10")
        for row in cur.fetchall():
            print(f'  id={row[0]}, username={row[1]}, role_level={row[2]}')
