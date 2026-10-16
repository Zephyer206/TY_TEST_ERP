import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='parts' ORDER BY ordinal_position")
print('parts columns:', [r[0] for r in cur.fetchall()])
conn.close()
