# Customer 实体组最终设计

**决策日期**: 2026-07-07  
**实体组**: Customer（客户、价格体系）

---

## 一、为什么要独立出 Customer 实体组

### 1.1 当前问题：表命名和归属混乱

**表名遗留问题**：`tooling_customers`
- 从字面看像是"模具下的客户子表"（tooling_customers = tooling 的 customers）
- 但业务上客户是独立主体，不是模具的附属
- 模型类已经正确命名为 `Customer`（`backend/app/models/customer.py`），但表名还是 `tooling_customers`

**价格表归属不清**：
- 之前把 `price_accounts`、`customer_material_prices`、`customer_treatment_prices` 都散落在 Part 实体组讨论
- 但这些表都是 `customer_id` 作为关键维度，从"给客户定价"的业务视角看，应该归在 Customer 实体组

### 1.2 业务实体层级关系

```
Customer（客户 - 顶级主体）
  ├── 客户基本信息（name, contact, ...）
  │
  ├── 零件关联
  │   └── part_customer_aliases（客户件号映射）
  │
  ├── 价格体系（三层结构）
  │   ├── 1. 零件级价格（已定案零件的价格台账）
  │   │   └── price_accounts（某零件卖给某客户的当前执行价）
  │   │       └── price_adjustments（调价流水，老板审批）
  │   │
  │   ├── 2. 材料级价格历史（报价时参考）
  │   │   └── customer_material_prices（该客户 SUS304 最近3次成交价）
  │   │
  │   └── 3. 工序级价格历史（报价时参考）
  │       └── customer_treatment_prices（该客户电镀锌最近3次成交价）
  │
  └── 报价单
      └── quotes（给客户的报价单，quote_items 明细）
```

**核心逻辑**：
- Customer 是业务的起点（"比亚迪询价了一个新零件"）
- 报价时查 customer_material_prices / customer_treatment_prices 作为参考基准
- 定点后价格固化进 price_accounts（成为该零件的台账价）
- 后续调价走 price_adjustments 审批流程

---

## 二、Customer 实体组表结构设计

### 2.1 customers（客户主表，重命名）

```sql
-- 重命名现有表
ALTER TABLE tooling_customers RENAME TO customers;

-- 表结构（现有字段保持，后续扩展）
CREATE TABLE customers (
    id                  SERIAL PRIMARY KEY,              -- 沿用 INTEGER（现有）
    name                VARCHAR(200) UNIQUE NOT NULL,    -- 客户名称
    sheet_key           VARCHAR(100) NULL,               -- 表格关联键（现有，可能对接外部系统）
    
    -- 扩展字段（建议补充）
    contact_person      VARCHAR(100) NULL,               -- 联系人
    contact_phone       VARCHAR(50) NULL,                -- 联系电话
    contact_email       VARCHAR(100) NULL,               -- 邮箱
    address             TEXT NULL,                       -- 地址
    
    -- 系统字段
    is_active           BOOLEAN DEFAULT TRUE,            -- 是否启用
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customers_name ON customers(name);
CREATE INDEX idx_customers_active ON customers(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE customers IS '客户主表 - 顶级实体，所有价格体系和报价的主体';
```

**重命名说明**：
- ✅ 从 `tooling_customers` 改为 `customers`，去掉 tooling 前缀的误导
- ⚠️ 需要同步修改所有外键引用：`part_customer_aliases.customer_id`、`price_accounts.customer_id`、`quotes.customer_id` 等（外键约束会自动跟随）
- ⚠️ 后端模型 `Customer.__tablename__` 需要从 `"tooling_customers"` 改为 `"customers"`

### 2.2 price_accounts（零件价格台账，从 Part 实体组移入）

```sql
CREATE TABLE price_accounts (
    -- 主键
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 关联关系（一个零件对一个客户唯一）
    part_id                   UUID REFERENCES parts(id) NOT NULL,
    customer_id               INTEGER REFERENCES customers(id) NOT NULL,  -- 关联客户主表

    -- 材料信息（可覆盖 parts 的基准值）
    material                  VARCHAR(100) NULL,

    -- 重量：估算值（从报价单带入）
    estimated_net_weight_kg   DECIMAL(10,3) NULL,
    estimated_gross_weight_kg DECIMAL(10,3) NULL,

    -- 重量：实测值（首件/量产后录入）
    actual_net_weight_kg      DECIMAL(10,3) NULL,
    actual_gross_weight_kg    DECIMAL(10,3) NULL,
    actual_weight_source      VARCHAR(20) NULL,           -- first_piece/mass_production
    actual_weight_updated_at  TIMESTAMP NULL,
    actual_weight_updated_by  UUID REFERENCES users(id) NULL,

    -- 价格构成
    material_unit_price       DECIMAL(10,4) NULL,         -- 材料单价 (元/kg)
    scrap_price               DECIMAL(10,4) NULL,         -- 废料回收价 (元/kg)
    base_price                DECIMAL(10,4) NULL,         -- 基准单价（定点时确定）
    current_price             DECIMAL(10,4) NULL,         -- 当前执行价（存储，手动调整）

    -- 年降参考
    reduction_pct             DECIMAL(5,2) NULL,          -- 合同年降率 (如 3.00 = 3%)
    price_year                INTEGER NULL,               -- 基准年份

    -- 成本偏离标记
    cost_deviation_flag       BOOLEAN DEFAULT FALSE,
    cost_deviation_note       TEXT NULL,

    -- 状态
    notes                     TEXT NULL,
    is_active                 BOOLEAN DEFAULT TRUE,
    created_at                TIMESTAMP DEFAULT NOW(),
    updated_at                TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_price_part_customer UNIQUE(part_id, customer_id)
);

CREATE INDEX idx_pa_part ON price_accounts(part_id);
CREATE INDEX idx_pa_customer ON price_accounts(customer_id);  -- 客户视角查询优化
CREATE INDEX idx_pa_material ON price_accounts(material) WHERE material IS NOT NULL;

COMMENT ON TABLE price_accounts IS '【Customer实体组】零件价格台账 - 某零件卖给某客户的完整价格档案';
COMMENT ON COLUMN price_accounts.customer_id IS '关联 customers.id，价格体系的主体维度';
```

**从 Part 移入 Customer 的理由**：
1. 业务流程是"给客户报价"，不是"零件定价"——客户是主语
2. `UNIQUE(part_id, customer_id)` 约束说明这是**双主体关系**，但客户视角更强
3. 和 `customer_material_prices` / `customer_treatment_prices` 归在同一实体组，形成完整的客户价格体系

### 2.3 price_adjustments（调价流水，从 Part 实体组移入）

```sql
CREATE TABLE price_adjustments (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 调价对象
    price_account_id          UUID REFERENCES price_accounts(id) NOT NULL,

    -- 调价内容
    old_price                 DECIMAL(10,4) NOT NULL,
    new_price                 DECIMAL(10,4) NOT NULL,
    adjustment_type           VARCHAR(20) NOT NULL,       -- annual_reduction/manual/material_change
    adjustment_pct            DECIMAL(6,2) NULL,

    -- 批量调价关联
    batch_id                  UUID NULL,
    batch_filter              JSONB NULL,

    -- 审批流程
    approval_status           VARCHAR(20) NOT NULL DEFAULT 'pending_approval',
    submitted_by              UUID REFERENCES users(id) NOT NULL,
    approved_by               UUID REFERENCES users(id) NULL,
    approved_at               TIMESTAMP NULL,
    rejection_reason          TEXT NULL,

    -- 原因和审计
    reason                    TEXT NOT NULL,
    adjusted_by               UUID REFERENCES users(id) NOT NULL,
    adjusted_at               TIMESTAMP DEFAULT NOW(),
    effective_date            DATE NULL
);

CREATE INDEX idx_padj_account ON price_adjustments(price_account_id);
CREATE INDEX idx_padj_batch ON price_adjustments(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_padj_status ON price_adjustments(approval_status) WHERE approval_status = 'pending_approval';

COMMENT ON TABLE price_adjustments IS '【Customer实体组】调价流水 - 价格台账的变动历史，需老板审批';
```

### 2.4 customer_material_prices（客户材料价格历史）

```sql
CREATE TABLE customer_material_prices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         INTEGER REFERENCES customers(id) NOT NULL,  -- 关联客户主表
    material_id         INTEGER REFERENCES material_dict(id) NOT NULL,

    unit_price          DECIMAL(10,4) NOT NULL,        -- 该客户该材质的成交单价 (元/kg)
    scrap_price         DECIMAL(10,4) NULL,            -- 该客户该材质的废料回收价

    quote_id            UUID REFERENCES quotes(id) NULL, -- 关联报价单，可追溯定价来源
    quoted_at           TIMESTAMP DEFAULT NOW(),

    created_by          UUID REFERENCES users(id) NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cmp_customer_material ON customer_material_prices(customer_id, material_id, quoted_at DESC);
CREATE INDEX idx_cmp_quote ON customer_material_prices(quote_id) WHERE quote_id IS NOT NULL;

COMMENT ON TABLE customer_material_prices IS '【Customer实体组】客户材料价格历史 - 保留全部历史，查询时取最近3次作为新零件报价参考';
COMMENT ON COLUMN customer_material_prices.quote_id IS '标记该价格是在哪次报价中确定的，可追溯上下文';
```

### 2.5 customer_treatment_prices（客户工序价格历史）

```sql
CREATE TABLE customer_treatment_prices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         INTEGER REFERENCES customers(id) NOT NULL,  -- 关联客户主表
    treatment_id        INTEGER REFERENCES treatment_dict(id) NOT NULL,

    unit_price          DECIMAL(10,4) NOT NULL,        -- 该客户该工序的成交价
    calc_mode_snapshot  VARCHAR(20) NULL,              -- 快照计价方式（manual/net_weight）
    unit_snapshot       VARCHAR(20) NULL,              -- 快照单位（元/件 或 元/kg）

    quote_id            UUID REFERENCES quotes(id) NULL,
    quoted_at           TIMESTAMP DEFAULT NOW(),

    created_by          UUID REFERENCES users(id) NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ctp_customer_treatment ON customer_treatment_prices(customer_id, treatment_id, quoted_at DESC);
CREATE INDEX idx_ctp_quote ON customer_treatment_prices(quote_id) WHERE quote_id IS NOT NULL;

COMMENT ON TABLE customer_treatment_prices IS '【Customer实体组】客户工序价格历史 - 保留全部历史，查询时取最近3次作为报价参考';
```

---

## 三、业务流程示例：以客户为中心的定价逻辑

### 3.1 新零件报价流程（Customer 视角）

```
① 客户"比亚迪"询价新零件
   - 零件材质：SUS304
   - 表面处理：电镀锌

② 查询客户材料价格历史（customer_material_prices）
   SELECT unit_price, scrap_price, quoted_at
   FROM customer_material_prices
   WHERE customer_id = :比亚迪_id AND material_id = :SUS304_id
   ORDER BY quoted_at DESC LIMIT 3;
   
   结果：[20.5元/kg(2026-05), 20.0元/kg(2026-03), 19.8元/kg(2026-01)]
   → 建议材料单价：20.5元/kg（最近一次成交价）

③ 查询客户工序价格历史（customer_treatment_prices）
   SELECT unit_price, quoted_at
   FROM customer_treatment_prices
   WHERE customer_id = :比亚迪_id AND treatment_id = :电镀锌_id
   ORDER BY quoted_at DESC LIMIT 3;
   
   结果：[0.5元/件(2026-06), 0.48元/件(2026-04), 0.50元/件(2026-02)]
   → 建议工序单价：0.5元/件

④ 业务人员参考历史价格，结合成本计算，填写报价单
   - 材料成本：20.5 × 净重 - 废料价 × 毛重
   - 工序费用：0.5元/件
   - 加成 + 老板审批 → 报价确定

⑤ 定点确认后
   - 新零件创建 price_accounts 记录
     - part_id = 新零件ID
     - customer_id = 比亚迪ID
     - material_unit_price = 20.5（固化，不再随 customer_material_prices 变动）
     - current_price = 5.20元/件
   
   - 同时写入历史记录（为下次报价留参考）
     INSERT INTO customer_material_prices (customer_id, material_id, unit_price, quote_id, quoted_at)
     VALUES (:比亚迪_id, :SUS304_id, 20.5, :本次报价单_id, NOW());
```

### 3.2 零件调价流程（Customer 视角）

```
① 业务人员发现实测重量偏离，需要调价
   - price_accounts.actual_net_weight = 0.155kg（实测）
   - price_accounts.estimated_net_weight = 0.150kg（报价时估算）
   - 成本偏离 +6% > 5%，cost_deviation_flag = TRUE

② 发起调价申请（业务人员或老板）
   INSERT INTO price_adjustments (
       price_account_id, old_price, new_price,
       adjustment_type, approval_status, submitted_by, reason
   ) VALUES (
       :零件价格台账ID, 5.20, 5.40,
       'material_change', 'pending_approval', :业务人员ID,
       '实测净重偏离估算，材料成本上升6%'
   );

③ 老板审批
   - 通过：approval_status = 'approved'
           price_accounts.current_price 5.20 → 5.40
   - 驳回：approval_status = 'rejected'
           rejection_reason = '偏离幅度可接受，暂不调价'
```

### 3.3 客户维度查询（新增能力）

**查询某客户的所有零件价格**：
```sql
SELECT 
    p.part_number,
    p.part_name,
    pa.current_price,
    pa.material,
    pa.updated_at as last_price_update
FROM price_accounts pa
JOIN parts p ON p.id = pa.part_id
WHERE pa.customer_id = :比亚迪_id
  AND pa.is_active = TRUE
ORDER BY pa.updated_at DESC;
```

**查询某客户的材料成交价趋势**：
```sql
SELECT 
    md.name as material_name,
    cmp.unit_price,
    cmp.quoted_at,
    q.id as quote_id
FROM customer_material_prices cmp
JOIN material_dict md ON md.id = cmp.material_id
LEFT JOIN quotes q ON q.id = cmp.quote_id
WHERE cmp.customer_id = :比亚迪_id
ORDER BY md.name, cmp.quoted_at DESC;
```

---

## 四、与 Part 实体组的关系边界

### 4.1 Part 实体组负责什么

```
Part 实体组（零件物理属性和客户映射）
├── parts（零件主表）
│   └── 物理属性：part_number, thickness, width, cavity_count, material_type
│
├── part_name_dict（零件名称字典）
│   └── 三级分类
│
└── part_customer_aliases（客户件号映射）
    └── 记录：零件A在比亚迪那边叫"BYD-2024-001"
    └── 不含价格信息，只是件号映射关系
```

**Part 实体组不管价格**——零件表只存"这个零件是什么"（物理属性），不存"卖多少钱"。

### 4.2 Customer 实体组负责什么

```
Customer 实体组（客户和价格体系）
├── customers（客户主表）
│
├── price_accounts（零件级价格台账）
│   └── 某零件卖给某客户的当前执行价
│
├── price_adjustments（调价流水）
│   └── 价格变动历史 + 审批记录
│
├── customer_material_prices（材料级价格历史）
│   └── 某客户 SUS304 的历史成交价
│
└── customer_treatment_prices（工序级价格历史）
    └── 某客户电镀锌的历史成交价
```

**Customer 实体组管价格**——所有和"钱"有关的，都在这里。

### 4.3 两个实体组的连接点

```
part_customer_aliases（桥接表，归 Part 实体组）
├── part_id → parts.id
├── customer_id → customers.id
├── customer_part_no（客户件号）
└── customer_part_name（客户件名）

price_accounts（价格台账，归 Customer 实体组）
├── part_id → parts.id
├── customer_id → customers.id
└── current_price（当前售价）
```

**两张表都有 part_id + customer_id 组合**，但职责不同：
- `part_customer_aliases`：件号映射关系（"叫什么"）
- `price_accounts`：价格档案（"卖多少"）

---

## 五、数据迁移影响评估

### 5.1 表重命名（tooling_customers → customers）

```sql
-- Step 1: 重命名表
ALTER TABLE tooling_customers RENAME TO customers;

-- Step 2: 外键会自动跟随，但索引名可能需要重建
ALTER INDEX tooling_customers_pkey RENAME TO customers_pkey;
ALTER INDEX tooling_customers_name_key RENAME TO customers_name_key;

-- Step 3: 后端代码修改
-- backend/app/models/customer.py
class Customer(Base):
    __tablename__ = "customers"  # 从 "tooling_customers" 改为 "customers"
```

**影响范围**：
- 所有引用 `tooling_customers` 的外键约束自动更新（part_customer_aliases, price_accounts, quotes 等）
- 后端模型类需要修改 `__tablename__`
- API 端点路径 `/api/customers` 不受影响（已经用的是 customers，不是 tooling_customers）

### 5.2 price_accounts / price_adjustments 归属变更

**不需要改表结构**，只是文档层面的重新组织：
- 从"Part 实体组文档"移到"Customer 实体组文档"
- 表本身的 foreign key（`customer_id`, `part_id`）不变
- 后端代码不需要修改

---

## 六、决策总结

| 决策点 | 结论 |
|-------|------|
| Customer 实体组定位 | 独立顶级实体，所有价格体系归其管理 |
| tooling_customers 重命名 | 改为 customers，去掉 tooling 误导前缀 |
| price_accounts 归属 | 从 Part 实体组移入 Customer 实体组 |
| price_adjustments 归属 | 从 Part 实体组移入 Customer 实体组 |
| 材料/工序价格历史 | customer_material_prices / customer_treatment_prices，归 Customer 实体组 |

**Customer 实体组包含的表**：
1. ✅ customers（重命名自 tooling_customers）
2. ✅ price_accounts（零件价格台账）
3. ✅ price_adjustments（调价流水）
4. ✅ customer_material_prices（客户材料价格历史）
5. ✅ customer_treatment_prices（客户工序价格历史）

**Part 实体组剩余的表**：
1. ✅ parts（零件主表）
2. ✅ part_name_dict（零件名称字典）
3. ✅ part_customer_aliases（客户件号映射，不含价格）

---

**决策完成时间**: 2026-07-07
