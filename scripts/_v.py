# -*- coding: utf-8 -*-
import psycopg2
conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()
cur.execute('''
    SELECT pt.part_number, pt.internal_name
    FROM prices p JOIN parts pt ON pt.id=p.part_id
    WHERE p.customer_id=27 ORDER BY pt.part_number;
''')
for r in cur.fetchall():
    print(r[0], '->', r[1])
conn.close()
