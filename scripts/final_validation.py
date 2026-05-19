# -*- coding: utf-8 -*-
"""V3.2 最终状态验证脚本"""
import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system', user='postgres',
    password='thehaoshi5DE', host='localhost', port='5432'
)
conn.autocommit = True
cur = conn.cursor()

print("=" * 60)
print("  V3.2 最终状态验证")
print("=" * 60)

# 1. parts 表字段
print("\n[1] parts 表字段（应无 pricing_mode/thickness/current_price 等）")
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'parts' AND column_name IN (
        'pricing_mode', 'referenced_part_id', 'thickness', 'width',
        'press_stroke', 'cavity_count', 'gross_weight',
        'material_unit_price_override', 'material_net_cost_override',
        'final_price_override', 'stamping_fee', 'surface_fee',
        'profit_margin', 'manual_override_fields',
        'pending_price', 'current_price', 'price_status'
    )
    ORDER BY column_name
""")
leaked = cur.fetchall()
if leaked:
    print(f"  FAIL: 发现已迁移字段仍存在于 parts 表: {[r[0] for r in leaked]}")
else:
    print("  PASS: parts 表无业务字段泄漏")

# 2. parts 表架构字段
print("\n[2] parts.version / part_status")
cur.execute("""
    SELECT column_name, column_default, is_nullable
    FROM information_schema.columns
    WHERE table_name='parts' AND column_name IN ('version', 'part_status')
    ORDER BY column_name
""")
for r in cur.fetchall():
    print(f"  {r[0]}: default={r[1]}, nullable={r[2]}")

# 3. part_status CHECK 约束
print("\n[3] part_status CHECK 约束")
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conname = 'chk_parts_part_status'
""")
chk = cur.fetchone()
if chk:
    print(f"  PASS: {chk[0]} — {chk[1]}")
else:
    print("  FAIL: CHECK 约束不存在")

# 4. 联合唯一约束
print("\n[4] 联合唯一约束")
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conname = 'uq_parts_number_version'
""")
uq = cur.fetchone()
if uq:
    print(f"  PASS: {uq[0]} — {uq[1]}")
else:
    print("  FAIL: 联合唯一约束不存在")

# 5. parts 数据验证
print("\n[5] parts 数据（part_status 应为 DRAFT/MASS_PRODUCTION）")
cur.execute("""
    SELECT id, part_number, version, part_status
    FROM parts ORDER BY id
""")
for r in cur.fetchall():
    print(f"  id={r[0]} part={r[1]} version={r[2]} status={r[3]}")

# 6. quotes 表字段完整性
print("\n[6] quotes 表关键字段")
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'quotes'
    ORDER BY column_name
""")
cols = [r[0] for r in cur.fetchall()]
required = ['part_id', 'quote_serial', 'pricing_mode', 'thickness',
            'scrap_rate', 'final_price', 'approval_status',
            'parent_quote_id', 'override_fields']
for col in required:
    status = "PASS" if col in cols else "FAIL"
    print(f"  [{status}] {col}")

# 7. quotes 数据
print("\n[7] quotes 数据验证")
cur.execute("""
    SELECT id, quote_serial, approval_status, final_price, part_id
    FROM quotes ORDER BY id
""")
for r in cur.fetchall():
    print(f"  id={r[0]} serial={r[1]} status={r[2]} price={r[3]} part_id={r[4]}")

# 8. 白盒公式验证（V3.2 新公式）
print("\n[8] 白盒公式验证（V3.2: Cost = ((GW-SW)*P) - (SW*SP)）")
T, W, P, D = 1.5, 100.0, 200.0, 7.85
CC = 1
SR = 0.10
UP = 20.50
SP = 12.00
GW = T * W * P * D * CC / 1_000_000
SW = GW * SR
mat_cost = (GW - SW) * UP - SW * SP
print(f"  GrossWeight = {T}x{W}x{P}x{D}x{CC}/1e6 = {GW:.8f} kg")
print(f"  ScrapWeight = {GW:.8f} x {SR} = {SW:.8f} kg")
print(f"  NetWeight   = {GW:.8f} - {SW:.8f} = {GW-SW:.8f} kg")
print(f"  mat_net_cost = (({GW:.6f}-{SW:.6f})x{UP}) - ({SW:.6f}x{SP})")
print(f"               = {mat_cost:.8f} yuan")
print(f"               = round(...,4) => {round(mat_cost, 4):.4f} yuan")

print()
print("=" * 60)
print("  验证完毕")
print("=" * 60)
conn.close()
