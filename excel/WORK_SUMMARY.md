# Excel数据导入项目 - 工作总结

> **历史工作记录，不是设计文档。** 当前数据库与 Excel 导入设计只见 [`../specs/001-erp-system-architecture/data-model.md`](../specs/001-erp-system-architecture/data-model.md)。

## 📊 项目概述

**目标：** 将"五金模具及产品清单表.xls"（95个Sheet，91个客户）导入到数据库

**核心业务逻辑：**
- 一个客户 → 拥有多个零件 → 每个零件对应一个或多个模具
- 支持"左右件"（一出2，不同产品）
- 智能解析TWP规格、模具类型、成型步数

---

## ✅ 已完成的工作

### 1. 数据库表重命名
```sql
ALTER TABLE tooling_customers RENAME TO customers;
ALTER TABLE tooling_molds RENAME TO tooling;
```

### 2. 数据库字段扩展

#### customers 表
- ✅ 无需修改，已满足需求
- `name` - 客户名称
- `sheet_key` - 客户编号（A, B, A-A等）

#### parts 表（新增8个字段）
```sql
ALTER TABLE parts ADD COLUMN customer_product_name VARCHAR(200);  -- 原图产品名称
ALTER TABLE parts ADD COLUMN spec_twph VARCHAR(100);              -- 用料规格原文
ALTER TABLE parts ADD COLUMN thickness NUMERIC(10,3);             -- T: 厚度(mm)
ALTER TABLE parts ADD COLUMN width NUMERIC(10,2);                 -- W: 宽度(mm)
ALTER TABLE parts ADD COLUMN pitch NUMERIC(10,2);                 -- P: 节距(mm)
ALTER TABLE parts ADD COLUMN height NUMERIC(10,2);                -- H: 高度(mm)
ALTER TABLE parts ADD COLUMN gross_weight NUMERIC(10,2);          -- 毛重(g)
ALTER TABLE parts ADD COLUMN net_weight NUMERIC(10,2);            -- 净重(g)
ALTER TABLE parts ADD COLUMN part_position VARCHAR(20);           -- 零件位置(left/right)
```

**已有重要字段：**
- `part_number` - 零件编号（原图产品编号）
- `internal_name` - 本厂产品名称
- `customer_id` - 客户关联
- `material_id` - 材料关联

#### tooling 表（新增12个字段）
```sql
ALTER TABLE tooling ADD COLUMN customer_id INTEGER REFERENCES customers(id);
ALTER TABLE tooling ADD COLUMN customer_product_name VARCHAR(200);
ALTER TABLE tooling ADD COLUMN mold_type VARCHAR(100);            -- 模具类型
ALTER TABLE tooling ADD COLUMN material VARCHAR(100);             -- 材质文本
ALTER TABLE tooling ADD COLUMN material_id INTEGER;               -- 材质外键
ALTER TABLE tooling ADD COLUMN mold_count INTEGER;                -- 模数
ALTER TABLE tooling ADD COLUMN forming_steps INTEGER;             -- 成型步数
ALTER TABLE tooling ADD COLUMN press_tonnage VARCHAR(50);         -- 冲床吨位
ALTER TABLE tooling ADD COLUMN remark TEXT;                       -- 备注
ALTER TABLE tooling ADD COLUMN mold_status VARCHAR(20);           -- 模具状态
ALTER TABLE tooling ADD COLUMN seq INTEGER;                       -- 序号
ALTER TABLE tooling ADD COLUMN is_multi_product BOOLEAN DEFAULT FALSE;  -- 是否左右件
ALTER TABLE tooling ADD COLUMN product_count INTEGER DEFAULT 1;         -- 产品数量
```

**已有重要字段：**
- `tooling_no` - 模具号（本厂产品编号）
- `name` - 模具名称
- `customer_product_no` - 客户零件号
- `cavity_count` - 穴数（VARCHAR，可存"1出2"）
- `ppap_no` - PPAP编号
- `vehicle_model` - 车型

---

## 📋 Excel数据结构

### Sheet组成
1. Sheet 1: 目录
2. Sheet 2: 五金模具进度一览表
3. Sheet 3: 客户名称代号
4. Sheet 4-94: 91个客户Sheet（每个客户的零件和模具清单）

### 每个客户Sheet的列结构
| 列 | Excel字段 | 存储位置 |
|----|----------|---------|
| 0 | 序号 | 不导入 |
| 1 | 客户 | customers.name |
| 2 | 原图产品编号 | parts.part_number |
| 3 | 原图产品名称1 | parts.customer_product_name |
| 4 | 原图产品名称2 | parts.customer_product_name（合并） |
| 5 | 本厂产品编号 | tooling.tooling_no |
| 6 | 本厂产品名称 | parts.internal_name |
| 7 | 模具类型 | tooling.mold_type |
| 8 | 模数 | 智能解析 |
| 9 | 材质 | tooling.material + material_id |
| 10 | 用料规格(T*W*PH) | parts.spec_twph + 拆分字段 |
| 11 | 备注 | tooling.remark |
| 12 | 参考冲床吨位 | tooling.press_tonnage |
| 13 | PPAP编号 | tooling.ppap_no |
| 15 | 车型 | tooling.vehicle_model |
| 16 | 单件毛重量(g) | parts.gross_weight |
| 17 | 单件净重量(g) | parts.net_weight |

---

## 🎯 核心业务逻辑

### 1. 左右件识别（多产品模式）

**特征：**
- 合并单元格（模具类型、材质等信息相同）
- 连续的零件编号（60008581, 60008582）
- 连续的模具号（TYAA-Q0063, TYAA-Q0064）

**处理方式：**
```python
# 检测到左右件时：
tooling.is_multi_product = True
tooling.product_count = 2

# 创建2条parts记录
parts[0].part_position = 'left'
parts[1].part_position = 'right'

# 共用同一个tooling记录
```

### 2. TWP解析

**格式：** "0.4*116+55 (1出2)"

**解析逻辑：**
```python
# 提取尺寸
thickness = 0.4   # T
width = 116       # W
pitch = 55        # P (或 116+55=171)

# 提取穴数
cavity_count = 2  # 从"1出2"提取

# 存储
parts.thickness = 0.4
parts.width = 116
parts.pitch = 55
parts.spec_twph = "0.4*116+55 (1出2)"  # 保留原文
tooling.cavity_count = "1出2"          # 原文
```

**注意：** 
- "1出2"可能出现在TWP中，也可能出现在模数列
- 有合并单元格的情况

### 3. 模具类型和成型步数

**连续模：**
```python
mold_type = "连续模"
forming_steps = None
cavity_count = 从TWP解析  # "1出2" -> 2
```

**工程模：**
```python
mold_type = "工程模9"
forming_steps = 9         # 提取数字
mold_count = 9            # 9套 = 9个成型步骤
cavity_count = None       # 工程模通常没有
```

### 4. 材料匹配

**双重存储：**
```python
# 1. 保存原文
tooling.material = "SUS301-3/4H"

# 2. 匹配标准材料
material_name = MATERIAL_MAPPING.get("SUS301-3/4H")  # -> "SUS301 3/4H"
material_id = get_material_id(material_name)
tooling.material_id = material_id
```

---

## 📦 已准备好的资源

### 1. 材料分类数据
**文件：** `materials_classified.json`

**内容：** 193种标准材料
```json
[
  {
    "name": "SUS301 3/4H",
    "category": "不锈钢",
    "base_material": "SUS301",
    "grade": "3/4H",
    "count": 1664,
    "variants": ["SUS301-3/4H", "SUS301-CSP3/4H", "SUS301 3/4H", ...]
  },
  ...
]
```

### 2. 客户列表
**文件：** `customer_list.txt`

**内容：** 91个客户的名称和编号

### 3. 导入脚本框架
**文件：** `excel/import_data.py`

**已实现：**
- TWP解析函数 `parse_twph()`
- 模具信息解析函数 `parse_mold_info()`
- 材料导入函数 `import_materials()`
- 客户导入函数 `import_customers()`

**待实现：**
- 合并单元格检测
- 主数据导入逻辑
- 左右件识别和处理

---

## 🚀 下一步任务

### Phase 1: 完善导入脚本

1. **实现合并单元格检测**
```python
def detect_merged_cells(sheet, row_index):
    """
    检测当前行是否与上一行是合并单元格
    通过比较模具类型、材质等关键字段
    """
    pass
```

2. **实现主数据导入逻辑**
```python
async def import_main_data(workbook):
    """
    遍历所有客户Sheet
    识别左右件
    导入parts和tooling
    """
    pass
```

3. **处理特殊情况**
- 合并单元格跨多行
- TWP格式变化（"116+55" vs "116*55"）
- 材料名称匹配失败的fallback

### Phase 2: 测试和验证

1. 先导入少量数据（1-2个客户）测试
2. 验证左右件识别准确性
3. 验证TWP解析正确性
4. 验证材料匹配率

### Phase 3: 全量导入

1. 导入所有91个客户
2. 生成导入报告
3. 统计数据质量

---

## 📝 重要注意事项

### 1. xlrd库处理合并单元格

**xlrd不直接提供合并单元格信息**，需要通过比较相邻行的值来判断：

```python
def is_merged_with_previous(current_row, previous_row, key_columns):
    """
    通过比较关键列的值来判断是否为合并单元格
    key_columns: [7, 9]  # 模具类型、材质
    """
    for col in key_columns:
        if current_row[col] != '' and current_row[col] != previous_row[col]:
            return False
        if current_row[col] == '' and previous_row[col] != '':
            # 当前行为空，可能是合并单元格的延续
            return True
    return True
```

### 2. 数据验证

导入时需要验证：
- 必填字段：part_number, tooling_no
- 外键有效性：customer_id, material_id
- 数据范围：thickness > 0, width > 0

### 3. 错误处理

建议记录：
- 无法匹配的材料名称
- 无法解析的TWP格式
- 重复的零件号/模具号

---

## 🗂️ 项目文件清单

```
excel/
├── 五金模具及产品清单表.xls          # 原始Excel文件
├── materials_classified.json         # 材料分类数据（193种）
├── customer_list.txt                 # 客户列表（91个）
├── materials_raw.txt                 # 原始材料列表（405种）
├── import_data.py                    # 导入脚本（待完善）
├── WORK_SUMMARY.md                   # 本文档
├── DATABASE_DIFF_ANALYSIS.md         # 数据库差异分析
├── FIELD_MAPPING_ANALYSIS.md         # 字段映射分析
├── FINAL_IMPORT_PLAN.md              # 导入方案
└── FINAL_TABLE_DESIGN.md             # 表结构设计

backend/app/models/
├── customer.py                       # Customer模型（需更新tablename）
├── part.py                           # Part模型
├── tooling.py                        # Tooling模型（需更新tablename和字段）
└── ...
```

---

## ✅ 检查清单（开始新对话时）

在新对话中开始前，请确认：

- [ ] 数据库表已重命名（customers, tooling）
- [ ] 所有新字段已添加（parts +8, tooling +12）
- [ ] materials_classified.json 文件存在
- [ ] Excel文件路径正确
- [ ] 数据库连接正常
- [ ] 已安装 xlrd 库

---

## 🎯 新对话中的第一句话

建议这样开始：

"我需要继续完成Excel数据导入项目。数据库表结构已准备好（customers, parts, tooling表，所有字段已添加），材料分类数据已就绪（193种标准材料）。现在需要完成导入脚本中的主数据导入逻辑，特别是：
1. 合并单元格检测（识别左右件）
2. 遍历91个客户Sheet并提取数据
3. 智能解析TWP、模具类型、材料等
请查看 excel/WORK_SUMMARY.md 了解完整背景。"

---

## 🙏 祝您继续顺利！
