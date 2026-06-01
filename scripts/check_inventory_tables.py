import psycopg2

conn = psycopg2.connect(
    dbname='stamping_system',
    user='postgres',
    password='thehaoshi5DE',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# 检查所有相关表的 FK 约束
for tbl in ['finished_inventory', 'remnant_inventory',
            'finished_inventory_sf', 'remnant_inventory_sf',
            'production_logs', 'sf_production_logs',
            'part_aliases', 'die_parts', 'quotes']:
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """, (tbl,))
    cols = cur.fetchall()
    if cols:
        print(f'\n=== {tbl} ===')
        for c in cols:
            print(f'  {c[0]}: {c[1]}')
    else:
        print(f'\n=== {tbl} === (表不存在)')

conn.close()
