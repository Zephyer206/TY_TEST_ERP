"""允许 part_customer_aliases.customer_part_no 为 NULL

Revision ID: 20260722_null_cust_part_no
Revises: v7_delivery_qa_switch
Create Date: 2026-07-22

变更说明：
---------
根据唯一权威数据模型 specs/001-erp-system-architecture/data-model.md，
part_customer_aliases.customer_part_no 应允许 NULL，因为 Excel 导入时
可能存在只有模具号和内部件名、但没有客户件号的记录。

修改内容：
- 将 part_customer_aliases.customer_part_no 从 NOT NULL 改为 NULL
- 保持唯一约束 UNIQUE(customer_id, customer_part_no, revision)
- NULL 值在 UNIQUE 约束中不参与比较（PostgreSQL 标准行为）

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260722_null_cust_part_no'
down_revision = 'v9_prod_sessions_qa'
branch_labels = None
depends_on = None


def upgrade():
    """将 customer_part_no 改为可空"""
    print('[20260722] Step 1: Modify part_customer_aliases.customer_part_no to allow NULL')

    # PostgreSQL: ALTER COLUMN ... DROP NOT NULL
    op.alter_column(
        'part_customer_aliases',
        'customer_part_no',
        existing_type=sa.String(length=150),
        nullable=True,
        existing_nullable=False
    )

    print('[20260722] SUCCESS: customer_part_no now allows NULL values')
    print('[20260722] Note: UNIQUE(customer_id, customer_part_no, revision) constraint unchanged')
    print('[20260722]       NULL values do not participate in uniqueness check (PostgreSQL standard)')


def downgrade():
    """回滚：将 customer_part_no 恢复为 NOT NULL（需先清理 NULL 数据）"""
    print('[20260722] Downgrade step 1: Check for NULL values')

    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM part_customer_aliases WHERE customer_part_no IS NULL"
    ))
    null_count = result.scalar()

    if null_count > 0:
        print(f'[20260722] WARNING: Found {null_count} records with NULL customer_part_no')
        print('[20260722] Must handle these records before downgrade to avoid NOT NULL constraint violation')
        raise Exception(
            f'Cannot downgrade: {null_count} records with NULL customer_part_no exist. '
            'Update or delete these records before executing downgrade.'
        )

    print('[20260722] Step 2: Restore customer_part_no NOT NULL constraint')
    op.alter_column(
        'part_customer_aliases',
        'customer_part_no',
        existing_type=sa.String(length=150),
        nullable=False,
        existing_nullable=True
    )

    print('[20260722] Downgrade complete')
