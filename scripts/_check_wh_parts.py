# -*- coding: utf-8 -*-
import openpyxl

path = r"C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\B-C武汉万向汽车制动器有限公司\武汉万向.xlsx"
wb = openpyxl.load_workbook(path, data_only=True)

print("Sheets:", wb.sheetnames)
ws = wb['Sheet1']
print(f"Total rows: {ws.max_row}")

# Find all A00125983 variants
print("\n=== A00125983 rows ===")
for i, row in enumerate(ws.iter_rows(values_only=True)):
    val = str(row[1] or '') if row[1] is not None else ''
    if 'A00125983' in val:
        print(f"  Row {i+1}: {list(row)[:12]}")

# Print ALL rows with part numbers
print("\n=== All part numbers ===")
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    part = str(row[1] or '') if row[1] is not None else ''
    name = str(row[3] or '') if row[3] is not None else ''
    if part:
        print(f"  Row {i+1}: {part} | {name}")
