"""add customer entity and price system tables

Revision ID: 20260707_customer_price_system
Revises: (check latest revision)
Create Date: 2026-07-07

实施数据库设计定稿（2026-07-07）的核心表：
1. 重命名 tooling_customers -> customers
2. 创建 customer_material_prices（客户材料价格历史）
3. 创建 customer_treatment_prices（客户工序价格历史）
4. 创建 treatment_dict（工序字典，重建）
5. 更新 parts 表添加 TWP 字段
6. 创建 price_accounts（价格台账）
7. 创建 price_adjustments（调价记录）
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260707_customer_price_system'
down_revision = None  # TODO: 设置为最新的 revision ID
branch_labels = None
depends_on = None


def upgrade():
    """应用迁移"""

    # ========================================
    # 1. 重命名 tooling_customers -> customers
    # ========================================
    print("Step 1: Renaming tooling_customers to customers...")
    op.rename_table('tooling_customers', 'customers')

    # 添加缺失的字段到 customers 表
    op.add_column('customers', sa.Column('contact_email', sa.String(100), nullable=True))
    op.add_column('customers', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('customers', sa.Column('sheet_key', sa.String(100), nullable=True))
    op.add_column('customers', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))

    # 添加注释
    op.execute("COMMENT ON TABLE customers IS '客户主表，业务主体，价格体系核心'")

    # ========================================
    # 2. 创建 treatment_dict（工序字典）
    # ========================================
    print("Step 2: Creating treatment_dict table...")
    op.create_table(
        'treatment_dict',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('calc_mode', sa.String(20), server_default='manual', nullable=False),
        sa.Column('default_rate', sa.Numeric(10, 4), server_default='0', nullable=False),
        sa.Column('unit', sa.String(20), server_default='元/件', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_treatment_dict_active', 'treatment_dict', ['is_active'])
    op.execute("COMMENT ON TABLE treatment_dict IS '表面处理工序字典 - 全局默认费率，客户特定价格见 customer_treatment_prices'")
    op.execute("COMMENT ON COLUMN treatment_dict.default_rate IS '默认费率，无客户历史价格时的兜底值'")

    # 迁移 treatment_dicts 中的真实工序数据
    print("  Migrating valid treatment data from treatment_dicts...")
    op.execute("""
        INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active)
        SELECT name, calc_mode, rate, unit, TRUE
        FROM treatment_dicts
        WHERE name IN ('热处理','电镀锌','发黑','喷涂','贴胶','阳极氧化','磷化','压铸镀层','电镀镍','达克罗涂装')
        ON CONFLICT (name) DO NOTHING
    """)

    # ========================================
    # 3. 创建 customer_material_prices（客户材料价格历史）
    # ========================================
    print("Step 3: Creating customer_material_prices table...")
    op.create_table(
        'customer_material_prices',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(10, 4), nullable=False),
        sa.Column('scrap_price', sa.Numeric(10, 4), nullable=True),
        sa.Column('quote_id', sa.Integer(), nullable=True),
        sa.Column('quoted_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['material_dict.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_cmp_customer_material', 'customer_material_prices',
                    ['customer_id', 'material_id', sa.text('quoted_at DESC')])
    op.create_index('idx_cmp_quote', 'customer_material_prices', ['quote_id'],
                    postgresql_where=sa.text('quote_id IS NOT NULL'))
    op.execute("COMMENT ON TABLE customer_material_prices IS '客户材料价格历史 - 保留全部历史记录，查询时取最近3次作为报价参考'")
    op.execute("COMMENT ON COLUMN customer_material_prices.quote_id IS '关联报价单，标记该价格是在哪次报价中确定的，可为空（补录历史数据时）'")

    # ========================================
    # 4. 创建 customer_treatment_prices（客户工序价格历史）
    # ========================================
    print("Step 4: Creating customer_treatment_prices table...")
    op.create_table(
        'customer_treatment_prices',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('treatment_id', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(10, 4), nullable=False),
        sa.Column('calc_mode_snapshot', sa.String(20), nullable=True),
        sa.Column('unit_snapshot', sa.String(20), nullable=True),
        sa.Column('quote_id', sa.Integer(), nullable=True),
        sa.Column('quoted_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['treatment_id'], ['treatment_dict.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_ctp_customer_treatment', 'customer_treatment_prices',
                    ['customer_id', 'treatment_id', sa.text('quoted_at DESC')])
    op.create_index('idx_ctp_quote', 'customer_treatment_prices', ['quote_id'],
                    postgresql_where=sa.text('quote_id IS NOT NULL'))
    op.execute("COMMENT ON TABLE customer_treatment_prices IS '客户表面处理工序价格历史 - 保留全部历史记录，查询时取最近3次作为报价参考'")

    # ========================================
    # 5. 更新 parts 表添加 TWP 字段
    # ========================================
    print("Step 5: Adding TWP columns to parts table...")
    op.add_column('parts', sa.Column('thickness', sa.Numeric(8, 3), nullable=True))
    op.add_column('parts', sa.Column('width', sa.Numeric(8, 3), nullable=True))
    op.add_column('parts', sa.Column('pitch', sa.Numeric(8, 3), nullable=True))
    op.add_column('parts', sa.Column('material_id', sa.Integer(), nullable=True))
    op.add_column('parts', sa.Column('press_tonnage_id', sa.Integer(), nullable=True))
    op.add_column('parts', sa.Column('cavity_position', sa.Integer(), nullable=True))
    op.add_column('parts', sa.Column('weight_source', sa.String(20), nullable=True))

    # 添加外键
    op.create_foreign_key('fk_parts_material', 'parts', 'material_dict', ['material_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_parts_tonnage', 'parts', 'machine_tonnage_dict', ['material_id'], ['id'], ondelete='SET NULL')

    # 添加索引
    op.create_index('idx_parts_material', 'parts', ['material_id'],
                    postgresql_where=sa.text('material_id IS NOT NULL'))

    op.execute("COMMENT ON COLUMN parts.thickness IS 'T 厚度 (mm)，技术部门维护的最精确值'")
    op.execute("COMMENT ON COLUMN parts.width IS 'W 宽度 (mm)，技术部门维护的最精确值'")
    op.execute("COMMENT ON COLUMN parts.pitch IS 'P 步距 (mm)，单个零件所需材料长度'")
    op.execute("COMMENT ON COLUMN parts.cavity_position IS '穴位（一模多腔时标识左右件，1/2/3...）'")

    # ========================================
    # 6. 创建 price_accounts（价格台账）
    # ========================================
    print("Step 6: Creating price_accounts table...")
    op.create_table(
        'price_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('part_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),

        # 重量：估算值 vs 实测值
        sa.Column('estimated_net_weight_kg', sa.Numeric(10, 3), nullable=True),
        sa.Column('actual_net_weight_kg', sa.Numeric(10, 3), nullable=True),

        # 价格构成
        sa.Column('base_price', sa.Numeric(14, 4), nullable=True),
        sa.Column('current_price', sa.Numeric(14, 4), nullable=True),
        sa.Column('material_unit_price', sa.Numeric(14, 4), nullable=True),
        sa.Column('scrap_price', sa.Numeric(14, 4), nullable=True),

        # 年降参考
        sa.Column('reduction_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('price_year', sa.Integer(), nullable=True),

        # 成本偏离标记
        sa.Column('cost_deviation_flag', sa.Boolean(), server_default='false', nullable=False),

        sa.Column('price_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('part_id', 'customer_id', name='uq_price_part_customer'),
        sa.ForeignKeyConstraint(['part_id'], ['parts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE')
    )
    op.create_index('idx_price_part_customer', 'price_accounts', ['part_id', 'customer_id'],
                    postgresql_where=sa.text('is_deleted = false'))
    op.execute("COMMENT ON TABLE price_accounts IS '零件价格台账 - 某零件卖给某客户的完整价格档案'")
    op.execute("COMMENT ON COLUMN price_accounts.estimated_net_weight_kg IS '报价阶段估算重量'")
    op.execute("COMMENT ON COLUMN price_accounts.actual_net_weight_kg IS '首件检验实测重量'")
    op.execute("COMMENT ON COLUMN price_accounts.current_price IS '当前执行价（存储字段，手动调整）'")
    op.execute("COMMENT ON COLUMN price_accounts.cost_deviation_flag IS '实测重量偏离 >5% 时自动标记'")

    # ========================================
    # 7. 创建 price_adjustments（调价记录）
    # ========================================
    print("Step 7: Creating price_adjustments table...")
    op.create_table(
        'price_adjustments',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('price_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_price', sa.Numeric(14, 4), nullable=False),
        sa.Column('new_price', sa.Numeric(14, 4), nullable=False),
        sa.Column('adjustment_reason', sa.Text(), nullable=False),
        sa.Column('approval_status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('adjusted_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('adjusted_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['price_account_id'], ['price_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['adjusted_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_price_adj_account', 'price_adjustments', ['price_account_id'])
    op.create_index('idx_price_adj_status', 'price_adjustments', ['approval_status'])
    op.execute("COMMENT ON TABLE price_adjustments IS '手动调价记录（老板审批）'")

    print("✅ Migration completed successfully!")


def downgrade():
    """回滚迁移"""

    print("Rolling back migration...")

    # 7. 删除 price_adjustments
    op.drop_table('price_adjustments')

    # 6. 删除 price_accounts
    op.drop_table('price_accounts')

    # 5. 移除 parts 表的 TWP 字段
    op.drop_constraint('fk_parts_material', 'parts', type_='foreignkey')
    op.drop_constraint('fk_parts_tonnage', 'parts', type_='foreignkey')
    op.drop_index('idx_parts_material', 'parts')
    op.drop_column('parts', 'weight_source')
    op.drop_column('parts', 'cavity_position')
    op.drop_column('parts', 'press_tonnage_id')
    op.drop_column('parts', 'material_id')
    op.drop_column('parts', 'pitch')
    op.drop_column('parts', 'width')
    op.drop_column('parts', 'thickness')

    # 4. 删除 customer_treatment_prices
    op.drop_table('customer_treatment_prices')

    # 3. 删除 customer_material_prices
    op.drop_table('customer_material_prices')

    # 2. 删除 treatment_dict
    op.drop_table('treatment_dict')

    # 1. 恢复 customers -> tooling_customers
    op.drop_column('customers', 'is_active')
    op.drop_column('customers', 'sheet_key')
    op.drop_column('customers', 'address')
    op.drop_column('customers', 'contact_email')
    op.rename_table('customers', 'tooling_customers')

    print("✅ Rollback completed!")
