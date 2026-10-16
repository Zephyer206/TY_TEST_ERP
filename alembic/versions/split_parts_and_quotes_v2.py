"""
parts 表拆分：零件主档 (parts) + 报价单台账 (quotes)
======================================================================

变更摘要
--------
1. 创建 quotes 表（报价单台账）
   - 继承原 parts 表所有报价/核价/审批字段
   - 新增 quote_serial（报价流水号）、annual_usage（年用量）、parent_quote_id（驳回重开链路）
   - approval_status 流转: DRAFT → PENDING_BOSS → APPROVED / REJECTED
2. parts 表追加 version / part_status 字段，建立 (part_number, version) 联合唯一约束
3. 数据平移：将已有零件的报价数据一次性迁移为初始报价单
4. parts 表瘦身：删除已转移至 quotes 的业务字段

关联 .cursorrules V3.1 §2.1 双轨报价 §2.2 主要件号制

依赖：nom003nomination_price_snapshot（head）
执行：alembic upgrade head
回滚：alembic downgrade -1
"""

from alembic import op
from alembic import context
import sqlalchemy as sa

revision = 'v2split_parts_and_quotes'
down_revision = 'nom003nomination_price_snapshot'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ===================================================================
    # 步骤 1：创建 quotes 表
    # ===================================================================
    print('[split-v2] 步骤1: 创建 quotes 表')
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS quotes (
            id                          SERIAL PRIMARY KEY,
            part_id                     INTEGER        NOT NULL
                                           REFERENCES parts(id) ON DELETE CASCADE,

            quote_serial                VARCHAR(50)    UNIQUE,
                -- 报价单流水号，格式: Q-{part_number}-{YYYYMM}-{4位序号}
                -- 示例: Q-1403-202505-0001

            annual_usage                INTEGER        NOT NULL DEFAULT 0,
                -- 年用量（件/年），用于阶梯报价参考

            pricing_mode                VARCHAR(20)    NOT NULL DEFAULT 'independent',
                -- 报价模式: independent=独立白盒, reference=关联参考

            -- 物理参数
            thickness                   NUMERIC(8,3),   -- 材料厚度 T (mm)
            width                       NUMERIC(10,2),  -- 材料宽度 W (mm)
            press_stroke               NUMERIC(8,2),   -- 冲压行程 P (mm)
            cavity_count                INTEGER        NOT NULL DEFAULT 1,
                -- 穴数（模具一出N），毛重放大系数

            scrap_rate                  NUMERIC(5,4)   NOT NULL DEFAULT 0.1000,
                -- 废料率，默认 10%。支持工艺路线差异化，前端可传参覆盖

            gross_weight                NUMERIC(12,4),
                -- 毛重 kg = T × W × P × Density × cavity_count / 10⁶

            -- 材料快照（定点时锁定，切断与 material_base_prices 联动）
            snapshot_mat_price          NUMERIC(10,4) NOT NULL DEFAULT 0,
                -- 报价当时快照的材料单价（元/kg）
            snapshot_mat_name           VARCHAR(100),
                -- 报价当时快照的材料牌号
            snapshot_density            NUMERIC(6,3),
                -- 报价当时快照的材料密度（g/cm³）
            snapshot_scrap_price        NUMERIC(10,4),
                -- 报价当时快照的废料回收价（元/kg）

            -- 成本分解
            material_net_cost           NUMERIC(12,4),
                -- 材料净成本 = 净重×单价 - 废料重量×废料回收价

            -- 费用
            stamping_fee                NUMERIC(10,4) NOT NULL DEFAULT 0,
                -- 冲压费（元/件）
            surface_fee                 NUMERIC(10,4) NOT NULL DEFAULT 0,
                -- 表面处理费（元/件）
            treatment_fee               NUMERIC(10,4) NOT NULL DEFAULT 0,
                -- 表面处理工序合计（元/件），由前端汇总传入

            -- 利润
            profit_margin               NUMERIC(8,4)  NOT NULL DEFAULT 0,
                -- 利润率系数，0.20 = 加价 20%

            -- 最终单价
            final_price                 NUMERIC(12,4),
                -- 最终单价（元/件），含所有费用和利润

            -- 人工覆盖（蓝色标识）
            unit_price_override         NUMERIC(10,4),
                -- 人工覆盖：材料单价（蓝色标识）
            material_cost_override      NUMERIC(12,4),
                -- 人工覆盖：材料净成本（蓝色标识）
            final_price_override        NUMERIC(12,4),
                -- 人工覆盖：最终总价（蓝色标识）

            override_fields             JSONB DEFAULT '[]'::jsonb,
                -- 被人工覆盖的字段名列表，前端蓝色渲染依据

            -- 审批状态（核心流转）
            approval_status             VARCHAR(20)    NOT NULL DEFAULT 'DRAFT',
                -- DRAFT       草稿（业务编辑中，未提交）
                -- PENDING_BOSS 待业务副总/老板审核
                -- APPROVED    审核通过（定点生效）
                -- REJECTED    驳回（可重开，链路保存在 parent_quote_id）

            rejection_reason            TEXT,
                -- 驳回原因（审批人填写）

            parent_quote_id             INTEGER        REFERENCES quotes(id),
                -- 驳回重开时指向父级报价单，支持历史链路追溯

            -- 提交时间戳
            submitted_at                TIMESTAMP,
                -- 提交至 PENDING_BOSS 的时间
            submitted_by                INTEGER        REFERENCES users(id),
                -- 提交人

            -- 审核时间戳
            approved_at                 TIMESTAMP,
                -- 审核通过时间
            approved_by                 INTEGER        REFERENCES users(id),
                -- 审核人（admin / 业务副总）

            -- 定点流程
            nomination_status            VARCHAR(20),
                -- 定点状态: pending_nomination / nominated / production_ready
            nomination_attachment        TEXT,
                -- 定点凭证文件路径（多文件逗号分隔）
            price_snapshot              JSONB,
                -- 定点确认时的完整价格快照（切断材料联动）
            nomination_confirmed_at      TIMESTAMP,
                -- 定点确认时间
            nomination_confirmed_by     INTEGER        REFERENCES users(id),
                -- 定点确认人

            created_at                  TIMESTAMP      NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMP      NOT NULL DEFAULT NOW()
        );
    """))
    print('[split-v2] quotes 表创建完成')

    # 索引：按零件查报价历史（按时间倒序）
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_quotes_part_id
        ON quotes(part_id DESC, created_at DESC);
    """))
    print('[split-v2] idx_quotes_part_id 索引创建完成')

    # 索引：加速审批状态查询（排除 DRAFT 减少扫描量）
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_quotes_approval_status
        ON quotes(approval_status) WHERE approval_status != 'DRAFT';
    """))
    print('[split-v2] idx_quotes_approval_status 索引创建完成')

    # 索引：加速父级追溯
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_quotes_parent
        ON quotes(parent_quote_id) WHERE parent_quote_id IS NOT NULL;
    """))
    print('[split-v2] idx_quotes_parent 索引创建完成')

    # ===================================================================
    # 步骤 2：parts 表追加架构约束字段
    # ===================================================================
    print('[split-v2] 步骤2: parts 表追加架构字段')

    _add_col_if_missing(conn, 'parts', 'version',
        sa.String(20).with_variant(sa.String(20), 'postgresql'),
        "零件版本号，默认 V1.0；图纸升版时新建 version='V1.1'，同一零件号多版本共存")

    _add_col_if_missing(conn, 'parts', 'part_status',
        sa.String(20).with_variant(sa.String(20), 'postgresql'),
        "零件主档状态: DRAFT=草稿, ACTIVE=活跃, ARCHIVED=归档, SUPERSEDED=已淘汰")

    # 联合唯一约束：同零件号 + 同版本不可重复
    if context.is_offline_mode():
        conn.execute(sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_parts_number_version'
                ) THEN
                    ALTER TABLE parts
                    ADD CONSTRAINT uq_parts_number_version
                    UNIQUE (part_number, version);
                END IF;
            END $$;
        """))
    else:
        _result = conn.execute(sa.text("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_parts_number_version';
        """)).fetchone()
        if not _result:
            conn.execute(sa.text("""
                ALTER TABLE parts
                ADD CONSTRAINT uq_parts_number_version
                UNIQUE (part_number, version);
            """))

    # ===================================================================
    # 步骤 3：数据平移（零件报价数据 → 初始报价单）
    # ===================================================================
    print('[split-v2] 步骤3: 数据平移开始')

    conn.execute(sa.text("""
        INSERT INTO quotes (
            part_id,
            quote_serial,
            annual_usage,
            pricing_mode,
            thickness,
            width,
            press_stroke,
            cavity_count,
            scrap_rate,
            gross_weight,
            snapshot_mat_price,
            snapshot_mat_name,
            snapshot_density,
            snapshot_scrap_price,
            stamping_fee,
            surface_fee,
            profit_margin,
            final_price,
            approval_status,
            submitted_at,
            approved_at,
            nomination_status,
            nomination_attachment,
            price_snapshot,
            nomination_confirmed_at,
            created_at,
            updated_at
        )
        SELECT
            p.id,

            -- 报价流水号: Q-{part_number}-{YYYYMM}-{4位序号}
            'Q-' || p.part_number || '-' || TO_CHAR(NOW(), 'YYYYMM')
                || '-' || LPAD(p.id::TEXT, 4, '0'),

            0,                                              -- annual_usage 需人工补录

            COALESCE(NULLIF(TRIM(p.pricing_mode), ''), 'independent'),

            p.thickness,
            p.width,
            p.press_stroke,
            COALESCE(p.cavity_count, 1),
            0.1000,                                        -- scrap_rate 默认 10%

            p.gross_weight,

            -- 材料快照（从 material_base_prices 联查，字段不存在时默认为 0）
            COALESCE(m.default_price, 0),
            p.material_name,
            COALESCE(m.default_density, 0),
            COALESCE(m.scrap_price, 0),

            COALESCE(p.stamping_fee, 0),
            COALESCE(p.surface_fee, 0),
            COALESCE(p.profit_margin, 0),

            -- final_price：优先取 final_price_override，再取 current_price，最后取 pending_price
            COALESCE(
                p.final_price_override,
                p.current_price,
                p.pending_price
            ),

            -- approval_status 映射旧状态
            CASE
                WHEN p.nomination_status = 'production_ready'  THEN 'APPROVED'
                WHEN p.price_status = '已锁定'                  THEN 'APPROVED'
                WHEN p.price_status = '待审核'                  THEN 'PENDING_BOSS'
                ELSE 'DRAFT'
            END,

            -- submitted_at：有提报价格即视为已提交
            CASE
                WHEN p.pending_price IS NOT NULL
                      OR p.current_price IS NOT NULL
                      OR p.final_price_override IS NOT NULL
                 THEN COALESCE(p.updated_at, p.created_at)
                ELSE NULL
            END,

            -- approved_at：已锁定/定点生效时视为已审核
            CASE
                WHEN p.price_status = '已锁定'
                      OR p.nomination_status = 'production_ready'
                 THEN COALESCE(p.updated_at, p.created_at)
                ELSE NULL
            END,

            p.nomination_status,
            p.nomination_attachment,
            p.price_snapshot,
            p.nomination_confirmed_at,
            COALESCE(p.updated_at, p.created_at),
            COALESCE(p.updated_at, p.created_at)

        FROM parts p
        LEFT JOIN material_base_prices m
            ON m.material_name = p.material_name;
    """))
    print('[split-v2] 数据平移 SQL 执行完成')

    if not context.is_offline_mode():
        cnt = conn.execute(sa.text("SELECT COUNT(*) FROM quotes")).fetchone()[0]
        print(f'[split-v2] quotes 表当前行数: {cnt}')

    # ===================================================================
    # 步骤 4：parts 表瘦身（删除已转移字段）
    # ===================================================================
    print('[split-v2] 步骤4: parts 表瘦身')

    drops = [
        'pricing_mode',
        'referenced_part_id',
        'thickness',
        'width',
        'press_stroke',
        'cavity_count',
        'gross_weight',
        'material_unit_price_override',
        'material_net_cost_override',
        'final_price_override',
        'stamping_fee',
        'surface_fee',
        'profit_margin',
        'manual_override_fields',
        'pending_price',
        'current_price',
        'price_status',
    ]
    for col in drops:
        conn.execute(sa.text(f"ALTER TABLE parts DROP COLUMN IF EXISTS {col};"))

    print('[split-v2] 步骤4完成: parts 表已瘦身')
    print('[split-v2] ======== 迁移完成 ========')


def downgrade():
    """
    回滚：重建 parts 业务字段，从 quotes 回写数据，再删 quotes 表。
    注意：回滚是破坏性操作，仅在开发测试阶段使用。
    """
    conn = op.get_bind()

    print('[split-v2] 回滚开始')

    # ---- R1: 重建 parts 业务字段 ----
    print('[split-v2] R1: 重建 parts 业务字段')
    adds = [
        ("pricing_mode",                "VARCHAR(20)"),
        ("referenced_part_id",          "INTEGER"),
        ("thickness",                  "NUMERIC(8,3)"),
        ("width",                       "NUMERIC(10,2)"),
        ("press_stroke",                "NUMERIC(8,2)"),
        ("cavity_count",                "INTEGER DEFAULT 1"),
        ("gross_weight",                "NUMERIC(12,4)"),
        ("material_unit_price_override","NUMERIC(10,4)"),
        ("material_net_cost_override",  "NUMERIC(12,4)"),
        ("final_price_override",        "NUMERIC(12,4)"),
        ("stamping_fee",                "NUMERIC(10,4) DEFAULT 0"),
        ("surface_fee",                 "NUMERIC(10,4) DEFAULT 0"),
        ("profit_margin",               "NUMERIC(8,4) DEFAULT 0"),
        ("manual_override_fields",       "JSONB DEFAULT '[]'::jsonb"),
        ("pending_price",               "NUMERIC(12,4)"),
        ("current_price",               "NUMERIC(12,4)"),
        ("price_status",                "VARCHAR(20)"),
    ]
    for col_name, col_type in adds:
        _r = conn.execute(sa.text(f"""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'parts' AND column_name = '{col_name}';
        """)).fetchone()
        if not _r:
            conn.execute(sa.text(f"ALTER TABLE parts ADD COLUMN {col_name} {col_type};"))
            print(f'  [ADD] parts.{col_name}')

    # ---- R2: 从 quotes 回写数据（取每个零件的最新报价）----
    print('[split-v2] R2: quotes 数据回写 parts')
    conn.execute(sa.text("""
        WITH latest AS (
            SELECT DISTINCT ON (part_id)
                   part_id,
                   pricing_mode, thickness, width, press_stroke, cavity_count,
                   gross_weight, stamping_fee, surface_fee, profit_margin,
                   final_price_override,
                   approval_status, nomination_status
            FROM quotes
            ORDER BY part_id, created_at DESC
        )
        UPDATE parts p SET
            pricing_mode               = l.pricing_mode,
            thickness                  = l.thickness,
            width                      = l.width,
            press_stroke               = l.press_stroke,
            cavity_count               = l.cavity_count,
            gross_weight               = l.gross_weight,
            stamping_fee               = l.stamping_fee,
            surface_fee                = l.surface_fee,
            profit_margin              = l.profit_margin,
            final_price_override       = l.final_price_override,
            pending_price              = CASE WHEN l.approval_status = 'PENDING_BOSS'
                                              THEN l.final_price_override END,
            current_price              = CASE WHEN l.approval_status = 'APPROVED'
                                              THEN l.final_price_override END,
            price_status               = CASE l.approval_status
                                            WHEN 'APPROVED'    THEN '已锁定'
                                            WHEN 'PENDING_BOSS' THEN '待审核'
                                            ELSE '待审核'
                                        END,
            nomination_status          = l.nomination_status,
            updated_at                = NOW()
        FROM latest l
        WHERE p.id = l.part_id;
    """))
    print('[split-v2] quotes 数据回写 parts 完成')

    # ---- R3: 删 quotes 表 ----
    conn.execute(sa.text("DROP TABLE IF EXISTS quotes;"))
    print('[split-v2] quotes 表已删除')

    # ---- R4: 删 parts 架构字段 ----
    conn.execute(sa.text("ALTER TABLE parts DROP CONSTRAINT IF EXISTS uq_parts_number_version;"))
    conn.execute(sa.text("ALTER TABLE parts DROP COLUMN IF EXISTS version;"))
    conn.execute(sa.text("ALTER TABLE parts DROP COLUMN IF EXISTS part_status;"))
    print('[split-v2] parts 架构字段已删除')
    print('[split-v2] ======== 回滚完成 ========')


def _add_col_if_missing(conn, table: str, col_name: str,
                        col_type, comment: str = None):
    """安全追加列（幂等）：仅在列不存在时添加，避免重复执行报错。"""
    if context.is_offline_mode():
        conn.execute(sa.text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
        ))
        if comment:
            escaped = comment.replace("'", "''")
            conn.execute(sa.text(
                f"COMMENT ON COLUMN {table}.{col_name} IS '{escaped}'"
            ))
        return
    result = conn.execute(sa.text(f"""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = '{table}' AND column_name = '{col_name}';
    """)).fetchone()
    if not result:
        col = sa.Column(col_name, col_type, nullable=True)
        op.add_column(table, col)
        if comment:
            # 单引号转义，防止 COMMENT 语法断裂
            escaped = comment.replace("'", "''")
            conn.execute(sa.text(
                f"COMMENT ON COLUMN {table}.{col_name} IS '{escaped}'"
            ))
        print(f'  [ADD] {table}.{col_name}')
    else:
        print(f'  [SKIP] {table}.{col_name}  已存在')
