# 数据库差异分析：设计模型 vs 云端实际

> **历史差异分析。** 其中引用的旧设计已废弃；新的目标端只使用 [`../specs/001-erp-system-architecture/data-model.md`](../specs/001-erp-system-architecture/data-model.md)。

## 🔍 关键差异总结

### 1. tooling_molds 表

#### 设计模型 (tooling.py - Tooling class)
```python
class Tooling(Base):
    __tablename__ = "tooling_molds"
    
    id: Mapped[int]
    tooling_no: Mapped[str]                    # String(50), unique
    name: Mapped[str]                          # String(200)
    customer_product_no: Mapped[Optional[str]] # String(100)
    cavity_count: Mapped[Optional[int]]        # Integer
    tonnage: Mapped[Optional[float]]           # Float
    ppap_no: Mapped[Optional[str]]             # String(100)
    vehicle_model: Mapped[Optional[str]]       # String(100)
    state: Mapped[ToolingState]                # Enum
    parent_id: Mapped[Optional[int]]           # 父子关系
    spec_data: Mapped[Optional[str]]           # Text
    drawing_path: Mapped[Optional[str]]        # Text
    sdr_drawing_path: Mapped[Optional[str]]    # Text
    active_maintenance_id: Mapped[Optional[int]]
    is_deleted: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

#### 云端实际表结构
```sql
id                      INTEGER PRIMARY KEY
customer_id             INTEGER                 -- ❌ 设计没有
mold_number             VARCHAR(100)            -- ✅ 对应 tooling_no
customer_product_no     VARCHAR(100)            -- ✅ 有
customer_product_name   VARCHAR(200)            -- ❌ 设计没有
mold_type               VARCHAR(100)            -- ❌ 设计没有
cavity_count            VARCHAR(20)             -- ⚠️ 设计是 Integer，云端是 VARCHAR
material                VARCHAR(100)            -- ❌ 设计没有
spec_twph               VARCHAR(100)            -- ⚠️ 设计是 spec_data(Text)
press_tonnage           VARCHAR(50)             -- ⚠️ 设计是 tonnage(Float)
remark                  TEXT                    -- ❌ 设计没有
ppap_no                 VARCHAR(100)            -- ✅ 有
vehicle_model           VARCHAR(100)            -- ✅ 有
seq                     INTEGER                 -- ❌ 设计没有
created_at              TIMESTAMP               -- ✅ 有
updated_at              TIMESTAMP               -- ✅ 有
cavity_status           VARCHAR(16)             -- ❌ 设计没有
mold_count              INTEGER                 -- ❌ 设计没有
mold_status             VARCHAR(20) NOT NULL    -- ⚠️ 设计是 state(Enum)
```

**差异汇总：**
- ❌ **设计缺少**：customer_id, customer_product_name, mold_type, material, remark, seq, cavity_status, mold_count
- ❌ **云端缺少**：name, parent_id, drawing_path, sdr_drawing_path, active_maintenance_id, is_deleted
- ⚠️ **类型不同**：cavity_count (Int vs Varchar), tonnage/press_tonnage (Float vs Varchar), state/mold_status (Enum vs Varchar)

---

### 2. tooling_parts 表

#### 设计模型 (tooling.py - ToolingPart class)
```python
class ToolingPart(Base):
    __tablename__ = "tooling_parts"
    
    id: Mapped[int]
    tooling_id: Mapped[int]          # FK -> tooling_molds.id
    part_id: Mapped[int]             # FK -> parts.id
    created_at: Mapped[datetime]
```

#### 云端实际表结构
```sql
id                      INTEGER PRIMARY KEY
mold_id                 INTEGER                 -- ⚠️ 设计是 tooling_id
customer_product_no     VARCHAR(100)            -- ❌ 设计没有
customer_product_name   VARCHAR(200)            -- ❌ 设计没有
gross_weight_g          NUMERIC                 -- ❌ 设计没有
net_weight_g            NUMERIC                 -- ❌ 设计没有
created_at              TIMESTAMP               -- ✅ 有
```

**差异汇总：**
- ❌ **设计缺少**：customer_product_no, customer_product_name, gross_weight_g, net_weight_g
- ❌ **云端缺少**：part_id (FK -> parts.id)
- ⚠️ **设计意图完全不同**：
  - 设计：tooling_parts = 模具与零件的多对多关联表
  - 云端：tooling_parts = 存储客户零件信息和重量的独立表

---

### 3. parts 表

#### 设计模型 (part.py - Part class)
```python
class Part(Base):
    __tablename__ = "parts"
    
    id: Mapped[int]
    part_number: Mapped[str]                    # String(50), unique
    internal_name: Mapped[Optional[str]]        # String(200)
    customer_id: Mapped[Optional[int]]          # Integer
    drawing_url: Mapped[Optional[str]]          # Text
    spec_info: Mapped[Optional[str]]            # Text
    status: Mapped[str]                         # String(50), default='待开发'
    part_status: Mapped[str]                    # String(50), default='DRAFT'
    is_urgent: Mapped[bool]
    target_count: Mapped[int]
    spray_status: Mapped[str]
    spray_stamped_at: Mapped[Optional[datetime]]
    customer_product_no: Mapped[Optional[str]]  # String(100)
    vehicle_model: Mapped[Optional[str]]        # String(100)
    material_name: Mapped[Optional[str]]        # String(100)
    nomination_status: Mapped[Optional[str]]
    nomination_attachment: Mapped[Optional[str]]
    price_snapshot: Mapped[Optional[dict]]      # JSON
    nomination_confirmed_at: Mapped[Optional[datetime]]
    nomination_confirmed_by: Mapped[Optional[int]]
    sample_judgment_status: Mapped[Optional[str]]
    version: Mapped[str]
    stock_pcs: Mapped[int]
    remark: Mapped[Optional[str]]               # String(500)
    mold_number: Mapped[Optional[str]]          # String(50)
    mold_type: Mapped[Optional[str]]            # String(50)
    press_tonnage: Mapped[Optional[str]]        # String(50)
    ppap_no: Mapped[Optional[str]]              # String(100)
    created_at: Mapped[Optional[datetime]]
    updated_at: Mapped[Optional[datetime]]
```

#### 云端实际表结构
```sql
-- 与设计模型基本一致，但增加了：
part_name_id            INTEGER -> part_name_dict.id  -- ❌ 设计没有
material_id             INTEGER -> materials.id       -- ❌ 设计没有
machine_tonnage_id      INTEGER                       -- ❌ 设计没有
mold_type_id            INTEGER                       -- ❌ 设计没有
```

**差异汇总：**
- ❌ **设计缺少**：part_name_id, material_id, machine_tonnage_id, mold_type_id（4个字典表外键）
- ⚠️ **设计用文本**：material_name (String)，云端用外键 material_id

---

## 🎯 关键发现

### 1. 设计理念差异

**设计模型的理念：**
- `tooling_molds` = 纯模具表
- `parts` = 零件表（包含客户零件和内部零件）
- `tooling_parts` = 模具-零件多对多关联表

**云端实际的理念：**
- `tooling_molds` = 模具 + 客户零件信息（合并表）
- `parts` = 内部零件管理表（空表）
- `tooling_parts` = 客户零件详细信息表（重量等）

### 2. 字典表策略差异

**设计模型：**
- 使用文本字段：material_name, mold_type 等

**云端实际：**
- 使用字典表外键：material_id, part_name_id, mold_type_id, machine_tonnage_id
- 已存在的字典表：
  - `part_name_dict`
  - `materials` (或 material_dict)
  - `mold_type_dict`
  - `machine_tonnage_dict`

### 3. tooling_molds 表的不同用途

**设计模型：**
```python
Tooling(
    tooling_no="TYA-Q0001",
    name="前壳体模具",
    customer_product_no="BYDLK-3510111",  # 只记录客户零件号
    # 其他是纯模具信息
)
```

**云端实际：**
```sql
INSERT INTO tooling_molds (
    mold_number = "TYA-Q0001",               -- 模具号
    customer_product_no = "BYDLK-3510111",   -- 客户零件号
    customer_product_name = "前壳体",         -- 客户零件名
    mold_type = "工程模9",                    -- 模具类型
    material = "冷轧板",                      -- 材料
    spec_twph = "1.2*125*37",                -- 规格
    press_tonnage = "160T",                  -- 吨位
    -- 这是模具+客户零件的合并信息
)
```

---

## 📋 导入策略的影响

### ✅ 好消息：

云端实际表结构**更适合**Excel导入，因为：
1. `tooling_molds` 已经有所有Excel字段
2. 不需要复杂的多表关联
3. 字段类型都是VARCHAR，更灵活

### ⚠️ 需要注意：

1. **模型文件需要同步更新**
   - 当前 `backend/app/models/tooling.py` 与云端不一致
   - 如果用ORM操作会出错

2. **材料字段的双重性**
   - 云端有 `material` (VARCHAR) 文本字段
   - 还有 `material_id` (INTEGER) 外键吗？（需要确认）

3. **字典表的使用**
   - parts表使用了字典表外键
   - tooling_molds表没有使用字典表外键

---

## 🚀 导入脚本建议

### 方案A：直接SQL导入（推荐）
```python
# 不使用ORM，直接执行SQL
async with conn.begin() as conn:
    await conn.execute(text("""
        INSERT INTO tooling_molds (
            customer_id, mold_number, customer_product_no,
            customer_product_name, mold_type, material, ...
        ) VALUES (:customer_id, :mold_number, ...)
    """), params)
```

**优点：**
- 不依赖模型定义
- 直接操作云端实际表结构
- 更快、更可控

### 方案B：更新模型后使用ORM
```python
# 1. 先同步 tooling.py 模型与云端
# 2. 然后使用ORM
mold = Tooling(
    customer_id=...,
    mold_number=...,
    ...
)
db.add(mold)
```

**缺点：**
- 需要先修改模型文件
- 可能影响现有代码

---

## ❓ 需要确认的问题

1. **是否应该更新模型文件？**
   - 同步 `backend/app/models/tooling.py` 与云端表结构？

2. **材料处理策略？**
   - tooling_molds.material 用文本存储即可？
   - 还是需要关联 materials 表？

3. **导入方式选择？**
   - 使用直接SQL（推荐）
   - 还是先更新模型再用ORM？

**请指示下一步如何处理！**
