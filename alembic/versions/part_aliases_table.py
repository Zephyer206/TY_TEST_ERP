"""
零件别名表 part_aliases —— 数据库迁移

本迁移为系统新增"一物多码"能力。

关联 .cursorrules V3.0 §2.2 零件管理规范：
- 基准件 (Base Part)：全厂生产统一使用内部熟知名称（如：大陆 1403）
- 发货别名 (Alias)：发货单据自动根据客户 ID 检索映射表，
                      将内部名转换为客户件号（如：Z101 2102）

变更内容：
  新建表 part_aliases：
  - id                   : SERIAL PRIMARY KEY
  - internal_part_id     : INTEGER FK → parts(id)，NOT NULL，基准件号
  - customer_id          : INTEGER FK → tooling_customers(id)，NOT NULL，客户
  - alias_part_number    : VARCHAR(100)，NOT NULL，客户件号（唯一约束）
  - alias_name           : VARCHAR(200)，客户件号名称（可读描述）
  - is_active            : BOOLEAN DEFAULT TRUE，是否激活
  - created_at           : TIMESTAMP DEFAULT NOW()

  UNIQUE 约束：(internal_part_id, customer_id) — 每对基准件+客户仅一条别名

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'ghi789part_aliases'
down_revision = 'def456tech_pending_pool'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. 创建 part_aliases 表
    op.execute("""
        CREATE TABLE IF NOT EXISTS part_aliases (
            id                    SERIAL PRIMARY KEY,
            internal_part_id      INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
            customer_id           INTEGER NOT NULL REFERENCES tooling_customers(id) ON DELETE CASCADE,
            alias_part_number     VARCHAR(100) NOT NULL,
            alias_name            VARCHAR(200),
            is_active             BOOLEAN NOT NULL DEFAULT TRUE,
            created_at            TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_part_alias_part_customer UNIQUE (internal_part_id, customer_id),
            CONSTRAINT uq_alias_part_number UNIQUE (alias_part_number)
        );
    """)

    # 2. 索引：按基准件查询别名列表
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_part_alias_internal_part
        ON part_aliases(internal_part_id);
    """)

    # 3. 索引：按客户查询别名列表
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_part_alias_customer
        ON part_aliases(customer_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS part_aliases;")
