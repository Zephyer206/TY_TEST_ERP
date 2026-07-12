# 客户数据问题分析报告

**日期：** 2026-07-12  
**问题：** 客户下拉列表中出现 "60T 连续模" 和字符编码错误

---

## 问题确认

### 1. 错误的客户记录

通过API分析发现以下异常记录：

| ID  | 客户名称 | Sheet Key | 问题 |
|-----|---------|-----------|------|
| 90  | 60T 连续模 | 60T | ❌ 这是Excel表格的分类标签，不是客户名 |
| 107 | B-U  IT | T | ⚠️ 可能是表头或错误数据 |

### 2. 字符编码问题

所有客户名称在API返回时显示为乱码，例如：
- 正常应该是："GBC浙江隆中"
- 实际显示为："鍘熷浘浜..."

**原因分析：** Excel导入脚本可能使用了错误的字符编码读取文件

---

## 根本原因

检查 Excel 导入流程，问题出在：

1. **未跳过表头和分类行**
   - Excel中的 "60T 连续模"、"80T 连续模" 等是工作表的分类标签
   - 导入脚本应该识别并跳过这些行

2. **字符编码不匹配**
   - Excel文件可能是 GB2312/GBK 编码
   - 导入脚本可能假设是 UTF-8 编码
   - 导致中文字符被错误解析

3. **表头行未正确处理**
   - 如果Excel第一行是列名（如"客户名称"、"Sheet Key"等）
   - 导入时应该跳过或正确识别

---

## 解决方案

### 立即修复（清理错误数据）

**方案 A：通过SQL删除**

```sql
-- 删除错误的客户记录
DELETE FROM customers WHERE id IN (90, 107);
```

**方案 B：通过后台API删除**

如果有DELETE接口，可以手动调用：
```bash
curl -X DELETE "http://127.0.0.1:8000/api/v1/customers/90" \
  -H "Authorization: Bearer <token>"
```

### 长期修复（修复导入脚本）

需要修改 `excel/import_data.py` 或相关导入脚本：

```python
# 1. 使用正确的编码读取Excel
import openpyxl
wb = openpyxl.load_workbook('file.xlsx')

# 2. 识别并跳过分类标签行
def is_category_row(row):
    """判断是否是分类标签行"""
    first_cell = row[0].value
    if first_cell and isinstance(first_cell, str):
        # 跳过包含这些关键字的行
        if any(keyword in first_cell for keyword in 
               ['连续模', 'T 模', '工作表', '客户名称']):
            return True
    return False

# 3. 跳过表头
for idx, row in enumerate(worksheet.iter_rows(min_row=2)):
    if is_category_row(row):
        continue
    # 处理正常数据行
    ...
```

---

## 建议的操作步骤

### 步骤 1：立即清理错误数据

```bash
# 进入数据库
psql postgresql://postgres:w981122@124.222.29.229:5432/zephyr_erp_test

# 执行清理SQL
DELETE FROM customers WHERE id = 90;  -- 删除 "60T 连续模"
-- 如果确认ID=107也是错误的，也删除它
-- DELETE FROM customers WHERE id = 107;
```

### 步骤 2：检查原始Excel文件

1. 打开原始Excel文件
2. 查看客户工作表的结构：
   - 是否有分类标签行？
   - 第一行是否是列名？
   - 字符编码是什么？

### 步骤 3：修复导入脚本（如果需要重新导入）

如果需要重新导入客户数据，建议：

1. 备份当前数据库
2. 修复导入脚本的字符编码问题
3. 添加跳过表头和分类行的逻辑
4. 在测试环境中验证
5. 重新导入

### 步骤 4：验证修复

```bash
# 通过API验证客户列表
curl -s "http://127.0.0.1:8000/api/v1/customers?skip=0&limit=10" \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

---

## 注意事项

1. **删除前检查依赖**
   - 客户ID=90可能在其他表中被引用（如parts表的customer_id）
   - 删除会级联影响这些记录
   - 建议先运行：
     ```sql
     SELECT COUNT(*) FROM parts WHERE customer_id = 90;
     ```

2. **字符编码问题**
   - 即使删除了错误记录，现有客户名称的乱码问题仍然存在
   - 这需要修复导入脚本并重新导入数据

3. **备份数据**
   - 在执行删除操作前，建议备份customers表：
     ```sql
     CREATE TABLE customers_backup_20260712 AS SELECT * FROM customers;
     ```

---

## 执行清理

如果你确认要删除ID=90的记录，我可以帮你执行。请确认：

1. ✅ 是否删除 ID=90 (60T 连续模)？
2. ⚠️ 是否删除 ID=107 (B-U  IT)？需要确认这是否是真实客户
3. 是否需要备份数据？

**当前建议：** 先只删除ID=90，保留ID=107直到确认其性质。
