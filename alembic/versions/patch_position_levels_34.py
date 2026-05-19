"""
补充脚本：回填 level 3/4 的 position 值（Alembic 迁移）

已在 a1b2c3d4e5f6 迁移中部分回填，
本脚本修正 level=4 -> 业务经理，level=3 -> 生产组长

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'p001patch_levels34'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # level=4 -> 业务经理
    op.execute("""
        UPDATE users SET position = '业务经理'
        WHERE role_level = 4 AND (position IS NULL OR position = '员工');
    """)

    # level=3 -> 生产组长
    op.execute("""
        UPDATE users SET position = '生产组长'
        WHERE role_level = 3 AND (position IS NULL OR position = '员工');
    """)

    # 验证（仅打印，不影响迁移）
    result = conn.execute(sa.text("""
        SELECT id, username, role_level, dept, position
        FROM users ORDER BY id
    """)).fetchall()
    print("\n=== 补充后用户数据 ===")
    for r in result:
        print(f"id={r[0]} username={r[1]} level={r[2]} dept={r[3]} position={r[4]}")


def downgrade():
    # 不需要降级，position 值已被 a1b2c3d4e5f6 的默认值覆盖
    pass
