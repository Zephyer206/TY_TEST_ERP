import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='thehaoshi5DE', host='localhost')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'material_transactions' ORDER BY ordinal_position")
print("material_transactions columns:", [(r[0], r[1]) for r in cur.fetchall()])

cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'production_sessions' ORDER BY ordinal_position")
print("production_sessions columns:", [(r[0], r[1]) for r in cur.fetchall()])

cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'qa_audit_logs' ORDER BY ordinal_position")
print("qa_audit_logs columns:", [(r[0], r[1]) for r in cur.fetchall()])

cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'defect_logs' ORDER BY ordinal_position")
print("defect_logs columns:", [(r[0], r[1]) for r in cur.fetchall()])

conn.close()
