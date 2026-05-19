# init_superadmin.py
# ─────────────────────────────────────────────────────────────
# 上帝账号初始化脚本（幂等：已存在则跳过）
# 同时注入材料基准测试数据（幂等：已存在则跳过）
# 用法：python init_superadmin.py
# ─────────────────────────────────────────────────────────────

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432"
}

# ── 1. 上帝账号 ──────────────────────────────────────────────
def init_superadmin():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE username = 'admin';")
            existing = cur.fetchone()

            if existing:
                print(f"[SKIP] 用户 'admin' 已存在（id={existing['id']}），跳过创建。")
                # 确保 is_superadmin 字段为 True
                cur.execute("""
                    UPDATE users
                    SET role_level = 9, is_superadmin = TRUE
                    WHERE username = 'admin'
                      AND (role_level < 9 OR is_superadmin = FALSE OR is_superadmin IS NULL);
                """)
                conn.commit()
                print("[OK]  已将 admin 的 role_level 提升为 9，is_superadmin 置为 TRUE。")
            else:
                cur.execute("""
                    INSERT INTO users (username, password, role_level, is_superadmin, department, dept, position, real_name)
                    VALUES ('admin', '123456', 9, TRUE, 'admin', 'admin', '老板', '系统管理员');
                """)
                conn.commit()
                print("[OK]  已创建上帝账号: admin / 123456 / Level 9 / is_superadmin=True")


# ── 2. 材料基准测试数据 ──────────────────────────────────────
MATERIALS = [
    {
        "material_number": "SUS301",
        "material_name": "不锈钢 SUS301",
        "material_type": "卷料",
        "density": 7.93,
        "default_price": 21.0,
        "scrap_price": 12.0,
        "spec": "1.0*1219*C",
        "remark": "初始化测试数据",
    },
    {
        "material_number": "SPCC",
        "material_name": "冷轧碳钢 SPCC",
        "material_type": "卷料",
        "density": 7.85,
        "default_price": 6.5,
        "scrap_price": 1.8,
        "spec": "0.8*1250*C",
        "remark": "初始化测试数据",
    },
]

def init_materials():
    for mat in MATERIALS:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id FROM materials WHERE material_number = %s;",
                    (mat["material_number"],)
                )
                existing = cur.fetchone()

                if existing:
                    print(f"[SKIP] 材料 '{mat['material_number']}' 已存在（id={existing['id']}），跳过。")
                    # 幂等更新：保持密度/价格一致
                    cur.execute("""
                        UPDATE materials
                        SET density = %s, default_price = %s, scrap_price = %s,
                            material_name = COALESCE(NULLIF(%s, ''), material_name),
                            remark = COALESCE(NULLIF(%s, ''), remark)
                        WHERE material_number = %s;
                    """, (
                        mat["density"], mat["default_price"], mat["scrap_price"],
                        mat["material_name"], mat["remark"],
                        mat["material_number"],
                    ))
                    conn.commit()
                    print(f"[OK]  已更新材料 '{mat['material_number']}' 密度/价格。")
                else:
                    cur.execute("""
                        INSERT INTO materials
                            (material_number, material_name, material_type, density,
                             default_price, scrap_price, spec, remark,
                             current_width, current_weight, incoming_date, status)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s,
                             1219, 1000.0, CURRENT_DATE, '已入库');
                    """, (
                        mat["material_number"], mat["material_name"], mat["material_type"],
                        mat["density"], mat["default_price"], mat["scrap_price"],
                        mat["spec"], mat["remark"],
                    ))
                    conn.commit()
                    print(f"[OK]  已创建材料: {mat['material_number']} "
                          f"(密度={mat['density']}, 单价={mat['default_price']}, 废料价={mat['scrap_price']})")


# ── 3. 主入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("Cloud-Stamping 上帝账号初始化")
    print("=" * 50)
    print()
    print("▶ 步骤1：初始化上帝账号...")
    init_superadmin()
    print()
    print("▶ 步骤2：初始化材料基准测试数据...")
    init_materials()
    print()
    print("=" * 50)
    print("初始化完成！")
    print("  上帝账号: admin / 123456")
    print("  材料数据: SUS301, SPCC")
    print("=" * 50)
