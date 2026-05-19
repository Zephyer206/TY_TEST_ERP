"""
阶段十二：库存体系 + 模具物理参数扩展
======================================================================

变更清单：
1. molds 表补充物理参数列：thickness_mm / width_mm / pitch_mm（T/W/P）
2. 新建 finished_inventory 表（成品库，按零件汇总）
3. 新建 remnant_inventory 表（尾数库，按零件汇总）
4. work_orders 补 mold_id 列（FK → molds.id，可空，向后兼容）

依赖：v11_industrial_pipeline_schema_align

执行：py -m alembic upgrade v12_inventory_die_architecture
回滚：py -m alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = "v12_inventory_die_architecture"
down_revision = "v11_industrial_pipeline_schema_align"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. molds 物理参数列（T/W/P）────────────────────────────────
    print("[v12-inventory] Step1: molds.thickness_mm / width_mm / pitch_mm")
    conn.execute(sa.text("""
        ALTER TABLE molds
        ADD COLUMN IF NOT EXISTS thickness_mm NUMERIC(8,3) DEFAULT NULL;
    """))
    conn.execute(sa.text("""
        ALTER TABLE molds
        ADD COLUMN IF NOT EXISTS width_mm NUMERIC(8,3) DEFAULT NULL;
    """))
    conn.execute(sa.text("""
        ALTER TABLE molds
        ADD COLUMN IF NOT EXISTS pitch_mm NUMERIC(8,3) DEFAULT NULL;
    """))

    # ── 2. finished_inventory 成品库 ────────────────────────────────
    print("[v12-inventory] Step2: CREATE finished_inventory")
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS finished_inventory (
            id          SERIAL PRIMARY KEY,
            part_id     INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
            quantity    INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            location    VARCHAR(100) NOT NULL DEFAULT '',
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_finished_inventory_part_location
                UNIQUE (part_id, location)
        );
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_finished_inventory_part_id
        ON finished_inventory(part_id);
    """))

    # ── 3. remnant_inventory 尾数库 ─────────────────────────────────
    print("[v12-inventory] Step3: CREATE remnant_inventory")
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS remnant_inventory (
            id          SERIAL PRIMARY KEY,
            part_id     INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
            quantity    INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_remnant_inventory_part UNIQUE (part_id)
        );
    """))

    # ── 4. work_orders.mold_id（关联模具，可空）─────────────────────
    print("[v12-inventory] Step4: work_orders.mold_id")
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS mold_id INTEGER REFERENCES molds(id);
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_work_orders_mold_id
        ON work_orders(mold_id)
        WHERE mold_id IS NOT NULL;
    """))

    print("[v12-inventory] ======== Migration complete ========")


def downgrade():
    conn = op.get_bind()

    print("[v12-inventory] Rollback: work_orders.mold_id")
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_work_orders_mold_id;"))
    conn.execute(sa.text("ALTER TABLE work_orders DROP COLUMN IF EXISTS mold_id;"))

    print("[v12-inventory] Rollback: remnant_inventory")
    conn.execute(sa.text("DROP TABLE IF EXISTS remnant_inventory;"))

    print("[v12-inventory] Rollback: finished_inventory")
    conn.execute(sa.text("DROP TABLE IF EXISTS finished_inventory;"))

    print("[v12-inventory] Rollback: molds T/W/P columns")
    conn.execute(sa.text("ALTER TABLE molds DROP COLUMN IF EXISTS pitch_mm;"))
    conn.execute(sa.text("ALTER TABLE molds DROP COLUMN IF EXISTS width_mm;"))
    conn.execute(sa.text("ALTER TABLE molds DROP COLUMN IF EXISTS thickness_mm;"))

    print("[v12-inventory] Rollback complete")
