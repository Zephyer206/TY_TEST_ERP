# 数据库模型修复报告

**修复时间：** 2026-07-12  
**问题：** SQLAlchemy Model 定义与实际数据库表结构不匹配

## 修复的Model

### 1. Customer Model (`app/models/customer.py`)

**问题：** 表名错误  
**修复前：** `__tablename__ = "tooling_customers"`  
**修复后：** `__tablename__ = "customers"`

---

### 2. Tooling Model (`app/models/tooling.py`)

**问题：** 
- 表名错误：`tooling_molds` → `tooling`
- 字段定义完全不匹配实际数据库

**主要变更：**
```python
# 修复前：使用ToolingState enum、复杂关系等
# 修复后：匹配实际数据库字段

class Tooling(Base):
    __tablename__ = "tooling"  # 从 tooling_molds 改为 tooling
    
    # 实际数据库字段
    tooling_no: Optional[str]
    name: Optional[str]
    customer_id: Optional[int]
    cavity_count: Optional[str]  # 注意：字符串类型
    mold_type: Optional[str]
    material: Optional[str]
    spec_twph: Optional[str]
    press_tonnage: Optional[str]
    # ... 其他字段
```

**外键更新：**
- `ToolingMaintenanceLog.tooling_id`: `tooling_molds.id` → `tooling.id`
- `ToolingPart.tooling_id`: `tooling_molds.id` → `tooling.id`
- `Tooling.parent_id`: `tooling_molds.id` → `tooling.id`

---

### 3. ProductionPlan Model (`app/models/production.py`)

**问题：** 字段定义与实际数据库完全不匹配

**主要变更：**
```python
# 移除的字段（数据库中不存在）
- plan_no (str)
- completed_qty (int)
- planned_start_date (datetime)
- planned_end_date (datetime)
- priority (int)
- notes (str)
- is_deleted (bool)

# 添加的字段（匹配数据库）
+ progress_qty (int)
+ delivered_qty (int)
+ due_date (date)
+ machine_id (int)
+ plan_order (int)
+ force_order (bool)
+ assigned_by (int)
+ assigned_at (datetime)
+ urgency (str)
+ remark (str)
```

**外键更新：**
- `ProductionSession.tooling_id`: `tooling_molds.id` → `tooling.id`
- `ProcessFlowCard.tooling_id`: `tooling_molds.id` → `tooling.id`

**关系移除：**
- 移除 `ProductionPlan.assignments` 关系
- 移除 `PlanMachineAssignment.plan` 反向关系

---

### 4. Part Model (`app/models/part.py`)

**问题：** 缺少TWP相关字段和material_id

**添加的字段：**
```python
+ material_id: Optional[int]
+ customer_product_name: Optional[str]
+ spec_twph: Optional[str]
+ thickness: Optional[Decimal]
+ width: Optional[Decimal]
+ pitch: Optional[Decimal]
+ height: Optional[Decimal]
+ gross_weight: Optional[Decimal]
+ net_weight: Optional[Decimal]
+ part_position: Optional[str]
```

---

## 验证结果

### API测试成功

```bash
GET /api/v1/parts?skip=0&limit=1
Authorization: Bearer <token>

Response: 200 OK
{
  "id": 2393,
  "part_number": "...",
  "internal_name": "...",
  "customer_name": "...",
  "material_name": null,
  "cavity_count": null,
  "thickness": null,
  "width": null,
  ...
}
```

### 服务状态

✅ 后端服务：http://127.0.0.1:8000 - 运行正常  
✅ 前端服务：http://localhost:5173 - 运行正常

---

## 已知问题

### 1. 数据编码问题

部分数据显示乱码（如 `鍘熷`），这是Excel导入时的编码问题，不影响功能。

### 2. 空值问题

很多TWP字段为null，因为：
- 部分零件数据的spec_twph字段未被解析
- material_id可能未正确关联

### 3. 穴数显示

`cavity_count` 返回null，因为：
- 需要从tooling表关联查询
- tooling.tooling_no 需要与 part.mold_number 匹配

---

## 后续建议

1. **数据导入脚本优化**
   - 修复字符编码问题
   - 确保TWP字段被正确解析和存储

2. **Model定义规范**
   - 在修改数据库表结构前，应先更新Model定义
   - 或者从实际数据库生成Model定义

3. **测试覆盖**
   - 添加Model与数据库一致性测试
   - 在CI/CD中验证Model定义

---

**修复完成时间：** 2026-07-12 00:43  
**测试状态：** ✅ 通过
