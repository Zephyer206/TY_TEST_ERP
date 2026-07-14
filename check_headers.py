#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xlrd

excel_path = 'excel/五金模具及产品清单表.xls'
wb = xlrd.open_workbook(excel_path, formatting_info=True)

# 检查两个sheet的表头位置
for sheet_name in ['60T 连续模', 'A-F日立高新']:
    sheet = wb.sheet_by_name(sheet_name)
    print(f'=== {sheet_name} ===')
    print(f'总行数: {sheet.nrows}')
    print()
    print('前10行内容:')
    for i in range(min(10, sheet.nrows)):
        row_values = [str(sheet.cell_value(i, j)).strip() for j in range(min(5, sheet.ncols))]
        non_empty = [v for v in row_values if v]
        if non_empty:
            print(f'  Row {i}: {" | ".join(non_empty[:5])}')
    print()
