"""
阶段十：打样与工业流水线扩展 — 数据库迁移
======================================================================

补全内容（本次任务需求）
--------
1. parts.mold_cost            — 模具费（默认值 0）
2. parts.mold_tonnage         — 要求吨位（默认值 0）
3. parts.thickness/width/press_stroke — T/W/P 物理基因参数
4. sample_inventory           — 打样虚拟库（NEW）

依赖：v9_prod_sessions_qa
执行：alembic upgrade v10_tech_qa_pipeline
回滚：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'v10_tech_qa_pipeline'
down_revision = 'v9_prod_sessions_qa'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. parts.mold_cost（模具费）─────────────────────────────────
    print('[v10-tech-qa] Step1: ADD parts.mold_cost')
    try:
        conn.execute(sa.text("""
            ALTER TABLE parts
            ADD COLUMN IF NOT EXISTS mold_cost NUMERIC(12,2) NOT NULL DEFAULT 0;
        """))
        print('[v10-tech-qa]   OK parts.mold_cost done')
    except Exception as e:
        print(f'[v10-tech-qa]   SKIP parts.mold_cost: {e}')

    # ── 2. parts.mold_tonnage（要求吨位）──────────────────────────
    print('[v10-tech-qa] Step2: ADD parts.mold_tonnage')
    try:
        conn.execute(sa.text("""
            ALTER TABLE parts
            ADD COLUMN IF NOT EXISTS mold_tonnage NUMERIC(10,2) NOT NULL DEFAULT 0;
        """))
        print('[v10-tech-qa]   OK parts.mold_tonnage done')
    except Exception as e:
        print(f'[v10-tech-qa]   SKIP parts.mold_tonnage: {e}')

    # ── 3. parts T/W/P（零件物理基因参数）──────────────────────────
    print('[v10-tech-qa] Step3: ADD parts.thickness/width/press_stroke')
    for col_name, col_type in [
        ("thickness",    "NUMERIC(10,4) NOT NULL DEFAULT 0"),
        ("width",        "NUMERIC(10,4) NOT NULL DEFAULT 0"),
        ("press_stroke", "NUMERIC(10,4) NOT NULL DEFAULT 0"),
    ]:
        try:
            conn.execute(sa.text(
                f"ALTER TABLE parts "
                f"ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
            ))
            print(f'[v10-tech-qa]   OK parts.{col_name} done')
        except Exception as e:
            print(f'[v10-tech-qa]   SKIP parts.{col_name}: {e}')

    # ── 4. sample_inventory（打样虚拟库）───────────────────────────
    print('[v10-tech-qa] Step4: CREATE sample_inventory')
    try:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS sample_inventory (
                id            SERIAL  PRIMARY KEY,
                part_id       INTEGER NOT NULL REFERENCES parts(id),
                sample_qty    INTEGER NOT NULL DEFAULT 0,
                created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """))
        print('[v10-tech-qa]   OK sample_inventory table done')
    except Exception as e:
        print(f'[v10-tech-qa]   ERR sample_inventory: {e}')

    print('[v10-tech-qa] NOTE: Prototype session_type and PROTOTYPING equipment status')
    print('[v10-tech-qa]       are code-level logic extensions — no schema change needed')
    print('[v10-tech-qa] ======== Migration complete ========')


def downgrade():
    conn = op.get_bind()
    print('[v10-tech-qa] Rollback: DROP sample_inventory')
    conn.execute(sa.text("DROP TABLE IF EXISTS sample_inventory;"))
    print('[v10-tech-qa] Rollback: DROP parts T/W/P')
    for col in ["press_stroke", "width", "thickness"]:
        conn.execute(sa.text(f"ALTER TABLE parts DROP COLUMN IF EXISTS {col};"))
    print('[v10-tech-qa] Rollback: DROP parts.mold_tonnage')
    conn.execute(sa.text("ALTER TABLE parts DROP COLUMN IF EXISTS mold_tonnage;"))
    print('[v10-tech-qa] Rollback: DROP parts.mold_cost')
    conn.execute(sa.text("ALTER TABLE parts DROP COLUMN IF EXISTS mold_cost;"))
    print('[v10-tech-qa] Rollback complete')
