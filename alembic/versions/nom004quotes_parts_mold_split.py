"""
Quotes/Parts 模具字段拆分重构 —— 数据库迁移
======================================================================
业务背景：
  预报价阶段（quotes）不包含模具信息，只有定点后才出现模具编号。
  定点确认时，将 quotes 的模具字段同步到 parts 表。

┌─────────────────────────────────────────────────────────────────────┐
│  变更 1：quotes 新增字段（预报价阶段由业务员填写）                    │
│  ┌──────────────────┬───────────────────────────────────────────┐    │
│  │ customer_id      │ INTEGER  FK → customers(id)  客户          │    │
│  │ customer_product_no │ VARCHAR(100)  客户产品号               │    │
│  │ vehicle_model    │ VARCHAR(100)  适用车型                   │    │
│  └──────────────────┴───────────────────────────────────────────┘    │
│                                                                      │
│  变更 2：parts 新增字段（定点确认后填写，模具基础信息）              │
│  ┌──────────────────┬───────────────────────────────────────────┐    │
│  │ mold_number      │ VARCHAR(50)   模具编号                    │    │
│  │ mold_type        │ VARCHAR(30)   模具类型（级进模/单工程/传递模）│  │
│  │ press_tonnage    │ VARCHAR(30)   冲压吨位（如 200T）         │    │
│  │ ppap_no          │ VARCHAR(50)   PPAP 编号                  │    │
│  │ customer_product_no │ VARCHAR(100) 客户产品号               │    │
│  │ vehicle_model    │ VARCHAR(100)  适用车型                   │    │
│  └──────────────────┴───────────────────────────────────────────┘    │
│                                                                      │
│  变更 3：quotes.die_id 改为模具编号字符串（取消外键）                │
│  - quotes.die_id (FK) → quotes.mold_number (VARCHAR)，模具编号        │
│    在预报价时可能尚未分配模具ID，仅记录编号字符串更灵活               │
│                                                                      │
│  执行：py -m alembic upgrade nom004quotes_parts_mold_split            │
│  回滚：py -m alembic downgrade -1                                    │
└─────────────────────────────────────────────────────────────────────┘
"""

from alembic import op
import sqlalchemy as sa

revision = 'nom004quotes_parts_mold_split'
down_revision = 'nom003nomination_price_snapshot'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 变更 1a：quotes.customer_id ──────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'quotes' AND column_name = 'customer_id';
    """)).fetchone()
    if not result:
        op.add_column('quotes', sa.Column('customer_id', sa.Integer(), nullable=True))
        op.execute("COMMENT ON COLUMN quotes.customer_id IS '客户 FK → customers(id)'")
        op.execute("CREATE INDEX IF NOT EXISTS idx_quotes_customer_id ON quotes(customer_id);")
        print('[nom004] quotes.customer_id added')

    # ── 变更 1b：quotes.customer_product_no ────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'quotes' AND column_name = 'customer_product_no';
    """)).fetchone()
    if not result:
        op.add_column('quotes', sa.Column('customer_product_no', sa.String(100), nullable=True))
        op.execute("COMMENT ON COLUMN quotes.customer_product_no IS '客户产品号（预报价阶段填写）'")
        print('[nom004] quotes.customer_product_no added')

    # ── 变更 1c：quotes.vehicle_model ────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'quotes' AND column_name = 'vehicle_model';
    """)).fetchone()
    if not result:
        op.add_column('quotes', sa.Column('vehicle_model', sa.String(100), nullable=True))
        op.execute("COMMENT ON COLUMN quotes.vehicle_model IS '适用车型（预报价阶段填写）'")
        print('[nom004] quotes.vehicle_model added')

    # ── 变更 2a：parts.mold_number ─────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'mold_number';
    """)).fetchone()
    if not result:
        op.add_column('parts', sa.Column('mold_number', sa.String(50), nullable=True))
        op.execute("COMMENT ON COLUMN parts.mold_number IS '模具编号（定点后填写）'")
        print('[nom004] parts.mold_number added')

    # ── 变更 2b：parts.mold_type ───────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'mold_type';
    """)).fetchone()
    if not result:
        op.add_column('parts', sa.Column('mold_type', sa.String(30), nullable=True))
        op.execute("COMMENT ON COLUMN parts.mold_type IS '模具类型：级进模/单工程/传递模（定点后填写）'")
        print('[nom004] parts.mold_type added')

    # ── 变更 2c：parts.press_tonnage ────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'press_tonnage';
    """)).fetchone()
    if not result:
        op.add_column('parts', sa.Column('press_tonnage', sa.String(30), nullable=True))
        op.execute("COMMENT ON COLUMN parts.press_tonnage IS '冲压吨位，如 200T（定点后填写）'")
        print('[nom004] parts.press_tonnage added')

    # ── 变更 2d：parts.ppap_no ─────────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'ppap_no';
    """)).fetchone()
    if not result:
        op.add_column('parts', sa.Column('ppap_no', sa.String(50), nullable=True))
        op.execute("COMMENT ON COLUMN parts.ppap_no IS 'PPAP 编号（定点后填写）'")
        print('[nom004] parts.ppap_no added')

    # ── 变更 2e：parts.customer_product_no ──────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'customer_product_no';
    """)).fetchone()
    if not result:
        op.add_column('parts', sa.Column('customer_product_no', sa.String(100), nullable=True))
        op.execute("COMMENT ON COLUMN parts.customer_product_no IS '客户产品号（定点后填写）'")
        print('[nom004] parts.customer_product_no added')

    # ── 变更 2f：parts.vehicle_model ────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'vehicle_model';
    """)).fetchone()
    if not result:
        op.add_column('parts', sa.Column('vehicle_model', sa.String(100), nullable=True))
        op.execute("COMMENT ON COLUMN parts.vehicle_model IS '适用车型（定点后填写）'")
        print('[nom004] parts.vehicle_model added')

    print('[nom004] ======== Migration complete ========')


def downgrade():
    conn = op.get_bind()

    # 回滚 parts 字段
    for col in ('mold_number', 'mold_type', 'press_tonnage', 'ppap_no',
                'customer_product_no', 'vehicle_model'):
        conn.execute(sa.text(f"ALTER TABLE parts DROP COLUMN IF EXISTS {col};"))
        print(f'[nom004] parts.{col} dropped')

    # 回滚 quotes 字段
    for col in ('customer_id', 'customer_product_no', 'vehicle_model'):
        conn.execute(sa.text(f"ALTER TABLE quotes DROP COLUMN IF EXISTS {col};"))
        print(f'[nom004] quotes.{col} dropped')

    # 删除索引
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_quotes_customer_id;"))

    print('[nom004] Downgrade complete')
