# 数据库表设计完整总结（已讨论完毕）

**决策日期**: 2026-07-07  
**文档版本**: v1.0

---

## 一、已完成的表格清单（15张核心表）

### 核心主表（3张）

| 表名 | 主键类型 | 定位 | 关键字段 |
|------|---------|------|---------|
| **customers** | INTEGER | 客户主体，价格体系核心 | name, contact_person, contact_phone |
| **parts** | UUID | 零件主数据，包含 TWP | part_number, T/W/P, material_id, tooling_id |
| **tooling** | UUID | 模具资产管理 | tooling_number, owner_customer_id, shot_count |

### Customer 实体组 - 价格体系（5张）

| 表名 | 定位 | 唯一约束 |
|------|------|---------|
| **part_customer_aliases** | 客户件号映射（一卖多） | UNIQUE(part_id, customer_id) |
| **price_accounts** | 零件价格台账 | UNIQUE(part_id, customer_id) |
| **price_adjustments** | 调价流水（老板审批） | - |
| **customer_material_prices** | 客户材料价格历史 | - |
| **customer_treatment_prices** | 客户工序价格历史 | - |

### 全局字典表（3张）

| 表名 | 定位 | 预置数据 |
|------|------|---------|
| **material_dict** | 材料标准价格 | 迁移 material_base_prices (14行) |
| **treatment_dict** | 工序标准费率 | 迁移 treatment_dicts 真实工序 (10条) |
| **machine_tonnage_dict** | 机床吨位规格 | 60/110/160/200/200双轴/250/400吨 |

### 报价单（1张）

| 表名 | 定位 | 关键特性 |
|------|------|---------|
| **quotes** | 报价单完整记录 | TWP估算、材料快照、审批流程、定点管理、版本管理 |

---

## 二、核心设计决策

| 决策点 | 结论 | 理由 |
|-------|------|------|
| **TWP 位置** | parts 表 | 零件固有属性，技术部门维护最精确值 |
| **P 的含义** | Pitch（步距） | 单个零件所需材料长度，用于计算材料用量 |
| **parts ↔ tooling** | parts.tooling_id → tooling | 先有零件后开模，从零件找模具 |
| **customers 定位** | 独立顶级实体 | 重命名 tooling_customers → customers |
| **机床吨位** | 固定字典表 | 60/110/160/200/200双轴/250/400吨 |
| **价格体系** | 字典表 + 客户历史 | 标准价格 vs 客户特定价格分层管理 |
| **一卖多** | part_customer_aliases | 一个零件多个客户，各有件号和价格 |
| **模具归属** | owner_customer_id | 支持客户审厂合规和跨客户使用检查 |
| **quotes 快照** | snapshot_* 字段 | 报价时价格固化，不随字典表变化 |

---

## 三、customers 表（客户主表）

### 定位
顶级实体，业务主体，所有价格体系的核心。

### 表结构
```sql
CREATE TABLE customers (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200) UNIQUE NOT NULL,
    contact_person      VARCHAR(100) NULL,
    contact_phone       VARCHAR(50) NULL,
    contact_email       VARCHAR(100) NULL,
    address             TEXT NULL,
    sheet_key           VARCHAR(100) NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);
```

### 迁移操作
```sql
ALTER TABLE tooling_customers RENAME TO customers;
```

### 关联子表
- quotes（报价单）
- price_accounts（零件价格台账）
- customer_material_prices（客户材料价格历史）
- customer_treatment_prices（客户工序价格历史）
- part_customer_aliases（客户件号映射，桥接表）
- tooling（通过 owner_customer_id，模具归属）

---

## 四、parts 表（零件主表）

### 定位
产品主数据，存储零件物理属性和技术参数（TWP）。

### 表结构
```sql
CREATE TABLE parts (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_number               VARCHAR(50) UNIQUE NOT NULL,
    part_name                 VARCHAR(200) NOT NULL,
    status                    VARCHAR(30) NOT NULL,
    
    -- 技术参数（TWP - 最精确的值）
    thickness                 DECIMAL(8,3) NULL,       -- T 厚度 (mm)
    width                     DECIMAL(8,3) NULL,       -- W 宽度 (mm)
    pitch                     DECIMAL(8,3) NULL,       -- P 步距 (mm)
    
    -- 材料和吨位
    material_id               INTEGER REFERENCES material_dict(id) NULL,
    press_tonnage_id          INTEGER REFERENCES machine_tonnage_dict(id) NULL,
    
    -- 模具关联
    tooling_id                UUID REFERENCES tooling(id) NULL,
    cavity_position           INTEGER NULL,
    
    -- 重量
    net_weight                DECIMAL(10,3) NULL,
    gross_weight              DECIMAL(10,3) NULL,
    weight_source             VARCHAR(20) NULL,
    
    -- 产品信息
    vehicle_model             VARCHAR(100) NULL,
    
    -- 图纸路径
    drawing_path              VARCHAR(500) NULL,
    sdr_drawing_path          VARCHAR(500) NULL,
    ppap_path                 VARCHAR(500) NULL,
    
    -- 表面处理
    surface_treatment_type    VARCHAR(100) NULL,
    
    -- 系统字段
    is_deleted                BOOLEAN DEFAULT FALSE,
    created_at                TIMESTAMP DEFAULT NOW(),
    updated_at                TIMESTAMP DEFAULT NOW()
);
```

### 关键设计点
- **TWP 存储在 parts**（不是 tooling）：零件的固有属性
- **数据流**：quotes 估算 → parts 初始值 → 技术部门维护 → 最精确值
- **一模多腔**：左右件虽然 TWP 可能相同，但分别存储

---

## 五、tooling 表（模具主表）

### 定位
资产管理，记录模具归属和寿命维护。

### 表结构
```sql
CREATE TABLE tooling (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tooling_number            VARCHAR(50) UNIQUE NOT NULL,
    name                      VARCHAR(200) NOT NULL,
    status                    VARCHAR(30) NOT NULL,
    total_cavity_count        INTEGER NOT NULL DEFAULT 1,
    
    -- 归属（客户审厂合规）
    owner_customer_id         INTEGER REFERENCES customers(id) NULL,
    
    -- 资产信息
    tooling_cost              DECIMAL(14,2) NULL,
    supplier                  VARCHAR(200) NULL,
    purchase_date             DATE NULL,
    
    -- 寿命管理
    shot_count                INTEGER DEFAULT 0,
    max_shot_count            INTEGER NULL,
    last_maintenance_date     DATE NULL,
    maintenance_cycle_days    INTEGER NULL,
    
    -- 系统字段
    is_deleted                BOOLEAN DEFAULT FALSE,
    created_at                TIMESTAMP DEFAULT NOW(),
    updated_at                TIMESTAMP DEFAULT NOW()
);
```

### 关键设计点
- **TWP 不存储在 tooling**：通过 parts.tooling_id 反向关联
- **owner_customer_id**：记录模具归属（NULL = 公司自有）
- **支持跨客户使用**：客户A的模具可以为客户B生产

---

## 六、quotes 表（报价单，完整版）

### 定位
报价阶段的完整记录，包含 TWP 估算、成本计算、审批流程、定点管理。

### 核心模块

**1. 基本信息**
- quote_serial, part_id, customer_id, customer_product_no, vehicle_model

**2. 技术参数（TWP 估算）**
- thickness, width, press_stroke（步距）, cavity_count, gross_weight, scrap_rate

**3. 材料快照（报价时固化）**
- material_id, snapshot_mat_name, snapshot_mat_price, snapshot_scrap_price, snapshot_density

**4. 成本计算**
- material_net_cost, stamping_fee, surface_fee, treatment_fee, inspection_fee, packaging_fee, mold_cost

**5. 表面处理（JSONB）**
- treatment_items: `[{treatment_id, treatment_name, unit_price, calc_mode}, ...]`

**6. 价格计算**
- profit_margin, final_price

**7. 手动覆盖**
- unit_price_override, material_cost_override, final_price_override, override_fields

**8. 审批流程**
- approval_status (DRAFT/PENDING/APPROVED/REJECTED)
- submitted_by/at, approved_by/at, rejection_reason

**9. 定点管理**
- nomination_status, nomination_attachment, nomination_confirmed_by/at

**10. 版本管理**
- parent_quote_id, price_snapshot

### 关键字段说明

| 字段 | 说明 |
|------|------|
| press_stroke | P（步距），单个零件所需材料长度 |
| snapshot_* | 材料价格快照，报价时固化，永久不变 |
| treatment_items | JSONB 数组，存储多道工序 |
| override_fields | 记录哪些字段被手动修改过 |
| parent_quote_id | 版本管理，修改报价时创建新版本 |

---

## 七、price_accounts 表（零件价格台账）

### 定位
某零件卖给某客户的完整价格档案。

### 核心字段
```sql
CREATE TABLE price_accounts (
    id                        UUID PRIMARY KEY,
    part_id                   UUID NOT NULL,
    customer_id               INTEGER NOT NULL,
    
    -- 重量：估算值 vs 实测值
    estimated_net_weight_kg   DECIMAL(10,3) NULL,
    actual_net_weight_kg      DECIMAL(10,3) NULL,
    
    -- 价格构成
    material_unit_price       DECIMAL(10,4) NULL,
    scrap_price               DECIMAL(10,4) NULL,
    base_price                DECIMAL(10,4) NULL,
    current_price             DECIMAL(10,4) NULL,  -- 当前执行价（存储字段，手动调整）
    
    -- 年降参考
    reduction_pct             DECIMAL(5,2) NULL,
    price_year                INTEGER NULL,
    
    -- 成本偏离标记
    cost_deviation_flag       BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT uq_price_part_customer UNIQUE(part_id, customer_id)
);
```

### 关键设计点
- **估算值和实测值并存**：不相互覆盖
- **current_price**：存储字段，手动调整（非自动年降）
- **成本偏离自动标记**：实测重量偏离 >5% 时标记

---

## 八、customer_material_prices 表（客户材料价格历史）

### 定位
某客户某材质的历史成交价，新零件报价时参考。

### 表结构
```sql
CREATE TABLE customer_material_prices (
    id                  UUID PRIMARY KEY,
    customer_id         INTEGER NOT NULL,
    material_id         INTEGER NOT NULL,
    unit_price          DECIMAL(10,4) NOT NULL,
    scrap_price         DECIMAL(10,4) NULL,
    quote_id            UUID NULL,  -- 关联报价单，可追溯
    quoted_at           TIMESTAMP DEFAULT NOW(),
    created_by          UUID NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

### 关键设计点
- **保留全部历史**：查询时取最近3条
- **关联 quote_id**：可追溯"这个价格是哪次报价定的"
- **不分零件**：同客户的所有 SUS304 零件共享历史参考价

---

## 九、material_dict 表（材料字典）

### 定位
全局材料标准价格，客户特定价格见 customer_material_prices。

### 表结构
```sql
CREATE TABLE material_dict (
    id                  SERIAL PRIMARY KEY,
    code                VARCHAR(50) UNIQUE NOT NULL,
    name                VARCHAR(100) NOT NULL,
    density             DECIMAL(10,3) NOT NULL,      -- 密度 (g/cm³)
    default_price       DECIMAL(10,4) NULL,          -- 标准材料单价 (元/kg)
    scrap_price         DECIMAL(10,4) NULL,          -- 标准废料价格 (元/kg)
    category            VARCHAR(50) NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

### 数据迁移
```sql
-- 迁移 material_base_prices 的 14 行数据
INSERT INTO material_dict (code, name, density, default_price, scrap_price)
SELECT material_name, material_name, default_density, default_price, scrap_price
FROM material_base_prices;

-- 废弃旧表
DROP TABLE material_base_prices;
DROP TABLE material_cost_history;
```

---

## 十、machine_tonnage_dict 表（机床吨位字典）

### 表结构
```sql
CREATE TABLE machine_tonnage_dict (
    id                  SERIAL PRIMARY KEY,
    tonnage             VARCHAR(50) UNIQUE NOT NULL,
    tonnage_value       INTEGER NOT NULL,
    description         VARCHAR(200) NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    sort_order          INTEGER DEFAULT 0
);
```

### 预置数据
```sql
INSERT INTO machine_tonnage_dict (tonnage, tonnage_value, description, sort_order) VALUES
    ('60吨', 60, '60吨冲床', 1),
    ('110吨', 110, '110吨冲床', 2),
    ('160吨', 160, '160吨冲床', 3),
    ('200吨', 200, '200吨冲床', 4),
    ('200吨双轴', 200, '200吨双轴冲床', 5),
    ('250吨', 250, '250吨冲床', 6),
    ('400吨', 400, '400吨冲床', 7);
```

---

## 十一、材料成本计算公式

### 公式

```
单件材料成本 = [T(mm) × W(mm) × P(mm) × 密度(g/cm³) × (材料单价 - 废料价格)(元/kg)] / (10^6 × 穴数)

取值优先级：
- TWP: parts 表（最精确）
- 密度: material_dict.density
- 材料单价: customer_material_prices（最近1次）或 material_dict.default_price
- 废料价格: customer_material_prices.scrap_price 或 material_dict.scrap_price
```

### 计算视图

```sql
CREATE VIEW part_material_cost AS
SELECT 
    p.part_number,
    c.name as customer_name,
    p.thickness, p.width, p.pitch,
    t.total_cavity_count,
    md.density,
    COALESCE(cmp.unit_price, md.default_price) as material_unit_price,
    
    -- 单件材料成本
    (p.thickness * p.width * p.pitch * md.density * 
     (COALESCE(cmp.unit_price, md.default_price) - COALESCE(cmp.scrap_price, md.scrap_price))
    ) / (1000000.0 * COALESCE(t.total_cavity_count, 1)) as material_cost_per_piece
    
FROM parts p
LEFT JOIN tooling t ON t.id = p.tooling_id
JOIN material_dict md ON md.id = p.material_id
LEFT JOIN part_customer_aliases pca ON pca.part_id = p.id
LEFT JOIN customers c ON c.id = pca.customer_id
LEFT JOIN LATERAL (
    SELECT unit_price, scrap_price
    FROM customer_material_prices
    WHERE material_id = md.id AND customer_id = c.id
    ORDER BY quoted_at DESC LIMIT 1
) cmp ON true
WHERE p.thickness IS NOT NULL AND p.width IS NOT NULL AND p.pitch IS NOT NULL;
```

---

## 十二、数据流转完整流程

```
① 报价阶段
   quotes: 填写估算 TWP (T=1.5, W=50, P=80)
   快照材料价格（snapshot_mat_price, snapshot_density）
   → 计算 material_net_cost
   → 老板审批（DRAFT → PENDING → APPROVED）

② 定点阶段
   quotes.nomination_status = confirmed
   → 创建/更新 parts: 从 quotes 拷贝 TWP（初始值）
   → 创建 price_accounts: estimated_net_weight
   → 写入 customer_material_prices: 本次成交价
   → 写入 customer_treatment_prices: 本次工序价

③ 开模阶段
   创建 tooling: 模具基本信息, owner_customer_id
   → 更新 parts.tooling_id: 关联零件到模具

④ 技术维护阶段
   更新 parts.TWP: 根据实际模具调整（T=1.48, W=49.5, P=82）
   → 重新计算 net_weight

⑤ 首件检验阶段
   更新 price_accounts.actual_net_weight: 实测重量
   → 自动检测成本偏离（>5% 标记 cost_deviation_flag）

⑥ 调价流程
   创建 price_adjustments: pending_approval
   → 老板审批 → approved
   → 更新 price_accounts.current_price
```

---

## 十三、表关系图

```
customers（客户）
  ├── 1:N → quotes（报价单）
  ├── 1:N → customer_material_prices（材料价格历史）
  ├── 1:N → customer_treatment_prices（工序价格历史）
  ├── N:M → parts（通过 part_customer_aliases）
  └── 1:N → tooling（通过 owner_customer_id，模具归属）

parts（零件，包含 TWP）
  ├── N:1 → material_dict（材料）
  ├── N:1 → machine_tonnage_dict（吨位）
  ├── N:1 → tooling（parts.tooling_id）
  ├── N:M → customers（通过 part_customer_aliases）
  ├── 1:N → quotes
  └── 1:N → price_accounts

tooling（模具）
  ├── 1:N → parts（parts.tooling_id 反向关联）
  └── N:1 → customers（owner_customer_id）

quotes（报价单）
  ├── N:1 → parts
  ├── N:1 → customers
  ├── N:1 → material_dict
  ├── N:1 → machine_tonnage_dict
  └── N:1 → quotes（parent_quote_id，版本管理）

price_accounts（价格台账）
  ├── N:1 → parts
  ├── N:1 → customers
  └── 1:N → price_adjustments（调价流水）
```

---

## 十四、特殊业务场景支持

### 场景1：一卖多（同一零件卖给多个客户）

```
parts（1条记录）
  part_number: ZJ-001
  TWP: T=1.5, W=50, P=80
  
part_customer_aliases（2条记录）
  ├── 客户A, customer_part_no: "A-001"
  └── 客户B, customer_part_no: "B-999"
  
price_accounts（2条记录）
  ├── 客户A, current_price: 5.0元
  └── 客户B, current_price: 4.8元
```

### 场景2：一模多腔（一个模具生产多个零件）

```
tooling M-001
  total_cavity_count: 2
  owner_customer_id: 客户A
  
parts（2条记录）
  ├── part A: TWP=(1.5, 50, 80), cavity_position=1
  └── part B: TWP=(1.5, 50, 80), cavity_position=2
```

### 场景3：跨客户使用（客户A的模具为客户B生产）

```
tooling M-001
  owner_customer_id: 客户A
  
production_plan
  tooling_id: M-001
  customer_id: 客户B  ← 为客户B生产
  
→ 合规检查视图标记："⚠️ 跨客户使用"
```

---

## 十五、需要清理的旧表

| 旧表 | 处理方式 | 数据量 |
|------|---------|--------|
| `tooling_customers` | ✅ 重命名为 customers | 89行 |
| `material_base_prices` | ⛔ 迁移到 material_dict 后删除 | 14行 |
| `material_cost_history` | ⛔ 直接删除 | 0行（空表） |
| `treatment_dicts` | ⛔ 迁移真实工序到 treatment_dict 后删除 | 28行（只迁移10条） |
| `treatment_cost_history` | ⛔ 直接删除 | 0行（空表） |

---

## 十六、主键类型说明

### 当前实际数据库

| 表 | 主键类型 | 说明 |
|---|---------|------|
| quotes | INTEGER | 实际使用中 |
| customers (tooling_customers) | INTEGER | 实际使用中 |
| parts | 需确认 | 设计建议 UUID |
| tooling | 需确认 | 设计建议 UUID |

### 建议策略

- **短期**：保持现状用 INTEGER（快速实施，兼容现有代码）
- **长期**：迁移到 UUID（分布式友好，避免 ID 碰撞）

---

## 十七、文档索引

### Part 实体组设计文档

- [part-entity-parts-table-final.md](part-entity-parts-table-final.md) — parts / part_name_dict
- [part-entity-aliases-table-final.md](part-entity-aliases-table-final.md) — part_customer_aliases
- [part-entity-price-tables-final.md](part-entity-price-tables-final.md) — price_accounts / price_adjustments

### Customer 实体组设计文档

- [customer-entity-group-final.md](customer-entity-group-final.md) — Customer 实体组完整设计
- [material-treatment-price-history-final.md](material-treatment-price-history-final.md) — 材料/工序价格历史

### 其他文档

- [gap-analysis.md](gap-analysis.md) — 设计与实际数据库差异对比
- [current-schema.md](current-schema.md) — 当前数据库完整结构（90张表）

---

## 十八、待实现功能（非表结构，后续开发）

1. **共享零件标记**：零件列表显示"🔄 3个客户"
2. **材料成本自动计算**：基于 TWP 和材料密度
3. **成本偏离自动标记**：实测重量偏离 >5% 时标记
4. **调价审批流程**：业务人员发起 → 老板审批
5. **模具跨客户使用提示**：排产时检查合规风险
6. **客户审厂报告导出**：模具台账 + 生产记录

---

**文档完成时间**: 2026-07-07  
**讨论完毕的核心表**: 15张  
**状态**: ✅ 设计定稿，可进入实施阶段
