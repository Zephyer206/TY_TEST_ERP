# 数据库全量质量检查报告

**检查日期：** 2026-07-12 01:00  
**数据库：** zephyr_erp_test @ 124.222.29.229:5432

---

## 执行概要

✅ 已完成4个主要表的schema检查  
⚠️ 发现数据质量问题需要修复  

---

## 1. CUSTOMERS 表

### Schema信息
- **字段数：** 4
- **主要字段：** id, name, sheet_key, created_at

### 已知问题

#### ❌ 严重问题：表头被导入为数据
- **ID=90:** "60T 连续模" (sheet_key="60T")
  - 这是Excel工作表的分类标签，不是真实客户
  - **影响：** 在零件页面的客户下拉列表中显示
  - **优先级：** 🔴 高 - 立即修复

- **ID=107:** "B-U  IT" (sheet_key="T")
  - 可能也是表头或错误数据
  - **优先级：** 🟡 中 - 需确认后处理

#### ⚠️ 字符编码问题
- **现象：** 所有客户名称显示为乱码
- **示例：** "GBC浙江隆中" → "鍘熷浘浜..."
- **原因：** Excel导入时使用了错误的字符编码
- **影响范围：** 所有117条客户记录
- **优先级：** 🔴 高 - 影响用户体验

### 修复建议
```sql
-- 删除错误的客户记录
DELETE FROM customers WHERE id IN (90, 107);

-- 重新导入客户数据（使用正确编码）
-- 需要修复 excel/import_data.py 脚本
```

---

## 2. PARTS 表

### Schema信息
- **字段数：** 43
- **关键字段：** part_number, internal_name, customer_id, material_id, mold_number

### 已知问题

#### ⚠️ 可能存在表头记录
需要检查是否有以下关键字的记录：
- "零件编号"
- "本厂产品编号"
- "客户产品编号"
- "原图产品编号"

#### 📊 字段完整性分析

基于前面的API测试，预计空值情况：
- **customer_id：** 部分为空（需要关联客户）
- **material_name：** 大量为空
- **mold_number：** 部分为空
- **spec_twph：** 大量为空（TWP规格未解析）
- **thickness/width/pitch/height：** 大量为空

#### 🔍 需要进一步检查
- 重复的part_number
- 无效的customer_id外键
- 字符编码问题（与customers表同样的问题）

---

## 3. TOOLING 表

### Schema信息
- **字段数：** 24
- **关键字段：** tooling_no, name, customer_id, mold_type, cavity_count

### Model修复状态
✅ **已修复** - Model定义已更新匹配实际数据库结构

### 潜在问题
- 字符编码问题（同customers）
- 可能有表头记录（需要检查）
- cavity_count是字符串类型（而非整数）

---

## 4. PRODUCTION_PLANS 表

### Schema信息
- **字段数：** 17
- **关键字段：** part_id, total_qty, progress_qty, machine_id, status

### Model修复状态
✅ **已修复** - Model定义已完全重写匹配实际结构

### 移除的字段（数据库中不存在）
- plan_no
- completed_qty
- planned_start_date/planned_end_date
- priority
- notes
- is_deleted

### 新增的字段（匹配数据库）
- progress_qty
- delivered_qty
- due_date
- machine_id
- plan_order
- force_order
- assigned_by/assigned_at
- urgency
- remark

---

## 5. 其他已修复的Model问题

### Customer Model ✅
- 表名：tooling_customers → customers

### Tooling Model ✅
- 表名：tooling_molds → tooling
- 完全重写字段定义

### Part Model ✅
- 添加缺失字段：material_id, TWP相关字段

### 外键引用 ✅
- 所有 tooling_molds.id → tooling.id

---

## 问题优先级总结

### 🔴 高优先级（立即处理）
1. **删除错误的客户记录** (ID=90, 107)
2. **修复字符编码问题** - 影响所有表的中文显示
3. **检查parts表的表头记录**

### 🟡 中优先级（计划修复）
4. **提高字段完整性** - 补充缺失的TWP数据
5. **检查重复数据**
6. **验证外键完整性**

### 🟢 低优先级（优化）
7. **统一数据类型** - 如cavity_count应为整数
8. **添加数据验证规则**

---

## 数据导入脚本问题

### 需要修复的脚本
- `excel/import_data.py`
- 或其他相关的导入脚本

### 修复要点
1. **字符编码**
   ```python
   # 使用正确的编码读取Excel
   wb = openpyxl.load_workbook('file.xlsx')
   # 确保使用UTF-8存储到数据库
   ```

2. **跳过表头和分类行**
   ```python
   def is_header_or_category(row):
       keywords = ['连续模', 'T 模', '客户名称', '零件编号', '本厂产品编号']
       first_cell = str(row[0].value or '')
       return any(kw in first_cell for kw in keywords)
   
   for row in worksheet.iter_rows(min_row=2):
       if is_header_or_category(row):
           continue
       # 处理数据
   ```

3. **数据验证**
   - 检查必填字段
   - 验证外键存在性
   - 检测异常值

---

## 立即执行的SQL修复脚本

```sql
-- 备份
CREATE TABLE customers_backup_20260712 AS SELECT * FROM customers;

-- 删除错误记录
DELETE FROM customers WHERE id = 90;  -- 60T 连续模

-- 验证
SELECT COUNT(*) FROM customers;
SELECT * FROM customers WHERE id IN (90, 107);
```

---

## 后续建议

1. **数据重新导入**
   - 修复导入脚本
   - 在测试环境验证
   - 重新导入客户和零件数据

2. **添加数据验证**
   - 在应用层添加数据验证
   - 防止无效数据进入数据库

3. **定期数据质量检查**
   - 建立定期检查机制
   - 监控数据质量指标

4. **文档化**
   - 记录正确的导入流程
   - 更新开发文档

---

## 检查工具和脚本

已创建以下工具：
- ✅ `backend/DATABASE_MODEL_FIXES.md` - Model修复文档
- ✅ `backend/CUSTOMER_DATA_ISSUES.md` - 客户数据问题详细分析
- ✅ `backend/cleanup_bad_customers.sql` - SQL清理脚本
- ✅ `backend/cleanup_bad_customers.py` - Python清理脚本
- ✅ `backend/delete_bad_customers.sql` - 删除指定记录的SQL

---

**报告结束**

*下一步行动：执行delete_bad_customers.sql清理错误数据*
