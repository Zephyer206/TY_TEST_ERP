"""
价格台账（prices）—— 数据库迁移
======================================================================
业务背景：
  为每个零件建立完整的价格台账，记录：
  - 成本要素（材料类型、净重、表面处理）
  - 年份维度（各年单价、年销量）
  - 年降规则（降多少、降几年、从哪年开始）
  - 手动调价记录（时间、调价前后价格、原因）

┌─────────────────────────────────────────────────────────────────────┐
│  表 1：prices（价格台账主表）                                        │
│  ┌─────────────────────┬────────────────────────────────────────┐  │
│  │ part_id             │ INTEGER FK→parts(id)  零件              │  │
│  │ customer_id         │ INTEGER FK→tooling_customers(id) 客户   │  │
│  │ material_name       │ VARCHAR(100)  材料类型（如 DC01）        │  │
│  │ net_weight          │ NUMERIC(10,4)  净重（kg/件）            │  │
│  │ surface_treatment   │ JSONB  表面处理（如 [{"name":"电镀锌"}]）│  │
│  │ created_at          │ TIMESTAMP  创建时间                      │  │
│  │ updated_at          │ TIMESTAMP  更新时间                      │  │
│  └─────────────────────┴────────────────────────────────────────┘  │
│  唯一约束：(part_id, customer_id)                                    │
│                                                                      │
│  表 2：price_years（年份单价与销量）                                 │
│  ┌─────────────────┬────────────────────────────────────────────┐  │
│  │ price_id       │ INTEGER FK→prices(id)                       │  │
│  │ year           │ INTEGER  年份                               │  │
│  │ unit_price     │ NUMERIC(12,4)  单价（元/件）                │  │
│  │ annual_sales   │ INTEGER  年销量（件）                       │  │
│  │ operator_id    │ INTEGER FK→users(id)  录入人                 │  │
│  │ updated_at     │ TIMESTAMP  更新时间                          │  │
│  └─────────────────┴────────────────────────────────────────────┘  │
│  唯一约束：(price_id, year)                                          │
│                                                                      │
│  表 3：annual_reductions（年降规则）                                 │
│  ┌─────────────────┬────────────────────────────────────────────┐  │
│  │ price_id       │ INTEGER FK→prices(id)                       │  │
│  │ reduction_pct  │ NUMERIC(5,2)  年降比例（如 3.00 表示 3%）  │  │
│  │ start_year     │ INTEGER  起始年份                            │  │
│  │ duration_years │ INTEGER  持续年数（0 表示无限期）           │  │
│  │ reason         │ VARCHAR(200)  年降原因（如 年度让利）       │  │
│  │ created_by     │ INTEGER FK→users(id)  创建人                │  │
│  │ created_at     │ TIMESTAMP  创建时间                         │  │
│  └─────────────────┴────────────────────────────────────────────┘  │
│                                                                      │
│  表 4：manual_adjustments（手动调价记录）                            │
│  ┌─────────────────┬────────────────────────────────────────────┐  │
│  │ price_id       │ INTEGER FK→prices(id)                       │  │
│  │ adjusted_at     │ TIMESTAMP  调价时间                         │  │
│  │ old_price       │ NUMERIC(12,4)  调价前单价                  │  │
│  │ new_price       │ NUMERIC(12,4)  调价后单价                  │  │
│  │ adjustment_type │ VARCHAR(30)  调价类型                       │  │
│  │                 │ （material/labor/overhead/profit/surface）  │  │
│  │ reason          │ VARCHAR(200)  调价原因                      │  │
│  │ operator_id     │ INTEGER FK→users(id)  操作人                │  │
│  └─────────────────┴────────────────────────────────────────────┘  │
│                                                                      │
│  执行：py -m alembic upgrade v18_prices                              │
│  回滚：py -m alembic downgrade -1                                    │
└─────────────────────────────────────────────────────────────────────┘
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import json

revision = 'v18_prices'
down_revision = 'v16_treatment_items_and_mold_discount'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 表 1：prices ───────────────────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'prices';
    """)).fetchone()
    if not result:
        op.execute("""
            CREATE TABLE prices (
                id SERIAL PRIMARY KEY,
                part_id INTEGER NOT NULL,
                customer_id INTEGER,
                material_name VARCHAR(100),
                net_weight NUMERIC(10,4),
                surface_treatment JSONB DEFAULT '[]'::jsonb,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(part_id, customer_id)
            );
        """)
        op.execute("CREATE INDEX idx_prices_part_id ON prices(part_id);")
        op.execute("CREATE INDEX idx_prices_customer_id ON prices(customer_id);")
        op.execute("COMMENT ON TABLE prices IS '价格台账主表：记录每个零件+客户的成本要素'")
        print('[v18] table prices created')

        # 外键
        op.execute("""
            ALTER TABLE prices
            ADD CONSTRAINT fk_prices_part_id
            FOREIGN KEY (part_id) REFERENCES parts(id)
            ON DELETE CASCADE;
        """)
        op.execute("""
            ALTER TABLE prices
            ADD CONSTRAINT fk_prices_customer_id
            FOREIGN KEY (customer_id) REFERENCES tooling_customers(id)
            ON DELETE SET NULL;
        """)
        print('[v18] prices foreign keys added')
    else:
        print('[v18] table prices already exists, skipping')

    # ── 表 2：price_years ──────────────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'price_years';
    """)).fetchone()
    if not result:
        op.execute("""
            CREATE TABLE price_years (
                id SERIAL PRIMARY KEY,
                price_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                unit_price NUMERIC(12,4),
                annual_sales INTEGER DEFAULT 0,
                operator_id INTEGER,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(price_id, year)
            );
        """)
        op.execute("CREATE INDEX idx_price_years_price_id ON price_years(price_id);")
        op.execute("CREATE INDEX idx_price_years_year ON price_years(year);")
        op.execute("COMMENT ON TABLE price_years IS '年份单价与年销量'")
        print('[v18] table price_years created')

        op.execute("""
            ALTER TABLE price_years
            ADD CONSTRAINT fk_price_years_price_id
            FOREIGN KEY (price_id) REFERENCES prices(id)
            ON DELETE CASCADE;
        """)
        print('[v18] price_years foreign key added')
    else:
        print('[v18] table price_years already exists, skipping')

    # ── 表 3：annual_reductions ────────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'annual_reductions';
    """)).fetchone()
    if not result:
        op.execute("""
            CREATE TABLE annual_reductions (
                id SERIAL PRIMARY KEY,
                price_id INTEGER NOT NULL,
                reduction_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
                start_year INTEGER NOT NULL,
                duration_years INTEGER DEFAULT 0,
                reason VARCHAR(200),
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        op.execute("CREATE INDEX idx_annual_reductions_price_id ON annual_reductions(price_id);")
        op.execute("COMMENT ON TABLE annual_reductions IS '年降规则表'")
        print('[v18] table annual_reductions created')

        op.execute("""
            ALTER TABLE annual_reductions
            ADD CONSTRAINT fk_annual_reductions_price_id
            FOREIGN KEY (price_id) REFERENCES prices(id)
            ON DELETE CASCADE;
        """)
        print('[v18] annual_reductions foreign key added')
    else:
        print('[v18] table annual_reductions already exists, skipping')

    # ── 表 4：manual_adjustments ──────────────────────────────────
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'manual_adjustments';
    """)).fetchone()
    if not result:
        op.execute("""
            CREATE TABLE manual_adjustments (
                id SERIAL PRIMARY KEY,
                price_id INTEGER NOT NULL,
                adjusted_at TIMESTAMP DEFAULT NOW(),
                old_price NUMERIC(12,4),
                new_price NUMERIC(12,4),
                adjustment_type VARCHAR(30),
                reason VARCHAR(200),
                operator_id INTEGER
            );
        """)
        op.execute("CREATE INDEX idx_manual_adjustments_price_id ON manual_adjustments(price_id);")
        op.execute("CREATE INDEX idx_manual_adjustments_adjusted_at ON manual_adjustments(adjusted_at);")
        op.execute("COMMENT ON TABLE manual_adjustments IS '手动调价记录'")
        print('[v18] table manual_adjustments created')

        op.execute("""
            ALTER TABLE manual_adjustments
            ADD CONSTRAINT fk_manual_adjustments_price_id
            FOREIGN KEY (price_id) REFERENCES prices(id)
            ON DELETE CASCADE;
        """)
        print('[v18] manual_adjustments foreign key added')
    else:
        print('[v18] table manual_adjustments already exists, skipping')


def downgrade():
    conn = op.get_bind()

    tables = ['manual_adjustments', 'annual_reductions', 'price_years', 'prices']
    for tbl in tables:
        result = conn.execute(sa.text(f"""
            SELECT 1 FROM information_schema.tables WHERE table_name = '{tbl}';
        """)).fetchone()
        if result:
            op.execute(f'DROP TABLE IF EXISTS {tbl} CASCADE;')
            print(f'[v18] table {tbl} dropped')
        else:
            print(f'[v18] table {tbl} does not exist, skipping')
