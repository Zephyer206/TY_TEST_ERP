import sys
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')
import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    'dbname': 'stamping_system',
    'user': 'postgres',
    'password': '__import__("os").environ.get("ZEPHYR_DB_PASSWORD", "")',
    'host': 'localhost',
    'port': '5432'
}

# Simulate EXACTLY what the db_service function does
print('=== 模拟 get_all_treatments 的 with 结构 ===')
conn = psycopg2.connect(**DB)
print('autocommit:', conn.autocommit)
print('isolation_level:', conn.isolation_level)

cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
    SELECT id, name, calc_mode, rate, unit
    FROM treatment_dicts
    WHERE is_active = TRUE
    ORDER BY id
""")
result = [dict(r) for r in cur.fetchall()]
print('Result:', result)
cur.close()
conn.close()

print()
print('=== 测试 autocommit=True 连接 ===')
conn2 = psycopg2.connect(**DB)
conn2.autocommit = True
cur2 = conn2.cursor()
cur2.execute('SELECT COUNT(*) FROM treatment_dicts WHERE is_active=TRUE')
print('Count with autocommit=True:', cur2.fetchone())
cur2.execute("INSERT INTO treatment_dicts (name,calc_mode,rate,unit) VALUES ('test_autocommit','manual',1,'元/件') ON CONFLICT (name) DO NOTHING")
cur2.execute('SELECT COUNT(*) FROM treatment_dicts WHERE is_active=TRUE')
print('Count after insert:', cur2.fetchone())
cur2.close()
conn2.close()

print()
print('=== 测试 without explicit commit ===')
conn3 = psycopg2.connect(**DB)
print('autocommit after connect:', conn3.autocommit)
cur3 = conn3.cursor()
cur3.execute("INSERT INTO treatment_dicts (name,calc_mode,rate,unit) VALUES ('test_no_commit','manual',1,'元/件') ON CONFLICT (name) DO NOTHING")
# NO commit here
cur3.execute('SELECT COUNT(*) FROM treatment_dicts WHERE is_active=TRUE')
print('Count (inside same conn, no commit):', cur3.fetchone())
cur3.close()
conn3.close()

# Reconnect and check
conn4 = psycopg2.connect(**DB)
conn4.autocommit = True
cur4 = conn4.cursor()
cur4.execute('SELECT COUNT(*) FROM treatment_dicts WHERE name IN (%s,%s)', ('test_autocommit', 'test_no_commit'))
print('Count (new conn, no explicit commit):', cur4.fetchone())
cur4.close()
conn4.close()
