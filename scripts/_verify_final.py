# -*- coding: utf-8 -*-
import os, psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

img_base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images'

for cust_folder in sorted(os.listdir(img_base)):
    cpath = os.path.join(img_base, cust_folder)
    if not os.path.isdir(cpath):
        continue
    parts = sorted(os.listdir(cpath))
    print(f"\n[{cust_folder}] {len(parts)} 个图片")
    for p in parts[:5]:
        imgs = sorted(os.listdir(os.path.join(cpath, p)))
        print(f"  {p}: {imgs}")
    if len(parts) > 5:
        print(f"  ... 还有 {len(parts)-5} 个")

print("\n=== internal_name 示例 ===")
for cid, name in [(55,'武汉万向'),(59,'芜湖伯特利'),(27,'上海万向')]:
    cur.execute('''
        SELECT pt.part_number, pt.internal_name
        FROM prices p
        JOIN parts pt ON pt.id=p.part_id
        WHERE p.customer_id=%s
        LIMIT 3;
    ''', (cid,))
    print(f"\n{name}:")
    for r in cur.fetchall():
        print(f"  {r[0]} -> {r[1]}")

conn.close()
