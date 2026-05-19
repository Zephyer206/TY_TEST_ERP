"""
阶段六：车间执行、机码协同与双轨报工 —— 数据库迁移（合并版）
======================================================================

变更摘要
--------
本迁移为合并版（基于 v5b），同时包含：
  1. equipments（机台表）
  2. work_orders（生产工单 + is_routing_enabled 软开关）
  3. production_logs（Shop Floor 冲压报工账本）
  4. maintenance_logs（报修与熔断日志）
  5. routing_tickets（纸质流转单主单）— 前瞻备用
  6. routing_records（工序交接账本）— 前瞻备用

关联 .cursorrules V3.2 §2.3 机台维修：两扫制闭环

防呆设计
--------
- 机台状态熔断：EQUIP_REPAIR → 禁止排产，RUNNING 工单强制 PAUSED
- 模具双轨：拆模 → 机台 IDLE（立即释放）；不拆模 → MOLD_REPAIR_ON_MACHINE
- 报工双轨：is_routing_enabled=False → 直报；=True → 必须扫流转单号

依赖：v5b_material_aux_unit
执行：alembic upgrade v6b_shopfloor_routing
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v6b_shopfloor_routing'
down_revision = 'v5b_material_aux_unit'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. equipments（机台表）────────────────────────────────────
    print('[v6b-shopfloor] 步骤1: 创建 / 确认 equipments 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS equipments (
            id               SERIAL      PRIMARY KEY,
            equipment_code   VARCHAR(50) UNIQUE NOT NULL,
            equipment_name   VARCHAR(100),
            tonnage          VARCHAR(50),
            current_status  VARCHAR(50) NOT NULL DEFAULT 'IDLE',
            created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_eq_status
        ON equipments(current_status)
        WHERE current_status != 'IDLE';
    """))
    print('[v6b-shopfloor]   equipments 完成')

    # ── 2. work_orders（生产工单）──────────────────────────────────
    # work_orders 可能由 v6 创建但缺 is_routing_enabled 列
    # 分支处理：先创建表（如不存在），再检查并补充列
    print('[v6b-shopfloor] 步骤2: 创建 / 确认 work_orders 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS work_orders (
            id                SERIAL       PRIMARY KEY,
            order_no          VARCHAR(50)  UNIQUE NOT NULL,
            part_id           INTEGER      NOT NULL REFERENCES parts(id),
            equipment_id      INTEGER      REFERENCES equipments(id),
            target_qty        INTEGER      NOT NULL,
            produced_qty      INTEGER      NOT NULL DEFAULT 0,
            priority          VARCHAR(20)  NOT NULL DEFAULT 'NORMAL',
            order_status      VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
            is_routing_enabled BOOLEAN     NOT NULL DEFAULT FALSE,
            created_by        INTEGER      REFERENCES users(id),
            created_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_wo_status
                CHECK (order_status IN (
                    'PENDING','SCHEDULED','RUNNING','PAUSED','COMPLETED'))
        );
    """))
    # 增量补充列（v6 版本没有此列）
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS is_routing_enabled BOOLEAN NOT NULL DEFAULT FALSE;
    """))
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_wo_part
        ON work_orders(part_id);
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_wo_equip
        ON work_orders(equipment_id)
        WHERE equipment_id IS NOT NULL;
    """))
    # 仅当列存在时建部分索引（Postgres 部分索引语法要求列存在）
    try:
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS idx_wo_routing
            ON work_orders(is_routing_enabled)
            WHERE is_routing_enabled = TRUE;
        """))
    except Exception:
        pass  # 列不存在则跳过
    print('[v6b-shopfloor]   work_orders 完成（is_routing_enabled 默认 FALSE）')

    # ── 3. sf_production_logs（Shop Floor 冲压报工账本）────────────
    print('[v6b-shopfloor] 步骤3: 创建 / 确认 sf_production_logs 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sf_production_logs (
            id             SERIAL      PRIMARY KEY,
            work_order_id  INTEGER     NOT NULL REFERENCES work_orders(id),
            equipment_id   INTEGER     NOT NULL REFERENCES equipments(id),
            material_qr_uid VARCHAR(50) REFERENCES material_batches(qr_uid),
            strokes        INTEGER     NOT NULL,
            yield_qty      INTEGER     NOT NULL,
            operator_id    INTEGER     REFERENCES users(id),
            created_at     TIMESTAMP   NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_sfpl_wo
        ON sf_production_logs(work_order_id, created_at DESC);
    """))
    print('[v6b-shopfloor]   sf_production_logs 完成')

    # ── 4. maintenance_logs（报修与熔断日志）──────────────────────
    print('[v6b-shopfloor] 步骤4: 创建 / 确认 maintenance_logs 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id            SERIAL      PRIMARY KEY,
            target_type   VARCHAR(20) NOT NULL,
            equipment_id  INTEGER     REFERENCES equipments(id),
            mold_id       INTEGER     REFERENCES molds(id),
            repair_mode   VARCHAR(50),
            status        VARCHAR(20) NOT NULL DEFAULT 'REPAIRING',
            tech_id       INTEGER     REFERENCES users(id),
            start_time    TIMESTAMP   NOT NULL DEFAULT NOW(),
            end_time      TIMESTAMP,
            remarks       TEXT,
            CONSTRAINT chk_target_type
                CHECK (target_type IN ('EQUIPMENT', 'MOLD'))
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_ml_target
        ON maintenance_logs(target_type, status)
        WHERE status = 'REPAIRING';
    """))
    print('[v6b-shopfloor]   maintenance_logs 完成')

    # ── 5. routing_tickets（纸质流转单主单）— 前瞻备用 ───────────
    print('[v6b-shopfloor] 步骤5: 创建 routing_tickets 表（前瞻备用）')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS routing_tickets (
            ticket_no         VARCHAR(50)  PRIMARY KEY,
            work_order_id     INTEGER      NOT NULL REFERENCES work_orders(id),
            current_step_seq  INTEGER      NOT NULL DEFAULT 10,
            current_good_qty  INTEGER      NOT NULL DEFAULT 0,
            ticket_status     VARCHAR(20)  NOT NULL DEFAULT 'WIP',
            created_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_ticket_status
                CHECK (ticket_status IN ('WIP', 'COMPLETED'))
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_rt_wo
        ON routing_tickets(work_order_id)
        WHERE ticket_status = 'WIP';
    """))
    print('[v6b-shopfloor]   routing_tickets 完成')

    # ── 6. routing_records（工序交接账本）— 前瞻备用 ──────────────
    print('[v6b-shopfloor] 步骤6: 创建 routing_records 表（前瞻备用）')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS routing_records (
            id           SERIAL      PRIMARY KEY,
            ticket_no    VARCHAR(50) NOT NULL REFERENCES routing_tickets(ticket_no),
            step_seq     INTEGER     NOT NULL,
            produced_qty INTEGER     NOT NULL,
            defect_qty   INTEGER     NOT NULL DEFAULT 0,
            operator_id  INTEGER     REFERENCES users(id),
            created_at   TIMESTAMP   NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_rr_ticket
        ON routing_records(ticket_no, step_seq DESC);
    """))
    print('[v6b-shopfloor]   routing_records 完成')

    print('[v6b-shopfloor] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v6b-shopfloor] 回滚：删除 routing_records')
    conn.execute(sa.text("DROP TABLE IF EXISTS routing_records CASCADE;"))
    print('[v6b-shopfloor] 回滚：删除 routing_tickets')
    conn.execute(sa.text("DROP TABLE IF EXISTS routing_tickets CASCADE;"))
    print('[v6b-shopfloor] 回滚：删除 maintenance_logs')
    conn.execute(sa.text("DROP TABLE IF EXISTS maintenance_logs CASCADE;"))
    print('[v6b-shopfloor] 回滚：删除 sf_production_logs')
    conn.execute(sa.text("DROP TABLE IF EXISTS sf_production_logs CASCADE;"))
    print('[v6b-shopfloor] 回滚：删除 work_orders')
    conn.execute(sa.text("DROP TABLE IF EXISTS work_orders CASCADE;"))
    print('[v6b-shopfloor] 回滚：删除 equipments')
    conn.execute(sa.text("DROP TABLE IF EXISTS equipments CASCADE;"))
    print('[v6b-shopfloor] 回滚完成')
