# -*- coding: utf-8 -*-
import openpyxl, sys
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')
from app.api.sales import _parse_price_excel_bytes

path = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\价格成本核算模板.xlsx'

# 先看工作表名称和第一行（表头）
wb = openpyxl.load_workbook(path, data_only=True)
print(f"工作表: {wb.sheetnames}")
for name in wb.sheetnames:
    ws = wb[name]
    print(f"\n=== 工作表: {name} (max_row={ws.max_row}, max_col={ws.max_column}) ===")
    for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
        print(f"  {row}")

# 用解析器解析
with open(path, 'rb') as f:
    content = f.read()

print("\n\n=== 解析器输出（preview） ===")
try:
    rows, summary = _parse_price_excel_bytes(content, customer_id=55)
    print(f"Total rows: {summary.get('total_rows')}")
    for row in rows:
        print(f"  part_number={row.get('part_number')!r}  "
              f"gross={row.get('gross_weight')}  net={row.get('net_weight')}  "
              f"mp={row.get('material_unit_price')}  scrap={row.get('scrap_price')}  "
              f"stc={row.get('surface_treatment_cost')}  mat_cost={row.get('material_cost')}  "
              f"override={row.get('cost_override')}  remark={row.get('remark')!r}")
except Exception as e:
    print(f"解析出错: {e}")
