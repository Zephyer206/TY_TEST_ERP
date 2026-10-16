import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost', port='5432')
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='parts' AND column_name='remark';")
print('remark column:', cur.fetchone())
cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='parts' AND indexname='uq_parts_remark';")
print('partial index:', cur.fetchone())
conn.close()
