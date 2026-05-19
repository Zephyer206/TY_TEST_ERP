"""
阶段八：生产执行 & 维修双轨 —— 数据库补全迁移
======================================================================

补全内容（.cursorrules V3.2 §8 工业执行专项）
--------
1. work_orders.mold_id          — 关联模具（工单级模具绑定）
2. molds.current_equipment_id    — 当前所在机台（快速定位维修对象）
3. sf_production_logs.consumed_weight — 报工时记录本次消耗重量
4. delivery_notes.stock_pcs     — 发货单记录本次发货数量汇总（快照）
5. parts.stock_pcs              — 成品库存（按 Primary ID 计数）

依赖：v7_delivery_qa_switch
执行：alembic upgrade v8_prod_maintenance
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v8_prod_maintenance'
down_revision = 'v7_delivery_qa_switch'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. work_orders.mold_id ────────────────────────────────────
    print('[v8-prod-maint] 步骤1: 添加 work_orders.mold_id')
    try:
        conn.execute(sa.text("""
            ALTER TABLE work_orders
            ADD COLUMN IF NOT EXISTS mold_id INTEGER REFERENCES molds(id);
        """))
        print('[v8-prod-maint]   work_orders.mold_id 完成')
    except Exception as e:
        print(f'[v8-prod-maint]   work_orders.mold_id 已存在或出错: {e}')

    # ── 2. molds.current_equipment_id ──────────────────────────
    print('[v8-prod-maint] 步骤2: 添加 molds.current_equipment_id')
    try:
        conn.execute(sa.text("""
            ALTER TABLE molds
            ADD COLUMN IF NOT EXISTS current_equipment_id INTEGER REFERENCES equipments(id);
        """))
        print('[v8-prod-maint]   molds.current_equipment_id 完成')
    except Exception as e:
        print(f'[v8-prod-maint]   molds.current_equipment_id 已存在: {e}')

    # ── 3. sf_production_logs.consumed_weight ────────────────────
    print('[v8-prod-maint] 步骤3: 添加 sf_production_logs.consumed_weight')
    try:
        conn.execute(sa.text("""
            ALTER TABLE sf_production_logs
            ADD COLUMN IF NOT EXISTS consumed_weight NUMERIC(12, 4) DEFAULT 0;
        """))
        print('[v8-prod-maint]   sf_production_logs.consumed_weight 完成')
    except Exception as e:
        print(f'[v8-prod-maint]   sf_production_logs.consumed_weight 已存在: {e}')

    # ── 4. parts.stock_pcs ────────────────────────────────────────
    print('[v8-prod-maint] 步骤4: 添加 parts.stock_pcs（成品库存件数）')
    try:
        conn.execute(sa.text("""
            ALTER TABLE parts
            ADD COLUMN IF NOT EXISTS stock_pcs INTEGER NOT NULL DEFAULT 0;
        """))
        print('[v8-prod-maint]   parts.stock_pcs 完成')
    except Exception as e:
        print(f'[v8-prod-maint]   parts.stock_pcs 已存在: {e}')

    print('[v8-prod-maint] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v8-prod-maint] 回滚：删除 parts.stock_pcs')
    conn.execute(sa.text("ALTER TABLE parts DROP COLUMN IF EXISTS stock_pcs;"))
    print('[v8-prod-maint] 回滚：删除 sf_production_logs.consumed_weight')
    conn.execute(sa.text("ALTER TABLE sf_production_logs DROP COLUMN IF EXISTS consumed_weight;"))
    print('[v8-prod-maint] 回滚：删除 molds.current_equipment_id')
    conn.execute(sa.text("ALTER TABLE molds DROP COLUMN IF EXISTS current_equipment_id;"))
    print('[v8-prod-maint] 回滚：删除 work_orders.mold_id')
    conn.execute(sa.text("ALTER TABLE work_orders DROP COLUMN IF EXISTS mold_id;"))
    print('[v8-prod-maint] 回滚完成')
