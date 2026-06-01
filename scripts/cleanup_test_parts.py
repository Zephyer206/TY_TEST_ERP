"""
直接删除 TEST 零件的脚本
验证 delete_part_by_id 函数是否正常工作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.db_service import delete_part_by_id

# 先查一下
import psycopg2
conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='thehaoshi5DE',
    host='localhost',
    port='5432'
)
cur = conn.cursor()
cur.execute("SELECT id, part_number FROM parts WHERE LOWER(part_number) LIKE '%test%';")
parts = cur.fetchall()
print(f"删除前 TEST 零件数: {len(parts)}")
for p in parts:
    print(f"  id={p[0]}, part_number={p[1]!r}")
conn.close()

# 执行删除
for p in parts:
    pid = p[0]
    pn = p[1]
    print(f"\n正在删除 id={pid}, part_number={pn!r}...")
    try:
        delete_part_by_id(pid)
        print(f"  删除成功！")
    except Exception as e:
        print(f"  删除失败: {e}")

# 确认
conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='thehaoshi5DE',
    host='localhost',
    port='5432'
)
cur = conn.cursor()
cur.execute("SELECT id, part_number FROM parts WHERE LOWER(part_number) LIKE '%test%';")
parts = cur.fetchall()
print(f"\n删除后 TEST 零件数: {len(parts)}")
conn.close()

if len(parts) == 0:
    print("\n所有 TEST 零件已删除完毕！")
