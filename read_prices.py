import os
import openpyxl

base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices'

for root, dirs, files in os.walk(base):
    for fname in files:
        fpath = os.path.join(root, fname)
        rel = os.path.relpath(fpath, base)
        print(f"\n{'='*60}")
        print(f"文件: {rel}")
        print(f"{'='*60}")
        try:
            wb = openpyxl.load_workbook(fpath, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                print(f"\n  Sheet: {sheet_name}  (rows={ws.max_row}, cols={ws.max_column})")
                # 打印前 min(10, max_row) 行
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i >= 10:
                        print("  ... (更多行)")
                        break
                    # 打印非空行
                    if any(cell is not None for cell in row):
                        print(f"  Row{i+1}: {list(row)}")
        except Exception as e:
            print(f"  读取失败: {e}")
