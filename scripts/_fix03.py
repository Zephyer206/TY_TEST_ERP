# -*- coding: utf-8 -*-
import openpyxl

path = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices\B-C武汉万向汽车制动器有限公司\武汉万向.xlsx'
wb = openpyxl.load_workbook(path, data_only=True)
ws = wb['Sheet1']

print("=== A00125983-03 Excel raw data ===")
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0: continue
    part = str(row[1]).strip() if row[1] else ''
    if 'A00125983-03' in part and '喷涂' not in part:
        gross_g = row[8]   # 单件毛重量(g)
        net_g   = row[9]   # 单件净重量(g)
        mp_excel = row[10] # 材料价格
        mat_cost = row[12] # 材料成本
        stc      = row[13]  # 外协成本
        cost     = row[14]  # 成本
        print(f"Excel raw: gross={gross_g}g net={net_g}g mp_excel={mp_excel}")
        print(f"  mat_cost={mat_cost} stc={stc} cost={cost}")

        # 旧导入公式（错误）：mp_db = mp_excel * 1000 → 120
        mp_old = mp_excel * 1000
        mat_old = net_g / 1000 * mp_old
        print(f"\n旧导入: mp_db={mp_old} mat={mat_old:.6f} (差{abs(mat_old - mat_cost):.4f})")

        # 新正确公式：mp_db = mat_cost / net_kg = mat_cost * 1000 / net_g
        mp_new = mat_cost / (net_g / 1000)
        mat_new = (net_g / 1000) * mp_new
        print(f"正确导入: mp_db={mp_new:.6f} mat={mat_new:.6f} (差{abs(mat_new - mat_cost):.6f})")

        # 验证: 用户期望 mat=0.0973 stc=0.03 total=0.13
        stc_new = 0.03
        total_new = round(mat_cost + stc_new, 4)
        print(f"\n修正后: mat={mat_cost:.6f} stc={stc_new} total={total_new}")
        print(f"  用户期望: mat=0.0973 stc=0.03 total=0.13")
        print(f"  match: {abs(mat_cost - 0.0973) < 0.001 and abs(stc_new - 0.03) < 0.001}")
