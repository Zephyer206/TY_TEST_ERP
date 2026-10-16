"""
物料分条日志表 + materials.original_weight 字段 —— 数据库迁移

关联 .cursorrules V3.0 仓库模块规范：
- materials.original_weight：记录入库初始重量（用于精确按重量比例分条）
- material_slitting_logs：记录每一次分条动作，支持父子料溯源

依赖：spr0001spray_module（head）

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'mat0001slitting_logs'
down_revision = 'spr0001spray_module'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. materials.original_weight ──────────────────────────────────
    # 新增原始重量字段（新料入库时记录，永不修改）
    op.execute(
        "ALTER TABLE materials ADD COLUMN IF NOT EXISTS original_weight NUMERIC(12, 4)"
    )
    # 将已有 current_weight 同步填充 original_weight（历史数据）
    op.execute("""
        UPDATE materials
        SET original_weight = current_weight
        WHERE original_weight IS NULL AND current_weight IS NOT NULL;
    """)
    print('[mat] materials.original_weight ensured')

    # ── 2. material_slitting_logs ─────────────────────────────────────
    # 幂等创建（可安全重复执行）
    op.execute("""
        CREATE TABLE IF NOT EXISTS material_slitting_logs (
            id                  SERIAL PRIMARY KEY,
            parent_id           INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            child_id           INTEGER REFERENCES materials(id) ON DELETE SET NULL,
            operator_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
            operator_name      VARCHAR(100),
            slit_width         NUMERIC(12, 4) NOT NULL,
            slit_count         INTEGER NOT NULL DEFAULT 1,
            slit_weight        NUMERIC(12, 4),          -- 本次分条总消耗重量（kg）
            parent_consumed_width  NUMERIC(12, 4) NOT NULL,  -- 母卷本次消耗宽度
            parent_remain_width  NUMERIC(12, 4),          -- 母卷分条后剩余宽度
            parent_auto_closed   BOOLEAN NOT NULL DEFAULT FALSE, -- 是否触发自动结案
            created_at          TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_slit_parent
        ON material_slitting_logs(parent_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_slit_child
        ON material_slitting_logs(child_id);
    """)
    print('[mat] material_slitting_logs table created')


def downgrade():
    op.execute("DROP TABLE IF EXISTS material_slitting_logs;")
    op.drop_column('materials', 'original_weight')
