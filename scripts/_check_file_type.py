# -*- coding: utf-8 -*-
import os

for base in [r"C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices",
              r"C:\Users\Administrator\Desktop\Cloud-Stamping\uploads\prices"]:
    if os.path.isdir(base):
        for fname in os.listdir(base):
            fpath = os.path.join(base, fname)
            with open(fpath, 'rb') as f:
                header = f.read(8)
            print(f"{fname}: {header}")
