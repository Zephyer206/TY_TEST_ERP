import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='thehaoshi5DE', host='localhost')
cur = conn.cursor()

# Check parts columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='parts' ORDER BY ordinal_position")
print('parts columns:', [r[0] for r in cur.fetchall()])

# Check material_batches columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='material_batches' ORDER BY ordinal_position")
print('material_batches columns:', [r[0] for r in cur.fetchall()])

# Check production_sessions columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='production_sessions' ORDER BY ordinal_position")
print('production_sessions columns:', [r[0] for r in cur.fetchall()])

# Check equipments columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='equipments' ORDER BY ordinal_position")
print('equipments columns:', [r[0] for r in cur.fetchall()])

# Check if sample_inventory exists
cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='sample_inventory'")
print('sample_inventory exists:', cur.fetchone() is not None)

# Check qa_audit_logs columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='qa_audit_logs' ORDER BY ordinal_position")
print('qa_audit_logs columns:', [r[0] for r in cur.fetchall()])

conn.close()
