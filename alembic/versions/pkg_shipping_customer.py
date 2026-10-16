"""
pkg_shipping_logs 表新增 customer_id 字段 —— 数据库迁移

关联 .cursorrules V3.0 §2.2 零件管理规范（发货别名）：
- 发货记录需要关联客户，以便自动解析发货件号
- 业务需求：发货单据根据 customer_id 检索 part_aliases 映射表，
            将内部件号转换为客户件号

变更内容（pkg_shipping_logs）：
  新增列：
  - customer_id  INTEGER  FK → tooling_customers(id)，NULLABLE
    理由：历史发货记录在补录时可能无法确定客户，设为 NULLABLE，
          业务层在提交时可强制要求必填（可编辑页面需注意）

  附加说明：
  - customer_id 与 actual_date 已在 pkg_log_actual_date 迁移中一并添加
  - 本迁移仅处理 customer_id

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'mno345pkg_shipping_customer'
down_revision = 'jkl012pkg_actual_date'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE pkg_shipping_logs "
        "ADD COLUMN IF NOT EXISTS customer_id INTEGER"
    )
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_pkg_shipping_customer_id'
            ) THEN
                ALTER TABLE pkg_shipping_logs
                ADD CONSTRAINT fk_pkg_shipping_customer_id
                FOREIGN KEY (customer_id) REFERENCES tooling_customers(id);
            END IF;
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_pkg_shipping_customer
        ON pkg_shipping_logs(customer_id);
    """)


def downgrade():
    op.drop_constraint('fk_pkg_shipping_customer_id', 'pkg_shipping_logs', type_='foreignkey')
    op.drop_column('pkg_shipping_logs', 'customer_id')
