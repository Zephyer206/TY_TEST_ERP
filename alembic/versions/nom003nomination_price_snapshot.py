"""
定点 (Nomination) 卡控体系 + 双时间戳补全 —— 数据库迁移

┌─────────────────────────────────────────────────────────────────────┐
│  变更 1：parts 表新增定点流程字段                                      │
│  ┌──────────────────┬───────────────────────────────────────────┐   │
│  │ nomination_status │ VARCHAR(20)                                │   │
│  │                   │ pending_nomination  报价完成，待定点      │   │
│  │                   │ nominated          已定点，待确认        │   │
│  │                   │ production_ready   定点已确认，量产就绪  │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ nomination_attachment │ TEXT  定点确认凭证文件路径（多文件:    │   │
│  │                       │   逗号分隔），确认定点时上传           │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ price_snapshot   │ JSONB  定点时价格快照（切断材料联动）     │   │
│  │                   │ {                                          │   │
│  │                   │   unit_price, scrap_price, density,       │   │
│  │                   │   stamping_fee, surface_fee,               │   │
│  │                   │   gross_weight, material_net_cost,        │   │
│  │                   │   final_price, profit_margin,             │   │
│  │                   │   material_name, cavity_count,            │   │
│  │                   │   thickness, width, press_stroke,         │   │
│  │                   │   snapshot_at (TIMESTAMP)                │   │
│  │                   │ }                                        │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ nomination_confirmed_at │ TIMESTAMP  定点确认时间              │   │
│  ├──────────────────┼───────────────────────────────────────────┤   │
│  │ nomination_confirmed_by │ INTEGER  FK → users(id) 定点确认人  │   │
│  └──────────────────┴───────────────────────────────────────────┘   │
│                                                                      │
│  变更 2：production_logs 新增 actual_date (业务发生日期)             │
│  - 默认 DEFAULT CURRENT_DATE，允许补录历史日期                         │
│  - CHECK 约束：actual_date <= CURRENT_DATE（禁止填未来）             │
│  - 旧数据回填：actual_date = CAST(report_time AS DATE)               │
│                                                                      │
│  变更 3：pkg_packaging_logs / pkg_shipping_logs 新增 actual_date     │
│  - 与变更 2 同步补全（pkg_log_actual_date 迁移已处理，此处兼容检查）   │
│                                                                      │
│  关联 .cursorrules V3.1 §2.1 定点流程 + §4 双时间戳规范             │
│                                                                      │
│  执行方式：alembic upgrade head                                      │
│  回滚方式：alembic downgrade -1                                      │
└─────────────────────────────────────────────────────────────────────┘
"""

from alembic import op
import sqlalchemy as sa

revision = 'nom003nomination_price_snapshot'
down_revision = 'mno345pkg_shipping_customer'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 变更 1a：parts.nomination_status ──────────────────────────────
    _add_col_if_missing(conn, 'parts', 'nomination_status',
        sa.String(20),
        "定点状态：pending_nomination=待定点，nominated=已定点，production_ready=量产就绪")

    # ── 变更 1b：parts.nomination_attachment ──────────────────────────
    _add_col_if_missing(conn, 'parts', 'nomination_attachment',
        sa.Text(),
        "定点确认凭证文件路径，多文件逗号分隔")

    # ── 变更 1c：parts.price_snapshot (JSONB) ─────────────────────────
    # PostgreSQL JSONB 列，存储定点时的完整价格快照
    result_snapshot = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'parts' AND column_name = 'price_snapshot';
    """)).fetchone()
    if not result_snapshot:
        op.add_column('parts', sa.Column('price_snapshot', sa.JSON, nullable=True))
        op.execute("COMMENT ON COLUMN parts.price_snapshot IS "
                   "'定点时价格快照 JSONB，切断与 material_base_prices 的联动'")

    # ── 变更 1d：parts.nomination_confirmed_at ─────────────────────────
    _add_col_if_missing(conn, 'parts', 'nomination_confirmed_at',
        sa.TIMESTAMP,
        "定点确认时间")

    # ── 变更 1e：parts.nomination_confirmed_by ────────────────────────
    _add_col_if_missing(conn, 'parts', 'nomination_confirmed_by',
        sa.Integer(),
        "定点确认人 FK → users(id)")

    # ── 变更 2：production_logs 新增 actual_date ──────────────────────
    result_prod = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'production_logs' AND column_name = 'actual_date';
    """)).fetchone()
    if not result_prod:
        op.add_column(
            'production_logs',
            sa.Column('actual_date', sa.Date(),
                      nullable=False, server_default='CURRENT_DATE')
        )
        # CHECK：禁止填入未来日期
        op.execute("""
            ALTER TABLE production_logs
            ADD CONSTRAINT chk_production_logs_actual_date
            CHECK (actual_date <= CURRENT_DATE);
        """)
        # 旧数据回填：actual_date = report_time 的日期部分
        op.execute("""
            UPDATE production_logs
            SET actual_date = CAST(report_time AS DATE)
            WHERE actual_date IS NULL;
        """)
        op.execute("COMMENT ON COLUMN production_logs.actual_date IS "
                   "'业务发生日期（双时间戳）；默认等于 report_time，允许补录'")

    # ── 变更 3：pkg_packaging_logs.actual_date（安全追加）────────────
    result_pkg = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'pkg_packaging_logs' AND column_name = 'actual_date';
    """)).fetchone()
    if not result_pkg:
        op.add_column(
            'pkg_packaging_logs',
            sa.Column('actual_date', sa.Date(),
                      nullable=False, server_default='CURRENT_DATE')
        )
        op.execute("""
            ALTER TABLE pkg_packaging_logs
            ADD CONSTRAINT chk_pkg_packaging_actual_date_v2
            CHECK (actual_date <= CURRENT_DATE);
        """)
        op.execute("""
            UPDATE pkg_packaging_logs
            SET actual_date = CAST(created_at AS DATE)
            WHERE actual_date IS NULL;
        """)

    # ── 变更 4：pkg_shipping_logs.actual_date（安全追加）─────────────
    result_ship = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'pkg_shipping_logs' AND column_name = 'actual_date';
    """)).fetchone()
    if not result_ship:
        op.add_column(
            'pkg_shipping_logs',
            sa.Column('actual_date', sa.Date(),
                      nullable=False, server_default='CURRENT_DATE')
        )
        op.execute("""
            ALTER TABLE pkg_shipping_logs
            ADD CONSTRAINT chk_pkg_shipping_actual_date_v2
            CHECK (actual_date <= CURRENT_DATE);
        """)
        op.execute("""
            UPDATE pkg_shipping_logs
            SET actual_date = CAST(created_at AS DATE)
            WHERE actual_date IS NULL;
        """)


def downgrade():
    op.execute("ALTER TABLE parts DROP COLUMN IF EXISTS nomination_status;")
    op.execute("ALTER TABLE parts DROP COLUMN IF EXISTS nomination_attachment;")
    op.execute("ALTER TABLE parts DROP COLUMN IF EXISTS price_snapshot;")
    op.execute("ALTER TABLE parts DROP COLUMN IF EXISTS nomination_confirmed_at;")
    op.execute("ALTER TABLE parts DROP COLUMN IF EXISTS nomination_confirmed_by;")
    op.execute("ALTER TABLE production_logs DROP CONSTRAINT IF EXISTS chk_production_logs_actual_date;")
    op.execute("ALTER TABLE production_logs DROP COLUMN IF EXISTS actual_date;")
    op.execute("ALTER TABLE pkg_packaging_logs DROP CONSTRAINT IF EXISTS chk_pkg_packaging_actual_date_v2;")
    op.execute("ALTER TABLE pkg_packaging_logs DROP COLUMN IF EXISTS actual_date;")
    op.execute("ALTER TABLE pkg_shipping_logs DROP CONSTRAINT IF EXISTS chk_pkg_shipping_actual_date_v2;")
    op.execute("ALTER TABLE pkg_shipping_logs DROP COLUMN IF EXISTS actual_date;")


def _add_col_if_missing(conn, table, col_name, col_type, comment=None):
    result = conn.execute(sa.text(f"""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = '{table}' AND column_name = '{col_name}';
    """)).fetchone()
    if not result:
        col = sa.Column(col_name, col_type, nullable=True)
        op.add_column(table, col)
        if comment:
            op.execute(f"COMMENT ON COLUMN {table}.{col_name} IS '{comment}'")
        print(f'[nom003] {table}.{col_name} added')
