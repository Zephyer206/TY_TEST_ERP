# -*- coding: utf-8 -*-
import psycopg2
conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', port='5432')
cur = conn.cursor()
for cid, name in [(55,'武汉万向'),(59,'芜湖伯特利'),(27,'上海万向')]:
    cur.execute('''
        SELECT pt.part_number, pt.internal_name
        FROM prices p JOIN parts pt ON pt.id=p.part_id
        WHERE p.customer_id=%s ORDER BY pt.part_number LIMIT 5;
    ''', (cid,))
    print(f"\n[{name}]")
    for r in cur.fetchall():
        print(f"  {r[0]} -> {r[1]}")
conn.close()
