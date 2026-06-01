# -*- coding: utf-8 -*-
import os

base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images'
print("目录内容:")
for name in os.listdir(base):
    print(f"  repr={repr(name)} len={len(name)}")

# 直接列出文件
p = os.path.join(base, os.listdir(base)[0])
print(f"\n零件目录 ({repr(p)}):")
for f in os.listdir(p):
    print(f"  repr={repr(f)}")

# glob 测试
import glob
customer = os.listdir(base)[0]
part = os.listdir(os.path.join(base, customer))[0]
print(f"\n测试 glob:")
pattern1 = os.path.join(base, customer, part + ".*")
print(f"  pattern1: {repr(pattern1)}")
matches1 = glob.glob(pattern1)
print(f"  matches1: {matches1}")

# 看看实际编码
part_dir = os.path.join(base, customer, part)
print(f"\npart_dir repr: {repr(part_dir)}")
print(f"exists: {os.path.exists(part_dir)}")
files = os.listdir(part_dir)
print(f"files: {files}")
