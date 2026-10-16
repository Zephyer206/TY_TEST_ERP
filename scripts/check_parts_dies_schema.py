"""检查 parts 表结构，确认 T/W/P 字段位置"""
import psycopg2

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": __import__("os").environ.get("ZEPHYR_DB_PASSWORD", ""),
    "host": "localhost",
    "port": "5432"
}

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True

with conn.cursor() as cur:
    # parts 表结构
    print("=== parts 表所有字段 ===")
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'parts'
        ORDER BY ordinal_position;
    """)
    for r in cur.fetchall():
        print("  %s: %s" % (r[0], r[1]))

    print("\n=== dies 表所有字段 ===")
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'dies'
        ORDER BY ordinal_position;
    """)
    for r in cur.fetchall():
        print("  %s: %s" % (r[0], r[1]))

    print("\n=== 剩余零件的实际数据 ===")
    cur.execute("SELECT * FROM parts ORDER BY id DESC;")
    cols = [desc[0] for desc in cur.description]
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        print("  id=%s, part_number=%r, thickness=%s, width=%s, press_stroke=%s" % (
            d.get('id'), d.get('part_number'), d.get('thickness'), d.get('width'), d.get('press_stroke')))

    print("\n=== dies 表数据 ===")
    cur.execute("SELECT * FROM dies ORDER BY id;")
    cols2 = [desc[0] for desc in cur.description]
    for row in cur.fetchall():
        d = dict(zip(cols2, row))
        print("  die_id=%s, part_id=%s, mold_number=%r, thickness_mm=%s, width_mm=%s, pitch_mm=%s" % (
            d.get('id'), d.get('part_id'), d.get('mold_number'),
            d.get('thickness_mm'), d.get('width_mm'), d.get('pitch_mm')))

conn.close()
print("\n[DONE]")
