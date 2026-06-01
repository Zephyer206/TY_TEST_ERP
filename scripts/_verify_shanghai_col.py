# -*- coding: utf-8 -*-
import openpyxl
p = r'static\uploads\prices\上海万向钱潮A-A\上海万向.xlsx'
wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
print('Sheets:', wb.sheetnames)
ws = wb['Sheet3']
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=3, values_only=True), 1):
    print(f'Row{i}: A={row[0]} B={str(row[1])[:30] if row[1] else None} C={row[2]} D={row[3]}')
wb.close()
