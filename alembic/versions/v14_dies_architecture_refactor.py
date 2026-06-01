"""
阶段十四：V7.0 三表架构重构
======================================================================

变更清单：
1. molds 表改名为 dies（生产方案主档）
2. parts 表删除 T/W/P/cavities/mold_tonnage 字段（物理参数归 dies）
3. quotes 表新增 die_id 外键（关联 dies）
4. quotes.approval_status CHECK 约束扩展，新增技术审核三态：
   WAITING_FOR_TECH / TECH_APPROVED / TECH_REJECTED
5. mold_parts 表改名为 die_parts（关联表同步）
6. 所有引用 molds 的外键约束同步更新

依赖：v13_allow_duplicate_part_numbers

执行：py -m alembic upgrade v14_dies_architecture_refactor
回滚：py -m alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = "v14_dies_architecture_refactor"
down_revision = "v13_allow_duplicate_part_numbers"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. molds 改名为 dies ─────────────────────────────────────────
    print("[v14] Step1: ALTER TABLE molds RENAME TO dies")
    conn.execute(sa.text("ALTER TABLE molds RENAME TO dies;"))

    # 同步序列名（PostgreSQL SERIAL 序列）
    conn.execute(sa.text(
        "ALTER SEQUENCE IF EXISTS molds_id_seq RENAME TO dies_id_seq;"
    ))

    # ── 2. mold_parts 改名为 die_parts ──────────────────────────────
    print("[v14] Step2: ALTER TABLE mold_parts RENAME TO die_parts")
    conn.execute(sa.text("ALTER TABLE mold_parts RENAME TO die_parts;"))
    conn.execute(sa.text(
        "ALTER SEQUENCE IF EXISTS mold_parts_id_seq RENAME TO die_parts_id_seq;"
    ))

    # die_parts 中的列名 mold_id 改为 die_id
    conn.execute(sa.text(
        "ALTER TABLE die_parts RENAME COLUMN mold_id TO die_id;"
    ))

    # ── 3. mold_offline_records 无 mold_id 外键列（用 mold_number 字符串），跳过 ──
    print("[v14] Step3: mold_offline_records 无 mold_id 列，跳过")

    # ── 4. work_orders.mold_id 改名 ──────────────────────────────────
    print("[v14] Step4: work_orders.mold_id → die_id")
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        RENAME COLUMN mold_id TO die_id;
    """))

    # ── 5. parts 表删除 T/W/P/cavities/mold_tonnage ──────────────────
    print("[v14] Step5: DROP T/W/P/cavities/mold_tonnage from parts")
    for col in ("thickness", "width", "press_stroke", "cavities", "mold_tonnage"):
        conn.execute(sa.text(
            f"ALTER TABLE parts DROP COLUMN IF EXISTS {col};"
        ))

    # ── 6. quotes 表新增 die_id 外键 ─────────────────────────────────
    print("[v14] Step6: quotes ADD COLUMN die_id FK → dies")
    conn.execute(sa.text("""
        ALTER TABLE quotes
        ADD COLUMN IF NOT EXISTS die_id INTEGER REFERENCES dies(id) ON DELETE SET NULL;
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_quotes_die_id ON quotes(die_id)
        WHERE die_id IS NOT NULL;
    """))

    # ── 7. quotes.approval_status CHECK 约束扩展 ─────────────────────
    # 先删旧约束（名称可能不同，用 IF EXISTS 保护）
    print("[v14] Step7: quotes approval_status CHECK 扩展技术审核三态")
    conn.execute(sa.text("""
        ALTER TABLE quotes
        DROP CONSTRAINT IF EXISTS quotes_approval_status_check;
    """))
    conn.execute(sa.text("""
        ALTER TABLE quotes
        DROP CONSTRAINT IF EXISTS chk_quotes_approval_status;
    """))
    conn.execute(sa.text("""
        ALTER TABLE quotes
        ADD CONSTRAINT chk_quotes_approval_status
        CHECK (approval_status IN (
            'WAITING_FOR_TECH',
            'TECH_APPROVED',
            'TECH_REJECTED',
            'DRAFT',
            'PENDING_BOSS',
            'APPROVED',
            'REJECTED'
        ));
    """))

    # ── 8. dies 表补充 die_type 字段（区分模具类型）────────────────
    print("[v14] Step8: dies ADD COLUMN die_type")
    conn.execute(sa.text("""
        ALTER TABLE dies
        ADD COLUMN IF NOT EXISTS die_type VARCHAR(30) NOT NULL DEFAULT 'progressive';
    """))
    # progressive=连续模, compound=复合模, single=单工序模

    # ── 9. 索引同步 ──────────────────────────────────────────────────
    print("[v14] Step9: 重建索引")
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_die_parts_die_id ON die_parts(die_id);
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_die_parts_part_id ON die_parts(part_id);
    """))

    print("[v14] ======== Migration complete ========")


def downgrade():
    conn = op.get_bind()

    print("[v14] Rollback: 删除新增索引和约束")
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_die_parts_die_id;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_die_parts_part_id;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_quotes_die_id;"))

    conn.execute(sa.text("""
        ALTER TABLE quotes DROP CONSTRAINT IF EXISTS chk_quotes_approval_status;
    """))
    conn.execute(sa.text("""
        ALTER TABLE quotes DROP COLUMN IF EXISTS die_id;
    """))
    conn.execute(sa.text("""
        ALTER TABLE dies DROP COLUMN IF EXISTS die_type;
    """))

    print("[v14] Rollback: 恢复 parts T/W/P 字段")
    conn.execute(sa.text("ALTER TABLE parts ADD COLUMN IF NOT EXISTS thickness NUMERIC(10,4) NOT NULL DEFAULT 0;"))
    conn.execute(sa.text("ALTER TABLE parts ADD COLUMN IF NOT EXISTS width NUMERIC(10,4) NOT NULL DEFAULT 0;"))
    conn.execute(sa.text("ALTER TABLE parts ADD COLUMN IF NOT EXISTS press_stroke NUMERIC(10,4) NOT NULL DEFAULT 0;"))
    conn.execute(sa.text("ALTER TABLE parts ADD COLUMN IF NOT EXISTS cavities INTEGER NOT NULL DEFAULT 1;"))
    conn.execute(sa.text("ALTER TABLE parts ADD COLUMN IF NOT EXISTS mold_tonnage INTEGER NOT NULL DEFAULT 0;"))

    print("[v14] Rollback: work_orders.die_id → mold_id")
    conn.execute(sa.text("ALTER TABLE work_orders RENAME COLUMN die_id TO mold_id;"))

    print("[v14] Rollback: mold_offline_records 无 die_id 列，跳过")

    print("[v14] Rollback: die_parts.die_id → mold_id")
    conn.execute(sa.text("ALTER TABLE die_parts RENAME COLUMN die_id TO mold_id;"))

    print("[v14] Rollback: die_parts → mold_parts")
    conn.execute(sa.text("ALTER TABLE die_parts RENAME TO mold_parts;"))
    conn.execute(sa.text("ALTER SEQUENCE IF EXISTS die_parts_id_seq RENAME TO mold_parts_id_seq;"))

    print("[v14] Rollback: dies → molds")
    conn.execute(sa.text("ALTER TABLE dies RENAME TO molds;"))
    conn.execute(sa.text("ALTER SEQUENCE IF EXISTS dies_id_seq RENAME TO molds_id_seq;"))

    print("[v14] Rollback complete")
