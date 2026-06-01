import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

cur.execute("""
    SELECT p.id, p.gross_weight, p.net_weight, p.material_unit_price,
           p.scrap_price, p.surface_treatment_cost, p.cost_override, pt.part_number
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE pt.part_number='F200005166-5T' AND p.customer_id=55;
""")
r = cur.fetchone()
gross, net, mp, sp, stc, override = r[1], r[2], r[3], r[4], r[5], r[6]
print(f"DB raw: gross={gross} net={net} mp={mp} sp={sp} stc={stc} override={override}")
print()

net_f = float(net)
mp_f = float(mp)
stc_f = float(stc) if stc else 0
sp_f = float(sp) if sp else 0
gross_f = float(gross)

print("=== 可能的公式 ===")
# Formula A: net_kg * mp (DB as kg)
a = round(net_f * mp_f, 6)
print(f"A: net_kg * mp = {net_f} * {mp_f} = {a}")

# Formula B: net_g * mp / 1000
b = round(net_f * 1000 * mp_f / 1000, 6)
print(f"B: net_g * mp / 1000 = {net_f*1000} * {mp_f} / 1000 = {b}")

# Formula C: gross_kg * mp (no scrap deduction)
c = round(gross_f * mp_f, 6)
print(f"C: gross_kg * mp = {gross_f} * {mp_f} = {c}")

# Formula D: net_kg * mp + stc
d = round(a + stc_f, 4)
print(f"D: net_kg*mp + stc = {a} + {stc_f} = {d}")

# Formula E: net_g * mp (if DB net is actually g)
e = round(net_f * mp_f, 6)
print(f"E: net_g * mp (if DB net is g) = {net_f} * {mp_f} = {e}")

# Excel reference
excel_mat = 0.45304
excel_total = 0.7861
excel_stc = 0.33306
print(f"\nExcel: mat_cost={excel_mat} stc={excel_stc} total={excel_total}")
print(f"Excel验证: {excel_mat} + {excel_stc} = {round(excel_mat + excel_stc, 5)}")

conn.close()
