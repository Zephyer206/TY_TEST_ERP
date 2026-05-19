# -*- coding: utf-8 -*-
"""
初始化脚本：注入上帝账号 + 材料测试数据
幂等设计：重复运行不报错，不破坏已有数据
"""
import psycopg2
import hashlib

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432"
}

def md5pw(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()

def init():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    changes = []

    # ── 1. 创建上帝账号 (admin / 123456, level=9) ──────────────────────────
    # 检查是否已存在
    cur.execute("SELECT id, role_level FROM users WHERE username = %s;", ("admin",))
    row = cur.fetchone()
    if row:
        if row[1] < 9:
            cur.execute(
                "UPDATE users SET role_level=9, dept='admin', position='老板', is_tech=false WHERE username=%s",
                ("admin",))
            changes.append("UPDATE admin role_level → 9")
        else:
            changes.append("admin 账号已存在 (role_level>=9)，无需修改")
    else:
        cur.execute("""
            INSERT INTO users (username, password, role_level, dept, position, real_name, is_tech)
            VALUES (%s, %s, 9, 'admin', '老板', '系统管理员', false)
            RETURNING id;
        """, ("admin", md5pw("123456")))
        new_id = cur.fetchone()[0]
        changes.append(f"CREATE admin 账号成功 (id={new_id})")

    # ── 2. 注入测试材料基准价 (SUS301, SPCC) ─────────────────────────────────
    materials = [
        ("SUS301", 8.0, 0.0078, 0.5),   # density=7.8e-6 for mm^3→kg, scrap_price=0.5
        ("SPCC",   5.0, 0.0078, 0.3),
        ("SECC",   6.0, 0.0078, 0.4),
        ("铝合金", 20.0, 0.0027, 1.0),
    ]
    for mat_name, price, density, scrap_price in materials:
        cur.execute("SELECT 1 FROM material_base_prices WHERE material_name = %s;", (mat_name,))
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE material_base_prices
                SET default_price=%s, default_density=%s, scrap_price=%s
                WHERE material_name=%s;
            """, (price, density, scrap_price, mat_name))
            changes.append(f"UPDATE material_base_prices[{mat_name}] price={price} density={density}")
        else:
            cur.execute("""
                INSERT INTO material_base_prices (material_name, default_price, default_density, scrap_price)
                VALUES (%s, %s, %s, %s);
            """, (mat_name, price, density, scrap_price))
            changes.append(f"INSERT material_base_prices[{mat_name}] price={price} density={density}")

    conn.commit()
    cur.close()
    conn.close()

    print("=" * 50)
    print("  init_db.py 执行结果")
    print("=" * 50)
    for line in changes:
        print(f"  {line}")
    print("=" * 50)
    print("  上帝账号: admin / 123456 (Level 9)")
    print("  材料数据: SUS301, SPCC, SECC, 铝合金")
    print("=" * 50)

if __name__ == "__main__":
    try:
        init()
    except psycopg2.OperationalError as e:
        print(f"数据库连接失败: {e}")
        print("请确认 PostgreSQL 已启动且 db_service.py 中的 DB_CONFIG 正确")
    except psycopg2.ProgrammingError as e:
        print(f"SQL 执行失败: {e}")
        print("请先执行 alembic upgrade head 初始化表结构")
