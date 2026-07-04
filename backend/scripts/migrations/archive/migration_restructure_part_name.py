"""
Alembic migration: Restructure part_name_dict for three-level categorization.

Revision ID: restructure_part_name_dict
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'restructure_part_name_dict'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 1. 添加新字段
    op.add_column('part_name_dict', sa.Column('primary_category', sa.String(100), nullable=True))
    op.add_column('part_name_dict', sa.Column('secondary_category', sa.String(100), nullable=True))
    op.add_column('part_name_dict', sa.Column('customer_part_name', sa.String(200), nullable=True))
    op.add_column('part_name_dict', sa.Column('remark', sa.Text(), nullable=True))

    # 2. 迁移现有数据
    # ID 1: 弹簧片 -> 一级=弹簧片, 二级=弹簧片, 三级=NULL
    op.execute("""
        UPDATE part_name_dict
        SET primary_category = '弹簧片',
            secondary_category = '弹簧片',
            customer_part_name = NULL,
            remark = '标准件'
        WHERE id = 1
    """)

    # ID 2: 摩擦片保持(右) -> 一级=弹簧片, 二级=弹簧片, 三级=摩擦片保持(右)
    op.execute("""
        UPDATE part_name_dict
        SET primary_category = '弹簧片',
            secondary_category = '弹簧片',
            customer_part_name = '摩擦片保持(右)',
            remark = NULL
        WHERE id = 2
    """)

    # ID 3: 摩擦片保持 -> 一级=弹簧片, 二级=弹簧片, 三级=摩擦片保持
    op.execute("""
        UPDATE part_name_dict
        SET primary_category = '弹簧片',
            secondary_category = '弹簧片',
            customer_part_name = '摩擦片保持',
            remark = NULL
        WHERE id = 3
    """)

    # ID 4: 报警器 -> 一级=报警器, 二级=报警器, 三级=NULL
    op.execute("""
        UPDATE part_name_dict
        SET primary_category = '报警器',
            secondary_category = '报警器',
            customer_part_name = NULL,
            remark = '标准件'
        WHERE id = 4
    """)

    # 3. 设置 primary_category 为 NOT NULL
    op.alter_column('part_name_dict', 'primary_category', nullable=False)

    # 4. 删除旧字段（保留 name 字段以防万一，可以之后手动删除）
    # op.drop_column('part_name_dict', 'category')
    # op.drop_column('part_name_dict', 'name')

    # 5. 创建复合唯一索引
    op.create_index(
        'idx_part_name_unique',
        'part_name_dict',
        ['primary_category', 'secondary_category', 'customer_part_name'],
        unique=True
    )


def downgrade():
    op.drop_index('idx_part_name_unique', 'part_name_dict')
    op.drop_column('part_name_dict', 'remark')
    op.drop_column('part_name_dict', 'customer_part_name')
    op.drop_column('part_name_dict', 'secondary_category')
    op.drop_column('part_name_dict', 'primary_category')
