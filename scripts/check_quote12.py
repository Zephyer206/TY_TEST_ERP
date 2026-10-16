import psycopg2
DB_CONFIG = {'dbname': 'stamping_system', 'user': 'postgres',
             'password': '__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', 'host': 'localhost', 'port': '5432'}
with psycopg2.connect(**DB_CONFIG) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'quotes'
            ORDER BY ordinal_position
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
