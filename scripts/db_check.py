import sys
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')
import psycopg2
DB = {
    'dbname': 'stamping_system',
    'user': 'postgres',
    'password': 'thehaoshi5DE',
    'host': 'localhost',
    'port': '5432'
}
try:
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='treatment_dicts'")
            print('Table exists:', cur.fetchall())
            cur.execute('SELECT COUNT(*) FROM treatment_dicts')
            print('Total rows:', cur.fetchone())
            cur.execute('SELECT id, name, calc_mode, rate, unit, is_active FROM treatment_dicts')
            rows = cur.fetchall()
            print('All rows:')
            for r in rows:
                print(' ', r)
            cur.execute('SELECT id, name, is_active FROM treatment_dicts WHERE is_active = TRUE')
            print('Active rows:', cur.fetchall())
except Exception as e:
    print('ERROR:', type(e).__name__, e)
