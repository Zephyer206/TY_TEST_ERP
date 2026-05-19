"""
阶段二补充：molds 表追加 mold_set_count / press_tonnage 列
======================================================================

已知问题：v4_sample_molds_bom 已创建 molds 表但缺少 mold_set_count / press_tonnage。
本迁移通过 ALTER TABLE 追加列，幂等（IF NOT EXISTS 等效逻辑）。

依赖：v4_sample_molds_bom（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v4b_sample_molds_cols'
down_revision = 'v4_sample_molds_bom'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    print('[v4b-molds-cols] 添加 mold_set_count 列')
    _add_col_if_missing(conn, 'molds', 'mold_set_count',
        'INTEGER DEFAULT 1',
        '物理模具套数 / 工序数')

    print('[v4b-molds-cols] 添加 press_tonnage 列')
    _add_col_if_missing(conn, 'molds', 'press_tonnage',
        'VARCHAR(50)',
        '参考冲床吨位')

    print('[v4b-molds-cols] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v4b-molds-cols] 回滚：删除追加列')
    conn.execute(sa.text("ALTER TABLE molds DROP COLUMN IF EXISTS mold_set_count;"))
    conn.execute(sa.text("ALTER TABLE molds DROP COLUMN IF EXISTS press_tonnage;"))
    print('[v4b-molds-cols] 回滚完成')


def _add_col_if_missing(conn, table: str, col_name: str,
                        col_type: str, comment: str = None):
    """安全追加列（幂等）：仅在列不存在时添加。"""
    result = conn.execute(sa.text(f"""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = '{table}' AND column_name = '{col_name}';
    """)).fetchone()
    if not result:
        conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};"))
        if comment:
            escaped = comment.replace("'", "''")
            conn.execute(sa.text(
                f"COMMENT ON COLUMN {table}.{col_name} IS '{escaped}'"
            ))
        print(f'  [ADD] {table}.{col_name} ({col_type})')
    else:
        print(f'  [SKIP] {table}.{col_name} 已存在')
