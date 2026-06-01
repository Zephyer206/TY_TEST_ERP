# 更新零件182的报价单：pending_tech -> independent, TECH_APPROVED -> DRAFT
import psycopg2

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432"
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# 先查看现状
cur.execute("""
    SELECT id, approval_status, pricing_mode FROM quotes
    WHERE part_id = 182 AND is_deleted = FALSE
    ORDER BY created_at DESC LIMIT 1;
""")
row = cur.fetchone()
print(f"更新前: id={row[0]}, status={row[1]}, mode={row[2]}")

# 更新：pending_tech -> independent, TECH_APPROVED -> DRAFT
cur.execute("""
    UPDATE quotes
    SET approval_status = 'DRAFT',
        pricing_mode    = 'independent',
        updated_at      = NOW()
    WHERE part_id = 182 AND is_deleted = FALSE
    RETURNING id, approval_status, pricing_mode;
""")
row2 = cur.fetchone()
print(f"更新后: id={row2[0]}, status={row2[1]}, mode={row2[2]}")
conn.commit()
conn.close()
print("完成!")
