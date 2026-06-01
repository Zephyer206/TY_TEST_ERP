# -*- coding: utf-8 -*-
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

# 删除 A00125983-04 的空 price 记录（子行，没有重量数据）
cur.execute("""
    SELECT p.id, pt.part_number
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE pt.part_number = 'A00125983-04' AND p.customer_id=55
""")
r = cur.fetchone()
if r:
    print(f"删除空子行: id={r[0]} part={r[1]}")
    cur.execute("DELETE FROM prices WHERE id=%s", (r[0],))
    conn.commit()
    print("已删除")
else:
    print("未找到 A00125983-04")

# 验证 A00125983-03
cur.execute("""
    SELECT p.id, pt.part_number, p.gross_weight, p.net_weight,
           p.material_unit_price, p.surface_treatment_cost, p.cost_override
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE pt.part_number = 'A00125983-03' AND p.customer_id=55
""")
r = cur.fetchone()
if r:
    net = float(r[3] or 0)
    mp = float(r[4] or 0)
    stc = float(r[5] or 0)
    mat = round(net * mp, 4)
    total = round(mat + stc, 4)
    print(f"\nA00125983-03: net={r[3]}kg mp={r[4]} stc={r[5]}")
    print(f"  计算: mat={mat} total={total}")
    print(f"  期望: mat=0.0973 total=0.13 (stc=0.03)")

conn.close()
