# -*- coding: utf-8 -*-
import psycopg2, openpyxl, os

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

# Check current prices data
cur.execute("""
    SELECT pt.part_number, p.gross_weight, p.net_weight,
           p.material_unit_price, p.scrap_price,
           p.surface_treatment_cost, p.cost_override,
           p.id as price_id
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE p.customer_id=55
    ORDER BY pt.part_number;
""")
print("=== DB prices (customer 55) ===")
for r in cur.fetchall():
    print(f"  {r[0]}: gross={r[1]} net={r[2]} mp={r[3]} sp={r[4]} stc={r[5]} cost_override={r[6]}")

# Calc what the system currently computes
print("\n=== What _calc_material_cost computes ===")
for r in cur.fetchall():
    part, gross, net, mp, sp, stc, override = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
    if net and mp:
        waste = (gross or 0) - net
        mat = round(net * mp - waste * (sp or 0), 4)
        total = round(mat + (stc or 0), 4)
        print(f"  {part}: mat_cost={mat} + stc={stc or 0} = total={total} | override={override}")

# Check Excel data for comparison
print("\n=== Excel data (武汉万向 Sheet1) ===")
path = r"C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\B-C武汉万向汽车制动器有限公司\武汉万向.xlsx"
wb = openpyxl.load_workbook(path, data_only=True)
ws = wb['Sheet1']
headers = [str(c).strip() if c else '' for c in next(ws.iter_rows(values_only=True))]
print("Headers:", headers)
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    if row[1] and '总计' not in str(row[1]) and str(row[1]).strip():
        part = str(row[1]).strip()
        print(f"  {part}: {[row[j] for j in range(len(headers))]}")

conn.close()
