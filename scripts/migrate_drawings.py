# -*- coding: utf-8 -*-
"""迁移现有图纸到标准分类路径"""
import sys, os, shutil
sys.stdout.reconfigure(encoding='utf-8')
import psycopg2

BASE = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\drawings'
DB_CONFIG = dict(dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost', port='5432')

def safe(s):
    import re
    return re.sub(r'[\\/:*?"<>|]', '_', (s or '').strip())

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# 找出所有 parts.drawing_url 中不含 _unassigned 的记录（需要迁移）
cur.execute("""
    SELECT p.id, p.part_number, p.internal_name, p.drawing_url, tc.name as customer_name
    FROM parts p
    LEFT JOIN tooling_customers tc ON p.customer_id = tc.id
    WHERE p.drawing_url IS NOT NULL
      AND p.drawing_url NOT LIKE '%_unassigned%'
""")
rows = cur.fetchall()
print(f'需要迁移的零件图纸记录: {len(rows)} 条')

for part_id, part_num, part_name, url, cust_name in rows:
    if not url or not cust_name:
        print(f'  part {part_id}: 跳过（无客户名或URL为空）')
        continue

    # 生成标准路径
    subdir = '/'.join([safe(cust_name), safe(part_name or ''), safe(part_num or str(part_id))]) + '/drawings'
    std_dir = os.path.join(BASE, subdir)
    old_file = os.path.join(BASE, url.replace('/static/uploads/drawings/', ''))
    new_file = os.path.join(std_dir, os.path.basename(old_file))

    print(f'\n迁移 part {part_id} ({part_num}):')
    print(f'  从: {url}')
    print(f'  到: /static/uploads/drawings/{subdir}{os.path.basename(old_file)}')

    if not os.path.exists(old_file):
        print(f'  错误: 文件不存在')
        continue

    os.makedirs(std_dir, exist_ok=True)
    if os.path.exists(new_file):
        print(f'  警告: 目标文件已存在，跳过')
        continue

    shutil.move(old_file, new_file)
    new_url = f'/static/uploads/drawings/{subdir}{os.path.basename(old_file)}'
    cur.execute("UPDATE parts SET drawing_url = %s WHERE id = %s", (new_url, part_id))
    conn.commit()
    print(f'  成功!')

# 同样处理 sdr 图纸（从 sdr/ 目录迁移）
print('\n\n=== 迁移 SDR 图纸 ===')
sdr_dir = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\sdr'
if os.path.exists(sdr_dir):
    for fname in os.listdir(sdr_dir):
        if fname.startswith('q'):
            # 格式: q{quote_id}_{uuid}.pdf
            parts2 = fname.split('_')
            if len(parts2) >= 2:
                try:
                    qid = int(parts2[0].replace('q', ''))
                except ValueError:
                    print(f'  SDR 文件 {fname}: 无法解析报价单ID，跳过')
                    continue

                cur.execute("""
                    SELECT tc.name, p.internal_name, p.part_number, q.sdr_drawing_path
                    FROM quotes q
                    JOIN parts p ON q.part_id = p.id
                    LEFT JOIN tooling_customers tc ON COALESCE(q.customer_id, p.customer_id) = tc.id
                    WHERE q.id = %s
                """, (qid,))
                row2 = cur.fetchone()
                if not row2:
                    print(f'  SDR 文件 {fname}: 报价单 {qid} 不存在，跳过')
                    continue

                cust_name2, part_name2, part_num2, old_sdr_path = row2
                old_path = os.path.join(sdr_dir, fname)

                if not cust_name2:
                    print(f'  SDR 文件 {fname}: 报价单 {qid} 无客户，移到 _unassigned')
                    subdir2 = f'_unassigned/{qid}/drawings'
                else:
                    subdir2 = '/'.join([safe(cust_name2), safe(part_name2 or ''), safe(part_num2 or str(qid))]) + '/drawings'

                std_dir2 = os.path.join(BASE, subdir2)
                new_path = os.path.join(std_dir2, f'SDR_{fname[fname.find("_")+1:]}')
                os.makedirs(std_dir2, exist_ok=True)
                shutil.move(old_path, new_path)
                new_url2 = f'/static/uploads/drawings/{subdir2}SDR_{fname[fname.find("_")+1:]}'
                cur.execute("UPDATE quotes SET sdr_drawing_path = %s WHERE id = %s", (new_url2, qid))
                conn.commit()
                print(f'  SDR 文件 {fname} -> {new_url2}')

conn.close()
print('\n完成!')
