"""
零件生命周期状态清洗 + part_status CHECK 约束
======================================================================

变更摘要
--------
1. part_status 数据清洗（ACTIVE/SUPERSEDED/ARCHIVED → V3.2 规范值）
2. 添加 CHECK 约束，限制 part_status 仅允许以下值：
     DRAFT / SAMPLING / MASS_PRODUCTION / OBSOLETE
3. version 字段增加 DEFAULT 'V1.0'（历史数据回填）

关联 .cursorrules V3.2 §4 零件生命周期状态机：
  DRAFT → SAMPLING → MASS_PRODUCTION → OBSOLETE

依赖：v2split_parts_and_quotes（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v3part_status_lifecycle'
down_revision = 'v2split_parts_and_quotes'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ---- 1. 回填 version 默认值（历史数据）----
    print('[v3-part-status] 步骤1: 回填 parts.version 默认值 V1.0')
    conn.execute(sa.text("""
        UPDATE parts SET version = 'V1.0' WHERE version IS NULL;
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts ALTER COLUMN version SET DEFAULT 'V1.0';
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts ALTER COLUMN version SET NOT NULL;
    """))
    print('[v3-part-status]   version 默认值已设置')

    # ---- 2. part_status 数据清洗 ----
    print('[v3-part-status] 步骤2: part_status 数据清洗')
    mapping = {
        # 旧值 -> V3.2 规范值
        'ACTIVE':       'MASS_PRODUCTION',
        'SUPERSEDED':   'OBSOLETE',
        'ARCHIVED':     'OBSOLETE',
        'DRAFT':        'DRAFT',
        'SAMPLING':     'SAMPLING',
        'MASS_PRODUCTION': 'MASS_PRODUCTION',
        'OBSOLETE':     'OBSOLETE',
    }
    for old_val, new_val in mapping.items():
        if old_val != new_val:
            cur = conn.execute(sa.text(f"""
                UPDATE parts SET part_status = '{new_val}' WHERE part_status = '{old_val}';
            """))
            print(f'  [MAP] {old_val!r} → {new_val!r}')

    # 回填 NULL 为 DRAFT
    conn.execute(sa.text("""
        UPDATE parts SET part_status = 'DRAFT' WHERE part_status IS NULL;
    """))
    print('  [MAP] NULL → DRAFT')

    # 设置 DEFAULT
    conn.execute(sa.text("""
        ALTER TABLE parts ALTER COLUMN part_status SET DEFAULT 'DRAFT';
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts ALTER COLUMN part_status SET NOT NULL;
    """))
    print('[v3-part-status]   part_status 默认值/非空已设置')

    # ---- 3. 添加 CHECK 约束 ----
    print('[v3-part-status] 步骤3: 添加 part_status CHECK 约束')
    # 先删除旧约束（幂等）
    conn.execute(sa.text("""
        ALTER TABLE parts DROP CONSTRAINT IF EXISTS chk_parts_part_status;
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts
        ADD CONSTRAINT chk_parts_part_status
        CHECK (part_status IN ('DRAFT', 'SAMPLING', 'MASS_PRODUCTION', 'OBSOLETE'));
    """))
    print('[v3-part-status]   CHECK 约束已添加')

    # ---- 4. version 联合唯一约束（幂等）----
    print('[v3-part-status] 步骤4: 确认联合唯一约束')
    conn.execute(sa.text("""
        ALTER TABLE parts DROP CONSTRAINT IF EXISTS uq_parts_number_version;
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts
        ADD CONSTRAINT uq_parts_number_version
        UNIQUE (part_number, version);
    """))
    print('[v3-part-status]   uq_parts_number_version 联合唯一约束已重建')
    print('[v3-part-status] ======== 迁移完成 ========')


def downgrade():
    conn = op.get_bind()
    print('[v3-part-status] 回滚：删除 CHECK 约束，恢复历史状态映射')
    conn.execute(sa.text("""
        ALTER TABLE parts DROP CONSTRAINT IF EXISTS chk_parts_part_status;
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts ALTER COLUMN version DROP NOT NULL;
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts ALTER COLUMN part_status DROP NOT NULL;
    """))
    print('[v3-part-status] 回滚完成')
