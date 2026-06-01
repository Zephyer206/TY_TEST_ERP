# -*- coding: utf-8 -*-
import openpyxl, os

path = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\B-G芜湖伯特利\伯特利.xlsx'
wb = openpyxl.load_workbook(path, data_only=True)

# Simulate sheets_priority logic
sheets_priority = []
for name in wb.sheetnames:
    ws = wb[name]
    if ws.max_row < 3:
        print(f"SKIP {name}: max_row={ws.max_row}")
        continue
    headers = [str(c).strip() if c is not None else '' for c in next(ws.iter_rows(values_only=True))]
    header_str = '|'.join(headers)
    print(f"\n{name}: headers={headers}")
    if '原图产品编号' in header_str or '件号' in header_str:
        sheets_priority.insert(0, (name, headers))
    else:
        sheets_priority.append((name, headers))

print(f"\nSheets priority: {sheets_priority}")
target_name, headers = sheets_priority[0]

def idx(keywords):
    for i, h in enumerate(headers):
        if h and any(kw in h for kw in keywords):
            return i
    return -1

col_part  = idx(['原图产品编号', '零件编号', '规格型号', '件号'])
col_gross = idx(['单件毛重量', '毛重', 'gross'])
col_net   = idx(['单件净重量', '产品净重', '净重'])
col_mp    = idx(['材料价格'])
col_sp    = idx(['废料价格'])
col_stc   = idx(['喷涂成本', '胶成本', '回火', '外协成本'])
col_cost  = idx(['成本'])
col_price = idx(['价格', '单价', 'price'])
col_sales = idx(['销量', 'sales', '年销量'])

print(f"\nColumn indices: part={col_part} gross={col_gross} net={col_net} mp={col_mp} sp={col_sp} stc={col_stc} cost={col_cost} price={col_price} sales={col_sales}")

# Now test reading row 1 (first data row)
ws = wb[target_name]
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    part = row[col_part] if col_part >= 0 else None
    if part:
        gross = row[col_gross] if col_gross >= 0 else None
        net   = row[col_net]   if col_net   >= 0 else None
        print(f"\nRow{i}: part={part} gross={gross} net={net}")
        break
