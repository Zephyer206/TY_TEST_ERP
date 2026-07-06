# Part 实体组设计决策记录

**决策日期**: 2026-07-04  
**决策原则**: 以 data-model.md 设计为主导，参考实际数据库

---

## ✅ parts 表设计决策

### 决策结果

| 决策点 | 问题 | 选择 | 说明 |
|-------|------|------|------|
| **D1.1** | 主键类型 | **A. UUID** | 分布式友好、避免碰撞、便于迁移 |
| **D1.2** | 字段命名 | **A. part_number** | 使用完整单词，代码可读性更好 |
| **D1.3** | 客户信息 | **A. 使用别名表** | 支持一对多关系，符合业务现实 |
| **D1.4** | 技术参数 | **C. 两处都有** | 报价时在 quote_items，定点后写入 parts |
| **D1.5** | 价格信息 | **A. 独立价格表** | 支持多客户不同价格，支持年降管理 |
| **D1.6** | 穴数吨位 | **C. 两处都有** | parts 和 dies 都存，便于查询 |

---

## 📋 最终 parts 表设计

### parts (零件主表)

```sql
CREATE TABLE parts (
    -- 主键
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    part_number               VARCHAR(50) UNIQUE NOT NULL,     -- 零件编号（完整单词）
    part_name                 VARCHAR(200) NOT NULL,           -- 零件名称
    status                    VARCHAR(30) NOT NULL,            -- draft/sampling/mass_production/obsolete
    
    -- 模具关联
    tooling_id                UUID REFERENCES toolings(id) NULL,  -- 关联模具
    
    -- 技术参数（定点后从 quote_items 写入）
    thickness                 DECIMAL(8,3) NULL,               -- 厚度 T (mm) ✅ 新增
    width                     DECIMAL(8,3) NULL,               -- 宽度 W (mm) ✅ 新增
    cavity_count              INTEGER NULL,                    -- 穴数 ✅
    press_tonnage             DECIMAL(10,2) NULL,              -- 吨位 ✅
    
    -- 产品信息
    ppap_number               VARCHAR(50) NULL,                -- PPAP 编号
    vehicle_model             VARCHAR(100) NULL,               -- 车型
    material_type             VARCHAR(100) NULL,               -- 材料类型
    
    -- 重量信息
    net_weight                DECIMAL(10,3) NULL,              -- 净重 (kg)
    gross_weight              DECIMAL(10,3) NULL,              -- 毛重 (kg)
    
    -- 图纸路径
    drawing_path              VARCHAR(500) NULL,               -- 客户图纸路径
    sdr_drawing_path          VARCHAR(500) NULL,               -- SDR 技术图纸路径 ✅ 新增
    
    -- 表面处理
    surface_treatment_type    VARCHAR(100) NULL,               -- 表面处理类型
    
    -- 系统字段
    is_deleted                BOOLEAN DEFAULT FALSE,
    created_at                TIMESTAMP DEFAULT NOW(),
    updated_at                TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_parts_status ON parts(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_parts_number ON parts(part_number);
CREATE INDEX idx_parts_tooling ON parts(tooling_id) WHERE tooling_id IS NOT NULL;
CREATE INDEX idx_parts_name ON parts(part_name);

-- 注释
COMMENT ON TABLE parts IS '零件主表 - 仅存储零件物理属性，不含客户和价格信息';
COMMENT ON COLUMN parts.part_number IS '零件编号，工厂内部唯一标识';
COMMENT ON COLUMN parts.status IS '零件状态: draft(草稿)/sampling(样件)/mass_production(量产)/obsolete(淘汰)';
COMMENT ON COLUMN parts.thickness IS '厚度参数，定点确认后从报价单写入';
COMMENT ON COLUMN parts.width IS '宽度参数，定点确认后从报价单写入';
COMMENT ON COLUMN parts.cavity_count IS '穴数，定点确认后从报价单写入（同时也存在 dies 表）';
COMMENT ON COLUMN parts.press_tonnage IS '吨位，定点确认后从报价单写入（同时也存在 dies 表）';
```

---

## 🔄 与实际数据库的对应关系

### 字段映射表

| data-model.md 设计 | 实际数据库 | 处理方式 |
|-------------------|-----------|---------|
| `id` (UUID) | `id` (INTEGER) | ✅ 改为 UUID |
| `part_number` | `part_no` | ✅ 改为 part_number |
| `tooling_id` | `die_id` | ✅ 改为 tooling_id（统一命名） |
| `thickness` (新增) | `thickness` | ✅ 保留，定点后写入 |
| `width` (新增) | `width` | ✅ 保留，定点后写入 |
| `cavity_count` | ❌ 不存在 | ✅ 新增 |
| `press_tonnage` | ❌ 不存在 | ✅ 新增 |
| `sdr_drawing_path` (新增) | `sdr_drawing_path` | ✅ 保留 |
| ❌ 不存在 | `customer_name` | ⛔ 删除（移到 part_customer_aliases） |
| ❌ 不存在 | `customer_part_no` | ⛔ 删除（移到 part_customer_aliases） |
| ❌ 不存在 | `material_unit_price` | ⛔ 删除（移到 price_accounts） |
| ❌ 不存在 | `scrap_price` | ⛔ 删除（移到 price_accounts） |

---

## 🎯 设计原则

### 1. 单一职责
**parts 表只存储零件的物理属性和状态**

✅ 应该存储:
- 零件编号、名称、状态
- 技术参数（thickness, width, cavity_count, press_tonnage）
- 物理属性（重量、材质）
- 模具关联、图纸路径

⛔ 不应该存储:
- 客户信息（→ part_customer_aliases）
- 价格信息（→ price_accounts）
- 报价信息（→ quotes）

### 2. 支持一对多关系
- 一个零件可以卖给多个客户
- 每个客户有不同的件号和价格
- 通过 part_customer_aliases 和 price_accounts 实现

### 3. 数据流转清晰
```
报价阶段:
  quote_items.thickness
  quote_items.width
  quote_items.cavity_count
  quote_items.press_tonnage
         ↓
定点确认后:
  写入 parts 表
  （作为零件的最终确定参数）
```

### 4. 冗余存储的合理性
**cavity_count 和 press_tonnage 在 parts 和 dies 都存储**

理由:
- parts 表: 便于查询零件信息时不需要 JOIN
- dies 表: 模具的固有属性
- 数据一致性: 定点时同时写入两处

---

## 📊 parts 表与其他表的关系

```
parts (零件主表)
  ├── 1:N → part_customer_aliases (客户别名)
  │         ├── customer_id
  │         ├── customer_part_no
  │         └── customer_part_name
  │
  ├── 1:N → price_accounts (价格台账)
  │         ├── part_id + customer_id (唯一)
  │         ├── material_unit_price
  │         ├── waste_price
  │         └── base_price
  │
  ├── N:1 → toolings (模具)
  │         └── tooling_id
  │
  ├── 1:N → quotes (报价单)
  │         └── part_id
  │
  └── 1:N → production_plans (生产计划)
            └── part_id
```

---

## 🔄 数据迁移策略

### 从实际数据库迁移到新设计

#### 步骤 1: 创建新表结构
```sql
-- 创建新的 parts 表（UUID 主键）
CREATE TABLE parts_new (
    -- 按照上面的设计创建
);
```

#### 步骤 2: 迁移零件基础数据
```sql
-- 迁移零件数据，排除客户和价格字段
INSERT INTO parts_new (
    id,                    -- 需要生成新的 UUID
    part_number,           -- 从 part_no 映射
    part_name,
    status,
    thickness,             -- 保留
    width,                 -- 保留
    material_type,
    net_weight,
    gross_weight,
    drawing_path,
    sdr_drawing_path,      -- 保留
    surface_treatment_type,
    created_at,
    updated_at
)
SELECT 
    gen_random_uuid(),     -- 生成新 UUID
    part_no,               -- 映射字段名
    part_name,
    status,
    thickness,
    width,
    material_type,
    net_weight,
    gross_weight,
    drawing_path,
    sdr_drawing_path,
    NULL,                  -- surface_treatment_type 需要手动补充
    created_at,
    updated_at
FROM parts_old
WHERE is_deleted = FALSE;
```

#### 步骤 3: 迁移客户关联
```sql
-- 提取客户信息到 part_customer_aliases
INSERT INTO part_customer_aliases (
    id,
    part_id,               -- 需要映射到新 UUID
    customer_name,         -- 从 parts_old.customer_name
    customer_part_no,      -- 从 parts_old.customer_part_no
    created_at
)
SELECT 
    gen_random_uuid(),
    pn.id,                 -- 映射到新 parts 表的 UUID
    po.customer_name,
    po.customer_part_no,
    po.created_at
FROM parts_old po
JOIN parts_new pn ON pn.part_number = po.part_no
WHERE po.customer_name IS NOT NULL;
```

#### 步骤 4: 迁移价格数据
```sql
-- 提取价格信息到 price_accounts
INSERT INTO price_accounts (
    id,
    part_id,
    customer_id,           -- 需要查询 customers 表
    material_unit_price,   -- 从 parts_old
    waste_price,           -- 从 parts_old.scrap_price
    created_at
)
SELECT 
    gen_random_uuid(),
    pn.id,
    c.id,                  -- 从 customers 表查询
    po.material_unit_price,
    po.scrap_price,
    po.created_at
FROM parts_old po
JOIN parts_new pn ON pn.part_number = po.part_no
JOIN customers c ON c.name = po.customer_name
WHERE po.material_unit_price IS NOT NULL;
```

---

## ✅ 决策总结

### 最终设计特点

1. ✅ **UUID 主键** - 分布式友好
2. ✅ **完整字段名** - part_number 而非 part_no
3. ✅ **技术参数齐全** - thickness, width, cavity_count, press_tonnage
4. ✅ **职责清晰** - 只存零件属性，不存客户和价格
5. ✅ **支持一对多** - 通过关联表支持多客户、多价格
6. ✅ **合理冗余** - 穴数和吨位在 parts 和 dies 都存

### 与 data-model.md 的差异

**新增字段**:
- ✅ `thickness` - 从实际数据库保留
- ✅ `width` - 从实际数据库保留
- ✅ `sdr_drawing_path` - 从实际数据库保留（SDR 技术图纸）

**删除字段**（相比实际数据库）:
- ⛔ `customer_name` - 移到 part_customer_aliases
- ⛔ `customer_part_no` - 移到 part_customer_aliases
- ⛔ `material_unit_price` - 移到 price_accounts
- ⛔ `scrap_price` - 移到 price_accounts

---

## 📝 下一步

parts 表设计已确定，接下来讨论：

1. ✅ **parts** - 已完成
2. ✅ **part_name_dict** - 已实现（三级分类）
3. 🔄 **part_customer_aliases** - 待讨论
4. 🔄 **price_accounts** - 待讨论
5. 🔄 **annual_price_records** - 待讨论
6. 🔄 **price_adjustments** - 待讨论

---

**决策完成时间**: 2026-07-04
