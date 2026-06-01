# -*- coding: utf-8 -*-
"""验证修改后的成本公式和图片URL"""
import os, glob, sys

# === 1. 验证成本公式 ===
def _calc_material_cost(gross_weight, net_weight, material_unit_price, scrap_price):
    if net_weight is None:
        return None
    gw = float(gross_weight or 0)
    nw = float(net_weight or 0)
    mp = float(material_unit_price or 0)
    sp = float(scrap_price or 0)
    waste = gw - nw
    return round(nw * mp - waste * sp, 4)

# 武汉万向 id=177: gross=0.0047, net=0.0013, mp=0.0424, sp=0.0068
cost = _calc_material_cost(0.0047, 0.0013, 0.0424, 0.0068)
print(f"武汉万向 id=177:")
print(f"  净重={0.0013}kg 毛重={0.0047}kg")
print(f"  废料={0.0047-0.0013}kg 材料单价={0.0424} 废料价={0.0068}")
print(f"  材料成本 = {0.0013}×{0.0424} - {0.0047-0.0013}×{0.0068} = {cost}")
print(f"  总成本 = {cost} + surface({0.0103}) = {round(cost+0.0103, 4)}")

# 上海万向 id=163: gross=0.0231, net=0.0080, mp=0.4611, sp=0.1054
cost2 = _calc_material_cost(0.0231, 0.0080, 0.4611, 0.1054)
print(f"\n上海万向 id=163:")
print(f"  净重={0.0080}kg 毛重={0.0231}kg")
print(f"  废料={0.0231-0.0080}kg 材料单价={0.4611} 废料价={0.1054}")
print(f"  材料成本 = {0.0080}×{0.4611} - {0.0231-0.0080}×{0.1054} = {cost2}")
print(f"  总成本 = {cost2} + surface({0.2400}) = {round(cost2+0.2400, 4)}")

# === 2. 验证图片 URL ===
_PART_IMG_BASE = os.path.join("static", "uploads", "part_images")

def _get_image_url(customer_name, part_number):
    if not customer_name or not part_number:
        return None
    pattern = os.path.join(_PART_IMG_BASE, customer_name, part_number + ".*")
    matches = glob.glob(pattern)
    if matches:
        ext = os.path.splitext(matches[0])[1]
        return f"/static/uploads/part_images/{customer_name}/{part_number}{ext}"
    return None

# 已知武汉万向有图片的零件
print(f"\n图片URL测试:")
for part in ['3502114XKV86A', 'A00125979-5']:
    url = _get_image_url('B-C\u6b66\u6c49\u4e07\u5411\u6c7d\u8f66\u5236\u52a8\u5668\u6709\u9650\u516c\u53f8', part)
    print(f"  {part}: {url}")

# 验证 kg→g 转换
print(f"\n重量单位转换:")
print(f"  0.0047 kg = {round(0.0047*1000, 6)} g")
print(f"  0.0013 kg = {round(0.0013*1000, 6)} g")
print(f"  0.0231 kg = {round(0.0231*1000, 6)} g")
print(f"  0.0080 kg = {round(0.0080*1000, 6)} g")
