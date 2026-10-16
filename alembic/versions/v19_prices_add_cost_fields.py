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
    fields = [
        ('gross_weight',        'NUMERIC(10,4)'),
        ('material_unit_price', 'NUMERIC(12,4)'),
        ('scrap_price',         'NUMERIC(12,4)'),
    ]

    for col, typ in fields:
        op.execute(f"ALTER TABLE prices ADD COLUMN IF NOT EXISTS {col} {typ};")
        op.execute(f"COMMENT ON COLUMN prices.{col} IS '{col}';")


def downgrade():
    for col in ['scrap_price', 'material_unit_price', 'gross_weight']:
        op.execute(f"ALTER TABLE prices DROP COLUMN IF EXISTS {col};")
