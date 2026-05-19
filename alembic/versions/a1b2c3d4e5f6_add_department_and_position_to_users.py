"""add_department_and_position_to_users

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-30 20:30:00.000000

[部门维度] users 表部门化重构：新增 position 字段，
存量 dept 值中文->英文标准化，存量数据平移 position 值。

存量 dept 映射规则：
    老板  -> admin
    业务  -> sales
    生产  -> prod
    仓库  -> whse

存量 position 推算规则（基于 role_level）：
    role_level = 9 -> dept 部门负责人
    role_level = 5 -> 组长
    role_level = 1 -> 员工
    role_level = 2 -> 开发工程师（特殊，dept 保持 prod 或独立）
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Step 1: 新增 position 列 ──────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("position", sa.String(50), nullable=True, server_default=None)
    )
    # 设置注释（PostgreSQL 特有）
    op.execute("COMMENT ON COLUMN users.position IS '职务/岗位，如：部门负责人、组长、员工、开发工程师';")

    # ── Step 2: dept 存量中文值 -> 英文标准缩写 ────────────────────────────
    # 存量数据 dept 值：老板、业务、生产、仓库
    dept_map = {
        "老板":  "admin",
        "业务":  "sales",
        "生产":  "prod",
        "仓库":  "whse",
    }
    for old_val, new_val in dept_map.items():
        op.execute(
            f"UPDATE users SET dept = '{new_val}' WHERE dept = '{old_val}';"
        )

    # ── Step 3: 回填存量 position 值 ──────────────────────────────────────
    # 规则：按 role_level 推算职务
    # Lv.9  -> 部门负责人（各 dept 的最高决策者）
    # Lv.5  -> 组长
    # Lv.1  -> 员工
    # Lv.2  -> 开发工程师（role_level=2 是开发岗）
    position_map = [
        (9, None, "部门负责人"),   # Lv.9：无论哪个 dept，都是部门负责人
        (5, None, "组长"),
        (1, None, "员工"),
        (2, None, "开发工程师"),   # Lv.2 特殊：开发工程师
    ]

    for rl, _dept, pos in position_map:
        if rl == 2:
            # Lv.2 开发岗，dept 归为 admin，position 为开发工程师
            op.execute(
                f"UPDATE users SET dept = 'admin', position = '开发工程师' "
                f"WHERE role_level = {rl};"
            )
        else:
            op.execute(
                f"UPDATE users SET position = '{pos}' "
                f"WHERE role_level = {rl} AND position IS NULL;"
            )

    # ── Step 4: 为 NULL 的 position 补默认值 ────────────────────────────────
    op.execute(
        "UPDATE users SET position = '员工' WHERE position IS NULL;"
    )

    # ── Step 5: 给新用户（未来 INSERT）设置 DEFAULT ────────────────────────
    # PostgreSQL: 给 dept 加 NOT NULL 约束（已有默认值）
    op.alter_column("users", "dept", existing_type=sa.String(), nullable=False)
    op.execute(
        "ALTER TABLE users ALTER COLUMN dept SET DEFAULT 'prod';"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN position SET DEFAULT '员工';"
    )


def downgrade() -> None:
    # 回滚：还原 dept 中文值（仅在数据仍为英文缩写时安全执行）
    dept_restore = {
        "admin": "老板",
        "sales": "业务",
        "prod":  "生产",
        "whse":  "仓库",
        "qc":    "品质",
    }
    for new_val, old_val in dept_restore.items():
        op.execute(
            f"UPDATE users SET dept = '{old_val}' WHERE dept = '{new_val}';"
        )

    # 删除 position 列（不还原 position 值，因为存量数据已覆盖）
    op.drop_column("users", "position")
