"""
qr003_fix_missing_columns
======================================================================
修复 material_batches 表缺失的列，这些列在 QR traceability Model 中声明，
但 qr002 迁移中遗漏。

幂等设计：所有操作均先检查是否已存在，安全重复执行。

依赖：qr002_material_traceability（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = "qr003_fix_missing_columns"
down_revision = "qr002_material_traceability"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 获取当前列
    cols = _get_columns(conn, "material_batches")

    # ── 尺寸字段 ──────────────────────────────────────────────────────
    if "thickness" not in cols:
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN thickness NUMERIC(12,4);
        """))
        print("[qr003] material_batches.thickness added")

    if "length" not in cols:
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN length NUMERIC(12,4);
        """))
        print("[qr003] material_batches.length added")

    # ── IQC 字段 ─────────────────────────────────────────────────────
    if "iqc_time" not in cols:
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN iqc_time TIMESTAMP;
        """))
        print("[qr003] material_batches.iqc_time added")

    if "iqc_by" not in cols:
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN iqc_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
        """))
        print("[qr003] material_batches.iqc_by added")

    if "iqc_notes" not in cols:
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN iqc_notes TEXT;
        """))
        print("[qr003] material_batches.iqc_notes added")

    # ── 批次状态 ─────────────────────────────────────────────────────
    if "status" not in cols:
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN status VARCHAR(20);
        """))
        print("[qr003] material_batches.status added")

    # ── 外键列 ───────────────────────────────────────────────────────
    # materials 表存在时才添加 material_id
    if "material_id" not in cols and _table_exists(conn, "materials"):
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL;
        """))
        print("[qr003] material_batches.material_id added")

    # suppliers 表存在时才添加 supplier_id
    if "supplier_id" not in cols and _table_exists(conn, "suppliers"):
        op.execute(sa.text("""
            ALTER TABLE material_batches ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL;
        """))
        print("[qr003] material_batches.supplier_id added")

    print("[qr003] ======== 迁移完成 ========")


def downgrade():
    conn = op.get_bind()
    cols = _get_columns(conn, "material_batches")

    if "supplier_id" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS supplier_id;"))
    if "material_id" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS material_id;"))
    if "status" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS status;"))
    if "iqc_notes" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS iqc_notes;"))
    if "iqc_by" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS iqc_by;"))
    if "iqc_time" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS iqc_time;"))
    if "length" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS length;"))
    if "thickness" in cols:
        op.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS thickness;"))

    print("[qr003] ======== 回滚完成 ========")


def _get_columns(conn, table: str) -> set:
    result = conn.execute(
        sa.text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table}';
        """)
    )
    return {row[0] for row in result.fetchall()}


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        sa.text(f"""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = '{table}';
        """)
    )
    return result.fetchone() is not None
