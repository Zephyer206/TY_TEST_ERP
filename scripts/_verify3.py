# -*- coding: utf-8 -*-
import psycopg2
import os

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

# 武汉万向 internal_name
print('=== 武汉万向 internal_name ===')
cur.execute('''
    SELECT pt.part_number, pt.internal_name
    FROM prices p
    JOIN parts pt ON pt.id=p.part_id
    WHERE p.customer_id=55
    ORDER BY pt.part_number;
''')
for r in cur.fetchall():
    print(f'  {r[0]} -> {r[1]}')

# 图片是否存在
print('\n=== 图片文件检查 ===')
img_base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images'
for cust in os.listdir(img_base):
    cpath = os.path.join(img_base, cust)
    if os.path.isdir(cpath):
        parts = os.listdir(cpath)
        print(f'  {cust}: {len(parts)} 个零件')
        for p in sorted(parts)[:3]:
            pdir = os.path.join(cpath, p)
            imgs = sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []
            print(f'    {p}: {imgs}')

conn.close()
