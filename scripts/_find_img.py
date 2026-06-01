# -*- coding: utf-8 -*-
import os

base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images'
print(f"Base: {base}")
print(f"Exists: {os.path.exists(base)}")

for root, dirs, files in os.walk(base):
    for f in files:
        if 'A00125983' in f or 'A00125983' in root:
            print(f"  {os.path.join(root, f)}")

# Also check the Wuhan directory
cust_dir = os.path.join(base, 'B-C武汉万向汽车制动器有限公司')
print(f"\nCustomer dir exists: {os.path.exists(cust_dir)}")
if os.path.exists(cust_dir):
    for f in os.listdir(cust_dir):
        print(f"  {f}")
