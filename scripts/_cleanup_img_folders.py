# -*- coding: utf-8 -*-
"""清理 part_images 目录，只保留数据库中真实存在零件号的图片文件夹"""
import os, shutil
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()

img_base = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images'

for cust_folder in os.listdir(img_base):
    cpath = os.path.join(img_base, cust_folder)
    if not os.path.isdir(cpath):
        continue

    # 获取该客户在数据库中的所有零件号
    cust_db_name = cust_folder  # 文件夹名 = tooling_customers.name
    cur.execute("""
        SELECT DISTINCT pt.part_number
        FROM prices p
        JOIN parts pt ON pt.id = p.part_id
        JOIN tooling_customers tc ON tc.id = p.customer_id
        WHERE tc.name = %s
    """, (cust_folder,))
    valid_parts = {r[0] for r in cur.fetchall() if r[0]}

    deleted = []
    kept = []
    for p_folder in os.listdir(cpath):
        pdir = os.path.join(cpath, p_folder)
        if not os.path.isdir(pdir):
            continue
        # 去掉工艺后缀后再匹配
        clean = p_folder
        for suffix_re in [r'[（(][^）)]*(?:涂|热|电|镀|磷|钝|氧)[^）)]*[）)]']:
            import re
            clean = re.sub(suffix_re, '', clean).strip()
        if clean in valid_parts:
            kept.append(p_folder)
        else:
            shutil.rmtree(pdir)
            deleted.append(p_folder)

    print(f"[{cust_folder}] 保留 {len(kept)}, 删除 {len(deleted)} {deleted if deleted else ''}")

conn.close()
