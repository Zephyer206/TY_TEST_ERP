# -*- coding: utf-8 -*-
"""
迁移：修复 prices 表中 material_unit_price 错误的问题。

症状：导入时将 Excel「材料价格」列直接存为 material_unit_price，
      但 Excel 中该列值与「材料成本/净重」不一致，导致成本计算错误。

修复逻辑：
  1. 有 cost_override 的行：用 cost_override - stc 推导正确的 material_unit_price
  2. 有 cost_override 但 stc 为 0 的行：用 cost_override / net
  3. 无 cost_override 的行：标记为待手动处理（mp 可能已错误）
  4. 重新计算 scrap_ratio = (gross - net) / gross

验证：对 F200005166-5T
  DB现状: cost_override=None, gross=0.0278, net=0.0092, mp=0.5829, stc=0.3331
  修复后: mp_derived = 0.45304 / 0.0092 = 49.2435  (错误！)
  → 等等，cost_override=None，无法推导。
  → 需要重新导入来获取正确的 cost_override。
"""
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', port='5432')
cur = conn.cursor()

# 先看现状
print("=== 迁移前数据样例 ===")
cur.execute("""
    SELECT p.id, pt.part_number, p.gross_weight, p.net_weight,
           p.material_unit_price, p.scrap_price,
           p.surface_treatment_cost, p.cost_override
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE p.customer_id=55
    ORDER BY pt.part_number;
""")
rows = cur.fetchall()

has_override = 0
no_override = 0
fixed = 0
for r in rows:
    pid, part, gross, net, mp, sp, stc, override = r
    gross_f = float(gross) if gross else 0
    net_f = float(net) if net else 0
    mp_f = float(mp) if mp else 0
    stc_f = float(stc) if stc else 0

    # 当前的错误计算
    wrong_mat = round(net_f * mp_f, 6)

    if override is not None:
        has_override += 1
        # 推导正确 mp
        correct_total = float(override)
        correct_mp = round((correct_total - stc_f) / net_f, 6) if net_f != 0 else None
        correct_mat = round(net_f * correct_mp, 6) if correct_mp else None
        scrap_ratio = round((gross_f - net_f) / gross_f, 6) if gross_f != 0 else None
        print(f"  {part}: mp_wrong={mp_f:.6f} -> mp_correct={correct_mp} | mat_wrong={wrong_mat:.6f} mat_correct={correct_mat} | scrap_ratio={scrap_ratio}")
        cur.execute("""
            UPDATE prices
            SET material_unit_price=%s, scrap_price=%s, updated_at=NOW()
            WHERE id=%s
        """, (correct_mp, scrap_ratio, pid))
        fixed += 1
    else:
        no_override += 1
        print(f"  {part}: cost_override=None (跳过，需重新导入) | current mat={wrong_mat:.6f} | mp={mp_f}")

conn.commit()
print(f"\n修复了 {fixed} 条，有 {no_override} 条无 cost_override（需重新导入 Excel 覆盖）")

# 验证修复
print("\n=== 验证修复结果 ===")
cur.execute("""
    SELECT pt.part_number, p.net_weight, p.material_unit_price,
           p.scrap_price, p.surface_treatment_cost, p.cost_override
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE p.customer_id=55
    ORDER BY pt.part_number;
""")
for r in cur.fetchall():
    part, net, mp, sp, stc, override = r
    net_f = float(net) if net else 0
    mp_f = float(mp) if mp else 0
    stc_f = float(stc) if stc else 0
    mat = round(net_f * mp_f, 4)
    total = round(mat + stc_f, 4)
    override_f = float(override) if override else None
    match = '✓' if override_f is None or abs(total - override_f) < 0.01 else f'✗ diff={abs(total - override_f):.4f}'
    print(f"  {part}: net={net_f} mp={mp_f} mat={mat:.4f} total={total:.4f} override={override_f} {match}")

conn.close()
print("\n迁移完成！")
