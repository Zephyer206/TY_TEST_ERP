"""
诊断脚本：验证 TEST 零件删除修复是否生效
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

BASE = "http://localhost:8000"

# 先用浏览器登录获取 session
# 这里直接用 Python requests 模拟登录
session = requests.Session()

# 登录（admin/密码）
login_resp = session.post(f"{BASE}/login", data={
    "username": "admin",
    "password": "admin123"
}, allow_redirects=False)
print(f"登录状态码: {login_resp.status_code}")
print(f"Cookies: {dict(session.cookies)}")

# 检查 TEST 零件是否还存在
conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

cur.execute("""
    SELECT id, part_number, internal_name
    FROM parts
    WHERE LOWER(part_number) LIKE '%test%'
    ORDER BY id DESC
    LIMIT 5;
""")
parts = cur.fetchall()
print(f"\n=== 当前 TEST 零件数量: {len(parts)} ===")
for p in parts:
    print(f"  id={p[0]}, part_number={p[1]!r}, name={p[2]!r}")

conn.close()

if not parts:
    print("\n所有 TEST 零件已删除完毕！")
else:
    print(f"\n还有 {len(parts)} 个 TEST 零件，请点击前端删除按钮进行清理。")
