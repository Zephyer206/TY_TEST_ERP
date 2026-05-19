import psycopg2

DB_CONFIG = {
    'dbname': 'stamping_system',
    'user': 'postgres',
    'password': 'thehaoshi5DE',
    'host': 'localhost',
    'port': '5432'
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

try:
    # 1. 扩展 CHECK 约束
    cur.execute("""
        ALTER TABLE mold_offline_records
        DROP CONSTRAINT IF EXISTS chk_maintenance_status
    """)
    cur.execute("""
        ALTER TABLE mold_offline_records
        ADD CONSTRAINT chk_maintenance_status
        CHECK (maintenance_status IN (
            'waiting_parts',
            'major_repair',
            'offline',
            'pending_offline_repair',
            'in_repair',
            'ready_to_use',
            'reinstalled'
        ))
    """)
    print('1. Added pending_offline_repair status')

    # 2. 确保 assigned_tech_id 存在
    cur.execute("""
        ALTER TABLE mold_offline_records
        ADD COLUMN IF NOT EXISTS assigned_tech_id INTEGER
    """)
    print('2. assigned_tech_id ready')

    # 3. 全文搜索索引
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        print('3a. pg_trgm extension ready')
    except Exception as e:
        print(f'3a. pg_trgm: {e}')

    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_offline_mold_number_trgm
            ON mold_offline_records USING gin (mold_number gin_trgm_ops)
        """)
        print('3b. mold_number trigram index ready')
    except Exception as e:
        print(f'3b. mold_number index: {e}')

    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_offline_mold_name_trgm
            ON mold_offline_records USING gin (mold_name gin_trgm_ops)
        """)
        print('3c. mold_name trigram index ready')
    except Exception as e:
        print(f'3c. mold_name index: {e}')

    # 4. 新增字段
    for col, coltype in [
        ('repair_start_time', 'TIMESTAMP'),
        ('repair_end_time', 'TIMESTAMP'),
        ('current_part_number', 'VARCHAR(100)'),
        ('current_part_name', 'VARCHAR(200)'),
    ]:
        cur.execute(f"""
            ALTER TABLE mold_offline_records
            ADD COLUMN IF NOT EXISTS {col} {coltype}
        """)
    print('4. Added columns: repair_start_time, repair_end_time, current_part_number, current_part_name')

    conn.commit()
    print('\nMigration completed successfully!')
except Exception as e:
    conn.rollback()
    print(f'Error: {e}')
finally:
    cur.close()
    conn.close()
