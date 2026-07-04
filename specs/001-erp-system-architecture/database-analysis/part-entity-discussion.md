# Part 实体组详细设计讨论

**实体组**: Part（零件、价格台账、年降）
**讨论日期**: 2026-07-04
**策略**: 以 data-model.md 设计为主导，参考 current-schema.md 实际数据库

---

## 📋 讨论议程

### 本次讨论的表

1. ✅ **parts** - 零件主表
2. ✅ **part_name_dict** - 零件名称字典（三级分类）
3. 🔄 **part_customer_aliases** - 客户件号别名
4. 🔄 **price_accounts** - 价格台账
5. 🔄 **annual_price_records** - 年降记录
6. 🔄 **price_adjustments** - 手动调价记录

---

## 1. parts（零件主表）

### 1.1 设计方案 (data-model.md)

```sql
Table: parts
├── id                        UUID PRIMARY KEY
├── part_number               VARCHAR(50) UNIQUE NOT NULL
├── part_name                 VARCHAR(200) NOT NULL
├── status                    VARCHAR(30) NOT NULL  -- draft/sampling/mass_production/obsolete
├── tooling_id                UUID REFERENCES toolings(id) NULL
├── ppap_number               VARCHAR(50) NULL
├── vehicle_model             VARCHAR(100) NULL
├── cavity_count              INTEGER NULL
├── press_tonnage             DECIMAL(10,2) NULL
├── material_type             VARCHAR(100) NULL
├── net_weight                DECIMAL(10,3) NULL  -- 净重 (kg)
├── gross_weight              DECIMAL(10,3) NULL  -- 毛重 (kg)
├── drawing_path              VARCHAR(500) NULL   -- 图纸路径
├── surface_treatment_type    VARCHAR(100) NULL   -- 表面处理类型
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()
```

### 1.2 实际数据库 (current-schema.md)

```sql
Table: parts
├── id                        INTEGER PRIMARY KEY  -- ⚠️ 不是 UUID
├── part_no                   VARCHAR(100)         -- ⚠️ 字段名不同
├── part_name                 VARCHAR(200)
├── customer_name             VARCHAR(150)         -- ➕ 设计中没有
├── customer_part_no          VARCHAR(100)         -- ➕ 设计中没有
├── status                    VARCHAR(20)
├── die_id                    INTEGER              -- ⚠️ tooling_id → die_id
├── ppap_no                   VARCHAR(50)
├── vehicle_model             VARCHAR(100)
├── material_type             VARCHAR(100)
├── thickness                 NUMERIC              -- ➕ 设计中没有
├── width                     NUMERIC              -- ➕ 设计中没有
├── net_weight                NUMERIC
├── gross_weight              NUMERIC
├── material_unit_price       NUMERIC              -- ➕ 设计中没有
├── scrap_price               NUMERIC              -- ➕ 设计中没有
├── drawing_path              VARCHAR(500)
├── sdr_drawing_path          VARCHAR(500)         -- ➕ 设计中没有
├── created_at                TIMESTAMP
├── updated_at                TIMESTAMP
└── [更多字段...]
```

### 1.3 核心差异

| 维度 | 设计 | 实际 | 决策 |
|------|------|------|------|
| **主键类型** | UUID | INTEGER | ❓ |
| **零件编号字段名** | part_number | part_no | ❓ |
| **模具关联** | tooling_id (UUID) | die_id (INTEGER) | ❓ |
| **客户信息** | 无（通过别名表关联） | 直接存储 customer_name | ❓ |
| **技术参数** | 无 thickness/width | 有 thickness/width | ❓ |
| **价格信息** | 无（在 price_accounts） | 有 material_unit_price/scrap_price | ❓ |
| **穴数字段** | cavity_count | ❌ 不存在 | ❓ |
| **吨位字段** | press_tonnage | ❌ 不存在 | ❓ |

### 1.4 需要讨论的问题

#### Q1.1: 主键类型 - UUID vs INTEGER？

**设计理由**（UUID）:
- 分布式系统友好
- 避免 ID 碰撞
- 数据迁移方便

**实际使用**（INTEGER）:
- 性能更好（索引更小）
- URL 更简洁
- 数据库主流实践

**问题**: 
- 是否坚持使用 UUID？
- 如果改为 INTEGER，需要修改所有外键引用

---

#### Q1.2: 零件编号字段名 - part_number vs part_no？

**设计**: `part_number`（完整单词）
**实际**: `part_no`（缩写）

**问题**: 
- 统一使用哪个？
- 是否需要迁移？

---

#### Q1.3: 零件表是否应包含客户信息？

**设计方案**（无客户字段）:
```
parts (零件主表，不含客户信息)
   ↓
part_customer_aliases (一个零件对多个客户)
   ├── customer_id
   ├── customer_part_no
   └── price_account_id → price_accounts
```

**实际方案**（有客户字段）:
```
parts 表直接包含:
   ├── customer_name
   └── customer_part_no
```

**冲突点**:
- 设计假设：一个零件可以卖给多个客户，每个客户有不同的件号和价格
- 实际实现：零件表直接绑定一个客户

**问题**:
- 如果一个零件卖给多个客户，实际数据库如何处理？
- 是否需要重构为设计的多对多关系？

---

#### Q1.4: 技术参数 thickness/width 应该在哪里？

**设计方案**: 技术参数在 **quote_items** 表
```
报价阶段: quote_items.t_parameter, w_parameter, p_parameter
定点后: 写入 parts 表的 tooling_id（模具信息）
```

**实际数据库**: 技术参数在 **parts** 表
```
parts.thickness, parts.width
```

**问题**:
- 技术参数是零件固有属性还是报价阶段临时参数？
- 如果一个零件有多次报价，参数会变化吗？

---

#### Q1.5: 价格信息应该在哪里？

**设计方案**: 价格在 **price_accounts** 表
```
parts (零件基础信息)
   ↓
price_accounts (价格台账，一个零件对一个客户一个价格档案)
   ├── material_unit_price
   ├── waste_price
   └── base_price
```

**实际数据库**: 价格在 **parts** 表
```
parts 表直接包含:
   ├── material_unit_price
   └── scrap_price
```

**问题**:
- 如果一个零件卖给多个客户，价格可能不同，如何处理？
- 是否应该拆分到独立的价格表？

---

#### Q1.6: cavity_count 和 press_tonnage 为什么实际数据库没有？

**设计方案**: parts 表包含
```
parts.cavity_count    -- 穴数
parts.press_tonnage   -- 吨位
```

**实际数据库**: ❌ 这两个字段不存在

**可能原因**:
1. 这些信息在 **quotes** 表中（报价阶段）
2. 这些信息在 **dies** 表中（模具信息）
3. 未实现

**问题**:
- 穴数和吨位是零件属性还是模具属性？
- 应该存在哪张表？

---

### 1.7 我的建议

**建议 A: 保持设计，创建新表**
```sql
CREATE TABLE parts_new (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_number            VARCHAR(50) UNIQUE NOT NULL,
    part_name              VARCHAR(200) NOT NULL,
    status                 VARCHAR(30) NOT NULL,
    tooling_id             UUID REFERENCES toolings(id) NULL,
    -- 不包含客户信息
    -- 不包含价格信息
    -- 不包含技术参数 thickness/width
    cavity_count           INTEGER NULL,
    press_tonnage          DECIMAL(10,2) NULL,
    ...
);
```

**建议 B: 混合方案，逐步迁移**
```sql
-- 保留实际的 parts 表（INTEGER 主键）
-- 但补充缺失字段
ALTER TABLE parts ADD COLUMN cavity_count INTEGER;
ALTER TABLE parts ADD COLUMN press_tonnage DECIMAL(10,2);
ALTER TABLE parts ADD COLUMN surface_treatment_type VARCHAR(100);

-- 移除应该在别名表的字段（通过应用层逐步迁移）
-- customer_name, customer_part_no → part_customer_aliases
```

---

## ⏸️ 暂停点 1

**在继续讨论其他表之前，我需要您的决策：**

### 关于 parts 表

**D1.1**: 主键类型？
- [ ] A. UUID（坚持设计）
- [ ] B. INTEGER（适配实际）
- [ ] C. 其他想法

**D1.2**: 零件编号字段名？
- [ ] A. part_number
- [ ] B. part_no
- [ ] C. 都保留（加别名）

**D1.3**: 客户信息存储？
- [ ] A. parts 表不含客户信息，使用 part_customer_aliases（设计）
- [ ] B. parts 表包含主客户信息（实际）
- [ ] C. 混合：主客户在 parts，其他客户在别名表

**D1.4**: 技术参数 thickness/width？
- [ ] A. 仅在 quote_items（设计）
- [ ] B. 在 parts 表（实际）
- [ ] C. 两处都有（报价阶段在 quote_items，定点后写入 parts）

**D1.5**: 价格信息？
- [ ] A. 独立 price_accounts 表（设计）
- [ ] B. 在 parts 表（实际）
- [ ] C. 两处都有（基准价在 parts，客户价在 price_accounts）

**D1.6**: cavity_count 和 press_tonnage？
- [ ] A. 在 parts 表（设计）
- [ ] B. 在 dies/toolings 表（模具属性）
- [ ] C. 两处都有（冗余存储）

---

**请逐一回答 D1.1 ~ D1.6，我们再继续讨论后续的表。** 🤔
