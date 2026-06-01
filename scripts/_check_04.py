# -*- coding: utf-8 -*-
import openpyxl

path = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\B-C武汉万向汽车制动器有限公司\武汉万向.xlsx'
wb = openpyxl.load_workbook(path, data_only=True)
ws = wb['Sheet1']

print("=== All rows with A00125983 ===")
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    part = str(row[1]).strip() if row[1] else ''
    if 'A00125983' in part:
        print(f"Row{i}: part={part}")
        print(f"  gross={row[8]} net={row[9]} mp={row[10]} mat={row[12]} stc={row[13]} cost={row[14]}")
        print(f"  price={row[16]} sales={row[17]}")
        print(f"  raw: {list(row)}")
        print()
