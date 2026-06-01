# -*- coding: utf-8 -*-
import zipfile, re

p = r'static\uploads\prices\上海万向钱潮A-A\上海万向.xlsx'
with zipfile.ZipFile(p, 'r') as z:
    sheet = z.read('xl/worksheets/sheet3.xml').decode('utf-8')
    sst = z.read('xl/sharedStrings.xml').decode('utf-8')

# 共享字符串
strings = []
for si in re.findall(r'<si>(.*?)</si>', sst, re.DOTALL):
    texts = re.findall(r'<t[^>]*>([^<]*)</t>', si)
    strings.append(''.join(texts))

print(f"共享字符串数量: {len(strings)}")
print("前20个共享字符串:")
for i, s in enumerate(strings[:20]):
    print(f"  [{i}] = {s}")

# 找 C 列单元格
print("\nC 列前5个单元格:")
for rm in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', sheet, re.DOTALL):
    rn = int(rm.group(1))
    if rn < 2 or rn > 10:
        continue
    content = rm.group(2)
    cm = re.search(r'<c r="C' + str(rn) + r'"([^>]*)>(.*?)</c>', content, re.DOTALL)
    if not cm:
        print(f"  行{rn}: 无C列单元格")
        continue
    attrs = cm.group(1)
    cell = cm.group(2)
    t_m = re.search(r'\bt="([^"]+)"', attrs)
    v_m = re.search(r'<v>([^<]+)</v>', cell)
    t = t_m.group(1) if t_m else 'n'
    v = v_m.group(1) if v_m else 'no_v'
    print(f"  行{rn}: t={t} v={v}")
