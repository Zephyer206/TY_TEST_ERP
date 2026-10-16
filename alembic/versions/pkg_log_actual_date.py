"""
pkg_packaging_logs / pkg_shipping_logs 表新增 actual_date 字段 —— 数据库迁移

关联 .cursorrules V3.0 §2.4 数据对账与日期追溯（Back-dating）规范：
- 双时间戳：所有日志必须区分 created_at（系统录入时）和 actual_date（业务发生日）
- 日期归位：pkg 全检数据使用 actual_date 补录，以业务实际发生日期为准

变更内容（pkg_packaging_logs）：
  新增列：
  - actual_date  DATE  NOT NULL DEFAULT CURRENT_DATE
    约束：CHECK (actual_date <= CURRENT_DATE)，禁止填入未来日期

  旧数据迁移：actual_date 默认等于 CAST(created_at AS DATE)
  即历史记录的实际日期等于系统记录时的日期，保证数据一致性

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'jkl012pkg_actual_date'
down_revision = 'ghi789part_aliases'
branch_labels = None
depends_on = None


def upgrade():
    # 1. pkg_packaging_logs 新增 actual_date 字段
    op.execute(
        "ALTER TABLE pkg_packaging_logs "
        "ADD COLUMN IF NOT EXISTS actual_date DATE NOT NULL DEFAULT CURRENT_DATE"
    )
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_pkg_packaging_actual_date'
            ) THEN
                ALTER TABLE pkg_packaging_logs
                ADD CONSTRAINT chk_pkg_packaging_actual_date
                CHECK (actual_date <= CURRENT_DATE);
            END IF;
        END $$;
    """)
    op.execute("""
        UPDATE pkg_packaging_logs
        SET actual_date = CAST(created_at AS DATE)
        WHERE actual_date IS NULL;
    """)

    # 2. pkg_shipping_logs 新增 actual_date 字段（同一迁移中处理，保持一致性）
    op.execute(
        "ALTER TABLE pkg_shipping_logs "
        "ADD COLUMN IF NOT EXISTS actual_date DATE NOT NULL DEFAULT CURRENT_DATE"
    )
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_pkg_shipping_actual_date'
            ) THEN
                ALTER TABLE pkg_shipping_logs
                ADD CONSTRAINT chk_pkg_shipping_actual_date
                CHECK (actual_date <= CURRENT_DATE);
            END IF;
        END $$;
    """)
    op.execute("""
        UPDATE pkg_shipping_logs
        SET actual_date = CAST(created_at AS DATE)
        WHERE actual_date IS NULL;
    """)


def downgrade():
    op.drop_constraint('chk_pkg_packaging_actual_date', 'pkg_packaging_logs', type_='check')
    op.drop_column('pkg_packaging_logs', 'actual_date')
    op.drop_constraint('chk_pkg_shipping_actual_date', 'pkg_shipping_logs', type_='check')
    op.drop_column('pkg_shipping_logs', 'actual_date')
