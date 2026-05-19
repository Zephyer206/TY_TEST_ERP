"""
阶段七：成品发货映射与首件检验 Admin 开关 —— 数据库迁移
======================================================================

变更摘要
--------
1. part_customer_aliases（客户件号对照表）：一内多外，Primary ID → 客户件号翻译
2. delivery_notes + delivery_items（发货单体系）：发货时自动翻译客户件号
3. work_orders 新增首件控制字段（is_first_piece_required / first_piece_passed_at / passed_by）

关联 .cursorrules V3.2 §2.1 业务部：包装发货（一内多外）

架构约束
--------
- 坚持纯 SQL（psycopg2），不引入 ORM
- 所有写操作包含 conn.commit()
- 返回标准 JSON：{"code": ..., "message": ..., "data": ...}

依赖：v6b_shopfloor_routing
执行：alembic upgrade v7_delivery_qa_switch
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v7_delivery_qa_switch'
down_revision = 'v6b_shopfloor_routing'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. part_customer_aliases（客户件号对照表）───────────────────
    print('[v7-delivery-qa] 步骤1: 创建 part_customer_aliases 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS part_customer_aliases (
            id                   SERIAL       PRIMARY KEY,
            part_id              INTEGER      NOT NULL REFERENCES parts(id),
                -- 内部 Primary ID（零件主键）
            customer_name        VARCHAR(150) NOT NULL,
                -- 客户名称（与 delivery_notes.customer_name 对应）
            customer_part_no     VARCHAR(100) NOT NULL,
                -- 客户方的件号
            customer_part_name   VARCHAR(150),
                -- 客户方的品名（可选）
            created_at           TIMESTAMP    NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_part_customer
                UNIQUE (part_id, customer_name)
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_pca_customer
        ON part_customer_aliases(customer_name);
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_pca_part
        ON part_customer_aliases(part_id);
    """))
    print('[v7-delivery-qa]   part_customer_aliases 完成')

    # ── 2. delivery_notes（发货单主表）──────────────────────────────
    print('[v7-delivery-qa] 步骤2: 创建 delivery_notes 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS delivery_notes (
            id          SERIAL      PRIMARY KEY,
            dn_no       VARCHAR(50) UNIQUE NOT NULL,
                -- 发货单号（如 DN-2026-001）
            customer_name VARCHAR(150) NOT NULL,
                -- 客户名称（发货对象）
            shipped_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
                -- 发货时间（actual_date 业务时间）
            status      VARCHAR(20) NOT NULL DEFAULT 'SHIPPED',
                -- SHIPPED（已发货）| CANCELLED（已取消）
            notes       TEXT,
                -- 备注（快递单号等）
            created_by  INTEGER     REFERENCES users(id),
            created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_dn_status
                CHECK (status IN ('SHIPPED', 'CANCELLED'))
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_dn_customer
        ON delivery_notes(customer_name);
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_dn_status
        ON delivery_notes(status, shipped_at DESC);
    """))
    print('[v7-delivery-qa]   delivery_notes 完成')

    # ── 3. delivery_items（发货明细）────────────────────────────────
    print('[v7-delivery-qa] 步骤3: 创建 delivery_items 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS delivery_items (
            id         SERIAL       PRIMARY KEY,
            dn_id      INTEGER      NOT NULL REFERENCES delivery_notes(id)
                                             ON DELETE CASCADE,
                -- 归属发货单
            part_id    INTEGER      NOT NULL REFERENCES parts(id),
                -- 内部零件 Primary ID
            qty        INTEGER      NOT NULL,
                -- 发货数量
            lot_no     VARCHAR(100),
                -- 对应生产批次号（用于追溯）
            remark     VARCHAR(200),
                -- 明细备注（如特殊规格说明）
            created_at TIMESTAMP    NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_di_dn
        ON delivery_items(dn_id);
    """))
    print('[v7-delivery-qa]   delivery_items 完成')

    # ── 4. work_orders 首件检验开关（增量 ALTER）───────────────────
    print('[v7-delivery-qa] 步骤4: 给 work_orders 新增首件控制字段')
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS is_first_piece_required BOOLEAN NOT NULL DEFAULT FALSE;
    """))
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS first_piece_passed_at TIMESTAMP;
    """))
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS first_piece_passed_by INTEGER REFERENCES users(id);
    """))
    print('[v7-delivery-qa]   work_orders 首件字段完成（IF NOT EXISTS 防重复）')

    print('[v7-delivery-qa] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v7-delivery-qa] 回滚：删除 delivery_items')
    conn.execute(sa.text("DROP TABLE IF EXISTS delivery_items CASCADE;"))
    print('[v7-delivery-qa] 回滚：删除 delivery_notes')
    conn.execute(sa.text("DROP TABLE IF EXISTS delivery_notes CASCADE;"))
    print('[v7-delivery-qa] 回滚：删除 part_customer_aliases')
    conn.execute(sa.text("DROP TABLE IF EXISTS part_customer_aliases CASCADE;"))
    print('[v7-delivery-qa] 回滚：删除 work_orders 首件字段')
    conn.execute(sa.text(
        "ALTER TABLE work_orders DROP COLUMN IF EXISTS first_piece_passed_by CASCADE;"))
    conn.execute(sa.text(
        "ALTER TABLE work_orders DROP COLUMN IF EXISTS first_piece_passed_at CASCADE;"))
    conn.execute(sa.text(
        "ALTER TABLE work_orders DROP COLUMN IF EXISTS is_first_piece_required CASCADE;"))
    print('[v7-delivery-qa] 回滚完成')
