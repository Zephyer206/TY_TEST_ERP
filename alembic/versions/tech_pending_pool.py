"""
技术部待修池自动流转 + 模糊搜索 —— 数据库迁移

1. 新增 maintenance_status = 'pending_offline_repair'
2. 新增 mold_offline_records.assigned_tech_id（维修责任人）
3. 模糊搜索索引（GIN Trigram）
"""

from alembic import op
import sqlalchemy as sa

revision = 'def456tech_pending_pool'
down_revision = 'abc123tech_twoscan'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. 扩展 CHECK 约束 ──────────────────────────────────────────────
    op.execute("""
        ALTER TABLE mold_offline_records
        DROP CONSTRAINT IF EXISTS chk_maintenance_status
    """)
    op.execute("""
        ALTER TABLE mold_offline_records
        ADD CONSTRAINT chk_maintenance_status
        CHECK (maintenance_status IN (
            'waiting_parts',
            'major_repair',
            'offline',
            'pending_offline_repair',  -- 新增：待修池
            'in_repair',
            'ready_to_use',
            'reinstalled'
        ))
    """)
    print('Added pending_offline_repair status')

    # ── 2. 确保 assigned_tech_id 字段存在 ─────────────────────────────
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mold_offline_records'
        AND column_name = 'assigned_tech_id'
    """)).fetchone()
    if not result:
        op.add_column('mold_offline_records',
                      sa.Column('assigned_tech_id', sa.Integer(), nullable=True))

    # ── 3. 全文搜索索引（GIN Trigram）──────────────────────────────
    # 启用扩展（如果未启用）
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception:
        pass

    # 为 mold_number 和 mold_name 创建 trigram 索引
    try:
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_offline_mold_number_trgm
            ON mold_offline_records USING gin (mold_number gin_trgm_ops)
        """)
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_offline_mold_name_trgm
            ON mold_offline_records USING gin (mold_name gin_trgm_ops)
        """)
        print('Created trigram indexes')
    except Exception as e:
        print(f'Index creation skipped (may already exist): {e}')

    # ── 4. current_part_number/current_part_name 字段 ─────────────
    for col, coltype in [
        ('current_part_number', 'VARCHAR(100)'),
        ('current_part_name', 'VARCHAR(200)'),
    ]:
        r = conn.execute(sa.text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'mold_offline_records'
            AND column_name = '{col}'
        """)).fetchone()
        if not r:
            op.add_column('mold_offline_records',
                         sa.Column(col, sa.String(100 if 'number' in col else 200), nullable=True))

    # ── 5. 维修时间戳 ──────────────────────────────────────────────
    for col in ['repair_start_time', 'repair_end_time']:
        r = conn.execute(sa.text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'mold_offline_records'
            AND column_name = '{col}'
        """)).fetchone()
        if not r:
            op.add_column('mold_offline_records',
                         sa.Column(col, sa.DateTime(), nullable=True))


def downgrade():
    op.execute("""
        ALTER TABLE mold_offline_records
        DROP CONSTRAINT IF EXISTS chk_maintenance_status
    """)
    op.execute("""
        ALTER TABLE mold_offline_records
        ADD CONSTRAINT chk_maintenance_status
        CHECK (maintenance_status IN (
            'waiting_parts', 'major_repair', 'offline',
            'in_repair', 'ready_to_use', 'reinstalled'
        ))
    """)
