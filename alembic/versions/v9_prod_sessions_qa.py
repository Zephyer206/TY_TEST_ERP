"""
阶段九：生产会话黑匣子 & QA 审计链 — 数据库迁移
======================================================================

补全内容（.cursorrules V3.2 任务需求）
--------
1. work_orders.wip_pcs            — 待检库存（报工后转全检前的中转件）
2. material_batches 补全字段       — batch_code, supplier, material_spec（扩展已有表）
3. production_sessions           — 生产会话黑匣子
4. qa_audit_logs                 — QA 审计黑匣子（emergency_release 特赦记录）
5. defect_logs                   — 全员不良品池

依赖：v8_prod_maintenance
执行：alembic upgrade v9_prod_sessions_qa
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v9_prod_sessions_qa'
down_revision = 'v8_prod_maintenance'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. work_orders.wip_pcs ────────────────────────────────────
    print('[v9-sessions-qa] 步骤1: 添加 work_orders.wip_pcs（待检库存）')
    try:
        conn.execute(sa.text("""
            ALTER TABLE work_orders
            ADD COLUMN IF NOT EXISTS wip_pcs INTEGER NOT NULL DEFAULT 0;
        """))
        print('[v9-sessions-qa]   OK work_orders.wip_pcs 完成')
    except Exception as e:
        print(f'[v9-sessions-qa]   SKIP work_orders.wip_pcs: {e}')

    # ── 2. material_batches 扩展字段 ─────────────────────────────
    print('[v9-sessions-qa] 步骤2: 扩展 material_batches 字段')
    for col_def in [
        ("batch_code",       "VARCHAR(50)"),
        ("supplier",         "VARCHAR(150)"),
        ("material_spec",    "VARCHAR(100)"),
    ]:
        col_name, col_type = col_def
        try:
            conn.execute(sa.text(
                f"ALTER TABLE material_batches "
                f"ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
            ))
            print(f'[v9-sessions-qa]   OK material_batches.{col_name} 完成')
        except Exception as e:
            print(f'[v9-sessions-qa]   SKIP material_batches.{col_name}: {e}')

    # ── 3. production_sessions — 生产会话黑匣子 ─────────────────
    # material_batch_id 引用 material_batches(qr_uid)，故用 VARCHAR 而非 INTEGER
    print('[v9-sessions-qa] 步骤3: 创建 production_sessions（生产会话黑匣子）')
    try:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS production_sessions (
                id                 SERIAL  PRIMARY KEY,
                machine_id         INTEGER NOT NULL REFERENCES equipments(id),
                work_order_id      INTEGER          REFERENCES work_orders(id),
                operator_id        INTEGER          REFERENCES users(id),
                material_qr_uid    VARCHAR(50)      REFERENCES material_batches(qr_uid),
                session_type       VARCHAR(20)  NOT NULL DEFAULT 'Continuous',
                status             VARCHAR(30)  NOT NULL DEFAULT 'RUNNING',
                start_time         TIMESTAMP   NOT NULL DEFAULT NOW(),
                end_time           TIMESTAMP,
                reported_qty        INTEGER     NOT NULL DEFAULT 0,
                created_at         TIMESTAMP   NOT NULL DEFAULT NOW(),
                updated_at         TIMESTAMP   NOT NULL DEFAULT NOW()
            );
        """))
        print('[v9-sessions-qa]   OK production_sessions 建表完成')
    except Exception as e:
        print(f'[v9-sessions-qa]   ERR production_sessions: {e}')

    # ── 4. qa_audit_logs — QA 审计黑匣子 ─────────────────────────
    print('[v9-sessions-qa] 步骤4: 创建 qa_audit_logs（QA 审计黑匣子）')
    try:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS qa_audit_logs (
                id            SERIAL  PRIMARY KEY,
                work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
                machine_id    INTEGER          REFERENCES equipments(id),
                operator_id   INTEGER          REFERENCES users(id),
                action_type   VARCHAR(50)  NOT NULL,
                reason        TEXT,
                created_at    TIMESTAMP   NOT NULL DEFAULT NOW()
            );
        """))
        print('[v9-sessions-qa]   OK qa_audit_logs 建表完成')
    except Exception as e:
        print(f'[v9-sessions-qa]   ERR qa_audit_logs: {e}')

    # ── 5. defect_logs — 全员不良品池 ────────────────────────────
    print('[v9-sessions-qa] 步骤5: 创建 defect_logs（全员不良品池）')
    try:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS defect_logs (
                id            SERIAL  PRIMARY KEY,
                work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
                defect_qty    INTEGER NOT NULL DEFAULT 1,
                reason        TEXT,
                reporter_id   INTEGER          REFERENCES users(id),
                created_at    TIMESTAMP   NOT NULL DEFAULT NOW()
            );
        """))
        print('[v9-sessions-qa]   OK defect_logs 建表完成')
    except Exception as e:
        print(f'[v9-sessions-qa]   ERR defect_logs: {e}')

    # ── 6. stock_in_logs — 全检入库流水（工单级追溯）───────────
    print('[v9-sessions-qa] 步骤6: 创建 stock_in_logs（工单级入库流水）')
    try:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS stock_in_logs (
                id            SERIAL  PRIMARY KEY,
                work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
                part_id       INTEGER NOT NULL REFERENCES parts(id),
                valid_qty     INTEGER NOT NULL,
                reject_qty    INTEGER NOT NULL DEFAULT 0,
                operator_id   INTEGER          REFERENCES users(id),
                created_at    TIMESTAMP   NOT NULL DEFAULT NOW()
            );
        """))
        print('[v9-sessions-qa]   OK stock_in_logs 建表完成')
    except Exception as e:
        print(f'[v9-sessions-qa]   ERR stock_in_logs: {e}')

    print('[v9-sessions-qa] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v9-sessions-qa] 回滚：删除 stock_in_logs')
    conn.execute(sa.text("DROP TABLE IF EXISTS stock_in_logs;"))
    print('[v9-sessions-qa] 回滚：删除 defect_logs')
    conn.execute(sa.text("DROP TABLE IF EXISTS defect_logs;"))
    print('[v9-sessions-qa] 回滚：删除 qa_audit_logs')
    conn.execute(sa.text("DROP TABLE IF EXISTS qa_audit_logs;"))
    print('[v9-sessions-qa] 回滚：删除 production_sessions')
    conn.execute(sa.text("DROP TABLE IF EXISTS production_sessions;"))
    print('[v9-sessions-qa] 回滚：删除 material_batches 扩展字段')
    for col in ["material_spec", "supplier", "batch_code"]:
        conn.execute(sa.text(f"ALTER TABLE material_batches DROP COLUMN IF EXISTS {col};"))
    print('[v9-sessions-qa] 回滚：删除 work_orders.wip_pcs')
    conn.execute(sa.text("ALTER TABLE work_orders DROP COLUMN IF EXISTS wip_pcs;"))
    print('[v9-sessions-qa] 回滚完成')
