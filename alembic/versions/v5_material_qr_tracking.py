"""
阶段五：原料入库与物联赋码 —— 数据库迁移
======================================================================

变更摘要
--------
1. material_batches（原料批次与二维码）：扫码一卷一码，支持母子分条溯源
2. material_transactions（物料流水账）：RECEIVE / SLIT / CONSUME 全链路记录

关联 .cursorrules V3.2 §2.2 原料管理极简入库原则

极简入库原则：
- 不强制录入炉批号和采购单价（二者均可为 NULL）
- 入库即视为 IN_STOCK（合格可用），无需品质二次放行
- 扫码一卷一码（唯一 UID），余料退库不换码

依赖：v4b_sample_molds_cols
执行：alembic upgrade v5_material_qr_tracking
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v5_material_qr_tracking'
down_revision = 'v4b_sample_molds_cols'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. material_batches 表 ─────────────────────────────────────
    print('[v5-material-qr] 步骤1: 创建 material_batches 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS material_batches (
            qr_uid                VARCHAR(50)  PRIMARY KEY,
                -- 唯一二维码 UID，格式如 MAT-2605-001（入库时生成）
            parent_qr_uid         VARCHAR(50)  REFERENCES material_batches(qr_uid),
                -- 分条母卷指向（NULL = 非分条卷）
            material_category     VARCHAR(20)  NOT NULL DEFAULT 'PROD',
                -- PROD(生产主材/钢带) | AUX(辅料)
            material_name         VARCHAR(100) NOT NULL,
                -- 物料名称（如 冷轧钢带、镀锌板等）
            spec                  VARCHAR(100),
                -- 规格描述（如 0.5*80mm）
            supplier_name         VARCHAR(150),
                -- 供应商名称
            heat_number           VARCHAR(100),
                -- 钢厂炉批号（非强制，可 NULL）
            cert_file_path        TEXT,
                -- 质保单附件路径（非强制，可 NULL）
            purchase_unit_price   NUMERIC(10,4),
                -- 采购单价 kg/元（非强制，可 NULL）
            initial_weight        NUMERIC(12,4) NOT NULL,
                -- 入库时初始重量 kg
            current_weight        NUMERIC(12,4) NOT NULL,
                -- 当前结存重量 kg（生产报工时自动扣减）
            lifecycle_status      VARCHAR(20)  NOT NULL DEFAULT 'IN_STOCK',
                -- IN_STOCK（在库可用）| IN_USE（生产中）| DEPLETED（耗尽/已用完）
                -- 入库即置 IN_STOCK，无需品质二次放行
            created_by           INTEGER      REFERENCES users(id),
                -- 入库操作人
            created_at            TIMESTAMP    NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMP    NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_material_category
                CHECK (material_category IN ('PROD', 'AUX')),
            CONSTRAINT chk_lifecycle_status
                CHECK (lifecycle_status IN ('IN_STOCK', 'IN_USE', 'DEPLETED')),
            CONSTRAINT chk_current_weight
                CHECK (current_weight >= 0)
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_mb_category
        ON material_batches(material_category)
        WHERE lifecycle_status != 'DEPLETED';
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_mb_parent
        ON material_batches(parent_qr_uid)
        WHERE parent_qr_uid IS NOT NULL;
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_mb_status
        ON material_batches(lifecycle_status)
        WHERE lifecycle_status != 'DEPLETED';
    """))
    print('[v5-material-qr]   material_batches 表 + 索引创建完成')

    # ── 2. material_transactions 表 ────────────────────────────────
    print('[v5-material-qr] 步骤2: 创建 material_transactions 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS material_transactions (
            id                    SERIAL       PRIMARY KEY,
            qr_uid                VARCHAR(50)  NOT NULL
                                           REFERENCES material_batches(qr_uid)
                                           ON DELETE CASCADE,
                -- 关联原料批次二维码
            transaction_type       VARCHAR(20)  NOT NULL,
                -- RECEIVE（入库）| SLIT（分条）| CONSUME（消耗/报工扣减）
            weight_change         NUMERIC(12,4) NOT NULL,
                -- 变化量（入库/分条入子卷为正，出库/消耗为负）
            current_balance       NUMERIC(12,4) NOT NULL,
                -- 本次动作执行后的结存重量
            related_work_order_id INTEGER,
                -- 关联工单 ID（消耗时必填，其余可 NULL）
            operator_id            INTEGER      REFERENCES users(id),
                -- 操作人
            created_at            TIMESTAMP    NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_tx_type
                CHECK (transaction_type IN ('RECEIVE', 'SLIT', 'CONSUME'))
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX idx_mt_qr_uid
        ON material_transactions(qr_uid DESC, created_at DESC);
    """))
    print('[v5-material-qr]   material_transactions 表 + 索引创建完成')
    print('[v5-material-qr] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v5-material-qr] 回滚：删除 material_transactions')
    conn.execute(sa.text("DROP TABLE IF EXISTS material_transactions CASCADE;"))
    print('[v5-material-qr] 回滚：删除 material_batches')
    conn.execute(sa.text("DROP TABLE IF EXISTS material_batches CASCADE;"))
    print('[v5-material-qr] 回滚完成')
