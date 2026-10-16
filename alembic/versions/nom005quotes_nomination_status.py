"""
Quotes 定点状态重构 —— 数据库迁移
======================================================================
变更：quotes 表新增定点状态体系字段

┌─────────────────────────────────────────────────────────────────────┐
│  quotes 新增字段                                                       │
│  ┌──────────────────┬───────────────────────────────────────────┐   │
│  │ nomination_status │ VARCHAR(20) 定点状态：                   │   │
│  │                   │   unfixed=未定点                          │   │
│  │                   │   fixed=已定点确认                        │   │
│  │                   │   revoked=已撤销定点                      │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ final_price      │ NUMERIC(12,4) 定点价格（定点时锁定）         │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ revoked_at       │ TIMESTAMP 撤销定点时间                     │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ revoked_by       │ INTEGER 撤销人 FK → users(id)             │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ revoke_reason    │ TEXT 撤销原因                              │   │
│  └──────────────────┴───────────────────────────────────────────┘   │
│                                                                      │
│  执行：py -m alembic upgrade head                                     │
│  回滚：py -m alembic downgrade -1                                     │
└─────────────────────────────────────────────────────────────────────┘
"""

from alembic import op
import sqlalchemy as sa

revision = 'nom005quotes_nomination_status'
down_revision = 'nom004quotes_parts_mold_split'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. nomination_status ─────────────────────────────────────────
    _add_col_if_missing(
        'quotes', 'nomination_status', sa.String(20),
        "定点状态：unfixed=未定点，fixed=已定点，revoked=已撤销"
    )

    # ── 2. final_price ───────────────────────────────────────────────
    _add_col_if_missing(
        'quotes', 'final_price', sa.Numeric(12, 4),
        "定点价格（定点确认时锁定，手动输入）"
    )

    # ── 3. revoked_at ───────────────────────────────────────────────
    _add_col_if_missing(
        'quotes', 'revoked_at', sa.TIMESTAMP(),
        "撤销定点时间"
    )

    # ── 4. revoked_by ───────────────────────────────────────────────
    _add_col_if_missing(
        'quotes', 'revoked_by', sa.Integer(),
        "撤销人 FK → users(id)"
    )

    # ── 5. revoke_reason ────────────────────────────────────────────
    _add_col_if_missing(
        'quotes', 'revoke_reason', sa.Text(),
        "撤销定点原因"
    )

    # ── 6. 索引 ─────────────────────────────────────────────────────
    _add_index_if_missing(
        'quotes', 'idx_quotes_nomination_status', 'nomination_status'
    )

    print('[nom005] ======== Migration complete ========')


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_quotes_nomination_status")
    for col in ('nomination_status', 'final_price', 'revoked_at', 'revoked_by', 'revoke_reason'):
        op.execute(f'ALTER TABLE quotes DROP COLUMN IF EXISTS {col}')
        print(f'[nom005] quotes.{col} dropped')
    print('[nom005] Downgrade complete')


def _add_col_if_missing(table, col_name, col_type, comment=None):
    op.execute(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {str(col_type).upper()}"
    )
    if comment:
        op.execute(f"COMMENT ON COLUMN {table}.{col_name} IS '{comment}'")


def _add_index_if_missing(table, idx_name, col_name):
    op.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({col_name})")
    print(f'[nom005] index {idx_name} on {table}({col_name}) ensured')
