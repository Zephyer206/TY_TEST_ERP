import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='thehaoshi5DE', host='localhost', port='5432')
conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'materials' ORDER BY ordinal_position;")
print('materials 字段:', [r['column_name'] for r in cur.fetchall()])
conn.close()
