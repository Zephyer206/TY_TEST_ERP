"""
v16_treatment_items_and_mold_discount.py

Migration: 添加 quotes 表新字段
- treatment_items   : JSONB   多道表面处理工序（替代旧的 surface_fee 手动输入）
- mold_discount_mode : VARCHAR 模具费收取模式 ('amortized'=分摊, 'direct'=直接收取)
- mold_discount_rate : NUMERIC 模具费折扣率 (0.0=不打折, 0.75=75折, 0.8=8折)

treatment_items 结构示例:
[
    {"name": "热处理", "fee": 2.5},
    {"name": "电镀锌", "fee": 1.8}
]
"""
from alembic import op
import sqlalchemy as sa

revision = 'v16_treatment_items_and_mold_discount'
down_revision = 'v16'  # 依赖上一个 migration v16_add_annual_avg_lifecycle
branch_labels = None
depends_on = None


def upgrade():
    # 1. treatment_items: JSONB，多道表面处理工序
    op.add_column('quotes', sa.Column(
        'treatment_items', sa.JSONB, nullable=True, server_default=None,
        comment='多道表面处理工序，结构：[{"name":"热处理","fee":2.5},...]'
    ))
    # 将旧 surface_fee 数据迁移到 treatment_items（保留旧字段，数据迁移后业务层统一用 treatment_items）
    op.execute("""
        UPDATE quotes
        SET treatment_items = '[{"name": "表面处理", "fee": COALESCE(surface_fee, 0)}]::jsonb'
        WHERE surface_fee IS NOT NULL AND surface_fee > 0;
    """)

    # 2. mold_discount_mode: 模具费收取模式
    op.add_column('quotes', sa.Column(
        'mold_discount_mode', sa.String(32), nullable=True, server_default='direct',
        comment="模具费收取模式: 'direct'=直接收取, 'amortized'=分摊到年用量和生命周期"
    ))

    # 3. mold_discount_rate: 模具费折扣率
    op.add_column('quotes', sa.Column(
        'mold_discount_rate', sa.Numeric(5, 4), nullable=True, server_default='1.0',
        comment='模具费折扣率，0.0~1.0，如 0.75=75折，1.0=不打折'
    ))


def downgrade():
    op.drop_column('quotes', 'treatment_items')
    op.drop_column('quotes', 'mold_discount_rate')
    op.drop_column('quotes', 'mold_discount_mode')
