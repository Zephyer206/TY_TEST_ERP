# -*- coding: utf-8 -*-
import os, openpyxl

for base in [r"C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices"]:
    if os.path.isdir(base):
        for name in os.listdir(base):
            subpath = os.path.join(base, name)
            if os.path.isdir(subpath):
                files = os.listdir(subpath)
                print(f"Dir: {name} -> {files}")
                for fname in files:
                    fpath = os.path.join(subpath, fname)
                    if fname.endswith('.xlsx'):
                        try:
                            wb = openpyxl.load_workbook(fpath, data_only=True)
                            print(f"  {fname}: sheets={wb.sheetnames}")
                            ws = wb.active
                            print(f"  First rows:")
                            for i, row in enumerate(ws.iter_rows(values_only=True)):
                                if i >= 5: break
                                print(f"    {list(row)[:12]}")
                        except Exception as e:
                            print(f"  {fname}: ERROR {e}")
            else:
                print(f"File: {name}")
