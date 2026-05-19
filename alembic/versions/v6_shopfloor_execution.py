"""
阶段六：车间执行与机码协同流 —— 数据库迁移
======================================================================

变更摘要
--------
1. equipments（机台表）：IDLE / RUNNING / EQUIP_REPAIR / MOLD_REPAIR_ON_MACHINE
2. work_orders（生产工单）：PENDING / SCHEDULED / RUNNING / PAUSED / COMPLETED
3. production_logs（冲压报工账本）：strokes × cavity_count = yield_qty，自动扣减原料
4. maintenance_logs（报修与熔断日志）：设备/模具双轨维修链

关联 .cursorrules V3.2 §2.3 机台维修：两扫制闭环

防呆设计
--------
- 机台状态熔断：EQUIP_REPAIR → 禁止排产，RUNNING 工单强制 PAUSED
- 模具双轨：拆模 → 机台 IDLE（立即释放）；不拆模 → MOLD_REPAIR_ON_MACHINE（霸占机台）
- 报工联动：strokes → yield_qty（cavity_count）→ 原料扣重（GrossWeight）

依赖：v5b_material_aux_unit
执行：alembic upgrade v6_shopfloor_execution
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v6_shopfloor_execution'
down_revision = 'v5b_material_aux_unit'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. equipments（机台表）────────────────────────────────────
    print('[v6-shopfloor] 步骤1: 创建 equipments 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS equipments (
            id               SERIAL      PRIMARY KEY,
            equipment_code   VARCHAR(50) UNIQUE NOT NULL,
                -- 机台唯一编码（如 EQ-001），扫码用
            equipment_name   VARCHAR(100),
                -- 机台名称/编号（如 "1号冲床 200T"）
            tonnage          VARCHAR(50),
                -- 吨位（如 "200T"），排产防呆用
            current_status  VARCHAR(50) NOT NULL DEFAULT 'IDLE',
                -- IDLE（空闲）| RUNNING（生产中）
                -- | EQUIP_REPAIR（设备损坏熔断，禁止排产）
                -- | MOLD_REPAIR_ON_MACHINE（模具在机维修，占用机台）
            created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_eq_status
        ON equipments(current_status)
        WHERE current_status != 'IDLE';
    """))
    print('[v6-shopfloor]   equipments 表 + 索引创建完成')

    # ── 2. work_orders（生产工单）──────────────────────────────────
    print('[v6-shopfloor] 步骤2: 创建 work_orders 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS work_orders (
            id           SERIAL       PRIMARY KEY,
            order_no     VARCHAR(50)  UNIQUE NOT NULL,
                -- 工单号（如 WO-260513-001）
            part_id      INTEGER      NOT NULL REFERENCES parts(id),
                -- 关联零件（Primary ID）
            equipment_id INTEGER      REFERENCES equipments(id),
                -- 排产到的机台（NULL = 待排产）
            target_qty   INTEGER      NOT NULL,
                -- 目标件数
            produced_qty INTEGER      NOT NULL DEFAULT 0,
                -- 已完成件数（报工累加）
            priority     VARCHAR(20)  NOT NULL DEFAULT 'NORMAL',
                -- NORMAL | URGENT（加急）
            order_status VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
                -- PENDING（待排产）| SCHEDULED（已排机台）
                -- | RUNNING（生产中）| PAUSED（被挂起/熔断）| COMPLETED
            created_by   INTEGER      REFERENCES users(id),
            created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMP    NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_order_status
                CHECK (order_status IN (
                    'PENDING', 'SCHEDULED', 'RUNNING', 'PAUSED', 'COMPLETED'))
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_wo_part
        ON work_orders(part_id);
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_wo_equip
        ON work_orders(equipment_id)
        WHERE equipment_id IS NOT NULL;
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_wo_status
        ON work_orders(order_status)
        WHERE order_status IN ('PENDING', 'SCHEDULED', 'RUNNING');
    """))
    print('[v6-shopfloor]   work_orders 表 + 索引创建完成')

    # ── 3. sf_production_logs（Shop Floor 冲压报工账本）────────────
    print('[v6-shopfloor] 步骤3: 创建 sf_production_logs 表（Shop Floor 专用）')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sf_production_logs (
            id             SERIAL      PRIMARY KEY,
            work_order_id  INTEGER     NOT NULL REFERENCES work_orders(id),
                -- 关联工单
            equipment_id   INTEGER     NOT NULL REFERENCES equipments(id),
                -- 关联机台
            material_qr_uid VARCHAR(50) REFERENCES material_batches(qr_uid),
                -- 消耗的原料批次码（可 NULL，如辅料报工不扫码）
            strokes        INTEGER     NOT NULL,
                -- 本次冲压次数（车间工人输入）
            yield_qty      INTEGER     NOT NULL,
                -- 计算得出件数：strokes × cavity_count
            operator_id    INTEGER     REFERENCES users(id),
                -- 报工操作人
            created_at     TIMESTAMP   NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_sfpl_wo
        ON sf_production_logs(work_order_id, created_at DESC);
    """))
    print('[v6-shopfloor]   sf_production_logs 表 + 索引创建完成')

    # ── 4. maintenance_logs（报修与熔断日志）───────────────────────
    print('[v6-shopfloor] 步骤4: 创建 maintenance_logs 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id            SERIAL      PRIMARY KEY,
            target_type   VARCHAR(20) NOT NULL,
                -- EQUIPMENT（机台故障）| MOLD（模具损坏）
            equipment_id  INTEGER     REFERENCES equipments(id),
                -- 关联机台（机台故障时必填）
            mold_id       INTEGER     REFERENCES molds(id),
                -- 关联模具（模具损坏时必填）
            repair_mode   VARCHAR(50),
                -- MACHINE_REPAIR（机台维修）
                -- | MOLD_ON_MACHINE（不拆模维修，模具在机）
                -- | MOLD_DISMOUNTED（拆模维修，模具离机）
            status        VARCHAR(20) NOT NULL DEFAULT 'REPAIRING',
                -- REPAIRING（维修中）| RESOLVED（已修复）
            tech_id       INTEGER     REFERENCES users(id),
                -- 介入修理的责任技术员
            start_time    TIMESTAMP   NOT NULL DEFAULT NOW(),
            end_time      TIMESTAMP,
                -- 修复时间（RESOLVED 时写入）
            remarks       TEXT,
            CONSTRAINT chk_target_type
                CHECK (target_type IN ('EQUIPMENT', 'MOLD'))
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_ml_target
        ON maintenance_logs(target_type, status)
        WHERE status = 'REPAIRING';
    """))
    print('[v6-shopfloor]   maintenance_logs 表 + 索引创建完成')

    print('[v6-shopfloor] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v6-shopfloor] 回滚：删除 maintenance_logs')
    conn.execute(sa.text("DROP TABLE IF EXISTS maintenance_logs CASCADE;"))
    print('[v6-shopfloor] 回滚：删除 sf_production_logs')
    conn.execute(sa.text("DROP TABLE IF EXISTS sf_production_logs CASCADE;"))
    print('[v6-shopfloor] 回滚：删除 work_orders')
    conn.execute(sa.text("DROP TABLE IF EXISTS work_orders CASCADE;"))
    print('[v6-shopfloor] 回滚：删除 equipments')
    conn.execute(sa.text("DROP TABLE IF EXISTS equipments CASCADE;"))
    print('[v6-shopfloor] 回滚完成')
