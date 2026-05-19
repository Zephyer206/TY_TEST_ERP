"""
材料基准价格表 + 预设材料数据注入

表：material_base_prices
  material_name     : VARCHAR PRIMARY KEY（材料牌号，如 SUS301）
  default_density  : NUMERIC(6,3)  — 密度 g/cm³
  default_price    : NUMERIC(10,4) — 默认含税单价 元/kg
  scrap_price      : NUMERIC(10,4) — 废料回收价 元/kg（nullable）
  updated_at       : TIMESTAMP

预设数据：
  SUS301  密度 7.93  单价 21.0  废料 12.0
  SUS304  密度 7.93  单价 20.5  废料 12.0
  SPCC   密度 7.85  单价  6.5  废料  1.8
  SECC   密度 7.85  单价  7.8  废料  1.8
  SGCC   密度 7.85  单价  6.2  废料  1.8
  SK5    密度 7.85  单价  9.5  废料  2.0
  6061   密度 2.70  单价 32.0  废料 18.0
  5052   密度 2.68  单价 30.0  废料 16.0

依赖：mat0001slitting_logs（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'mbp0001_material_base_prices'
down_revision = 'mat0001slitting_logs'
branch_labels = None
depends_on = None

# ── 预设材料数据 ────────────────────────────────────────────────
SEED_DATA = [
    ('SUS301',  7.93, 21.00, 12.00),
    ('SUS304',  7.93, 20.50, 12.00),
    ('SPCC',    7.85,  6.50,  1.80),
    ('SECC',    7.85,  7.80,  1.80),
    ('SGCC',    7.85,  6.20,  1.80),
    ('SK5',     7.85,  9.50,  2.00),
    ('6061',    2.70, 32.00, 18.00),
    ('5052',    2.68, 30.00, 16.00),
]


def upgrade():
    conn = op.get_bind()

    # ── 1. 创建表 ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS material_base_prices (
            material_name    VARCHAR(100) PRIMARY KEY,
            default_density  NUMERIC(6,3)  NOT NULL DEFAULT 7.85,
            default_price    NUMERIC(10,4) NOT NULL DEFAULT 0,
            scrap_price      NUMERIC(10,4),
            updated_at       TIMESTAMP     NOT NULL DEFAULT NOW()
        );
    """)
    print('[mbp] material_base_prices created')

    # ── 2. 注入预设材料（INSERT IGNORE 语义，ON CONFLICT DO NOTHING）─
    for name, density, price, scrap in SEED_DATA:
        op.execute(f"""
            INSERT INTO material_base_prices
                (material_name, default_density, default_price, scrap_price, updated_at)
            VALUES ('{name}', {density}, {price}, {scrap}, NOW())
            ON CONFLICT (material_name) DO NOTHING;
        """)
        print(f'[mbp] seed: {name}')


def downgrade():
    op.execute("DROP TABLE IF EXISTS material_base_prices;")
