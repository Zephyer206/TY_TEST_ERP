# -*- coding: utf-8 -*-
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

cur.execute("""
    SELECT pt.part_number, p.gross_weight, p.net_weight,
           p.material_unit_price, p.scrap_price,
           p.surface_treatment_cost, p.cost_override
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE p.customer_id=55
    ORDER BY pt.part_number;
""")

print("=== 成本计算诊断 ===")
for r in cur.fetchall():
    part, gross, net, mp, sp, stc, override = r
    if net is None or mp is None: continue

    # 废料率（废料/毛重）
    waste = (gross or 0) - net
    scrap_ratio = waste / gross if gross else 0

    # 旧公式（错误）：net*mp - waste*sp
    old_mat = round(net * mp - waste * (sp or 0), 6)

    # 正确公式：net * mp * (1 - scrap_ratio)
    # scrap_ratio = waste / gross, not scrap_price
    correct_mat = round(net * mp * (1 - scrap_ratio), 6)

    # 如果 scrap_price 就是 scrap_ratio（某些零件对，某些错）
    as_ratio_mat = round(net * mp * (1 - (sp or 0)), 6)

    total_old = round(old_mat + (stc or 0), 4)
    total_correct = round(correct_mat + (stc or 0), 4)
    total_override = round(override, 4) if override else None

    print(f"\n{part}:")
    print(f"  gross={gross}kg net={net}kg mp={mp}元/kg sp={sp}")
    print(f"  waste={waste:.6f} scrap_ratio(废/毛)={scrap_ratio:.4f}")
    print(f"  旧公式 mat={old_mat:.6f} + stc={stc} = {total_old:.4f}")
    print(f"  正确 mat={correct_mat:.6f} + stc={stc} = {total_correct:.4f}")
    print(f"  as_ratio mat={as_ratio_mat:.6f}")
    print(f"  cost_override={override} -> total={total_override}")
    print(f"  cost_override vs 正确: {'✓ MATCH' if override and abs(total_override - total_correct) < 0.01 else '✗ DIFF'}")

conn.close()
