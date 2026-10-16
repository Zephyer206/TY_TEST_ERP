"""
为 parts 表增加 material_name 字段（用于关联材料基准价格，支持草稿价格联动）

依赖：mbp0001_material_base_prices（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'mbp0002_parts_material_name'
down_revision = 'mbp0001_material_base_prices'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE parts ADD COLUMN IF NOT EXISTS material_name VARCHAR(100)")
    op.execute("COMMENT ON COLUMN parts.material_name IS '零件所用材料牌号，用于关联 material_base_prices'")
    print('[mbp] parts.material_name ensured')


def downgrade():
    op.drop_column('parts', 'material_name')
