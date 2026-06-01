# -*- coding: utf-8 -*-
"""清理武汉万向残留的非零件号图片文件夹"""
import os, shutil

img_base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images'
wuhan = os.path.join(img_base, 'B-C\u6b66\u6c49\u4e07\u5411\u6c7d\u8f66\u5236\u52a8\u5668\u6709\u9650\u516c\u53f8')

# 已知正确的零件号（来自导入数据）
valid_parts = {
    '3502114XKV86A', '3502314AKY00A', '3502414AKY00A',
    '3502637XGW04A', 'A00125979-5', 'A00125983-03',
    'A00125983-3', 'A00126959-5', 'B00039879-07', 'F200005166-5T'
}

deleted = []
for p in os.listdir(wuhan):
    if p not in valid_parts:
        pdir = os.path.join(wuhan, p)
        if os.path.isdir(pdir):
            shutil.rmtree(pdir)
            deleted.append(p)

print(f"删除了 {len(deleted)} 个残留文件夹: {deleted}")

# 重新检查
remaining = sorted(os.listdir(wuhan))
print(f"\n清理后武汉万向共 {len(remaining)} 个文件夹:")
for p in remaining:
    print(f"  {p}")
