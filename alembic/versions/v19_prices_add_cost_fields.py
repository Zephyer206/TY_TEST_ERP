"""
价格台账补充成本字段 —— 数据库迁移
======================================================================
在 prices 表增加三个字段：
  - gross_weight         毛重（kg/件）
  - material_unit_price  当前材料单价（元/kg）
  - scrap_price          废料回收价（元/kg）

执行：py -m alembic upgrade v19_prices_add_cost_fields
回滚：py -m alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v19_prices_add_cost_fields'
down_revision = 'v18_prices'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    existing = {}
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'prices';
    """)).fetchall()
    existing = {r[0] for r in result}

    fields = [
        ('gross_weight',        'NUMERIC(10,4)'),
        ('material_unit_price', 'NUMERIC(12,4)'),
        ('scrap_price',         'NUMERIC(12,4)'),
    ]

    for col, typ in fields:
        if col not in existing:
            op.execute(f"ALTER TABLE prices ADD COLUMN {col} {typ};")
            op.execute(f"COMMENT ON COLUMN prices.{col} IS '{col}';")
            print(f'[v19] prices.{col} added')
        else:
            print(f'[v19] prices.{col} already exists, skipping')


def downgrade():
    conn = op.get_bind()
    for col in ['scrap_price', 'material_unit_price', 'gross_weight']:
        result = conn.execute(sa.text(f"""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'prices' AND column_name = '{col}';
        """)).fetchone()
        if result:
            op.execute(f"ALTER TABLE prices DROP COLUMN IF EXISTS {col};")
            print(f'[v19] prices.{col} dropped')
