# -*- coding: utf-8 -*-
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', port='5432')
cur = conn.cursor()

# F200005166-5T raw DB values
cur.execute("""
    SELECT p.id, p.gross_weight, p.net_weight, p.material_unit_price,
           p.scrap_price, p.surface_treatment_cost, p.cost_override,
           pt.part_number
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE pt.part_number='F200005166-5T' AND p.customer_id=55;
""")
r = cur.fetchone()
print(f"DB raw: id={r[0]} gross={r[1]} net={r[2]} mp={r[3]} sp={r[4]} stc={r[5]} override={r[6]} part={r[7]}")
print(f"  0.027755*0.582855 = {0.027755*0.582855:.6f}")
print(f"  0.00921*0.582855 = {0.00921*0.582855:.6f}")
print(f"  0.0092*0.5829 = {0.0092*0.5829:.6f}")
print(f"  9.21*0.582855/1000 = {9.21*0.582855/1000:.6f}")

# What _calc_material_cost computes (kg * mp)
if r[2] and r[3]:
    nw = float(r[2])
    mp = float(r[3])
    print(f"\n_calc_material_cost result: {nw} * {mp} = {nw*mp:.6f}")

# What Excel says
print(f"\nExcel: mat_cost=0.45304, total=0.7861")
print(f"Excel stc=0.33306, so 0.45304+0.33306={0.45304+0.33306:.5f}")

# So: 0.45304 / 0.582855 = 0.7773 kg
print(f"\n0.45304 / 0.582855 = {0.45304/0.582855:.6f} kg (net_weight in DB?)")
print(f"But DB net = {r[2]} kg")
print(f"0.45304 * 1000 / 0.582855 = {0.45304*1000/0.582855:.6f} (if net were grams)")

conn.close()
