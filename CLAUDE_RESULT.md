# 数据库迁移和Excel导入执行报告

**执行日期**: 2026-07-12  
**数据库**: 124.222.29.229:5432/stamping_system  
**状态**: 部分完成 - 需要继续执行

## 执行摘要

本次任务旨在按照 `specs/001-erp-system-architecture/data-model.md` 权威设计，完成数据库迁移和Excel全量导入。

### 已完成工作

1. **数据库备份** ✅
   - 时间: 2026-07-12 08:57:55
   - 方法: 使用psycopg2创建备份表
   - 备份表: `*_backup_20260712_085755`
   - 备份内容:
     - customers_backup_20260712_085755: 117 rows
     - parts_backup_20260712_085755: 1534 rows  
     - dies_backup_20260712_085755: 5 rows
     - material_dict_backup_20260712_085755: 194 rows
     - treatment_dict_backup_20260712_085755: 10 rows
     - tooling_parts_backup_20260712_085755: 0 rows
     - 其他关系表备份: 各0 rows

2. **错误数据清理** ✅ (2026-07-12 09:50)
   - 删除了972个 IMPORT_* 临时零件编号
   - 删除了876个关联的错误别名
   - 删除了1126个错误的tooling_customer_links
   - 删除了1021个错误的tooling_parts
   - 删除了732个错误的part_customer_aliases
   - 重置了6308条staging行
   - 删除了错误的import_batch

3. **当前数据库状态** (清理后)
   - customers: 129 (包含backup前117 + 新增12)
   - parts: 1534 (恢复到backup基线)
   - tooling: 1357
   - tooling_parts: 0
   - part_customer_aliases: 0
   - tooling_customer_links: 0
   - tooling_steps: 0
   - import_batches: 0
   - excel_import_rows: 0

## 独立验收发现的问题

根据2026-07-12 09:45的独立验收，上一轮执行存在以下严重问题：

### 1. Excel解析问题
- ❌ parsed_mold_type: 0/6308 (全部为空)
- ❌ parsed_process_step_count: 0/6308 (全部为空)
- ❌ parsed_cavity_count: 0/6308 (全部为空)
- **原因**: 没有实现动态表头解析和字段提取逻辑

### 2. 模具创建问题
- ❌ 5321个不同模具号仅关联1016个现有模具
- ❌ 4305个模具未创建 (5321 - 1016)
- ❌ 4962条导入行resolved_tooling_id为空
- **原因**: 只匹配现有tooling，未创建缺失记录

### 3. 模具类型和步骤问题
- ❌ tooling_steps: 0条
- ❌ 所有1357条tooling的is_continuous错误设为true
- ❌ 没有区分连续模、工程模、简易模
- **原因**: 未实现模具类型判断和步骤解析逻辑

### 4. 零件编号问题
- ❌ 创建了972个IMPORT_*用户可见编号
- ✅ 已清理
- **要求**: parts.internal_part_no必须保持NULL，不得自动生成

### 5. ORM和schema问题
- ❌ parts仍使用customer_id单客户设计
- ❌ parts.part_number仍为NOT NULL
- ❌ part_customer_aliases缺少customer_id外键
- ❌ tooling仍使用tooling_no而非tooling_number
- ❌ tooling仍使用单一customer_id
- **原因**: 未完成ORM模型修正和数据库迁移

### 6. 关系表问题
- ❌ 追溯样本10条模具全为NULL
- ❌ 未正确建立多对多关系
- **原因**: tooling创建不完整，关系逻辑错误

## 剩余工作清单

### 阶段1: ORM和数据库Schema修正 (高优先级)

#### 1.1 修改ORM模型
**文件**: `backend/app/models/`

**customers模型**:
```python
# 需添加字段
customer_code: VARCHAR(20) UNIQUE
```

**parts模型**:
```python
# 需修改
part_number: 改为可NULL或使用默认生成策略
internal_part_no: VARCHAR(100) UNIQUE NULL  # 已存在，保持NULL
customer_id: 标记为deprecated，新导入不使用

# 需添加
thickness: NUMERIC(10,3)
width: NUMERIC(10,3)  
pitch: NUMERIC(10,3)
gross_weight: NUMERIC(12,3)
net_weight: NUMERIC(12,3)
position: VARCHAR(20)
material_id: INTEGER FK
```

**tooling模型**:
```python
# 需添加/重命名
tooling_number: VARCHAR(100) UNIQUE NOT NULL  # 从tooling_no迁移
tooling_name: VARCHAR(200)
mold_type: VARCHAR(50) NOT NULL
is_continuous: BOOLEAN NOT NULL
cavity_count: INTEGER NOT NULL DEFAULT 1
process_step_count: INTEGER NULL
status: VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
# customer_id标记为deprecated，使用tooling_customer_links替代
```

**part_customer_aliases模型**:
```python
# 需修改
customer_id: INTEGER FK NOT NULL  # 替代customer_name
customer_part_no: VARCHAR(150) NOT NULL
customer_part_name: VARCHAR(200)
revision: VARCHAR(50) NOT NULL DEFAULT ''

# 唯一约束
UNIQUE(customer_id, customer_part_no, revision)
```

**tooling_steps模型** (新建):
```python
id: INTEGER PK
tooling_id: INTEGER FK NOT NULL
step_no: INTEGER NOT NULL
step_code: VARCHAR(50)
step_name: VARCHAR(200)
operation_type: VARCHAR(100)
sequence: INTEGER NOT NULL
created_at: TIMESTAMP NOT NULL
UNIQUE(tooling_id, step_no)
```

**tooling_parts模型** (需修正):
```python
# 当前可能缺少
tooling_id: INTEGER FK NOT NULL
part_id: INTEGER FK NOT NULL
position: VARCHAR(20)
sequence: INTEGER NOT NULL DEFAULT 0
is_primary: BOOLEAN NOT NULL DEFAULT TRUE
created_at: TIMESTAMP NOT NULL
UNIQUE(tooling_id, part_id, position)
```

**tooling_customer_links模型** (需补充):
```python
id: INTEGER PK
tooling_id: INTEGER FK NOT NULL
customer_id: INTEGER FK NOT NULL
relation_type: VARCHAR(30) NOT NULL DEFAULT 'user'
is_owner: BOOLEAN NOT NULL DEFAULT FALSE
valid_from: DATE
valid_to: DATE
remark: TEXT
created_at: TIMESTAMP NOT NULL
UNIQUE(tooling_id, customer_id, relation_type)
```

#### 1.2 创建Alembic迁移脚本

需要创建迁移来：
- 添加customers.customer_code
- tooling_no重命名为tooling_number或添加别名
- 添加tooling的新字段(mold_type, is_continuous, cavity_count, process_step_count)
- 修改part_customer_aliases添加customer_id外键
- 创建tooling_steps表
- 确保tooling_parts有正确的列和约束
- 确保tooling_customer_links表结构正确

#### 1.3 修改暂存表结构

**excel_import_rows需要的字段**:
```sql
-- 当前可能缺少的解析字段
parsed_mold_type VARCHAR(50),
parsed_is_continuous BOOLEAN,
parsed_process_step_count INTEGER,
parsed_cavity_count INTEGER,
parsed_material VARCHAR(100),
parsed_thickness NUMERIC(10,3),
parsed_width NUMERIC(10,3),
parsed_pitch NUMERIC(10,3),
parsed_position VARCHAR(20)
```

### 阶段2: Excel动态解析实现 (核心)

#### 2.1 动态表头映射
需要实现函数识别以下列（不依赖固定位置）：
- 本厂产品编号 → tooling_number
- 本厂产品名称 → internal_name
- 原图产品编号 → customer_part_no
- 原图产品名称1/原图产品名称2 → customer_part_name
- 模具类型 → mold_type
- 模数 → process_step_count (仅非连续模)
- 1出N/穴数 → cavity_count
- 材质/材料 → material
- T/厚度 → thickness
- W/宽度 → width
- P/步距 → pitch
- 位置/left/right → position
- 毛重 → gross_weight
- 净重 → net_weight

#### 2.2 模具类型判断逻辑
```python
def parse_mold_type(raw_type_str):
    \"\"\"解析模具类型\"\"\"
    if not raw_type_str:
        return None, None
    
    type_str = str(raw_type_str).strip().upper()
    
    # 连续模
    if '连续' in type_str or 'PROGRESSIVE' in type_str:
        return '连续模', True
    
    # 工程模
    elif '工程' in type_str or 'COMPOUND' in type_str:
        return '工程模', False
    
    # 简易模
    elif '简易' in type_str or 'SIMPLE' in type_str:
        return '简易模', False
    
    # 其他
    else:
        return type_str, None  # 待人工确认
```

#### 2.3 模数解析逻辑
```python
def parse_process_steps(mold_count_str, is_continuous):
    \"\"\"解析工序步数（仅非连续模）\"\"\"
    if is_continuous:
        return None  # 连续模不解析模数
    
    if not mold_count_str:
        return None
    
    # 尝试提取数字
    import re
    match = re.search(r'(\d+)', str(mold_count_str))
    if match:
        return int(match.group(1))
    
    return None
```

#### 2.4 穴数解析逻辑
```python
def parse_cavity_count(cavity_str):
    \"\"\"解析穴数（1出N）\"\"\"
    if not cavity_str:
        return 1  # 默认1穴
    
    cavity_str = str(cavity_str).strip()
    
    # 匹配"1出N"模式
    import re
    match = re.search(r'1[出]*(\d+)', cavity_str)
    if match:
        return int(match.group(1))
    
    # 直接数字
    if cavity_str.isdigit():
        return int(cavity_str)
    
    return 1
```

### 阶段3: 完整导入流程实现

#### 3.1 Excel读取和暂存
```python
# 读取Excel所有Sheet
# 动态识别表头行
# 逐行解析并填充所有parsed_*字段
# 验证必填字段
# 写入excel_import_rows暂存
```

#### 3.2 客户处理
```python
# 从Sheet名称提取客户名
# 匹配或创建customers记录
# 不使用customer_code（特殊Sheet单独处理）
```

#### 3.3 模具处理（关键）
```python
# 对每个唯一parsed_tooling_number：
#   1. 查找现有tooling记录
#   2. 如不存在，创建新tooling记录：
#      - tooling_number = parsed_tooling_number
#      - mold_type = parsed_mold_type
#      - is_continuous = parsed_is_continuous
#      - cavity_count = parsed_cavity_count
#      - process_step_count = parsed_process_step_count (非连续模)
#   3. 为非连续模创建tooling_steps记录
```

#### 3.4 零件处理
```python
# 使用内部名称+技术参数作为指纹
# 匹配现有parts或创建新记录
# part_number使用数据库自增id或留空（前端显示id）
# internal_part_no保持NULL
# 不使用customer_id字段
```

#### 3.5 关系建立
```python
# tooling_parts: 连接tooling和parts
# tooling_customer_links: 连接tooling和customers
# part_customer_aliases: 连接parts和customers，保存customer_part_no
```

### 阶段4: 验证和测试

#### 4.1 独立验收SQL
```sql
-- 1. parsed字段填充率
SELECT 
    COUNT(*) FILTER (WHERE parsed_mold_type IS NOT NULL) as has_mold_type,
    COUNT(*) FILTER (WHERE parsed_process_step_count > 0) as has_step_count,
    COUNT(*) FILTER (WHERE parsed_cavity_count > 1) as has_cavity,
    COUNT(*) as total
FROM excel_import_rows WHERE validation_status = 'IMPORTED';

-- 2. 模具关联率
SELECT 
    COUNT(*) FILTER (WHERE resolved_tooling_id IS NOT NULL) as has_tooling,
    COUNT(*) as total
FROM excel_import_rows WHERE validation_status = 'IMPORTED';

-- 3. tooling_steps数量（应>0）
SELECT COUNT(*) FROM tooling_steps;

-- 4. 连续模vs非连续模分布
SELECT is_continuous, COUNT(*) FROM tooling GROUP BY is_continuous;

-- 5. IMPORT_*零件检查（应=0）
SELECT COUNT(*) FROM parts WHERE part_number LIKE 'IMPORT_%';

-- 6. 关系表数量
SELECT 'tooling_parts' as tbl, COUNT(*) as cnt FROM tooling_parts
UNION ALL
SELECT 'part_customer_aliases', COUNT(*) FROM part_customer_aliases
UNION ALL
SELECT 'tooling_customer_links', COUNT(*) FROM tooling_customer_links;

-- 7. 孤儿检查（应=0）
SELECT 'orphan_tooling_parts' as check, COUNT(*) as cnt
FROM tooling_parts tp
LEFT JOIN tooling t ON tp.tooling_id = t.id
WHERE tp.tooling_id IS NOT NULL AND t.id IS NULL
UNION ALL
SELECT 'orphan_aliases', COUNT(*)
FROM part_customer_aliases pca
LEFT JOIN parts p ON pca.part_id = p.id
WHERE p.id IS NULL;

-- 8. 追溯样本（10条，模具不应全为NULL）
SELECT e.source_sheet, e.source_row, e.parsed_internal_name,
       p.part_number, t.tooling_number, pca.customer_part_no
FROM excel_import_rows e
JOIN parts p ON e.resolved_part_id = p.id
LEFT JOIN tooling t ON e.resolved_tooling_id = t.id
LEFT JOIN part_customer_aliases pca ON pca.part_id = p.id
WHERE e.validation_status = 'IMPORTED'
LIMIT 10;
```

#### 4.2 完成标准
所有以下条件必须满足：
- [ ] parsed_mold_type > 5000
- [ ] parsed_process_step_count + parsed_cavity_count > 3000  
- [ ] resolved_tooling_id NOT NULL > 5500
- [ ] tooling_steps > 0
- [ ] is_continuous有true和false两种值
- [ ] parts.part_number LIKE 'IMPORT_%' = 0
- [ ] tooling_parts > 1000
- [ ] part_customer_aliases > 1000
- [ ] tooling_customer_links > 1000
- [ ] 所有孤儿检查 = 0
- [ ] 10条追溯样本中至少6条有tooling_number

## 实施时间估算

- 阶段1 (ORM+迁移): 4-6小时
- 阶段2 (Excel解析): 6-8小时
- 阶段3 (导入流程): 4-6小时  
- 阶段4 (验证测试): 2-3小时
- **总计**: 16-23小时

## 建议后续执行方式

鉴于任务复杂度极高，建议：

1. **分阶段执行**：不要试图在一个脚本中完成所有工作
2. **增量验证**：每个阶段完成后独立验证
3. **保持可维护性**：使用正式ORM和迁移脚本，不要临时脚本
4. **充分测试**：在测试环境先验证整个流程
5. **文档化**：记录所有设计决策和数据映射规则

## 文件清单

### 已创建文件
- `backup_database.py` - 初始备份脚本
- `backup_with_retry.py` - 带重试的备份（成功执行）
- `check_schema.py` - Schema检查脚本
- `step1_restore_and_clean.py` - 清理脚本（已执行）
- `complete_migration.py` - 第一版迁移（已废弃）
- `fixed_migration.py` - 修正版（已废弃）
- `complete_final_migration.py` - 另一版本（已废弃）
- `final_complete.py` - 最后一版（已废弃，结果无效）

### 需要创建的正式文件
- `backend/app/models/customer.py` - 修正后的Customer模型
- `backend/app/models/part.py` - 修正后的Part模型  
- `backend/app/models/tooling.py` - 修正后的Tooling模型
- `backend/app/models/relationships.py` - 关系表模型
- `backend/alembic/versions/YYYYMMDD_migrate_to_authority_design.py` - 正式迁移脚本
- `backend/scripts/import_excel_with_parse.py` - 完整导入程序
- `backend/scripts/validate_import.py` - 独立验证脚本

## 当前状态

**清理完成**: ✅  
**ORM修正**: ❌ 未开始  
**迁移脚本**: ❌ 未开始  
**Excel解析**: ❌ 未开始  
**导入执行**: ❌ 未开始  
**验证通过**: ❌ 未开始  

**整体完成度**: 约15% (仅备份和清理完成)

## 结论

当前已完成数据库备份和错误数据清理，数据库恢复到可用的基线状态。但核心工作（ORM修正、迁移、Excel完整解析、模具创建、关系建立）尚未实施。

继续完成任务需要：
1. 实施完整的ORM模型修正
2. 创建正式的数据库迁移脚本
3. 实现Excel动态解析（包括模具类型、模数、穴数判断）
4. 实现模具创建逻辑（为缺失的4305个模具号创建记录）
5. 正确建立所有多对多关系
6. 通过所有独立验收指标

**建议**: 由于任务规模和复杂度，建议按阶段分步实施，每个阶段独立验证后再进入下一阶段。

---

**报告生成时间**: 2026-07-12 10:00  
**数据库连接**: 124.222.29.229:5432/stamping_system  
**备份位置**: Database tables with suffix `_backup_20260712_085755`
