# Changes to correct_left_right_shared_specs.py

## Summary
静态代码审查和优化完成，未连接数据库或使用浏览器。所有修改已通过py_compile和静态测试验证。

## Changes Made

### 1. Position字段统一为小写 (left/right)
- **位置**: `detect_position_from_name()` 函数 (行 238-260)
- **改动**: 返回值从 `'LEFT'`, `'RIGHT'` 改为 `'left'`, `'right'`
- **影响**: 
  - `find_candidate_groups()` 中的分组判断逻辑 (行 316)
  - 所有使用position的地方统一为小写

### 2. Parts表材料列修正为material_name
- **位置**: `apply_corrections()` 函数 (行 609-670)
- **改动**: 
  - SELECT查询: `material` → `material_name` (行 615)
  - UPDATE语句: `material = %s` → `material_name = %s` (行 631)
  - 变量命名和日志输出相应更新
- **原因**: 权威数据模型中parts表的材料列是material_name，不是material

### 3. Tooling.cavity_count处理逻辑强化
- **位置**: `apply_corrections()` 函数 (行 694-717)
- **改动**: 
  ```python
  # 旧逻辑: 只检查 NULL
  if t_cavity is None:
      # 填充
  
  # 新逻辑: 只允许 NULL 或 0 时填充
  if t_cavity is None or t_cavity == 0:
      # 填充
  elif t_cavity != analysis['shared_cavity']:
      # 报告冲突，不覆盖
  ```
- **原因**: 
  - tooling.cavity_count实际未知值可能是0或NULL
  - 只有明确Excel来源时才允许0/NULL填2
  - 其他非空正数不同则冲突不覆盖

### 4. Excel行提取性能优化
- **位置**: `extract_excel_row_data()` 和 `find_candidate_groups()`
- **改动**:
  - `extract_excel_row_data()` 签名修改:
    ```python
    # 旧: 每次打开workbook
    def extract_excel_row_data(excel_file: Path, sheet_name: str, row_number: int)
    
    # 新: 复用缓存的sheet上下文
    def extract_excel_row_data(sheet, header_row_idx: int, column_map: Dict, 
                               merged_map: Dict, row_number: int)
    ```
  - `find_candidate_groups()` 中增加sheet缓存逻辑:
    - 一次打开workbook
    - 为每个sheet缓存: header_row_idx, column_map, merged_map
    - 通过 `get_sheet_context()` 函数管理缓存
- **性能改进**: 避免每行重新xlrd.open_workbook，大幅减少I/O操作

### 5. JSON序列化增强
- **位置**: 顶部导入和所有json.dump调用
- **改动**:
  - 新增 `json_serializer()` 函数处理Decimal和Path对象
  - 所有 `json.dump()` 调用增加 `default=json_serializer`
  - 增加 `ensure_ascii=False` 支持中文
- **影响位置**:
  - `backup_records()`: 4个json.dump调用 (行 741, 752, 768, 781)
  - `generate_report()`: 1个json.dump调用 (行 829)

### 6. 导入优化
- **位置**: 顶部import区域
- **改动**: 添加 `from decimal import Decimal` 导入

## Validation

### py_compile验证
```bash
python -m py_compile correct_left_right_shared_specs.py
```
✅ 通过 - 无语法错误

### 静态测试
创建 `test_correct_left_right_shared_specs.py` 测试以下函数:
- ✅ `json_serializer()` - Decimal/Path序列化
- ✅ `extract_base_tooling_number()` - 模具号提取
- ✅ `detect_position_from_name()` - 左右位置检测 (返回小写)
- ✅ `build_merged_cell_map()` - 合并单元格映射

所有测试通过。

## 保持不变

- ✅ 单事务流程保持不变
- ✅ 干运行/应用模式不变
- ✅ 备份逻辑不变
- ✅ 冲突检测逻辑不变
- ✅ 报告生成逻辑不变

## 未执行操作

按照要求，以下操作未执行:
- ❌ 未连接数据库
- ❌ 未运行main()函数
- ❌ 未使用浏览器
- ❌ 未修改数据库数据

## 文件清单

修改的文件:
- `backend/scripts/correct_left_right_shared_specs.py` - 主脚本

新增的文件:
- `backend/scripts/test_correct_left_right_shared_specs.py` - 静态测试脚本
- `backend/scripts/CHANGES_correct_left_right_shared_specs.md` - 本变更说明
