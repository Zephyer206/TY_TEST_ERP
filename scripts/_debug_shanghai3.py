# -*- coding: utf-8 -*-
"""调试：比较不同读取方式下的上海数据"""
import openpyxl

p = r'static\uploads\prices\上海万向钱潮A-A\上海万向.xlsx'

wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
print("Sheets:", wb.sheetnames)

# 用 openpyxl 直接读 Sheet3
ws = wb['Sheet3']
print("\n=== Sheet3 前5行（完整） ===")
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=5, values_only=True), 1):
    print(f"Row{i}: {list(row[:8])}")

wb.close()
