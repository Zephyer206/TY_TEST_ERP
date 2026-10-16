#!/usr/bin/env python3
"""
Test header detection on real Excel file
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

import xlrd

# Test on the real file path used by the script
excel_path = Path(__file__).parent / 'backend' / '..' / 'excel' / '五金模具及产品清单表.xls'

# Try to find the file
possible_paths = [
    Path('C:/Users/WIT_User/Desktop/Zephyr_test_Erp/excel/五金模具及产品清单表.xls'),
    Path(__file__).parent / 'excel' / '五金模具及产品清单表.xls',
]

excel_path = None
for p in possible_paths:
    if p.exists():
        excel_path = p
        break

if not excel_path:
    print("ERROR: Cannot find Excel file")
    sys.exit(1)

print(f"Found Excel: {excel_path}")

wb = xlrd.open_workbook(str(excel_path))

# Test sheet 1: 五金模具进度一览表
sheet = wb.sheet_by_index(1)
print(f"\n=== Sheet: {sheet.name} ===")
print(f"Rows: {sheet.nrows}, Cols: {sheet.ncols}")

# Print first 3 rows
for row_idx in range(min(3, sheet.nrows)):
    print(f"\nRow {row_idx}:")
    for col_idx in range(min(15, sheet.ncols)):
        val = sheet.cell_value(row_idx, col_idx)
        if val:
            print(f"  col_{col_idx}: {repr(val)}")

# Test sheet: 浙江万宝机械有限公司(A)
sheet2 = wb.sheet_by_name('浙江万宝机械有限公司(A)')
print(f"\n\n=== Sheet: {sheet2.name} ===")
print(f"Rows: {sheet2.nrows}, Cols: {sheet2.ncols}")

for row_idx in range(min(5, sheet2.nrows)):
    print(f"\nRow {row_idx}:")
    for col_idx in range(min(15, sheet2.ncols)):
        val = sheet2.cell_value(row_idx, col_idx)
        if val:
            print(f"  col_{col_idx}: {repr(val)}")
