# -*- coding: utf-8 -*-
"""
迁移脚本：为 parts 表补充白盒核算引擎所需字段
执行方式：python scripts/migrate_parts_physics.py
"""
import psycopg2

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432"
}

def get_existing_columns(cur):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='parts';")
    return {r[0] for r in cur.fetchall()}

ALTER_STATEMENTS = [
    # 白盒物理参数
    ("thickness",          "NUMERIC(8,3)"),        # 料厚 T (mm)
    ("width",              "NUMERIC(8,2)"),         # 料宽 W (mm)
    ("press_stroke",       "INTEGER"),              # 冲次 P (SPM)
    # 模具出数
    ("cavity_count",       "INTEGER DEFAULT 1"),   # 模具穴数
    # 关联件（路径A参考定价）
    ("referenced_part_id",  "INTEGER"),             # FK → parts.id，关联已有件
    # 白盒核算中间结果
    ("gross_weight",                    "NUMERIC(12,4)"),  # 毛重 kg
    ("material_unit_price_override",    "NUMERIC(12,4)"),  # 人工覆盖：材料单价
    ("material_net_cost_override",      "NUMERIC(12,4)"),  # 人工覆盖：材料净成本
    ("final_price_override",            "NUMERIC(12,4)"),  # 人工覆盖：总价
    ("stamping_fee",                    "NUMERIC(12,4)"),  # 冲压费
    ("surface_fee",                     "NUMERIC(12,4)"),  # 表面处理费
    ("profit_margin",                   "NUMERIC(6,3)"),   # 利润率（系数，如 0.15 = 15%）
    # 路径标识
    ("pricing_mode",    "VARCHAR(20) DEFAULT 'Independent'"),  # 'Associated' | 'Independent'
    # 覆盖字段记录（JSON 数组，记录哪些字段被人工覆盖，用于前端蓝色高亮）
    ("manual_override_fields", "JSONB DEFAULT '[]'::jsonb"),
    # 样件判定
    ("sample_judgment_status", "VARCHAR(30)"),     # 待评价/合格/需改模/不合格
    # 时间戳
    ("created_at", "TIMESTAMP DEFAULT NOW()"),
    ("updated_at", "TIMESTAMP DEFAULT NOW()"),
]

def migrate():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    existing = get_existing_columns(cur)
    print(f"parts 表已有字段：{sorted(existing)}")
    print()

    added = []
    for col_name, col_type in ALTER_STATEMENTS:
        if col_name in existing:
            print(f"  [SKIP] {col_name}  已存在")
            continue
        sql = f"ALTER TABLE parts ADD COLUMN {col_name} {col_type};"
        try:
            cur.execute(sql)
            added.append(f"  [ADD]   {col_name}  {col_type}")
            print(f"  [ADD]   {col_name}  {col_type}")
        except psycopg2.Error as e:
            print(f"  [FAIL]  {col_name}  →  {e}")
            conn.rollback()
            conn.close()
            raise

    conn.commit()
    cur.close()
    conn.close()

    print()
    print("=" * 50)
    if added:
        print(f"  成功新增 {len(added)} 个字段：")
        for line in added:
            print(line)
    else:
        print("  所有字段均已存在，无需迁移。")
    print("=" * 50)

if __name__ == "__main__":
    try:
        migrate()
    except psycopg2.OperationalError as e:
        print(f"[FATAL] 数据库连接失败：{e}")
        print("  请确认 PostgreSQL 已启动")
    except psycopg2.Error as e:
        print(f"[FATAL] SQL 执行失败：{e}")
