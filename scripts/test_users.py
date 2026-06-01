"""检查用户表结构和测试登录"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\Cloud-Stamping")
from app.services.db_service import DB_CONFIG, verify_user
import psycopg2

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# 列出 users 表的所有列
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'users'
    ORDER BY ordinal_position;
""")
print("=== users 表字段 ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# 列出所有用户
cur.execute("SELECT id, username, role_level FROM users LIMIT 10;")
print("\n=== 用户列表 ===")
for r in cur.fetchall():
    print(f"  id={r[0]}, username={r[1]}, role_level={r[2]}")

conn.close()

# 测试 verify_user
print("\n=== 测试 verify_user ===")
for username, password in [("admin", "admin123"), ("test", "test"), ("user", "user")]:
    result = verify_user(username, password)
    if result:
        print(f"  OK: {username}/{password} -> id={result.get('id')}, role_level={result.get('role_level')}")
    else:
        print(f"  FAIL: {username}/{password}")
