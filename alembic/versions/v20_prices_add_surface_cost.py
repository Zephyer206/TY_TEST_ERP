"""
价格台账补充表面处理成本字段 —— 数据库迁移
======================================================================
在 prices 表增加两个字段：
  - surface_treatment_cost  表面处理成本（元/件），手动填写
  - cost_override           成本覆盖值，手动填写后优先使用

执行：py -m alembic upgrade v20_prices_add_surface_cost
回滚：py -m alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v20_prices_add_surface_cost'
down_revision = 'v19_prices_add_cost_fields'
branch_labels = None
depends_on = None


def upgrade():
    fields = [
        ('surface_treatment_cost', 'NUMERIC(12,4)'),
        ('cost_override',         'NUMERIC(12,4)'),
    ]

    for col, typ in fields:
        op.execute(f"ALTER TABLE prices ADD COLUMN IF NOT EXISTS {col} {typ};")


def downgrade():
    for col in ['cost_override', 'surface_treatment_cost']:
        op.execute(f"ALTER TABLE prices DROP COLUMN IF EXISTS {col};")
