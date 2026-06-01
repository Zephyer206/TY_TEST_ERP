"""直接测试数据库登录验证"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\Cloud-Stamping")

from app.services.db_service import verify_user, DB_CONFIG
import psycopg2

# 1. 测试数据库连接
print("=== 数据库连接测试 ===")
try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(f"PostgreSQL: {cur.fetchone()[0][:60]}")
    conn.close()
except Exception as e:
    print(f"数据库连接失败: {e}")
    sys.exit(1)

# 2. 查找 admin 用户
print("\n=== 查找用户 ===")
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute("SELECT id, username, password_hash, role_level FROM users WHERE is_deleted = FALSE LIMIT 10;")
rows = cur.fetchall()
conn.close()
for r in rows:
    print(f"  id={r[0]}, username={r[1]}, role_level={r[3]}")
    # 不打印密码

# 3. 测试 verify_user
print("\n=== 测试 verify_user ===")
for username, password in [("admin", "admin123"), ("admin", "password"), ("test", "test")]:
    result = verify_user(username, password)
    if result:
        print(f"  {username}/{password}: 成功! id={result.get('id')}, role_level={result.get('role_level')}")
    else:
        print(f"  {username}/{password}: 失败")
