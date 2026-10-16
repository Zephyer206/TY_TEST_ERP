# -*- coding: utf-8 -*-
import psycopg2, os

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', port='5432')
cur = conn.cursor()

cur.execute("""
    SELECT p.id, pt.part_number, pt.internal_name, p.gross_weight, p.net_weight,
           p.material_unit_price, p.scrap_price, p.surface_treatment_cost, p.cost_override
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE pt.part_number IN ('A00125983-03','A00125983-04','A00125983-3','A00125983-03（喷涂）')
      AND p.customer_id=55
    ORDER BY pt.part_number;
""")
print("=== DB prices for A00125983-* ===")
for r in cur.fetchall():
    pid, part, name, gross, net, mp, scrap, stc, override = r
    net_f = float(net or 0)
    mp_f  = float(mp  or 0)
    stc_f = float(stc or 0)
    mat    = round(net_f * mp_f, 4)
    total  = round(mat + stc_f, 4)
    print(f"  id={pid} part={part} name={name}")
    print(f"    gross={gross}kg net={net}kg mp={mp} scrap={scrap} stc={stc}")
    print(f"    cost_override={override}")
    print(f"    calc: mat={mat} total={total} | user: mat=0.0973 stc=0.03 total=0.13")

# Excel data for reference
print("\n=== Excel data ===")
import openpyxl
path = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\B-C武汉万向汽车制动器有限公司\武汉万向.xlsx'
wb = openpyxl.load_workbook(path, data_only=True)
ws = wb['Sheet1']
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    part = str(row[1]).strip() if row[1] else ''
    if 'A00125983' in part:
        gross = row[8]   # 单件毛重量
        net   = row[9]   # 单件净重量
        mp    = row[10]  # 材料价格
        sp    = row[11]  # 废料价格
        mat_cost = row[12]  # 材料成本
        stc   = row[13]  # 外协成本
        cost  = row[14]  # 成本
        print(f"  {part}: gross={gross} net={net} mp={mp} mat_cost={mat_cost} stc={stc} cost={cost}")

# Image files
print("\n=== Image files ===")
base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images'
cust = 'B-C武汉万向汽车制动器有限公司'
for part in ['A00125983-03', 'A00125983-04', 'A00125983-3', 'A00125983-03（喷涂）']:
    path = os.path.join(base, cust, part)
    if os.path.exists(path):
        files = os.listdir(path)
        print(f"  {part}: {files}")
    else:
        print(f"  {part}: 无图片目录")

conn.close()
