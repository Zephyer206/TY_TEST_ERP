# -*- coding: utf-8 -*-
"""直接更新上海零件 internal_name（从 Excel XML 正确读取）"""
import zipfile, re, psycopg2, openpyxl

p = r'static\uploads\prices\上海万向钱潮A-A\上海万向.xlsx'

# 读取 Excel 中正确的 C 列产品名称
wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
ws = wb['Sheet3']
part_names = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0] and row[2]:
        part_no = str(row[0]).strip()
        internal_name = str(row[2]).strip()
        if part_no and internal_name and part_no not in ('总计', '合计', 'sum'):
            # 去掉工艺后缀
            part_no_clean = re.sub(r'[（(][^）)]*(?:涂|热|电|镀|喷|磷|钝|氧)[^）)]*[）)]', '', part_no).strip()
            if part_no_clean and part_no_clean not in part_names:
                part_names[part_no_clean] = internal_name
wb.close()

print(f"从 Excel 读取到 {len(part_names)} 个产品名称映射")
for pn, nm in sorted(part_names.items()):
    print(f"  {pn} -> {nm}")

# 更新数据库
conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', port='5432')
cur = conn.cursor()
updated = 0
for part_no, internal_name in part_names.items():
    cur.execute("""
        UPDATE parts SET internal_name=%s
        WHERE (part_number=%s OR customer_product_no=%s)
          AND customer_id=27
          AND (internal_name IS NULL OR internal_name = '' OR internal_name ~ '^[0-9.]+$')
    """, (internal_name, part_no, part_no))
    if cur.rowcount > 0:
        print(f"  更新: {part_no} -> {internal_name}")
        updated += cur.rowcount

conn.commit()
print(f"\n共更新 {updated} 条记录")

# 验证
cur.execute('''
    SELECT pt.part_number, pt.internal_name
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE p.customer_id=27 ORDER BY pt.part_number;
''')
print("\n上海万向 internal_name 更新后:")
for r in cur.fetchall():
    print(f"  {r[0]} -> {r[1]}")
conn.close()
