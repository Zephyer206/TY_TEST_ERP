"""
阶段十一：工业流水线 schema 对齐（模具费归位 + 批次/会话/不良池补强）
======================================================================

与业务拍板一致（.cursorrules §2.5）：
1. quotes.mold_cost           — 模具费（元），默认 0；定点快照由应用层写入 price_snapshot 时并入
2. parts.mold_tonnage         — 改为 INTEGER DEFAULT 0（工艺吨位上限，0=不限制）
3. parts.mold_cost            — 从零件主档移除（数据迁移至 quotes 后 DROP）
4. parts.cavities             — 模具出数（物理），默认 1
5. material_batches           — 表已存在（v5 以 qr_uid 为主键）：补 surrogate id、强化 batch_code
6. production_sessions        — 补 material_batch_id（FK → material_batches.id），CHECK 约束与规范对齐
7. sample_inventory / defect_logs / work_orders — 幂等补列或补约束

依赖：v10_tech_qa_pipeline（车间链 head 之一；若仓库存在多 head，请按实际部署线 upgrade）

执行：py -m alembic upgrade v11_industrial_pipeline_schema_align
回滚：py -m alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = "v11_industrial_pipeline_schema_align"
down_revision = "v10_tech_qa_pipeline"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 0. 先扩 alembic_version.version_num（迁名超长，v11 专用）────
    print("[v11-pipeline] Step0: Widen alembic_version.version_num → VARCHAR(64)")
    conn.execute(sa.text("""
        ALTER TABLE alembic_version
        ALTER COLUMN version_num TYPE VARCHAR(64);
    """))

    # ── 1. quotes.mold_cost（报价维度模具费）────────────────────────
    print("[v11-pipeline] Step1: quotes.mold_cost")
    conn.execute(sa.text("""
        ALTER TABLE quotes
        ADD COLUMN IF NOT EXISTS mold_cost NUMERIC(12,2) NOT NULL DEFAULT 0.00;
    """))

    # 从 parts.mold_cost 回填（仅当该列仍存在时执行，避免解析期引用不存在的列）
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'parts' AND column_name = 'mold_cost'
            ) THEN
                EXECUTE $mig$
                    UPDATE quotes q
                    SET mold_cost = COALESCE(p.mold_cost, 0)::NUMERIC(12,2)
                    FROM parts p
                    WHERE q.part_id = p.id
                $mig$;
            END IF;
        END$$;
    """))
    print("[v11-pipeline]   quotes.mold_cost backfill from parts (if parts.mold_cost existed)")

    # ── 2. 移除 parts.mold_cost（越界金额字段）──────────────────────
    print("[v11-pipeline] Step2: DROP parts.mold_cost (if present)")
    conn.execute(sa.text("""
        ALTER TABLE parts DROP COLUMN IF EXISTS mold_cost;
    """))

    # ── 3. parts.mold_tonnage → INTEGER ────────────────────────────
    print("[v11-pipeline] Step3: parts.mold_tonnage as INTEGER")
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'parts'
                  AND column_name = 'mold_tonnage'
            ) THEN
                ALTER TABLE parts
                    ALTER COLUMN mold_tonnage TYPE INTEGER
                    USING ROUND(COALESCE(mold_tonnage, 0))::INTEGER;
                ALTER TABLE parts
                    ALTER COLUMN mold_tonnage SET DEFAULT 0;
            ELSE
                ALTER TABLE parts
                    ADD COLUMN mold_tonnage INTEGER NOT NULL DEFAULT 0;
            END IF;
        END$$;
    """))

    # ── 4. parts.cavities（模具出数，物理主档）──────────────────────
    print("[v11-pipeline] Step4: parts.cavities")
    conn.execute(sa.text("""
        ALTER TABLE parts
        ADD COLUMN IF NOT EXISTS cavities INTEGER NOT NULL DEFAULT 1;
    """))

    # ── 5. parts.part_status 扩展：打样发货后待批复核 ────────────────
    print("[v11-pipeline] Step5: parts.chk_parts_part_status + WAITING_FOR_APPROVAL")
    conn.execute(sa.text("""
        ALTER TABLE parts DROP CONSTRAINT IF EXISTS chk_parts_part_status;
    """))
    conn.execute(sa.text("""
        ALTER TABLE parts
        ADD CONSTRAINT chk_parts_part_status
        CHECK (part_status IN (
            'DRAFT',
            'SAMPLING',
            'MASS_PRODUCTION',
            'OBSOLETE',
            'WAITING_FOR_APPROVAL'
        ));
    """))

    # ── 6. material_batches：surrogate id + batch_code 规范 ─────────
    # 说明：v5 以 qr_uid 为主键；v9 可能已新增 batch_code(VARCHAR50)。此处补整数 id 供 FK 引用，并将 batch_code 扩至 100 且非空唯一。
    print("[v11-pipeline] Step6: material_batches id + batch_code")
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'material_batches'
                  AND column_name = 'id'
            ) THEN
                ALTER TABLE material_batches ADD COLUMN id SERIAL UNIQUE;
            END IF;
        END$$;
    """))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'material_batches'
                  AND column_name = 'batch_code'
            ) THEN
                ALTER TABLE material_batches ADD COLUMN batch_code VARCHAR(100);
            ELSE
                ALTER TABLE material_batches
                    ALTER COLUMN batch_code TYPE VARCHAR(100);
            END IF;
        END$$;
    """))
    conn.execute(sa.text("""
        UPDATE material_batches
        SET batch_code = qr_uid
        WHERE batch_code IS NULL OR TRIM(batch_code) = '';
    """))
    conn.execute(sa.text("""
        ALTER TABLE material_batches
        ALTER COLUMN batch_code SET NOT NULL;
    """))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_material_batches_batch_code'
            ) THEN
                ALTER TABLE material_batches
                ADD CONSTRAINT uq_material_batches_batch_code UNIQUE (batch_code);
            END IF;
        END$$;
    """))

    # ── 7. production_sessions：material_batch_id + CHECK ────────────
    print("[v11-pipeline] Step7: production_sessions material_batch_id + CHECK")
    conn.execute(sa.text("""
        ALTER TABLE production_sessions
        ADD COLUMN IF NOT EXISTS material_batch_id INTEGER
            REFERENCES material_batches(id);
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_production_sessions_material_batch_id
        ON production_sessions(material_batch_id)
        WHERE material_batch_id IS NOT NULL;
    """))

    conn.execute(sa.text("""
        UPDATE production_sessions SET session_type = 'Continuous'
        WHERE session_type IS NOT NULL AND session_type ILIKE 'continuous';
    """))
    conn.execute(sa.text("""
        UPDATE production_sessions SET session_type = 'Simple'
        WHERE session_type IS NOT NULL AND session_type ILIKE 'simple';
    """))
    conn.execute(sa.text("""
        UPDATE production_sessions SET session_type = 'Prototype'
        WHERE session_type IS NOT NULL AND session_type ILIKE 'prototype';
    """))
    conn.execute(sa.text("""
        UPDATE production_sessions SET status = 'RUNNING'
        WHERE status IS NOT NULL AND status ILIKE 'running';
    """))
    conn.execute(sa.text("""
        UPDATE production_sessions SET status = 'PENDING_REPORT'
        WHERE status IS NOT NULL AND status ILIKE 'pending_report';
    """))
    conn.execute(sa.text("""
        UPDATE production_sessions SET status = 'CLOSED'
        WHERE status IS NOT NULL AND status ILIKE 'closed';
    """))
    conn.execute(sa.text("""
        UPDATE production_sessions SET status = 'ABNORMAL_TERMINATED'
        WHERE status IS NOT NULL AND status ILIKE 'abnormal_terminated';
    """))

    conn.execute(sa.text("""
        ALTER TABLE production_sessions DROP CONSTRAINT IF EXISTS chk_production_sessions_session_type;
    """))
    conn.execute(sa.text("""
        ALTER TABLE production_sessions
        ADD CONSTRAINT chk_production_sessions_session_type
        CHECK (session_type IN ('Continuous', 'Simple', 'Prototype'));
    """))

    conn.execute(sa.text("""
        ALTER TABLE production_sessions DROP CONSTRAINT IF EXISTS chk_production_sessions_status;
    """))
    conn.execute(sa.text("""
        ALTER TABLE production_sessions
        ADD CONSTRAINT chk_production_sessions_status
        CHECK (status IN ('RUNNING', 'PENDING_REPORT', 'CLOSED', 'ABNORMAL_TERMINATED'));
    """))

    # ── 8. sample_inventory（打样虚拟库，与 v10 兼容）───────────────
    print("[v11-pipeline] Step8: sample_inventory IF NOT EXISTS")
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sample_inventory (
            id            SERIAL PRIMARY KEY,
            part_id       INTEGER NOT NULL REFERENCES parts(id),
            sample_qty    INTEGER NOT NULL DEFAULT 0,
            created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """))

    # ── 9. defect_logs.source ────────────────────────────────────────
    print("[v11-pipeline] Step9: defect_logs.source")
    conn.execute(sa.text("""
        ALTER TABLE defect_logs
        ADD COLUMN IF NOT EXISTS source VARCHAR(30) NOT NULL DEFAULT 'Manual';
    """))
    conn.execute(sa.text("""
        ALTER TABLE defect_logs DROP CONSTRAINT IF EXISTS chk_defect_logs_source;
    """))
    conn.execute(sa.text("""
        ALTER TABLE defect_logs
        ADD CONSTRAINT chk_defect_logs_source
        CHECK (source IN ('Manual', 'Auto_Deduction'));
    """))

    # ── 10. work_orders：wip_pcs（v9 可能已加）+ is_pkg_closed ─────
    print("[v11-pipeline] Step10: work_orders.wip_pcs + is_pkg_closed")
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS wip_pcs INTEGER NOT NULL DEFAULT 0;
    """))
    conn.execute(sa.text("""
        ALTER TABLE work_orders
        ADD COLUMN IF NOT EXISTS is_pkg_closed BOOLEAN NOT NULL DEFAULT FALSE;
    """))

    print("[v11-pipeline] ======== Migration complete ========")


def downgrade():
    conn = op.get_bind()

    # ── 0. 确保 alembic_version.version_num 够宽（Alembic 最后写入旧版本号）──
    print("[v11-pipeline] Rollback-Step0: Widen alembic_version.version_num → VARCHAR(64)")
    conn.execute(sa.text("""
        ALTER TABLE alembic_version
        ALTER COLUMN version_num TYPE VARCHAR(64);
    """))

    print("[v11-pipeline] Rollback: work_orders.is_pkg_closed")
    conn.execute(sa.text("ALTER TABLE work_orders DROP COLUMN IF EXISTS is_pkg_closed;"))

    print("[v11-pipeline] Rollback: defect_logs.source + chk")
    conn.execute(sa.text("ALTER TABLE defect_logs DROP CONSTRAINT IF EXISTS chk_defect_logs_source;"))
    conn.execute(sa.text("ALTER TABLE defect_logs DROP COLUMN IF EXISTS source;"))

    print("[v11-pipeline] Rollback: sample_inventory — 保留表（由 v10 创建，不在此回滚 DROP）")

    print("[v11-pipeline] Rollback: production_sessions CHECKs + material_batch_id")
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_production_sessions_material_batch_id;"))
    conn.execute(sa.text("ALTER TABLE production_sessions DROP CONSTRAINT IF EXISTS chk_production_sessions_status;"))
    conn.execute(sa.text("ALTER TABLE production_sessions DROP CONSTRAINT IF EXISTS chk_production_sessions_session_type;"))
    conn.execute(sa.text("ALTER TABLE production_sessions DROP COLUMN IF EXISTS material_batch_id;"))

    print("[v11-pipeline] Rollback: material_batches surrogate id + batch_code UNIQUE（保留 batch_code 列以兼容 v9）")
    conn.execute(sa.text("ALTER TABLE material_batches DROP CONSTRAINT IF EXISTS uq_material_batches_batch_code;"))
    conn.execute(sa.text("ALTER TABLE material_batches DROP COLUMN IF EXISTS id;"))

    print("[v11-pipeline] Rollback: parts.chk / cavities → cavity_count 回填 / mold_tonnage type / mold_cost restore")
    conn.execute(sa.text("ALTER TABLE parts DROP CONSTRAINT IF EXISTS chk_parts_part_status;"))
    conn.execute(sa.text("""
        ALTER TABLE parts
        ADD CONSTRAINT chk_parts_part_status
        CHECK (part_status IN ('DRAFT', 'SAMPLING', 'MASS_PRODUCTION', 'OBSOLETE'));
    """))

    # ── 关键：cavities 数据安全回填 cavity_count，再删 cavities ──
    # 必须处理两种历史状态：
    #   A. cavity_count 列仍存在（中间迁移未触及）：直接 UPDATE 回填
    #   B. cavity_count 列已被其他迁移 DROP：先 ADD COLUMN，再回填
    conn.execute(sa.text("""
        DO $$
        BEGIN
            -- 情况 A：cavity_count 仍存在 → 直接回填
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'parts'
                  AND column_name  = 'cavity_count'
            ) THEN
                UPDATE parts
                SET cavity_count = COALESCE(cavities, 1)
                WHERE cavity_count IS DISTINCT FROM COALESCE(cavities, 1);
                RAISE NOTICE '[v11-rollback] cavity_count ← cavities (直接回填)';

            -- 情况 B：cavity_count 已被其他迁移 DROP → 重建列并回填
            ELSE
                ALTER TABLE parts ADD COLUMN cavity_count INTEGER NOT NULL DEFAULT 1;
                UPDATE parts
                SET cavity_count = COALESCE(cavities, 1);
                RAISE NOTICE '[v11-rollback] cavity_count 列已重建并回填 cavities 数据';
            END IF;
        END$$;
    """))

    # ── 正式删除 cavities 列（数据已安全转移）────────────────────
    conn.execute(sa.text("ALTER TABLE parts DROP COLUMN IF EXISTS cavities;"))
    print("[v11-rollback] cavities 列已删除（数据已回填 cavity_count）")
    conn.execute(sa.text("""
        ALTER TABLE parts
        ALTER COLUMN mold_tonnage TYPE NUMERIC(10,2)
        USING COALESCE(mold_tonnage, 0)::NUMERIC(10,2);
    """))
    conn.execute(sa.text("ALTER TABLE parts ALTER COLUMN mold_tonnage SET DEFAULT 0;"))

    conn.execute(sa.text("""
        ALTER TABLE parts
        ADD COLUMN IF NOT EXISTS mold_cost NUMERIC(12,2) NOT NULL DEFAULT 0;
    """))
    conn.execute(sa.text("""
        UPDATE parts p
        SET mold_cost = sub.mc
        FROM (
            SELECT DISTINCT ON (part_id) part_id, mold_cost
            FROM quotes
            ORDER BY part_id, id DESC
        ) sub
        WHERE p.id = sub.part_id;
    """))

    print("[v11-pipeline] Rollback: quotes.mold_cost")
    conn.execute(sa.text("ALTER TABLE quotes DROP COLUMN IF EXISTS mold_cost;"))

    print("[v11-pipeline] Rollback complete")
