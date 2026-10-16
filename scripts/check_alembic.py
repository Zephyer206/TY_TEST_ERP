import psycopg2
conn = psycopg2.connect(dbname='stamping_system', user='postgres', password='__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")', host='localhost', port='5432')
cur = conn.cursor()
for tbl in ['part_customer_aliases', 'delivery_notes', 'delivery_items']:
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = '{tbl}'
        ORDER BY ordinal_position;
    """)
    print(f'\n=== {tbl} ===')
    for row in cur.fetchall():
        print(f'  {row[0]:<30} {row[1]:<25} nullable={row[2]} default={row[3]}')
# 检查 work_orders 首件字段
cur.execute("""
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'work_orders'
      AND column_name IN ('is_first_piece_required', 'first_piece_passed_at', 'first_piece_passed_by')
    ORDER BY ordinal_position;
""")
print('\n=== work_orders 首件字段 ===')
for row in cur.fetchall():
    print(f'  {row[0]:<35} {row[1]:<25} default={row[2]}')
conn.close()
