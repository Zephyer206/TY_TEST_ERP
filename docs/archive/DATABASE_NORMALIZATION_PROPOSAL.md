# 数据库规范化 - 字典表设计方案

## 📊 第一部分：现有选项字段分析

### 1️⃣ **零件名称** (internal_name)
- **当前状态**: `parts.internal_name` - String(200), 自由文本
- **使用场景**: 
  - parts 表 - 零件基础信息
  - quotes 表 - 通过 part_id 关联
  - production_plans 表 - 通过 part_id 关联
  - coating_records 表 - 通过 part_id 关联
- **重复性**: ⚠️ 高 - 同一零件名称可能拼写不一致
- **需要字典表**: ✅ **是（高优先级）**

### 2️⃣ **客户** (customers)
- **当前状态**: ✅ 已有独立表 `tooling_customers`
- **使用场景**: parts, quotes, tooling 等多处引用
- **规范性**: ✅ 已规范化
- **需要改进**: ⚠️ 删除保护已实现，但需要增加更多元数据

### 3️⃣ **车型** (vehicle_model)
- **当前状态**: 
  - `parts.vehicle_model` - String(100)
  - `quotes.vehicle_model` - String(100)
  - `sampling_tasks.vehicle_model` - String(100)
- **重复性**: ⚠️ 中高 - 同一车型在多处重复录入
- **需要字典表**: ✅ **是（高优先级）**
- **示例值**: "比亚迪 汉", "大众 ID.4", "特斯拉 Model 3"

### 4️⃣ **材质** (material_name)
- **当前状态**: 
  - `parts.material_name` - String(100)
  - `quotes.snapshot_mat_name` - String(100)
  - `sampling_tasks.material_name` - String(100)
- **重复性**: ⚠️ 高 - 材质名称应该标准化
- **需要字典表**: ✅ **是（高优先级）**
- **示例值**: "SPCC", "08AL", "Q235", "不锈钢304"

### 5️⃣ **模具类型** (mold_type)
- **当前状态**: 
  - `parts.mold_type` - String(50)
  - `quotes.mold_type` - String(50)
  - `tooling_molds.mold_type` - String(100)
  - `die.die_type` - String(50), 有枚举: progressive, transfer, single_stage
- **重复性**: ⚠️ 中 - 选项相对固定
- **需要字典表**: ✅ **是（中优先级）**
- **示例值**: "连续模", "传递模", "单工序模", "复合模"

### 6️⃣ **机台类型** (machine_type)
- **当前状态**: 
  - `quotes.machine_type` - String(100)
  - `machines.machine_type` - String(50), 有枚举: punch_press, hydraulic_press, other
- **重复性**: ⚠️ 低 - 已有部分枚举
- **需要字典表**: ⚠️ **考虑（低优先级）** - 可以用枚举

### 7️⃣ **吨位** (press_tonnage)
- **当前状态**: 
  - `parts.press_tonnage` - String(50)
  - `quotes.press_tonnage` - Integer
  - `machines.tonnage` - Integer
- **重复性**: ⚠️ 中 - 吨位是标准值
- **需要字典表**: ✅ **是（中优先级）**
- **示例值**: 25, 40, 63, 80, 110, 160, 200, 315, 400, 630

### 8️⃣ **表面处理** (surface_treatment)
- **当前状态**: 
  - `quotes.SurfaceTreatment` 枚举: none, electroplate, powder_coating, painting
- **重复性**: ✅ 已枚举，选项固定
- **需要字典表**: ❌ **否** - 枚举已足够

### 9️⃣ **涂装类型** (coating_type)
- **当前状态**: 
  - `coating_recipes.coating_type` 枚举: powder, liquid, electrophoretic
  - `coating_recipes.primer_type` - String(100), 自由文本
  - `coating_recipes.topcoat_type` - String(100), 自由文本
- **需要字典表**: ⚠️ **考虑（低优先级）** - 底漆和面漆类型可以字典化

### 🔟 **包装类型** (packaging_type)
- **当前状态**: 需要查看 packaging 模型
- **重复性**: 待确认
- **需要字典表**: ⚠️ **待评估**

### 1️⃣1️⃣ **客户件号** (customer_product_no)
- **当前状态**: 
  - `parts.customer_product_no` - String(100)
  - `quotes.customer_product_no` - String(100)
  - `tooling_molds.customer_product_no` - String(100)
- **重复性**: ❌ 低 - 每个零件通常唯一
- **需要字典表**: ❌ **否** - 不适合字典表

### 1️⃣2️⃣ **状态字段** (status)
- **当前状态**: 多处使用枚举
  - `parts.part_status` - PartState 枚举
  - `quotes.approval_status` - QuoteState 枚举
  - `production_plans.status` - PlanStatus 枚举
  - `tooling_molds.lifecycle_status` - ToolingState 枚举
- **需要字典表**: ❌ **否** - 枚举已足够

---

## 🎯 第二部分：推荐字典表清单

### 优先级分类

#### 🔴 **高优先级（必须实现）**

1. **零件名称字典** - `part_name_dict`
2. **材质字典** - `material_dict`
3. **车型字典** - `vehicle_model_dict`

#### 🟡 **中优先级（建议实现）**

4. **模具类型字典** - `mold_type_dict`
5. **吨位字典** - `press_tonnage_dict`

#### 🟢 **低优先级（可选实现）**

6. **底漆类型字典** - `primer_type_dict`
7. **面漆类型字典** - `topcoat_type_dict`
8. **包装类型字典** - `packaging_type_dict` (需进一步确认)

---

## 💡 第三部分：详细表结构设计（高优先级）

### 1. 零件名称字典表
```sql
CREATE TABLE part_name_dict (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(200) NOT NULL UNIQUE COMMENT '零件名称',
  name_en VARCHAR(200) COMMENT '英文名称',
  category VARCHAR(100) COMMENT '分类（如：弹簧片、摩擦片、支架）',
  sub_category VARCHAR(100) COMMENT '子分类',
  is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
  sort_order INT DEFAULT 0 COMMENT '排序',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by INT COMMENT '创建人',
  
  INDEX idx_name (name),
  INDEX idx_category (category),
  INDEX idx_active (is_active)
) COMMENT='零件名称字典表';
```

### 2. 材质字典表
```sql
CREATE TABLE material_dict (
  id INT PRIMARY KEY AUTO_INCREMENT,
  code VARCHAR(50) NOT NULL UNIQUE COMMENT '材质代码（如 SPCC, 08AL）',
  name VARCHAR(100) NOT NULL COMMENT '材质名称',
  name_cn VARCHAR(100) COMMENT '中文名称',
  specification VARCHAR(200) COMMENT '规格说明',
  density DECIMAL(10, 4) COMMENT '密度 g/cm³',
  category VARCHAR(50) COMMENT '分类（冷轧板、不锈钢、铝合金等）',
  standard VARCHAR(100) COMMENT '执行标准（如 GB/T）',
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by INT,
  
  INDEX idx_code (code),
  INDEX idx_name (name),
  INDEX idx_category (category),
  INDEX idx_active (is_active)
) COMMENT='材质字典表';
```

### 3. 车型字典表
```sql
CREATE TABLE vehicle_model_dict (
  id INT PRIMARY KEY AUTO_INCREMENT,
  model VARCHAR(100) NOT NULL UNIQUE COMMENT '车型',
  manufacturer VARCHAR(100) COMMENT '制造商/品牌',
  manufacturer_code VARCHAR(50) COMMENT '制造商代码',
  model_year VARCHAR(20) COMMENT '年款',
  category VARCHAR(50) COMMENT '车型分类（轿车、SUV、MPV等）',
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by INT,
  
  INDEX idx_model (model),
  INDEX idx_manufacturer (manufacturer),
  INDEX idx_active (is_active)
) COMMENT='车型字典表';
```

### 4. 模具类型字典表
```sql
CREATE TABLE mold_type_dict (
  id INT PRIMARY KEY AUTO_INCREMENT,
  code VARCHAR(50) NOT NULL UNIQUE COMMENT '模具类型代码',
  name VARCHAR(100) NOT NULL COMMENT '模具类型名称',
  name_en VARCHAR(100) COMMENT '英文名称',
  description TEXT COMMENT '描述',
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  INDEX idx_code (code),
  INDEX idx_active (is_active)
) COMMENT='模具类型字典表';
```

### 5. 吨位字典表
```sql
CREATE TABLE press_tonnage_dict (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tonnage INT NOT NULL UNIQUE COMMENT '吨位值',
  display_name VARCHAR(50) COMMENT '显示名称（如 "25T", "63吨"）',
  category VARCHAR(50) COMMENT '分类（小型、中型、大型）',
  is_active BOOLEAN DEFAULT TRUE,
  sort_order INT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  INDEX idx_tonnage (tonnage),
  INDEX idx_active (is_active)
) COMMENT='吨位字典表';
```

---

## 📝 第四部分：初始数据建议

### 模具类型初始数据
```sql
INSERT INTO mold_type_dict (code, name, name_en, sort_order) VALUES
('progressive', '连续模', 'Progressive Die', 1),
('transfer', '传递模', 'Transfer Die', 2),
('single_stage', '单工序模', 'Single Stage Die', 3),
('compound', '复合模', 'Compound Die', 4),
('drawing', '拉伸模', 'Drawing Die', 5),
('bending', '弯曲模', 'Bending Die', 6);
```

### 吨位初始数据
```sql
INSERT INTO press_tonnage_dict (tonnage, display_name, category, sort_order) VALUES
(25, '25T', '小型', 1),
(40, '40T', '小型', 2),
(63, '63T', '小型', 3),
(80, '80T', '中型', 4),
(110, '110T', '中型', 5),
(160, '160T', '中型', 6),
(200, '200T', '中型', 7),
(250, '250T', '大型', 8),
(315, '315T', '大型', 9),
(400, '400T', '大型', 10),
(630, '630T', '大型', 11),
(800, '800T', '特大型', 12),
(1000, '1000T', '特大型', 13);
```

---

## 🔄 第五部分：表关系改造

### parts 表改造
```sql
ALTER TABLE parts
  ADD COLUMN part_name_id INT COMMENT '零件名称ID（关联part_name_dict）',
  ADD COLUMN material_id INT COMMENT '材质ID（关联material_dict）',
  ADD COLUMN vehicle_model_id INT COMMENT '车型ID（关联vehicle_model_dict）',
  ADD COLUMN mold_type_id INT COMMENT '模具类型ID（关联mold_type_dict）',
  ADD COLUMN press_tonnage_id INT COMMENT '吨位ID（关联press_tonnage_dict）',
  
  ADD FOREIGN KEY (part_name_id) REFERENCES part_name_dict(id),
  ADD FOREIGN KEY (material_id) REFERENCES material_dict(id),
  ADD FOREIGN KEY (vehicle_model_id) REFERENCES vehicle_model_dict(id),
  ADD FOREIGN KEY (mold_type_id) REFERENCES mold_type_dict(id),
  ADD FOREIGN KEY (press_tonnage_id) REFERENCES press_tonnage_dict(id);

-- 保留旧字段用于过渡
-- internal_name, material_name, vehicle_model 等暂时保留
```

### quotes 表改造
```sql
ALTER TABLE quotes
  ADD COLUMN vehicle_model_id INT COMMENT '车型ID',
  ADD COLUMN material_id INT COMMENT '材质ID（快照）',
  ADD COLUMN mold_type_id INT COMMENT '模具类型ID',
  ADD COLUMN press_tonnage_id INT COMMENT '吨位ID',
  
  ADD FOREIGN KEY (vehicle_model_id) REFERENCES vehicle_model_dict(id),
  ADD FOREIGN KEY (material_id) REFERENCES material_dict(id),
  ADD FOREIGN KEY (mold_type_id) REFERENCES mold_type_dict(id),
  ADD FOREIGN KEY (press_tonnage_id) REFERENCES press_tonnage_dict(id);
```

---

## ❓ 第六部分：需要和您讨论的问题

### 问题 1: 数据迁移策略
- **方案A**: 一次性迁移所有现有数据
- **方案B**: 新数据使用字典表，旧数据逐步迁移
- **方案C**: 保留双字段，逐步替换

**您的选择**: _______________

### 问题 2: 字典表优先级
我建议的优先级是：
1. 零件名称（最高）
2. 材质（高）
3. 车型（高）
4. 模具类型（中）
5. 吨位（中）

**您是否同意？如果不同意，请调整**: _______________

### 问题 3: 是否需要额外字段
字典表中是否需要：
- [ ] 英文名称（用于国际化）
- [ ] 图片/图标（用于UI展示）
- [ ] 扩展属性（JSON字段存储额外信息）
- [ ] 审批流程（新增字典项需要审批）

**您的选择**: _______________

### 问题 4: 材质数据来源
材质字典表的初始数据从哪里来？
- [ ] 从现有数据库提取去重
- [ ] 导入标准材质库（需要您提供）
- [ ] 手动录入常用材质

**您的选择**: _______________

### 问题 5: 前端交互
字典项管理是否需要：
- [ ] 独立的"系统配置"页面（管理所有字典）
- [ ] 每个表单内"快捷新增"功能（已实现）
- [ ] 批量导入功能（Excel导入字典数据）

**您的选择**: _______________

---

## 📊 第七部分：影响范围评估

### 需要修改的文件数量估算

#### 后端
- 模型文件: 5-8 个
- API 文件: 8-12 个
- 迁移脚本: 10+ 个

#### 前端
- 表单组件: 10-15 个
- API 调用: 15-20 处

### 预计工作量
- **完全规范化（所有字典表）**: 2-3天
- **高优先级字典表（零件名称、材质、车型）**: 1-1.5天
- **数据迁移和测试**: 0.5-1天

---

## 📋 总结

请您审阅以上分析，并回答第六部分的问题。我会根据您的反馈制定详细的实施计划。

**需要您决定的关键点：**
1. ✅ 字典表优先级排序
2. ✅ 数据迁移策略
3. ✅ 需要哪些额外字段
4. ✅ 初始数据来源
5. ✅ 前端管理界面需求
