"""
业务部双驱报价核算引擎 —— 数据库迁移

扩展 parts 表，支持：
1. 报价分流模式  pricing_mode : 'independent'(独立白盒) | 'reference'(关联参考)
2. 关联参考老件  referenced_part_id → parts(id)，定价模式关闭手动输入 final_price
3. T/W/P 物理参数  thickness / width / press_stroke（冲压行程）
4. 白盒成本分解  gross_weight / material_net_cost / material_unit_price_override
5. 人工覆盖标识  manual_override_fields（JSON），blue 样式标记
6. 样件判定流程  sample_judgment_status : 'pending'|'approved'|'rejected'
7. 毛重公式参数  cavity_count（穴数）

执行方式：alembic upgrade head
回滚方式：alembic downgrade -1
"""

from alembic import op
import sqlalchemy as sa

revision = 'sales_pricing_engine_v1'
down_revision = 'abc123tech_twoscan'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. pricing_mode ───────────────────────────────────────────────
    _add_col_if_missing(conn, 'parts', 'pricing_mode',
        sa.String(20).with_variant(sa.String(20), 'postgresql'),
        "报价分流模式：independent=独立白盒，reference=关联参考。空=未指定（兼容旧数据）")

    # ── 2. referenced_part_id ─────────────────────────────────────────
    _add_col_if_missing(conn, 'parts', 'referenced_part_id',
        sa.Integer(),
        "关联参考件号ID（关联模式时填写）")

    # ── 3. T/W/P 物理参数 ──────────────────────────────────────────
    _add_col_if_missing(conn, 'parts', 'thickness',
        sa.Numeric(8, 3),
        "材料厚度 mm")
    _add_col_if_missing(conn, 'parts', 'width',
        sa.Numeric(10, 2),
        "材料宽度 mm")
    _add_col_if_missing(conn, 'parts', 'press_stroke',
        sa.Numeric(8, 2),
        "冲压行程 mm（冲压力 P）")

    # ── 4. cavity_count ──────────────────────────────────────────────
    _add_col_if_missing(conn, 'parts', 'cavity_count',
        sa.Integer(),
        "穴数（1出N），用于毛重 = T×W×P×Density×腔数/10⁶")

    # ── 5. 白盒成本分解字段 ─────────────────────────────────────────
    _add_col_if_missing(conn, 'parts', 'gross_weight',
        sa.Numeric(12, 4),
        "毛重 kg = T×W×P×Density×腔数/10⁶")
    _add_col_if_missing(conn, 'parts', 'material_unit_price_override',
        sa.Numeric(10, 4),
        "人工覆盖后的材料单价（蓝色显示标识），NULL=未覆盖")
    _add_col_if_missing(conn, 'parts', 'material_net_cost_override',
        sa.Numeric(12, 4),
        "人工覆盖后的材料净成本（蓝色显示标识），NULL=未覆盖")
    _add_col_if_missing(conn, 'parts', 'final_price_override',
        sa.Numeric(12, 4),
        "人工覆盖后的总价（蓝色显示标识），NULL=未覆盖")

    # ── 6. 冲压费/表面处理费/利润（独立模式白盒核算参数）─────────
    _add_col_if_missing(conn, 'parts', 'stamping_fee',
        sa.Numeric(10, 4),
        "冲压费（元/件）")
    _add_col_if_missing(conn, 'parts', 'surface_fee',
        sa.Numeric(10, 4),
        "表面处理费（元/件）")
    _add_col_if_missing(conn, 'parts', 'profit_margin',
        sa.Numeric(8, 4),
        "利润率系数（默认 0，即无加价；0.2=加价20%）")

    # ── 7. manual_override_fields ────────────────────────────────────
    _add_col_if_missing(conn, 'parts', 'manual_override_fields',
        sa.Text(),
        "人工覆盖字段列表，JSON 数组如 ['material_unit_price_override','final_price_override']")

    # ── 8. sample_judgment_status ───────────────────────────────────
    _add_col_if_missing(conn, 'parts', 'sample_judgment_status',
        sa.String(20).with_variant(sa.String(20), 'postgresql'),
        "样件判定状态：pending=待判定，approved=已通过，rejected=未通过/待解绑重算")


def downgrade():
    conn = op.get_bind()
    cols = [
        'pricing_mode', 'referenced_part_id',
        'thickness', 'width', 'press_stroke', 'cavity_count',
        'gross_weight',
        'material_unit_price_override', 'material_net_cost_override',
        'final_price_override',
        'stamping_fee', 'surface_fee', 'profit_margin',
        'manual_override_fields', 'sample_judgment_status',
    ]
    for col in cols:
        op.execute(f'ALTER TABLE parts DROP COLUMN IF EXISTS {col};')


# ── 内部工具 ─────────────────────────────────────────────────────────
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
        print(f'[sales_pricing] {table}.{col_name} added')
