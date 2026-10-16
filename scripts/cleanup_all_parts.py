"""强制清理 part_number='12' 及相关数据"""
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
    # 查出 part_number='12' 的零件
    cur.execute("SELECT id, part_number, remark FROM parts WHERE part_number = '12';")
    rows = cur.fetchall()
    if not rows:
        print("part_number='12' 不存在于 parts 表中，任务完成。")
    else:
        part_id = rows[0][0]
        print("查到 part_number='12': ID=%d" % part_id)

        # 先查出该零件的所有报价单（含已软删除的）
        cur.execute("""
            SELECT id, part_id, approval_status, is_deleted, quote_serial
            FROM quotes WHERE part_id = %s;
        """, (part_id,))
        quotes = cur.fetchall()
        print("该零件的报价单:")
        for q in quotes:
            print("  Q_id=%s, status=%s, deleted=%s" % (q[0], q[2], q[3]))

        print("\n--- 开始强制清理 ---")

        # 清理机台上的模具引用
        cur.execute("""
            UPDATE machines SET current_mold_id = NULL
            WHERE current_mold_id IN (SELECT id FROM dies WHERE part_id = %s);
        """, (part_id,))
        print("  [machines] 清理 current_mold_id: %d 条" % cur.rowcount)

        # 删除别名
        cur.execute("DELETE FROM part_aliases WHERE internal_part_id = %s;", (part_id,))
        print("  [part_aliases] 删除: %d 条" % cur.rowcount)

        # 删除库存
        cur.execute("DELETE FROM finished_inventory WHERE part_id = %s;", (part_id,))
        print("  [finished_inventory] 删除: %d 条" % cur.rowcount)
        cur.execute("DELETE FROM remnant_inventory WHERE part_id = %s;", (part_id,))
        print("  [remnant_inventory] 删除: %d 条" % cur.rowcount)

        # 删除报工
        cur.execute("DELETE FROM production_logs WHERE part_id = %s;", (part_id,))
        print("  [production_logs] 删除: %d 条" % cur.rowcount)

        # 删除模具关联（会触发 dies 级联删除）
        cur.execute("DELETE FROM die_parts WHERE part_id = %s;", (part_id,))
        print("  [die_parts] 删除: %d 条" % cur.rowcount)

        # 删除该零件所有报价单（不管 is_deleted 状态）
        cur.execute("DELETE FROM quotes WHERE part_id = %s;", (part_id,))
        print("  [quotes] 物理删除: %d 条" % cur.rowcount)

        # 删除零件主档
        cur.execute("DELETE FROM parts WHERE id = %s;", (part_id,))
        print("  [parts] 删除: %d 条" % cur.rowcount)

        print("\n--- 验证 ---")
        cur.execute("SELECT COUNT(*) FROM parts WHERE id = %s;", (part_id,))
        print("  parts 中该零件剩余: %d" % cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM quotes WHERE part_id = %s;", (part_id,))
        print("  quotes 中该零件剩余: %d" % cur.fetchone()[0])
        cur.execute("SELECT id, part_number FROM parts ORDER BY id DESC;")
        print("\n  剩余零件:")
        for r in cur.fetchall():
            print("    ID=%s, part_number=%r" % (r[0], r[1]))

conn.close()
print("\n[DONE]")
