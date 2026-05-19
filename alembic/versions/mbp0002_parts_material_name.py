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
    conn = op.get_bind()

    # 检查字段是否已存在
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'material_name';
    """)).fetchone()

    if not result:
        op.add_column(
            'parts',
            sa.Column('material_name', sa.String(100), nullable=True)
        )
        op.execute("COMMENT ON COLUMN parts.material_name IS '零件所用材料牌号，用于关联 material_base_prices'")
        print('[mbp] parts.material_name added')


def downgrade():
    op.drop_column('parts', 'material_name')
