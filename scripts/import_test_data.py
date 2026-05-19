"""
为生产员工（Lv.1）账号创建测试数据
零件 + tooling_molds 模具 + tooling_parts 关联 + 报工记录
"""
import psycopg2

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432"
}

def get_or_create_part(cur, part_number, part_name, status="新录入"):
    cur.execute("SELECT id FROM parts WHERE part_number = %s;", (part_number,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE parts SET internal_name=%s, status=%s WHERE id=%s;",
                    (part_name, status, row[0]))
        return row[0]
    cur.execute(
        "INSERT INTO parts (part_number, internal_name, status, current_price) "
        "VALUES (%s, %s, %s, 0.5) RETURNING id;",
        (part_number, part_name, status)
    )
    return cur.fetchone()[0]

def tooling_mold_exists(cur, mold_number):
    cur.execute("SELECT id FROM tooling_molds WHERE mold_number=%s;", (mold_number,))
    return cur.fetchone()

def main():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:

            # ── 1. 获取客户 ───────────────────────────────────────────
            cur.execute("SELECT id FROM tooling_customers LIMIT 1;")
            cust = cur.fetchone()
            customer_id = cust[0] if cust else None

            # ── 2. 创建零件 ──────────────────────────────────────────
            parts = [
                ("TEST-A001", "连接支架（一出二）",  "生产中"),
                ("TEST-A002", "法兰盘（四穴）",      "待产"),
                ("TEST-B001", "上盖板（单穴）",      "生产中"),
                ("TEST-B002", "固定卡扣",            "修模中"),
                ("TEST-C001", "底壳（一出三）",      "模具制作中"),
                ("TEST-C002", "加强筋板（单穴）",    "生产中"),
                ("TEST-D001", "定位套筒（一出二）",  "待产"),
            ]
            part_ids = {}
            for part_number, part_name, status in parts:
                pid = get_or_create_part(cur, part_number, part_name, status)
                part_ids[part_number] = pid
                print(f"  [零件] {part_number} → ID {pid}")

            conn.commit()

            # ── 3. 创建 tooling_molds ─────────────────────────────────
            molds = [
                ("TEST-M001", "连接支架",    "1出2", "生产中",     "已确认", "一出二，正常生产"),
                ("TEST-M002", "法兰盘",      "1出4", "待产",       "已确认", "一出四，待上模"),
                ("TEST-M003", "上盖板",      "1出1", "生产中",     "已确认", "单穴，正常"),
                ("TEST-M004", "固定卡扣",    "1出1", "修模中",     "已确认", "修模暂停"),
                ("TEST-M005", "底壳",        "1出3", "模具制作中", "待确认", "一出三，模具厂制作中"),
                ("TEST-M006", "加强筋板",    "1出1", "生产中",     "已确认", "单穴，正常"),
                ("TEST-M007", "定位套筒",    "1出2", "待产",       "已确认", "一出二，待上模"),
            ]

            mold_ids = {}
            for mold_number, prod_name, cavity_count, mold_status, cavity_status, remark in molds:
                row = tooling_mold_exists(cur, mold_number)
                if row:
                    mold_id = row[0]
                    mold_ids[mold_number] = mold_id
                    cur.execute("""
                        UPDATE tooling_molds SET mold_status=%s, cavity_status=%s,
                        remark=%s, customer_product_name=%s, cavity_count=%s
                        WHERE id=%s;
                    """, (mold_status, cavity_status, remark, prod_name, cavity_count, mold_id))
                    print(f"  [已存在] 模具 {mold_number} → ID {mold_id}")
                else:
                    cur.execute("""
                        INSERT INTO tooling_molds
                            (mold_number, customer_product_name, cavity_count, mold_status,
                             cavity_status, customer_id, customer_product_no,
                             material, spec_twph, remark)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING id;
                    """, (
                        mold_number, prod_name, cavity_count, mold_status,
                        cavity_status, customer_id,
                        mold_number.replace("TEST-M", "CUST-PN-"),
                        "SPCC", cavity_count, remark
                    ))
                    mold_id = cur.fetchone()[0]
                    mold_ids[mold_number] = mold_id
                    print(f"  [新增] 模具 {mold_number} → ID {mold_id}")

            conn.commit()

            # ── 4. 关联零件到 tooling_parts ──────────────────────────
            mappings = [
                ("TEST-A001", "TEST-M001"),
                ("TEST-A002", "TEST-M002"),
                ("TEST-B001", "TEST-M003"),
                ("TEST-B002", "TEST-M004"),
                ("TEST-C001", "TEST-M005"),
                ("TEST-C002", "TEST-M006"),
                ("TEST-D001", "TEST-M007"),
            ]
            for part_number, mold_number in mappings:
                mold_id = mold_ids.get(mold_number)
                part_id = part_ids.get(part_number)
                if not mold_id or not part_id:
                    continue
                cur.execute(
                    "SELECT id FROM tooling_parts WHERE mold_id=%s AND customer_product_no=%s;",
                    (mold_id, mold_number.replace("TEST-M", "CUST-PN-"))
                )
                if cur.fetchone():
                    print(f"  [已有] tooling_parts → 模具{mold_number} / 零件{part_number}")
                else:
                    cur.execute("""
                        INSERT INTO tooling_parts
                            (mold_id, customer_product_no, customer_product_name)
                        VALUES (%s,%s,%s);
                    """, (mold_id,
                          mold_number.replace("TEST-M", "CUST-PN-"),
                          molds[[m[0] for m in molds].index(mold_number)][1]))
                    print(f"  [关联] tooling_parts → 模具{mold_number} / 零件{part_number}")

            conn.commit()

            # ── 5. 报工记录 ──────────────────────────────────────────
            cur.execute("SELECT id FROM users WHERE role_level=1 LIMIT 1;")
            worker = cur.fetchone()
            if not worker:
                print("  未找到 Lv.1 员工账号，请先创建员工账号。")
                return
            worker_id = worker[0]

            # 清理旧测试报工
            part_id_list = list(part_ids.values())
            cur.execute(
                "DELETE FROM production_logs WHERE part_id = ANY(%s);",
                (part_id_list,)
            )

            logs = [
                # (零件编号,        良品, 报废, 报废原因,    状态)
                ("TEST-A001",  120,  3,  "冲压刮伤",  "approved"),
                ("TEST-A001",   80,  0,  None,        "pending"),
                ("TEST-A002",  200,  8,  "模具故障",  "pending"),
                ("TEST-B001",   50,  0,  None,        "approved"),
                ("TEST-B002",   10,  5,  "模具故障",  "rejected"),
                ("TEST-C001",   30,  2,  "材料不良",  "pending"),
                ("TEST-C002",   90,  1,  "定位偏移",  "approved"),
                ("TEST-D001",  150,  0,  None,        "pending"),
            ]
            for part_number, qty_good, qty_bad, scrap_reason, status in logs:
                part_id = part_ids.get(part_number)
                if not part_id:
                    continue
                cur.execute("""
                    INSERT INTO production_logs
                        (part_id, worker_id, qty_good, qty_bad, scrap_reason, status)
                    VALUES (%s,%s,%s,%s,%s,%s);
                """, (part_id, worker_id, qty_good, qty_bad, scrap_reason, status))
                print(f"  [报工] {part_number} 良品{qty_good} 报废{qty_bad} [{status}]")

            conn.commit()
            print("")
            print("=" * 50)
            print("Test data import complete!")
            print("=" * 50)

if __name__ == "__main__":
    main()
