"""add_price_management_tables

Revision ID: feb2532a66b9
Revises: 
Create Date: 2026-07-20 07:51:06.738028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'feb2532a66b9'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建价格管理系统表."""

    # 1. treatment_dict - 工序字典表
    op.create_table(
        'treatment_dict',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('calc_mode', sa.String(length=20), nullable=False, server_default='manual'),
        sa.Column('default_rate', sa.Numeric(precision=10, scale=4), nullable=False, server_default='0'),
        sa.Column('unit', sa.String(length=20), nullable=False, server_default='元/件'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_treatment_dict_name'), 'treatment_dict', ['name'], unique=True)

    # 2. customer_material_prices - 客户材料价格历史表
    op.create_table(
        'customer_material_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('scrap_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('quote_id', sa.Integer(), nullable=True),
        sa.Column('quoted_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customer_material_prices_customer_id'), 'customer_material_prices', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customer_material_prices_material_id'), 'customer_material_prices', ['material_id'], unique=False)
    op.create_index(op.f('ix_customer_material_prices_quote_id'), 'customer_material_prices', ['quote_id'], unique=False)

    # 3. customer_treatment_prices - 客户工序价格历史表
    op.create_table(
        'customer_treatment_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('treatment_id', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('calc_mode_snapshot', sa.String(length=20), nullable=True),
        sa.Column('unit_snapshot', sa.String(length=20), nullable=True),
        sa.Column('quote_id', sa.Integer(), nullable=True),
        sa.Column('quoted_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customer_treatment_prices_customer_id'), 'customer_treatment_prices', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customer_treatment_prices_treatment_id'), 'customer_treatment_prices', ['treatment_id'], unique=False)
    op.create_index(op.f('ix_customer_treatment_prices_quote_id'), 'customer_treatment_prices', ['quote_id'], unique=False)

    # 4. price_adjustments - 价格调整审批表
    op.create_table(
        'price_adjustments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=True),
        sa.Column('material_id', sa.Integer(), nullable=True),
        sa.Column('treatment_name', sa.String(length=100), nullable=True),
        sa.Column('adjustment_type', sa.String(length=20), nullable=False),
        sa.Column('old_price', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('new_price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('requested_by', sa.Integer(), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('effective_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_adjustments_customer_id'), 'price_adjustments', ['customer_id'], unique=False)
    op.create_index(op.f('ix_price_adjustments_status'), 'price_adjustments', ['status'], unique=False)


def downgrade() -> None:
    """回滚价格管理系统表."""
    op.drop_index(op.f('ix_price_adjustments_status'), table_name='price_adjustments')
    op.drop_index(op.f('ix_price_adjustments_customer_id'), table_name='price_adjustments')
    op.drop_table('price_adjustments')

    op.drop_index(op.f('ix_customer_treatment_prices_quote_id'), table_name='customer_treatment_prices')
    op.drop_index(op.f('ix_customer_treatment_prices_treatment_id'), table_name='customer_treatment_prices')
    op.drop_index(op.f('ix_customer_treatment_prices_customer_id'), table_name='customer_treatment_prices')
    op.drop_table('customer_treatment_prices')

    op.drop_index(op.f('ix_customer_material_prices_quote_id'), table_name='customer_material_prices')
    op.drop_index(op.f('ix_customer_material_prices_material_id'), table_name='customer_material_prices')
    op.drop_index(op.f('ix_customer_material_prices_customer_id'), table_name='customer_material_prices')
    op.drop_table('customer_material_prices')

    op.drop_index(op.f('ix_treatment_dict_name'), table_name='treatment_dict')
    op.drop_table('treatment_dict')
