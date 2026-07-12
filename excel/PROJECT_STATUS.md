# Excel数据导入项目 - 当前状态

> **历史状态，已不代表当前结论。** 唯一权威设计见 [`../specs/001-erp-system-architecture/data-model.md`](../specs/001-erp-system-architecture/data-model.md)。

## 项目进度

### ✅ 已完成

1. **数据库表结构准备**
   - customers, parts, tooling表已就绪
   - 所有必要字段已添加

2. **材料分类数据**
   - 193种标准材料已导入material_dict表
   - 材料映射字典已建立

3. **客户数据导入**
   - 91个客户已成功导入customers表

4. **模具数据导入**
   - 6177条模具记录已成功导入tooling表

5. **导入脚本开发**
   - ✅ TWP解析函数 (thickness, width, pitch)
   - ✅ 模具类型和成型步数解析
   - ✅ 材料匹配逻辑
   - ✅ 合并单元格检测（左右件识别）
   - ✅ 独立事务处理（每个客户一个事务）
   - ✅ 错误处理和日志记录

### 🔄 进行中

**零件数据导入**
- 导入脚本正在后台运行
- 当前状态：tooling表有6177条记录，但parts表仍为0条
- 可能原因：parts表字段需要调整

### ⚠️ 发现的问题

1. **Parts表结构问题**
   - parts表没有`tooling_id`外键字段
   - parts表有必填字段需要提供默认值：
     - `spray_status` (默认: 'pending')
     - `version` (默认: 'v1')
     - `part_status` (默认: 'active')
     - `stock_pcs` (默认: 0)

2. **编码问题**
   - Windows控制台Unicode编码问题导致特殊字符显示异常
   - SQLAlchemy日志中某些材料名称包含特殊字符导致编码错误
   - 已在代码中替换特殊符号（✓ → [OK]，⚠ → [!]）

3. **SQLAlchemy日志过多**
   - 输出文件中包含大量INSERT语句日志
   - 需要在生产环境中关闭详细日志

## 核心功能实现

### 1. 左右件识别逻辑

```python
def is_merged_row(sheet, row_idx, prev_row_data):
    """
    通过以下特征识别左右件：
    1. 零件编号为空
    2. 模具类型和材质字段为空（合并单元格）
    3. 模具类型和材质相同，且零件编号连续
    """
```

**处理方式：**
- 创建一条tooling记录
- 创建两条parts记录（left/right）
- 设置tooling.is_multi_product = TRUE
- 设置tooling.product_count = 2

### 2. TWP解析

支持格式：
- `0.4*116+55 (1出2)` → T=0.4, W=116, P=55, cavity=2
- `1.2*125*37` → T=1.2, W=125, P=37

### 3. 材料匹配

- 使用materials_classified.json中的193种标准材料
- 建立Excel原文 → 标准名称的映射
- 匹配失败时记录到日志，但继续导入

### 4. 模具类型解析

- **连续模：** 从TWP中提取穴数
- **工程模N：** 提取N作为forming_steps

## 文件清单

```
excel/
├── 五金模具及产品清单表.xls       # Excel源文件
├── import_data.py                  # 主导入脚本 ✅
├── test_import.py                  # 测试脚本 ✅
├── monitor_import.py               # 进度监控脚本 ✅
├── verify_import.py                # 数据验证脚本 ✅
├── WORK_SUMMARY.md                 # 工作总结文档
├── DATABASE_DIFF_ANALYSIS.md       # 数据库差异分析
├── FIELD_MAPPING_ANALYSIS.md       # 字段映射分析
├── FINAL_IMPORT_PLAN.md            # 导入方案
└── FINAL_TABLE_DESIGN.md           # 表结构设计

materials_classified.json           # 材料分类数据（项目根目录）
customer_list.txt                   # 客户列表（项目根目录）
```

## 下一步行动

### 立即任务

1. **等待当前导入完成**
   - 监控后台任务状态
   - 检查parts表是否有数据插入

2. **如果parts导入失败**
   - 检查详细错误日志
   - 修复字段映射问题
   - 重新运行导入

3. **运行数据验证**
   ```bash
   cd excel && python verify_import.py
   ```

### 验证清单

- [ ] Parts表记录数 = Tooling表记录数（或略多，因为有左右件）
- [ ] 左右件识别准确性
- [ ] TWP解析正确性
- [ ] 材料匹配率 > 90%
- [ ] 无重复零件编号
- [ ] 无重复模具号

## 预期结果

- **材料：** 193种
- **客户：** 91个
- **模具：** ~6000条
- **零件：** ~6000-7000条（含左右件）
- **左右件组：** ~500-1000组

## 已知限制

1. xlrd库不直接提供合并单元格信息，通过比较相邻行判断
2. TWP格式可能有变化，当前支持常见格式
3. 材料匹配基于193种标准材料，可能有未匹配项
4. 编码问题在Windows环境下影响日志输出

## 技术栈

- Python 3.13
- xlrd (Excel读取)
- SQLAlchemy (异步ORM)
- asyncpg (PostgreSQL驱动)
- PostgreSQL (数据库)

## 联系信息

遇到问题请查看：
- excel/WORK_SUMMARY.md - 完整背景和业务逻辑
- 后台任务输出文件 - 详细日志和错误信息
