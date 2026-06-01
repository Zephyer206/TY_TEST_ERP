# -*- coding: utf-8 -*-
import openpyxl, os

BASE = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices'
files = [
    ('武汉万向', os.path.join(BASE, 'B-C武汉万向汽车制动器有限公司', '武汉万向.xlsx')),
    ('伯特利',   os.path.join(BASE, 'B-G芜湖伯特利', '伯特利.xlsx')),
    ('上海万向', os.path.join(BASE, '上海万向钱潮A-A', '上海万向.xlsx')),
]

for name, path in files:
    print(f"\n{'='*60}")
    print(f"=== {name} ===")
    wb = openpyxl.load_workbook(path, data_only=True)
    print(f"Sheets: {wb.sheetnames}")
    for sname in wb.sheetnames:
        ws = wb[sname]
        headers = [str(c).strip() if c else '' for c in next(ws.iter_rows(values_only=True))]
        print(f"\n  Sheet: {sname} | Headers: {headers}")
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0: continue
            if row[0] is None and row[1] is None: continue
            print(f"  Row{i}: {[str(v)[:20] if v else None for v in row]}")
            if i >= 2: break
