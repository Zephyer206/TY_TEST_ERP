"""
技术部"极简两扫制"维修闭环 —— 数据库迁移

扩展 mold_offline_records 表：
1. 新增维修状态枚举：offline / in_repair / ready_to_use / reinstalled
2. 新增维修时间戳：repair_start_time, repair_end_time
3. 新增绩效统计字段：net_repair_minutes

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123tech_twoscan'
down_revision = 'xyz999tech_manager'  # 依赖上一版本迁移
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # ─────────────────────────────────────────────────────────────
    # 1. 修改 maintenance_status CHECK 约束（扩展状态枚举）
    # ─────────────────────────────────────────────────────────────
    # 删除旧约束
    op.execute("""
        ALTER TABLE mold_offline_records
        DROP CONSTRAINT IF EXISTS chk_maintenance_status
    """)
    
    # 添加新约束（包含两扫制新状态）
    op.execute("""
        ALTER TABLE mold_offline_records
        ADD CONSTRAINT chk_maintenance_status
        CHECK (maintenance_status IN (
            'waiting_parts',    -- 待件（保留原状态）
            'major_repair',     -- 大修中（保留原状态）
            'offline',         -- 下线待修（新状态）
            'in_repair',       -- 维修中（新状态：扫第一下）
            'ready_to_use',    -- 已修好待装机（新状态：扫第二下）
            'reinstalled'       -- 已装机（保留原状态）
        ))
    """)
    
    # ─────────────────────────────────────────────────────────────
    # 2. 新增维修时间戳字段
    # ─────────────────────────────────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mold_offline_records' AND column_name = 'repair_start_time'
    """)).fetchone()
    
    if not result:
        op.add_column('mold_offline_records', sa.Column('repair_start_time', sa.DateTime(), nullable=True))
    
    result2 = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mold_offline_records' AND column_name = 'repair_end_time'
    """)).fetchone()
    
    if not result2:
        op.add_column('mold_offline_records', sa.Column('repair_end_time', sa.DateTime(), nullable=True))
    
    # ─────────────────────────────────────────────────────────────
    # 3. 新增模具信息字段（便于直接关联零件）
    # ─────────────────────────────────────────────────────────────
    result3 = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'mold_offline_records' AND column_name = 'current_part_number'
    """)).fetchone()
    
    if not result3:
        op.add_column('mold_offline_records', sa.Column('current_part_number', sa.String(100), nullable=True))
        op.add_column('mold_offline_records', sa.Column('current_part_name', sa.String(200), nullable=True))


def downgrade():
    # 删除新增的列
    op.drop_column('mold_offline_records', 'current_part_name')
    op.drop_column('mold_offline_records', 'current_part_number')
    op.drop_column('mold_offline_records', 'repair_end_time')
    op.drop_column('mold_offline_records', 'repair_start_time')
    
    # 恢复旧约束
    op.execute("""
        ALTER TABLE mold_offline_records
        DROP CONSTRAINT IF EXISTS chk_maintenance_status
    """)
    op.execute("""
        ALTER TABLE mold_offline_records
        ADD CONSTRAINT chk_maintenance_status
        CHECK (maintenance_status IN (
            'waiting_parts', 'major_repair', 'ready_to_install', 'reinstalled'
        ))
    """)
