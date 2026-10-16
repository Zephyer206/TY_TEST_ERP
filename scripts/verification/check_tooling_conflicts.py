#!/usr/bin/env python3
"""Check for conflicts in tooling migration"""

import os

import psycopg2

conn = psycopg2.connect(
    host=os.environ["ZEPHYR_DB_HOST"],
    port=int(os.environ.get("ZEPHYR_DB_PORT", "5432")),
    database=os.environ.get("ZEPHYR_DB_NAME", "stamping_system"),
    user=os.environ.get("ZEPHYR_DB_USER", "postgres"),
    password=os.environ["ZEPHYR_DB_PASSWORD"],
)

cur = conn.cursor()

# Check if any tooling_no values that need migration would conflict with existing tooling_number
cur.execute("""
    SELECT t1.tooling_no, COUNT(*) as need_migrate,
           (SELECT COUNT(*) FROM tooling t2
            WHERE t2.tooling_number = t1.tooling_no) as already_exists
    FROM tooling t1
    WHERE t1.tooling_no IS NOT NULL AND t1.tooling_number IS NULL
    GROUP BY t1.tooling_no
    HAVING COUNT(*) = 1
    AND EXISTS (SELECT 1 FROM tooling t2 WHERE t2.tooling_number = t1.tooling_no)
    LIMIT 10
""")
conflicts = cur.fetchall()

if conflicts:
    print(f"Found {len(conflicts)} conflicts where tooling_no would conflict with existing tooling_number:")
    for tooling_no, need_migrate, already_exists in conflicts:
        print(f"  {tooling_no}: need to migrate {need_migrate}, but {already_exists} already have this tooling_number")
else:
    print("No conflicts found - safe to migrate unique tooling_no values")

cur.close()
conn.close()
