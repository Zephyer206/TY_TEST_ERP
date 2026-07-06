# 客户材料/工序价格历史表最终设计

**决策日期**: 2026-07-06
**涉及表**: material_dict（沿用）、treatment_dict（新建）、customer_material_prices（新建）、customer_treatment_prices（新建）

---

## 一、决策汇总

| 决策点 | 问题 | 选择 | 说明 |
|-------|------|------|------|
| Q6.1 | 材料字典表怎么合并 | **保留 material_dict，废弃 material_base_prices** | material_dict 字段更全（含 density/category/standard），且已有 API |
| Q6.2 | 材料价格历史怎么记录 | **按客户记录，只看最近3次** | 保留全部历史，查询时取最近3条 |
| Q6.2a | 是否关联报价单 | **关联 quote_id** | 方便追溯"这个价格是哪次报价定的" |
| Q6.3 | 表面处理怎么设计 | **独立 treatment_dict 字典表 + 客户历史子表** | 与材料价格模式对称，同样保留最近3次历史 |

---

## 二、背景：为什么现在要做这个设计

代码调研发现，当前报价流程里材料成本和表面处理费完全靠人工/前端填写快照字段（`quotes.snapshot_mat_price`、`treatment_items` JSONB），没有任何代码去联查材料或工序字典表算价格。相关的四张遗留表都处于"游离"状态：

| 表 | 状态 | 处理方式 |
|---|------|---------|
| `material_dict` | 有 API，无引用，1行数据（脚本抽取） | ✅ 保留作为全局材料字典 |
| `material_base_prices` | 无模型无API，14行真实种子数据 | ⛔ 数据迁移进 material_dict 后废弃 |
| `material_cost_history` | 零引用，空表 | ⛔ 直接废弃（历史改为按客户记录，见下文） |
| `treatment_dicts` | 零引用，28行数据全部 is_active=false | ⛔ 只迁移10条真实工序数据，重建为 treatment_dict |
| `treatment_cost_history` | 零引用，空表 | ⛔ 直接废弃（历史改为按客户记录） |

**关键设计转向**：原设计里材料/工序的价格变动历史是"全局"的（`material_cost_history` 记录默认价涨跌）。现在改为"按客户"记录——因为业务上真正有用的是"上次给这个客户 SUS304 报了多少钱"，而不是"材料默认价什么时候变过"。全局字典表的 `default_price`/`default_rate` 只作为兜底参考值，不追踪历史。

---

## 三、material_dict（沿用现有表，明确定位）

现有表结构不变，明确其角色：**全局材料默认参考价字典**，供没有客户历史记录时兜底使用。

```sql
-- 现有表，仅明确字段用途注释，不改结构
COMMENT ON COLUMN material_dict.default_price IS '材料默认参考单价，无客户历史价格时的兜底值，不追踪历史';
COMMENT ON COLUMN material_dict.scrap_price IS '材料默认废料回收价，兜底值';
```

### 数据清理：迁移 material_base_prices → material_dict

```sql
-- 按 material_name 匹配，补充 material_dict 中缺失的材质
INSERT INTO material_dict (code, name, density, default_price, scrap_price, is_active, created_at)
SELECT
    mbp.material_name,          -- code 暂用 material_name
    mbp.material_name,          -- name
    mbp.default_density,
    mbp.default_price,
    mbp.scrap_price,
    TRUE,
    mbp.updated_at
FROM material_base_prices mbp
WHERE NOT EXISTS (
    SELECT 1 FROM material_dict md WHERE md.name = mbp.material_name
);

-- 确认迁移无误后废弃旧表
DROP TABLE IF EXISTS material_base_prices;
DROP TABLE IF EXISTS material_cost_history;
```

---

## 四、treatment_dict（新建，清理重建）

```sql
CREATE TABLE treatment_dict (
    id                   SERIAL PRIMARY KEY,          -- 沿用 INTEGER，与 material_dict 一致
    name                 VARCHAR(100) UNIQUE NOT NULL, -- 工序名称：电镀锌/热处理/喷涂...
    calc_mode            VARCHAR(20) NOT NULL DEFAULT 'manual',  -- manual(按件) / net_weight(按重量)
    default_rate         DECIMAL(10,4) NOT NULL DEFAULT 0,       -- 默认费率，兜底值，不追踪历史
    unit                 VARCHAR(20) NOT NULL DEFAULT '元/件',   -- 元/件 或 元/kg
    is_active            BOOLEAN DEFAULT TRUE,
    sort_order           INTEGER DEFAULT 0,
    created_at           TIMESTAMP DEFAULT NOW(),
    updated_at           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_treatment_dict_active ON treatment_dict(is_active);

COMMENT ON TABLE treatment_dict IS '表面处理工序字典 - 全局默认费率，客户特定价格见 customer_treatment_prices';
COMMENT ON COLUMN treatment_dict.default_rate IS '默认费率，无客户历史价格时的兜底值';
```

### 数据清理：只迁移真实工序，丢弃测试脏数据

```sql
-- 旧表 treatment_dicts 里 28 行数据全部 is_active=false，且混有大量测试数据
-- (RequestsTest_*, APIFlowTest_*, test_autocommit 等)，只迁移真实工序名称
INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active)
SELECT name, calc_mode, rate, unit, TRUE
FROM treatment_dicts
WHERE name IN ('热处理','电镀锌','发黑','喷涂','贴胶','阳极氧化','磷化','压铸镀层','电镀镍','达克罗涂装');

DROP TABLE IF EXISTS treatment_dicts;
DROP TABLE IF EXISTS treatment_cost_history;
```

---

## 五、customer_material_prices（客户材料价格历史）

```sql
CREATE TABLE customer_material_prices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID REFERENCES customers(id) NOT NULL,
    material_id         INTEGER REFERENCES material_dict(id) NOT NULL,

    unit_price          DECIMAL(10,4) NOT NULL,        -- 该客户该材质的成交单价 (元/kg)
    scrap_price         DECIMAL(10,4) NULL,             -- 该客户该材质的废料回收价

    quote_id            UUID REFERENCES quotes(id) NULL, -- 关联报价单，可追溯定价来源
    quoted_at           TIMESTAMP DEFAULT NOW(),         -- 报价/记录时间

    created_by          UUID REFERENCES users(id) NULL,
    created_at           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cmp_customer_material ON customer_material_prices(customer_id, material_id, created_at DESC);
CREATE INDEX idx_cmp_quote ON customer_material_prices(quote_id) WHERE quote_id IS NOT NULL;

COMMENT ON TABLE customer_material_prices IS '客户材料价格历史 - 保留全部历史记录，查询时取最近3次作为报价参考';
COMMENT ON COLUMN customer_material_prices.quote_id IS '关联报价单，标记该价格是在哪次报价中确定的，可为空（补录历史数据时）';
```

### 查询：某客户某材质的最近3次价格

```sql
SELECT unit_price, scrap_price, quoted_at, quote_id
FROM customer_material_prices
WHERE customer_id = :customer_id AND material_id = :material_id
ORDER BY quoted_at DESC
LIMIT 3;
```

### 报价时取值优先级（兜底逻辑）

```sql
-- 新零件报价时，材料单价的取值顺序：
-- 1. 该客户该材质的最近一次历史价 (customer_material_prices)
-- 2. 材料默认参考价 (material_dict.default_price)
COALESCE(
    (SELECT unit_price FROM customer_material_prices
     WHERE customer_id = :cid AND material_id = :mid
     ORDER BY quoted_at DESC LIMIT 1),
    (SELECT default_price FROM material_dict WHERE id = :mid)
) AS suggested_unit_price
```

---

## 六、customer_treatment_prices（客户工序价格历史）

结构与 customer_material_prices 对称：

```sql
CREATE TABLE customer_treatment_prices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID REFERENCES customers(id) NOT NULL,
    treatment_id        INTEGER REFERENCES treatment_dict(id) NOT NULL,

    unit_price          DECIMAL(10,4) NOT NULL,        -- 该客户该工序的成交价
    calc_mode_snapshot  VARCHAR(20) NULL,               -- 快照当时计价方式，防止字典表后续变更影响历史真实性
    unit_snapshot        VARCHAR(20) NULL,               -- 快照当时单位

    quote_id            UUID REFERENCES quotes(id) NULL,
    quoted_at           TIMESTAMP DEFAULT NOW(),

    created_by          UUID REFERENCES users(id) NULL,
    created_at           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ctp_customer_treatment ON customer_treatment_prices(customer_id, treatment_id, created_at DESC);
CREATE INDEX idx_ctp_quote ON customer_treatment_prices(quote_id) WHERE quote_id IS NOT NULL;

COMMENT ON TABLE customer_treatment_prices IS '客户表面处理工序价格历史 - 保留全部历史记录，查询时取最近3次作为报价参考';
```

**为什么要快照 calc_mode/unit**：字典表里的计价方式或单位后续可能调整（比如某工序从按件改成按重量计价），但历史记录要保持"当时是怎么算的"，不能被字典表变更影响，所以历史行里快照一份。

---

## 七、与已有表的关系区分

容易混淆的是 `customer_material_prices` 和 `price_accounts.material_unit_price` 看起来很像，但概念不同：

```
customer_material_prices          price_accounts.material_unit_price
（客户材料价格历史）                （零件价格台账里的材料单价）
├── 维度: 客户 + 材质              ├── 维度: 零件 + 客户
├── 用途: 报价新零件时的参考基准     ├── 用途: 该零件已定案的材料单价
├── 不分零件（同材质多个零件通用）   ├── 特定零件专属
└── 多条历史记录                    └── 当前生效值（单条）
```

**业务场景**：给客户"比亚迪"报一个新零件，材质是 SUS304。查 `customer_material_prices` 看比亚迪最近3次 SUS304 的成交价作为参考 → 确定这次报价的材料单价 → 定点后写入该零件的 `price_accounts.material_unit_price`（固化，不再随 customer_material_prices 变动）。

表面处理同理：`customer_treatment_prices` 是参考基准，`quotes.treatment_items`（JSONB）是该报价单实际使用的工序和费用快照。

---

## 八、决策状态

| 决策点 | 结论 |
|-------|------|
| Q6.1 | material_dict 保留为全局材料字典，material_base_prices 数据迁移后废弃 |
| Q6.2 | 材料价格历史按客户记录，保留全部历史，查询取最近3条 |
| Q6.2a | customer_material_prices 关联 quote_id，可追溯定价来源 |
| Q6.3 | 新建 treatment_dict 全局字典表 + customer_treatment_prices 客户历史子表，与材料价格模式对称 |

清理表：`material_base_prices`、`material_cost_history`、`treatment_dicts`、`treatment_cost_history` 全部废弃。

**决策完成时间**: 2026-07-06
