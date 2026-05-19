"""
diagnose_treatment.py
=====================
直接连库诊断 treatment_dicts 真实状态。
"""

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432",
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# ── 1. 检查表是否存在 ─────────────────────────────────────────
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_name = 'treatment_dicts'
    AND table_schema = 'public';
""")
tables = cur.fetchall()
print(f"[1] treatment_dicts 表存在: {len(tables) > 0}")
for t in tables:
    print(f"    {t}")

# ── 2. 检查表结构 ─────────────────────────────────────────────
if tables:
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'treatment_dicts'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    print(f"\n[2] 表结构（{len(cols)} 列）:")
    for c in cols:
        print(f"    {c[0]:20s} {c[1]:20s} nullable={c[2]} default={c[3]}")

    # ── 3. 查所有数据（含已删除）────────────────────────────────
    cur.execute("""
        SELECT id, name, calc_mode, rate, unit, is_active, created_at
        FROM treatment_dicts
        ORDER BY id;
    """)
    rows = cur.fetchall()
    print(f"\n[3] 总行数（含软删除）: {len(rows)}")
    for r in rows:
        print(f"    id={r[0]} name={r[1]!r:10s} calc_mode={r[2]} "
              f"rate={r[3]} unit={r[4]!r} is_active={r[5]} created_at={r[6]}")

    # ── 4. 单独查 is_active=TRUE ─────────────────────────────
    cur.execute("""
        SELECT id, name, calc_mode, rate, unit
        FROM treatment_dicts
        WHERE is_active = TRUE
        ORDER BY id;
    """)
    active = cur.fetchall()
    print(f"\n[4] is_active=TRUE 行数（GET 查询结果）: {len(active)}")
    for r in active:
        print(f"    id={r[0]} name={r[1]!r} calc_mode={r[2]} rate={r[3]} unit={r[4]!r}")

    # ── 5. 检查是否有事务未提交 ───────────────────────────────
    # 通过新连接查询当前未提交事务
    conn2 = psycopg2.connect(**DB_CONFIG)
    cur2 = conn2.cursor()
    cur2.execute("""
        SELECT pid, state, query, xact_start
        FROM pg_stat_activity
        WHERE datname = 'stamping_system'
          AND state != 'idle'
          AND application_name != 'psycopg2'
        ORDER BY xact_start;
    """)
    xacts = cur2.fetchall()
    print(f"\n[5] 当前活跃事务数（来自另一连接）: {len(xacts)}")
    for x in xacts:
        print(f"    pid={x[0]} state={x[1]} query={x[2][:80]}")
    conn2.close()

    # ── 6. 检查约束 ───────────────────────────────────────────
    cur.execute("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'treatment_dicts'::regclass;
    """)
    constraints = cur.fetchall()
    print(f"\n[6] 约束列表:")
    for c in constraints:
        print(f"    {c[0]}: {c[1]} -> {c[2]}")

conn.close()

print("\n=== 诊断完成 ===")
