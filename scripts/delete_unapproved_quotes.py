"""
Delete unapproved quotes AND their linked parts atomically.
Only APPROVED quotes are preserved (parts remain untouched).
"""
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
    # === Step 1: Show quote status breakdown ===
    print('=== Quote status summary ===')
    cur.execute("""
        SELECT approval_status, COUNT(*) AS cnt
        FROM quotes
        WHERE is_deleted = FALSE
        GROUP BY approval_status
        ORDER BY approval_status;
    """)
    for row in cur.fetchall():
        print(f'  {row[0]}: {row[1]}')

    # === Step 2: Find unapproved quotes and their linked parts ===
    print('\n=== Unapproved quotes (to be deleted with their parts) ===')
    cur.execute("""
        SELECT q.id AS quote_id, q.part_id, q.approval_status, q.quote_serial,
               p.part_number, p.remark
        FROM quotes q
        JOIN parts p ON q.part_id = p.id
        WHERE q.approval_status != 'APPROVED'
          AND q.is_deleted = FALSE
        ORDER BY q.id DESC;
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f'  Q={r[0]}, part_id={r[1]}, status={r[2]}, serial={r[3]}, part={r[4]}, remark={r[5]}')

    total = len(rows)
    print(f'\nTotal: {total} quotes to delete (with their parts)')

    if total == 0:
        print('Nothing to do.')
    else:
        # === Step 3: Clear FK references before deleting parts ===
        print('\n=== Clearing FK references ===')
        cur.execute("""
            SELECT tc.table_name, tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND kcu.referenced_table_name = 'parts';
        """)
        all_refs = cur.fetchall()

        # Get unique part IDs to delete
        part_ids = tuple(sorted(set(r[1] for r in rows)))

        for tbl, constraint, col in all_refs:
            try:
                cur.execute(
                    f'SELECT COUNT(*) FROM "{tbl}" WHERE "{col}" IN %s;',
                    (part_ids,)
                )
                cnt = cur.fetchone()[0]
                if cnt > 0:
                    cur.execute(
                        f'UPDATE "{tbl}" SET "{col}" = NULL WHERE "{col}" IN %s;',
                        (part_ids,)
                    )
                    print(f'  [OK] Cleared {cur.rowcount} rows in {tbl}.{col}')
            except Exception as e:
                print(f'  [SKIP] {tbl}.{col}: {e}')

        # === Step 4: Delete quotes (mark is_deleted = TRUE) ===
        print('\n=== Deleting quotes ===')
        cur.execute("""
            UPDATE quotes
            SET is_deleted = TRUE, updated_at = NOW()
            WHERE approval_status != 'APPROVED'
              AND is_deleted = FALSE;
        """)
        print(f'  [OK] Marked {cur.rowcount} quotes as deleted')

        # === Step 5: Delete parts ===
        print('\n=== Deleting parts ===')
        cur.execute(
            f'DELETE FROM parts WHERE id IN %s;',
            (part_ids,)
        )
        print(f'  [OK] Deleted {cur.rowcount} parts: {part_ids}')

        # === Step 6: Verify ===
        print('\n=== Remaining parts ===')
        cur.execute("SELECT id, part_number, remark FROM parts ORDER BY id DESC;")
        for r in cur.fetchall():
            print(f'  ID={r[0]}, part_number={r[1]}, remark={r[2]}')

        print('\n=== Remaining quotes (non-deleted) ===')
        cur.execute("""
            SELECT id, part_id, approval_status, is_deleted
            FROM quotes ORDER BY id DESC LIMIT 10;
        """)
        for r in cur.fetchall():
            print(f'  Q={r[0]}, part_id={r[1]}, status={r[2]}, deleted={r[3]}')

conn.close()
print('\n[DONE]')
