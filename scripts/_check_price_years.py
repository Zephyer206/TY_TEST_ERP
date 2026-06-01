import psycopg2
conn = psycopg2.connect(host='localhost', dbname='stamping_system', user='postgres', password='thehaoshi5DE', port='5432')
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'price_years'
    ORDER BY ordinal_position;
""")
print("price_years columns:", cur.fetchall())
cur.execute("SELECT * FROM price_years LIMIT 3;")
print("Sample data:", cur.fetchall())
conn.close()
