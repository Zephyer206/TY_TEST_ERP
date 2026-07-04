# 数据库完全规范化方案 - 修订版

## 🔍 实际数据分析结果

### 从实际数据中发现的高复用字段

#### 1. **零件名称** (internal_name) - 🔴 极高复用率
**实际数据样本**：
- "弹簧片-摩擦片保持（右）" - 出现 6 次
- "弹簧片-摩擦片保持" - 出现 4 次
- 同一零件名称，不同零件编号

**问题**：
- ❌ 相同零件名称重复录入，浪费存储
- ❌ 可能存在拼写差异（如：有无空格、括号全半角）
- ❌ 无法统计某个零件名称的总用量

**表分布**：
- `parts.internal_name` - String(200)
- `quotes` 通过 part_id 关联获取
- `production_plans` 通过 part_id 关联获取
- `sampling_tasks` 通过 part_id 关联获取

#### 2. **客户** (customer) - 🔴 高优先级（已规范化）
**实际数据样本**：
- "上海万向钱潮A-A" - 多次出现
- 已有独立表 `tooling_customers`

**状态**：✅ 已完成规范化，现有客户（ID ≤ 89）受删除保护

#### 3. **材质** (material_name) - 🔴 高复用率（但数据缺失严重）
**实际数据样本**：
- "" (空) - 10 次
- "成型机 SUS 301" - 2 次

**问题**：
- ❌ 大量数据为空
- ❌ 材质名称不标准（混合了工艺和材质）
- ❌ 缺少材质属性（密度、规格等）

**表分布**：
- `parts.material_name` - String(100)
- `quotes.snapshot_mat_name` - String(100) (报价快照)
- `sampling_tasks.material_name` - String(100)

#### 4. **机台吨位** (press_tonnage + machine_type) - 🔴 高复用率
**核心概念**：吨位就是机台类型，需要合并统一

**问题**：
- ❌ 吨位和机台类型分散在多处
- ❌ 在 parts 表中 press_tonnage 是 String(50)
- ❌ 在 quotes 表中 press_tonnage 是 Integer，machine_type 是 String(100)
- ❌ 数据类型不统一
- ❌ 吨位是标准值，应该字典化

**表分布**：
- `parts.press_tonnage` - String(50)
- `quotes.press_tonnage` - Integer
- `quotes.machine_type` - String(100)
- `machines.tonnage` - Integer
- `machines.machine_type` - String(50) + 枚举

#### 5. **模具类型** (mold_type) - 🔴 高复用率
**提升为高优先级**

**表分布**：
- `parts.mold_type` - String(50)
- `quotes.mold_type` - String(50)
- `tooling_molds.mold_type` - String(100)
- `die.die_type` - String(50) + 枚举

#### 6. **车型** (vehicle_model) - 🟡 中复用率（但数据缺失）
**实际数据样本**：
- 大部分为 null

**表分布**：
- `parts.vehicle_model` - String(100)
- `quotes.vehicle_model` - String(100)
- `sampling_tasks.vehicle_model` - String(100)

---

## 📊 Quotes 表完整字段分析

### Quotes 表中需要字典化的字段

| 字段名 | 当前类型 | 是否重复 | 优先级 | 说明 |
|--------|---------|---------|--------|------|
| `customer_id` | Integer FK | ✅ 已规范 | 🔴 高 | 客户外键（已完成） |
| `snapshot_mat_name` | String(100) | ✅ 高 | 🔴 高 | 材质名称快照 |
| `machine_type` + `press_tonnage` | String + Integer | ✅ 高 | 🔴 高 | 机台吨位（合并） |
| `mold_type` | String(50) | ✅ 高 | 🔴 高 | 模具类型（已提升） |
| `vehicle_model` | String(100) | ✅ 中 | 🟡 中 | 车型 |
| `pricing_mode` | String(50) | ❌ 固定值 | ⚪ 枚举 | 定价模式 |
| `mold_discount_mode` | String(50) | ❌ 固定值 | ⚪ 枚举 | 模具折扣模式 |
| `approval_status` | String(50) | ❌ 固定值 | ⚪ 枚举 | 审批状态（已枚举）|
| `nomination_status` | String(50) | ❌ 固定值 | ⚪ 枚举 | 定点状态（已枚举）|

### Quotes 表中的其他字段（不需要字典）
- `thickness`, `width`, `press_stroke` - 数值，每个报价不同
- `cavity_count`, `scrap_rate`, `gross_weight` - 数值
- `stamping_fee`, `surface_fee`, `treatment_fee` - 价格
- `final_price`, `profit_margin` - 计算结果
- `mold_cost`, `mold_life` - 数值
- `inspection_fee`, `packaging_fee` - 价格
- `treatment_items` - JSON，动态内容

---

## 🎯 最终字典表清单（按优先级）

### 🔴 极高优先级（立即实施）

#### 1. **零件名称字典** `part_name_dict`
```sql
CREATE TABLE part_name_dict (
  id SERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL UNIQUE COMMENT '零件名称（标准化）',
  name_en VARCHAR(200) COMMENT '英文名称',
  category VARCHAR(100) COMMENT '一级分类（弹簧片、摩擦片、支架等）',
  sub_category VARCHAR(100) COMMENT '二级分类',
  description TEXT COMMENT '描述',
  
  -- 元数据
  usage_count INT DEFAULT 0 COMMENT '使用次数（统计用）',
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  
  -- 审计
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by INT,
  
  INDEX idx_name (name),
  INDEX idx_category (category),
  INDEX idx_active (is_active)
);
```

**初始数据来源**：
```sql
-- 从现有 parts 表提取并去重
INSERT INTO part_name_dict (name, usage_count)
SELECT internal_name, COUNT(*) as cnt
FROM parts
WHERE internal_name IS NOT NULL AND internal_name != ''
GROUP BY internal_name
ORDER BY cnt DESC;
```

#### 2. **材质字典** `material_dict`
```sql
CREATE TABLE material_dict (
  id SERIAL PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE COMMENT '材质代码（标准）',
  name VARCHAR(100) NOT NULL COMMENT '材质名称',
  name_cn VARCHAR(100) COMMENT '中文俗称',
  
  -- 物理属性
  density DECIMAL(10, 4) COMMENT '密度 g/cm³',
  thickness_range VARCHAR(100) COMMENT '常用厚度范围',
  
  -- 分类
  category VARCHAR(50) COMMENT '大类（冷轧板、热轧板、不锈钢、铝合金等）',
  standard VARCHAR(100) COMMENT '执行标准（GB/T、JIS等）',
  
  -- 价格相关（可选）
  default_price DECIMAL(12, 4) COMMENT '默认单价（元/吨）',
  scrap_price DECIMAL(12, 4) COMMENT '废料单价（元/吨）',
  
  -- 元数据
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by INT,
  
  INDEX idx_code (code),
  INDEX idx_name (name),
  INDEX idx_category (category),
  INDEX idx_active (is_active)
);
```

**初始数据示例**：
```sql
INSERT INTO material_dict (code, name, name_cn, density, category, standard) VALUES
('SPCC', 'SPCC冷轧板', '冷轧钢板', 7.85, '冷轧板', 'JIS G3141'),
('08AL', '08AL深冲钢', '深冲板', 7.85, '冷轧板', 'GB/T 5213'),
('Q235', 'Q235普通碳钢', '碳钢板', 7.85, '热轧板', 'GB/T 700'),
('SUS304', 'SUS304不锈钢', '304不锈钢', 7.93, '不锈钢', 'JIS G4305'),
('SUS301', 'SUS301不锈钢', '301不锈钢', 7.93, '不锈钢', 'JIS G4305'),
('DC01', 'DC01冷轧钢', '欧标冷轧板', 7.85, '冷轧板', 'EN 10130');
```

#### 3. **客户** - ✅ 已完成
现有表 `tooling_customers` 已规范化，无需改动。

#### 4. **机台吨位字典** `machine_tonnage_dict` (合并 tonnage + machine_type)
```sql
CREATE TABLE machine_tonnage_dict (
  id SERIAL PRIMARY KEY,
  tonnage INT NOT NULL COMMENT '吨位值（统一为整数）',
  machine_type VARCHAR(50) NOT NULL COMMENT '机台类型',
  display_name VARCHAR(100) NOT NULL COMMENT '显示名称',
  
  -- 分类
  size_category VARCHAR(50) COMMENT '规模分类（小型、中型、大型、特大型）',
  type_category VARCHAR(50) COMMENT '类型分类（冲床、液压机、伺服压力机等）',
  
  -- 技术参数
  min_stroke INT COMMENT '最小行程 mm',
  max_stroke INT COMMENT '最大行程 mm',
  work_table_size VARCHAR(100) COMMENT '工作台尺寸',
  
  -- 元数据
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE (tonnage, machine_type),
  INDEX idx_tonnage (tonnage),
  INDEX idx_machine_type (machine_type),
  INDEX idx_size_category (size_category),
  INDEX idx_active (is_active)
);
```

**初始数据**：
```sql
INSERT INTO machine_tonnage_dict (tonnage, machine_type, display_name, size_category, type_category, sort_order) VALUES
-- 冲床系列
(25, 'punch_press', '25吨冲床', '小型', '冲床', 1),
(40, 'punch_press', '40吨冲床', '小型', '冲床', 2),
(63, 'punch_press', '63吨冲床', '小型', '冲床', 3),
(80, 'punch_press', '80吨冲床', '中型', '冲床', 4),
(110, 'punch_press', '110吨冲床', '中型', '冲床', 5),
(160, 'punch_press', '160吨冲床', '中型', '冲床', 6),
(200, 'punch_press', '200吨冲床', '中型', '冲床', 7),
(250, 'punch_press', '250吨冲床', '大型', '冲床', 8),
(315, 'punch_press', '315吨冲床', '大型', '冲床', 9),
(400, 'punch_press', '400吨冲床', '大型', '冲床', 10),
(500, 'punch_press', '500吨冲床', '大型', '冲床', 11),
(630, 'punch_press', '630吨冲床', '特大型', '冲床', 12),
(800, 'punch_press', '800吨冲床', '特大型', '冲床', 13),
(1000, 'punch_press', '1000吨冲床', '特大型', '冲床', 14),
(1250, 'punch_press', '1250吨冲床', '特大型', '冲床', 15),

-- 液压机系列
(100, 'hydraulic_press', '100吨液压机', '中型', '液压机', 20),
(200, 'hydraulic_press', '200吨液压机', '中型', '液压机', 21),
(315, 'hydraulic_press', '315吨液压机', '大型', '液压机', 22),
(500, 'hydraulic_press', '500吨液压机', '大型', '液压机', 23),
(630, 'hydraulic_press', '630吨液压机', '特大型', '液压机', 24),

-- 伺服压力机系列
(80, 'servo_press', '80吨伺服压力机', '中型', '伺服压力机', 30),
(110, 'servo_press', '110吨伺服压力机', '中型', '伺服压力机', 31),
(160, 'servo_press', '160吨伺服压力机', '中型', '伺服压力机', 32),
(200, 'servo_press', '200吨伺服压力机', '中型', '伺服压力机', 33);
```

#### 5. **模具类型字典** `mold_type_dict` (提升为高优先级)
```sql
CREATE TABLE mold_type_dict (
  id SERIAL PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE COMMENT '类型代码',
  name VARCHAR(100) NOT NULL COMMENT '类型名称',
  name_en VARCHAR(100) COMMENT '英文名称',
  description TEXT COMMENT '描述说明',
  
  -- 特性
  typical_lifecycle INT COMMENT '典型寿命（万次）',
  complexity_level VARCHAR(50) COMMENT '复杂度（简单、中等、复杂）',
  typical_tonnage_range VARCHAR(100) COMMENT '适用吨位范围',
  
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_code (code),
  INDEX idx_active (is_active)
);
```

**初始数据**：
```sql
INSERT INTO mold_type_dict (code, name, name_en, typical_lifecycle, complexity_level, sort_order) VALUES
('progressive', '连续模', 'Progressive Die', 1000000, '复杂', 1),
('transfer', '传递模', 'Transfer Die', 800000, '复杂', 2),
('single', '单工序模', 'Single Stage Die', 500000, '简单', 3),
('compound', '复合模', 'Compound Die', 600000, '中等', 4),
('drawing', '拉伸模', 'Drawing Die', 500000, '中等', 5),
('bending', '弯曲模', 'Bending Die', 600000, '简单', 6),
('blanking', '冲裁模', 'Blanking Die', 800000, '简单', 7),
('trimming', '修边模', 'Trimming Die', 500000, '简单', 8),
('forming', '成型模', 'Forming Die', 600000, '中等', 9),
('fine_blanking', '精冲模', 'Fine Blanking Die', 1200000, '复杂', 10);
```

### 🟡 中优先级（第二阶段）

#### 6. **车型字典** `vehicle_model_dict`
```sql
CREATE TABLE vehicle_model_dict (
  id SERIAL PRIMARY KEY,
  model VARCHAR(100) NOT NULL COMMENT '车型全称',
  short_name VARCHAR(50) COMMENT '简称',
  
  -- 制造商信息
  manufacturer VARCHAR(100) COMMENT '制造商',
  manufacturer_code VARCHAR(50) COMMENT '厂商代码',
  brand VARCHAR(100) COMMENT '品牌',
  
  -- 车型信息
  model_year VARCHAR(20) COMMENT '年款',
  category VARCHAR(50) COMMENT '车型分类（轿车、SUV、MPV、卡车等）',
  platform VARCHAR(100) COMMENT '平台',
  
  -- 元数据
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by INT,
  
  UNIQUE (manufacturer, model, model_year),
  INDEX idx_model (model),
  INDEX idx_manufacturer (manufacturer),
  INDEX idx_active (is_active)
);
```

#### 6. **模具类型字典** `mold_type_dict`
```sql
CREATE TABLE mold_type_dict (
  id SERIAL PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE COMMENT '类型代码',
  name VARCHAR(100) NOT NULL COMMENT '类型名称',
  name_en VARCHAR(100) COMMENT '英文名称',
  description TEXT COMMENT '描述说明',
  
  -- 特性
  typical_lifecycle INT COMMENT '典型寿命（万次）',
  complexity_level VARCHAR(50) COMMENT '复杂度（简单、中等、复杂）',
  
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_code (code),
  INDEX idx_active (is_active)
);
```

**初始数据**：
```sql
INSERT INTO mold_type_dict (code, name, name_en, typical_lifecycle, complexity_level, sort_order) VALUES
('progressive', '连续模', 'Progressive Die', 1000000, '复杂', 1),
('transfer', '传递模', 'Transfer Die', 800000, '复杂', 2),
('single', '单工序模', 'Single Stage Die', 500000, '简单', 3),
('compound', '复合模', 'Compound Die', 600000, '中等', 4),
('drawing', '拉伸模', 'Drawing Die', 500000, '中等', 5),
('bending', '弯曲模', 'Bending Die', 600000, '简单', 6),
('blanking', '冲裁模', 'Blanking Die', 800000, '简单', 7),
('trimming', '修边模', 'Trimming Die', 500000, '简单', 8);
```

#### 7. **机台类型字典** `machine_type_dict`
```sql
CREATE TABLE machine_type_dict (
  id SERIAL PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  name_en VARCHAR(100),
  description TEXT,
  
  -- 特性
  typical_tonnage_range VARCHAR(100) COMMENT '常用吨位范围',
  stroke_range VARCHAR(100) COMMENT '行程范围',
  
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_code (code)
);
```

**初始数据**：
```sql
INSERT INTO machine_type_dict (code, name, name_en, sort_order) VALUES
('punch_press', '冲床', 'Punch Press', 1),
('hydraulic_press', '液压机', 'Hydraulic Press', 2),
('servo_press', '伺服压力机', 'Servo Press', 3),
('pneumatic_press', '气动压力机', 'Pneumatic Press', 4),
('high_speed_press', '高速冲床', 'High Speed Press', 5);
```

---

## 🔄 表改造方案

### Parts 表改造
```sql
ALTER TABLE parts
  -- 新增字典表外键
  ADD COLUMN part_name_id INT REFERENCES part_name_dict(id),
  ADD COLUMN material_id INT REFERENCES material_dict(id),
  ADD COLUMN vehicle_model_id INT REFERENCES vehicle_model_dict(id),
  ADD COLUMN mold_type_id INT REFERENCES mold_type_dict(id),
  ADD COLUMN machine_tonnage_id INT REFERENCES machine_tonnage_dict(id),
  
  -- 添加索引
  ADD INDEX idx_part_name_id (part_name_id),
  ADD INDEX idx_material_id (material_id),
  ADD INDEX idx_vehicle_model_id (vehicle_model_id),
  ADD INDEX idx_mold_type_id (mold_type_id),
  ADD INDEX idx_machine_tonnage_id (machine_tonnage_id);

-- 保留旧字段暂不删除，用于数据迁移和向后兼容
-- internal_name, material_name, vehicle_model, mold_type, press_tonnage 保留
```

### Quotes 表改造
```sql
ALTER TABLE quotes
  -- 新增字典表外键
  ADD COLUMN material_id INT REFERENCES material_dict(id) COMMENT '材质ID（快照关联）',
  ADD COLUMN vehicle_model_id INT REFERENCES vehicle_model_dict(id),
  ADD COLUMN mold_type_id INT REFERENCES mold_type_dict(id),
  ADD COLUMN machine_tonnage_id INT REFERENCES machine_tonnage_dict(id),
  
  -- 添加索引
  ADD INDEX idx_material_id (material_id),
  ADD INDEX idx_vehicle_model_id (vehicle_model_id),
  ADD INDEX idx_mold_type_id (mold_type_id),
  ADD INDEX idx_machine_tonnage_id (machine_tonnage_id);

-- 保留 snapshot_mat_name, press_tonnage, machine_type 等旧字段用于过渡
```

### Machines 表改造（如果需要）
```sql
ALTER TABLE machines
  ADD COLUMN machine_tonnage_id INT REFERENCES machine_tonnage_dict(id),
  
  ADD INDEX idx_machine_tonnage_id (machine_tonnage_id);
```

---

## 📝 数据迁移策略

### 阶段 1：创建字典表并导入基础数据
1. 创建所有字典表
2. 导入标准数据（吨位、模具类型、机台类型）
3. 从现有数据提取并去重（零件名称、材质）

### 阶段 2：关联现有数据
```sql
-- 示例：关联零件名称
UPDATE parts p
SET part_name_id = (
  SELECT id FROM part_name_dict d
  WHERE d.name = p.internal_name
)
WHERE p.internal_name IS NOT NULL AND p.internal_name != '';

-- 示例：关联材质
UPDATE parts p
SET material_id = (
  SELECT id FROM material_dict d
  WHERE d.code = p.material_name OR d.name = p.material_name
)
WHERE p.material_name IS NOT NULL AND p.material_name != '';

-- 示例：关联吨位（需要处理字符串转整数，并匹配机台类型）
UPDATE parts p
SET machine_tonnage_id = (
  SELECT id FROM machine_tonnage_dict t
  WHERE t.tonnage = CAST(REGEXP_REPLACE(p.press_tonnage, '[^0-9]', '', 'g') AS INT)
  AND t.machine_type = 'punch_press'  -- 默认冲床，可根据实际情况调整
  LIMIT 1
)
WHERE p.press_tonnage IS NOT NULL AND p.press_tonnage ~ '[0-9]+';

-- 示例：关联模具类型
UPDATE parts p
SET mold_type_id = (
  SELECT id FROM mold_type_dict d
  WHERE d.name = p.mold_type OR d.code = p.mold_type
)
WHERE p.mold_type IS NOT NULL AND p.mold_type != '';
```

### 阶段 3：前端改造
1. 下拉选择框从字典表获取选项
2. 保留"快捷新增"功能，新增到字典表
3. 显示时优先使用字典表数据

### 阶段 4：逐步弃用旧字段
1. 新数据只写入字典表ID
2. 查询时优先使用字典表关联
3. 确认无问题后删除旧字段

---

## ❓ 需要您决策的问题

### 1. 优先级确认
我建议的实施顺序：
1. 🔴 客户字典（高优先级，已完成）
2. 🔴 零件名称字典
3. 🔴 材质字典
4. 🔴 机台吨位字典（合并后）
5. 🔴 模具类型字典
6. 🟡 车型字典

**您是否同意？** _______________

### 2. 材质数据来源
材质字典的初始数据：
- [ ] 从现有 parts 表提取（但数据不规范）
- [ ] 我提供标准材质库（您补充）
- [ ] 您提供公司常用材质清单

**您的选择**：_______________

### 3. 前端管理界面
是否需要：
- [ ] 独立的"字典管理"模块（可批量维护所有字典）
- [ ] 每个字典的独立管理页面
- [ ] 只在表单内"快捷新增"（已有）
- [ ] Excel 批量导入功能

**您的选择**：_______________

### 4. 数据迁移时机
- [ ] 方案A：一次性迁移所有数据（停机维护）
- [ ] 方案B：渐进式迁移（新旧字段并存，逐步替换）
- [ ] 方案C：新数据用新字段，旧数据保持不变

**您的选择**：_______________

### 5. 字典表扩展字段
是否需要：
- [ ] 英文名称（国际化）
- [ ] 图片/图标
- [ ] 自定义属性（JSON 字段）
- [ ] 审批流程（新增字典项需审批）

**您的选择**：_______________

---

## 📊 工作量估算

### 完整实施（所有5个字典表）
- 后端开发：2-3 天
  - 模型改造：0.5 天
  - API 开发：1 天
  - 数据迁移脚本：1 天
  - 测试：0.5 天

- 前端开发：1.5-2 天
  - 字典管理页面：1 天
  - 表单改造：0.5-1 天

- **总计：3.5-5 天**

### 高优先级（零件名称、材质、机台吨位、模具类型）
- 后端：2 天
- 前端：1.5 天
- **总计：3.5 天**

---

请您审阅并回答决策问题，我会立即开始实施！
