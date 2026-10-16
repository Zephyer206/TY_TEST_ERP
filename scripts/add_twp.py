import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost')
cur = conn.cursor()

# Check current parts columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='parts' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print('parts columns:', cols)

# Add T/W/P if not present
for col_name, col_type in [
    ("thickness",    "NUMERIC(10,4) NOT NULL DEFAULT 0"),
    ("width",        "NUMERIC(10,4) NOT NULL DEFAULT 0"),
    ("press_stroke", "NUMERIC(10,4) NOT NULL DEFAULT 0"),
]:
    if col_name not in cols:
        cur.execute(f"ALTER TABLE parts ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
        print(f'ADDED: {col_name}')
    else:
        print(f'EXISTS: {col_name}')

conn.commit()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='parts' ORDER BY ordinal_position")
print('parts columns after:', [r[0] for r in cur.fetchall()])
conn.close()
print('Done.')
