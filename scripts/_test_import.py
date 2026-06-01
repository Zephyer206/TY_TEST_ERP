# -*- coding: utf-8 -*-
import io, openpyxl

def _cell(row, col):
    if col < 0 or col >= len(row): return None
    v = row[col]
    if v is None: return None
    s = str(v).strip()
    return s if s else None

def _num(row, col):
    if col < 0 or col >= len(row): return None
    v = row[col]
    if v is None: return None
    try: return float(v)
    except: return None

def _parse(content):
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    sheets_priority = []
    for name in wb.sheetnames:
        ws = wb[name]
        if ws.max_row < 3: continue
        headers = [str(c).strip() if c is not None else '' for c in next(ws.iter_rows(values_only=True))]
        header_str = '|'.join(headers)
        if '原图产品编号' in header_str or '件号' in header_str:
            sheets_priority.insert(0, (name, headers))
        else:
            sheets_priority.append((name, headers))
    if not sheets_priority: raise ValueError("No sheet")
    target_name, headers = sheets_priority[0]
    ws = wb[target_name]

    def idx(keywords):
        for i, h in enumerate(headers):
            if any(kw in h for kw in keywords): return i
        return -1

    col_part  = idx(['原图产品编号', '零件编号', '规格型号', '件号'])
    col_gross = idx(['毛重', '单件毛重量', 'gross'])
    col_net   = idx(['净重', '单件净重量', '产品净重'])
    col_mp    = idx(['材料价格'])
    col_sp    = idx(['废料价格'])
    col_stc   = idx(['喷涂成本', '胶成本', '回火', '外协成本'])
    col_cost  = idx(['成本'])
    col_price = idx(['价格', '单价', 'price'])
    col_sales = idx(['销量', 'sales', '年销量'])

    rows_out = []
    last_valid = None

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0: continue
        part = _cell(row, col_part)
        if not part: continue
        part = str(part).strip()
        if '总计' in part or '合计' in part or not part:
            last_valid = None
            continue
        gross = _num(row, col_gross)
        net   = _num(row, col_net)
        mp    = _num(row, col_mp)
        sp    = _num(row, col_sp)
        stc   = _num(row, col_stc)
        cost  = _num(row, col_cost)
        price = _num(row, col_price)
        sales = _num(row, col_sales)
        if gross is None and net is None and mp is None:
            if last_valid:
                gross = last_valid['gross_weight']
                net   = last_valid['net_weight']
                mp    = last_valid['material_unit_price']
                sp    = last_valid['scrap_price']
                stc   = last_valid.get('surface_treatment_cost')
                cost  = last_valid.get('excel_cost')
        else:
            last_valid = {'gross_weight':gross,'net_weight':net,'material_unit_price':mp,'scrap_price':sp,'surface_treatment_cost':stc,'excel_cost':cost}
        mat_cost = None
        if net is not None and mp is not None:
            mat_cost = round(net * mp, 6)
        total_cost = None
        excel_cost = cost
        if excel_cost is not None:
            total_cost = excel_cost
            if stc is not None: total_cost = round(total_cost + stc, 6)
        elif mat_cost is not None:
            total_cost = mat_cost
            if stc is not None: total_cost = round(total_cost + stc, 6)
        rows_out.append({'part_number':part,'gross_weight':gross,'net_weight':net,'material_unit_price':mp,'scrap_price':sp,'surface_treatment_cost':stc,'excel_cost':excel_cost,'material_cost':mat_cost,'cost_override':total_cost,'current_price':price,'prev_year_sales':sales})
    return rows_out

path = r"C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\B-C武汉万向汽车制动器有限公司\武汉万向.xlsx"
with open(path, 'rb') as f: content = f.read()
rows = _parse(content)
print(f"Total rows: {len(rows)}")
for r in rows:
    print(f"  {r['part_number']}: gross={r['gross_weight']} net={r['net_weight']} mat_cost={r['material_cost']} excel_cost={r['excel_cost']} stc={r['surface_treatment_cost']} total_cost={r['cost_override']} price={r['current_price']} sales={r['prev_year_sales']}")

# Verify key cases
a03 = [r for r in rows if 'A00125983-03' in r['part_number'] and '喷涂' not in r['part_number']][0]
a04 = [r for r in rows if 'A00125983-04' in r['part_number']][0]
print(f"\n=== Key verifications ===")
print(f"A00125983-03: total_cost={a03['cost_override']} (expected ~0.285757)")
print(f"A00125983-04: total_cost={a04['cost_override']} (inherited + stc, expected ~0.285757+0.02832=0.314077)")
print(f"Verify mat_cost for 3502114XKV86A: 8.31 * 0.588317 = {8.31 * 0.588317184:.6f}")
