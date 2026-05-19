"""
重构技术部管理端 —— 数据库迁移

本迁移包含两部分：
1. 扩展 users 表：支持 dept='tech' 和 position='manager'
2. 新建 mold_offline_records 表：记录下线模具的维修节点追踪
3. 扩展 machines 表：增加维修责任人字段

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers
revision = 'xyz999tech_manager'
down_revision = 'p001patch_levels34'  # 依赖上一版本迁移
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # ─────────────────────────────────────────────────────────────
    # 1. 检查 users 表是否有 dept 字段（兼容旧迁移）
    # ─────────────────────────────────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'dept'
    """)).fetchone()
    
    if not result:
        # 添加 dept 字段
        op.add_column('users', sa.Column('dept', sa.String(50), nullable=True))
    
    # 检查是否有 position 字段
    result2 = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'position'
    """)).fetchone()
    
    if not result2:
        op.add_column('users', sa.Column('position', sa.String(100), nullable=True))
    
    # 检查是否有 is_tech 字段
    result3 = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'is_tech'
    """)).fetchone()
    
    if not result3:
        op.add_column('users', sa.Column('is_tech', sa.Boolean(), server_default='false', nullable=False))

    # ─────────────────────────────────────────────────────────────
    # 2. 扩展 machines 表：增加维修责任人字段
    # ─────────────────────────────────────────────────────────────
    result4 = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'machines' AND column_name = 'tech_user_id'
    """)).fetchone()
    
    if not result4:
        op.add_column('machines', sa.Column('tech_user_id', sa.Integer(), nullable=True))
        # 添加外键约束
        op.create_foreign_key(
            'fk_machines_tech_user',
            'machines', 'users',
            ['tech_user_id'], ['id'],
            onupdate='SET NULL',
            ondelete='SET NULL'
        )
    
    # ─────────────────────────────────────────────────────────────
    # 3. 创建 mold_offline_records 表：记录下线模具的维修节点追踪
    # ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS mold_offline_records (
            id SERIAL PRIMARY KEY,
            machine_id INTEGER NOT NULL,
            mold_number VARCHAR(100),
            mold_name VARCHAR(200),
            fault_reason TEXT,
            offline_time TIMESTAMP NOT NULL DEFAULT NOW(),
            -- 维修节点状态：waiting_parts(待件) / major_repair(大修中) / ready_to_install(已修好待装机) / reinstalled(已装机)
            maintenance_status VARCHAR(50) NOT NULL DEFAULT 'waiting_parts',
            -- 维修节点更新时间
            status_updated_at TIMESTAMP DEFAULT NOW(),
            -- 维修节点更新人
            status_updated_by INTEGER,
            -- 维修责任人（模修师傅）
            assigned_tech_id INTEGER,
            -- 备注
            remark TEXT,
            -- 完成时间
            completed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            -- 外键约束
            CONSTRAINT fk_offline_machine FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE,
            CONSTRAINT fk_offline_tech FOREIGN KEY (assigned_tech_id) REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT fk_offline_updater FOREIGN KEY (status_updated_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    
    # 创建索引提升查询性能
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_offline_records_status 
        ON mold_offline_records(maintenance_status)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_offline_records_machine 
        ON mold_offline_records(machine_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_offline_records_offline_time 
        ON mold_offline_records(offline_time DESC)
    """)

    # ─────────────────────────────────────────────────────────────
    # 4. 创建索引：优化维修统计查询
    # ─────────────────────────────────────────────────────────────
    # 为 machines 表创建状态索引（如果有的话）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_machines_status 
        ON machines(status)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_machines_fault_reported 
        ON machines(fault_reported_at)
    """)


def downgrade():
    # 删除外键约束
    op.execute("ALTER TABLE mold_offline_records DROP CONSTRAINT IF EXISTS fk_offline_updater")
    op.execute("ALTER TABLE mold_offline_records DROP CONSTRAINT IF EXISTS fk_offline_tech")
    op.execute("ALTER TABLE mold_offline_records DROP CONSTRAINT IF EXISTS fk_offline_machine")
    
    # 删除表
    op.execute("DROP TABLE IF EXISTS mold_offline_records")
    
    # 删除 machines 表的扩展字段
    op.drop_column('machines', 'tech_user_id')
