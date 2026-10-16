"""
原料二维码追溯体系 —— 数据库迁移
======================================================================
基于现有 v5 旧表结构（material_batches.qr_uid 主键）进行扩展。

实际数据库列名（已确认）：
- material_batches: qr_uid(主键), parent_qr_uid, qr_uid, ... 无 qr_code / parent_batch_id
- batch_transactions: 不存在
- material_batch_children: 不存在
- qr_scan_logs: 不存在

变更内容：
1. material_batches 新增：qr_code, parent_batch_id, batch_no, status, current_weight 替换 initial_weight
2. 新建 batch_transactions 表（原料流水账）
3. 新建 material_batch_children 表（子卷，兼容新模型）
4. 新建 qr_scan_logs 表（扫码日志）

幂等设计：所有操作均先检查是否已存在，安全重复执行。

依赖：v20_prices_add_surface_cost（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
from alembic import context
import sqlalchemy as sa
import re

revision = "qr002_material_traceability"
down_revision = "v20_prices_add_surface_cost"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 0. 获取当前列 ────────────────────────────────────────────────────
    mb_cols = _get_columns(conn, "material_batches")
    print(f"[qr002] material_batches 当前列: {sorted(mb_cols)}")

    bt_exists = _table_exists(conn, "batch_transactions")
    mbc_exists = _table_exists(conn, "material_batch_children")
    qrlog_exists = _table_exists(conn, "qr_scan_logs")
    print(f"[qr002] batch_transactions exists: {bt_exists}")
    print(f"[qr002] material_batch_children exists: {mbc_exists}")
    print(f"[qr002] qr_scan_logs exists: {qrlog_exists}")

    # ── 1. material_batches 新增列 ───────────────────────────────────────
    # qr_code: 唯一二维码内容（与 qr_uid 独立，供扫码展示）
    if "qr_code" not in mb_cols:
        _safe_add_col(conn, "material_batches", "qr_code", "VARCHAR(200)")
        print("[qr002] material_batches.qr_code added")
    else:
        print("[qr002] material_batches.qr_code already exists")

    # batch_no: 人类可读批次号（从 qr_uid 迁移或重新生成）
    if "batch_no" not in mb_cols:
        _safe_add_col(conn, "material_batches", "batch_no", "VARCHAR(100)")
        # 从 qr_uid 填充（兼容旧数据）
        conn.execute(sa.text("""
            UPDATE material_batches
            SET batch_no = qr_uid
            WHERE batch_no IS NULL AND qr_uid IS NOT NULL;
        """))
        print("[qr002] material_batches.batch_no added + filled from qr_uid")
    else:
        print("[qr002] material_batches.batch_no already exists")

    # parent_batch_id: 指向母卷 id（替代 parent_qr_uid 的自引用）
    if "parent_batch_id" not in mb_cols:
        _safe_add_col(conn, "material_batches", "parent_batch_id", "INTEGER")
        # 建立自引用外键
        _safe_add_fk(
            conn,
            "material_batches",
            "fk_mb_parent",
            "parent_batch_id",
            "material_batches",
            "id",
        )
        print("[qr002] material_batches.parent_batch_id added")
    else:
        print("[qr002] material_batches.parent_batch_id already exists")

    # 重建 qr_code 唯一约束（基于 batch_no，因为 qr_uid 已作为主键）
    if not _constraint_exists(conn, "material_batches", "uq_mb_qr_code"):
        conn.execute(sa.text("""
            ALTER TABLE material_batches
            ADD CONSTRAINT uq_mb_qr_code UNIQUE (qr_code);
        """))
        print("[qr002] uq_mb_qr_code constraint added")

    # 索引
    _safe_create_index(conn, "idx_mb_parent_batch", """
        CREATE INDEX idx_mb_parent_batch
        ON material_batches(parent_batch_id)
        WHERE parent_batch_id IS NOT NULL;
    """)
    _safe_create_index(conn, "idx_mb_qr_code", """
        CREATE INDEX idx_mb_qr_code ON material_batches(qr_code)
        WHERE qr_code IS NOT NULL;
    """)
    _safe_create_index(conn, "idx_mb_batch_no", """
        CREATE INDEX idx_mb_batch_no ON material_batches(batch_no);
    """)

    # ── 2. batch_transactions 表 ────────────────────────────────────────
    if not bt_exists:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS batch_transactions (
                id                  SERIAL PRIMARY KEY,
                batch_id            INTEGER REFERENCES material_batches(id) ON DELETE CASCADE,
                batch_no            VARCHAR(100),
                transaction_type     VARCHAR(20) NOT NULL,
                    -- receive(入库) | iqc | split(分条) | consume(消耗) | scrap(报废)
                quantity_change      NUMERIC(12,4) NOT NULL DEFAULT 0,
                weight_after         NUMERIC(12,4) NOT NULL,
                reference_type       VARCHAR(50),
                reference_id         INTEGER,
                operator_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
                notes                TEXT,
                created_at          TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """))
        print("[qr002] batch_transactions table created")
        _safe_create_index(conn, "idx_bt_batch_id", """
            CREATE INDEX idx_bt_batch_id ON batch_transactions(batch_id DESC, created_at DESC);
        """)
    else:
        print("[qr002] batch_transactions already exists, checking operator_id...")
        bt_cols = _get_columns(conn, "batch_transactions")
        if "operator_id" not in bt_cols:
            _safe_add_col(conn, "batch_transactions", "operator_id", "INTEGER")
            print("[qr002] batch_transactions.operator_id added")

    # ── 3. material_batch_children 表 ───────────────────────────────────
    if not mbc_exists:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS material_batch_children (
                id                  SERIAL PRIMARY KEY,
                parent_batch_id     INTEGER NOT NULL
                    REFERENCES material_batches(id) ON DELETE CASCADE,
                child_batch_no      VARCHAR(100) NOT NULL,
                child_qr_code      VARCHAR(200),
                width               NUMERIC(12,4),
                length              NUMERIC(12,4),
                current_weight      NUMERIC(12,4) NOT NULL DEFAULT 0,
                status              VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
                    -- AVAILABLE | IN_USE | EXHAUSTED
                created_at          TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """))
        print("[qr002] material_batch_children table created")
        _safe_create_index(conn, "idx_mbc_parent", """
            CREATE INDEX idx_mbc_parent ON material_batch_children(parent_batch_id);
        """)
        _safe_create_index(conn, "idx_mbc_child_qr", """
            CREATE INDEX idx_mbc_child_qr ON material_batch_children(child_qr_code)
            WHERE child_qr_code IS NOT NULL;
        """)
        _safe_create_index(conn, "idx_mbc_child_no", """
            CREATE INDEX idx_mbc_child_no ON material_batch_children(child_batch_no);
        """)
    else:
        print("[qr002] material_batch_children already exists")
        mbc_cols = _get_columns(conn, "material_batch_children")
        if "child_qr_code" not in mbc_cols:
            _safe_add_col(conn, "material_batch_children", "child_qr_code", "VARCHAR(200)")
            print("[qr002] material_batch_children.child_qr_code added")
        if "child_batch_no" not in mbc_cols:
            _safe_add_col(conn, "material_batch_children", "child_batch_no", "VARCHAR(100)")
            print("[qr002] material_batch_children.child_batch_no added")

    # ── 4. qr_scan_logs 表 ─────────────────────────────────────────────
    if not qrlog_exists:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS qr_scan_logs (
                id              SERIAL PRIMARY KEY,
                scan_type       VARCHAR(20) NOT NULL,
                    -- MAT(原料) | MCN(机台) | PFC(工艺流转单) | PRT(零件)
                entity_id       INTEGER NOT NULL,
                entity_no       VARCHAR(100),
                operator_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                operation       VARCHAR(20) NOT NULL,
                    -- query(查询) | split(分条) | consume(消耗) | report(报工) | inbound(入库)
                notes           TEXT,
                scanned_at      TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """))
        print("[qr002] qr_scan_logs table created")
        _safe_create_index(conn, "idx_qr_scan_entity", """
            CREATE INDEX idx_qr_scan_entity ON qr_scan_logs(scan_type, entity_id);
        """)
        _safe_create_index(conn, "idx_qr_scan_operator", """
            CREATE INDEX idx_qr_scan_operator ON qr_scan_logs(operator_id);
        """)
        _safe_create_index(conn, "idx_qr_scan_time", """
            CREATE INDEX idx_qr_scan_time ON qr_scan_logs(scanned_at DESC);
        """)
    else:
        print("[qr002] qr_scan_logs already exists")

    print("[qr002] ======== 迁移完成 ========")


def downgrade():
    conn = op.get_bind()
    print("[qr002] 回滚开始")

    conn.execute(sa.text("DROP INDEX IF EXISTS idx_qr_scan_time;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_qr_scan_operator;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_qr_scan_entity;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS qr_scan_logs CASCADE;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_mbc_child_no;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_mbc_child_qr;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_mbc_parent;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS material_batch_children CASCADE;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_bt_batch_id;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS batch_transactions CASCADE;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_mb_batch_no;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_mb_qr_code;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_mb_parent_batch;"))
    conn.execute(sa.text("ALTER TABLE material_batches DROP CONSTRAINT IF EXISTS uq_mb_qr_code;"))
    conn.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS parent_batch_id;"))
    conn.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS batch_no;"))
    conn.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS qr_code;"))

    print("[qr002] ======== 回滚完成 ========")


# ── 工具函数 ──────────────────────────────────────────────────────────────

def _get_columns(conn, table: str) -> set:
    if context.is_offline_mode():
        return set()
    result = conn.execute(
        sa.text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table}';
        """)
    )
    return {row[0] for row in result.fetchall()}


def _table_exists(conn, table: str) -> bool:
    if context.is_offline_mode():
        return False
    result = conn.execute(
        sa.text(f"""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = '{table}';
        """)
    )
    return result.fetchone() is not None


def _constraint_exists(conn, table: str, name: str) -> bool:
    if context.is_offline_mode():
        return False
    result = conn.execute(
        sa.text(f"""
            SELECT 1 FROM pg_constraint WHERE conname = '{name}';
        """)
    )
    return result.fetchone() is not None


def _safe_add_col(conn, table: str, col: str, typ: str):
    # IF NOT EXISTS keeps generated offline SQL repeatable and also covers
    # concurrent/partially-applied online migrations without a result query.
    conn.execute(sa.text(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ};"
    ))
    print(f"[qr002] ensured {table}.{col}")


def _safe_add_fk(conn, table: str, fk_name: str, col: str,
                  ref_table: str, ref_col: str):
    # PostgreSQL has no ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS.  A DO
    # block provides the same idempotency while remaining valid in offline
    # SQL output (and avoids fetching a result set from a static connection).
    conn.execute(sa.text(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{fk_name}'
            ) THEN
                ALTER TABLE {table} ADD CONSTRAINT {fk_name}
                    FOREIGN KEY ({col}) REFERENCES {ref_table}({ref_col})
                    ON DELETE SET NULL;
            END IF;
        END $$;
    """))
    print(f"[qr002] ensured {table}.{col} FK to {ref_table}({ref_col})")


def _safe_create_index(conn, name: str, ddl: str):
    # CREATE INDEX IF NOT EXISTS is supported by PostgreSQL and works for
    # both online execution and Alembic's static SQL generation.
    ddl = re.sub(r"CREATE\s+INDEX\s+", "CREATE INDEX IF NOT EXISTS ",
                 ddl, count=1, flags=re.IGNORECASE)
    conn.execute(sa.text(ddl))
    print(f"[qr002] ensured index {name}")
