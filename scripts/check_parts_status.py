"""检查 parts 158/157 的当前状态"""
import psycopg2

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432"
}

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True

with conn.cursor() as cur:
    print("=== 检查剩余零件 quotes 关联 ===")
    cur.execute("""
        SELECT p.id, p.part_number, q.id, q.approval_status, q.is_deleted, q.quote_serial
        FROM parts p
        LEFT JOIN quotes q ON q.part_id = p.id
        ORDER BY p.id;
    """)
    for r in cur.fetchall():
        print("part_id=%s, part_number=%r | Q_id=%s, status=%s, deleted=%s, serial=%s" % (
            r[0], r[1], r[2], r[3], r[4], r[5]))

    print("\n=== dies 表 ===")
    cur.execute("SELECT id, part_id, mold_number FROM dies ORDER BY id;")
    for r in cur.fetchall():
        print("  die_id=%s, part_id=%s, mold_number=%r" % (r[0], r[1], r[2]))

conn.close()
print("\n[DONE]")
