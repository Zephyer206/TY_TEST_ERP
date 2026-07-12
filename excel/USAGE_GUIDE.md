# Excel数据导入 - 使用指南

> **旧导入脚本使用说明，当前禁止据此重新导入正式库。** 新导入实现必须遵循 [`../specs/001-erp-system-architecture/data-model.md`](../specs/001-erp-system-architecture/data-model.md) 的暂存、动态表头和校验规则。

## 快速开始

### 1. 运行完整导入

```bash
cd c:/Users/WIT_User/Desktop/Zephyr_test_Erp/excel
python import_data.py
```

**导入内容：**
- 193种标准材料 → material_dict表
- 91个客户 → customers表
- 约6000条模具记录 → tooling表
- 约6000-7000条零件记录 → parts表

### 2. 验证导入结果

```bash
python verify_import.py
```

**验证项：**
- 数据统计
- 左右件识别准确性
- TWP解析覆盖率
- 材料匹配率
- 数据完整性检查

### 3. 测试功能

```bash
python test_import.py
```

测试Excel读取和数据库连接。

## 导入逻辑说明

### 数据流程

```
Excel文件
  ↓
材料字典导入 (materials_classified.json)
  ↓
客户信息导入 (91个Sheet)
  ↓
主数据导入
  ├─ 遍历每个客户Sheet
  ├─ 逐行解析数据
  ├─ 检测左右件（合并单元格）
  ├─ 解析TWP规格
  ├─ 匹配材料
  ├─ 插入tooling记录
  └─ 插入parts记录
```

### 左右件识别

**识别条件（满足任一）：**
1. 零件编号为空
2. 模具类型和材质字段为空（合并单元格）
3. 模具类型和材质相同，且零件编号连续

**处理方式：**
```python
# 第一行（左件）
tooling: mold_number=TYAA-Q0063, is_multi_product=FALSE
parts: part_number=60008581, part_position=NULL

# 第二行（右件，检测到合并）
tooling: 更新 is_multi_product=TRUE, product_count=2
parts[0]: 更新 part_position='left'
parts[1]: 插入 part_number=60008582, part_position='right'
```

### TWP解析

**支持格式：**
- `0.4*116+55` → T=0.4, W=116, P=55
- `0.4*116+55 (1出2)` → T=0.4, W=116, P=55, cavity=2
- `1.2*125*37` → T=1.2, W=125, P=37

**代码：**
```python
thickness, width, pitch, cavity_count = parse_twph("0.4*116+55 (1出2)")
# 返回: (0.4, 116, 55, 2)
```

### 材料匹配

使用193种标准材料进行匹配：

```python
# Excel原文
"SUS301-3/4H"

# 映射到标准名称
MATERIAL_MAPPING["SUS301-3/4H"] → "SUS301 3/4H"

# 查询material_dict表
SELECT id FROM material_dict WHERE name = 'SUS301 3/4H'
```

未匹配的材料会记录到日志，但不会中断导入。

## 数据库表结构

### material_dict（材料字典）

```sql
- id: 主键
- code: 材料代码（唯一）
- name: 标准名称
- category: 分类（不锈钢、冷轧板等）
- sort_order: 排序
```

### customers（客户）

```sql
- id: 主键
- name: 客户名称
- sheet_key: 客户编号（A, B, C等）
```

### tooling（模具）

```sql
- id: 主键
- customer_id: 客户ID
- mold_number: 模具号（本厂产品编号）
- customer_product_no: 零件编号（原图产品编号）
- customer_product_name: 产品名称
- mold_type: 模具类型（连续模、工程模等）
- material: 材质原文
- material_id: 材质ID（外键）
- forming_steps: 成型步数
- press_tonnage: 冲床吨位
- cavity_count: 穴数（"1出2"）
- is_multi_product: 是否左右件
- product_count: 产品数量（1或2）
- seq: 序号
- ppap_no: PPAP编号
- vehicle_model: 车型
- remark: 备注
```

### parts（零件）

```sql
- id: 主键
- customer_id: 客户ID
- part_number: 零件编号（唯一）
- internal_name: 本厂产品名称
- customer_product_name: 客户产品名称
- material_id: 材质ID
- spec_twph: 用料规格原文
- thickness: 厚度(mm)
- width: 宽度(mm)
- pitch: 节距(mm)
- gross_weight: 毛重(g)
- net_weight: 净重(g)
- part_position: 零件位置（left/right）
- spray_status: 喷涂状态（默认: 'pending'）
- version: 版本（默认: 'v1'）
- part_status: 零件状态（默认: 'active'）
- stock_pcs: 库存数量（默认: 0）
- mold_number: 模具号
- mold_type: 模具类型
- press_tonnage: 冲床吨位
- ppap_no: PPAP编号
- customer_product_no: 客户零件号
- vehicle_model: 车型
```

## 常见问题

### Q: 导入失败怎么办？

1. 检查Excel文件路径
2. 检查数据库连接
3. 查看错误日志
4. 清空数据重新导入：

```python
# 清空tooling和parts表
async with engine.begin() as conn:
    await conn.execute(text('DELETE FROM parts'))
    await conn.execute(text('DELETE FROM tooling'))
```

### Q: 如何只导入部分客户？

修改 `import_data.py` 中的循环范围：

```python
# 只导入前5个客户Sheet
for sheet_idx in range(3, min(8, workbook.nsheets)):
    ...
```

### Q: 如何处理材料匹配失败？

材料匹配失败不会中断导入，会记录到日志：

```
[!] 材料匹配失败 (XX):
    浙江万宝机械有限公司(A) - 行10: SUS301-XXX
```

可以手动更新parts表的material_id：

```sql
UPDATE parts 
SET material_id = (SELECT id FROM material_dict WHERE name = 'SUS301 3/4H')
WHERE part_number = '60008581';
```

### Q: 导入需要多长时间？

- 材料导入: ~5秒
- 客户导入: ~10秒
- 主数据导入: ~2-5分钟（取决于数据量）

## 文件说明

```
excel/
├── 五金模具及产品清单表.xls       # Excel源文件（95个Sheet）
├── import_data.py                  # 主导入脚本（核心）
├── test_import.py                  # 测试脚本
├── verify_import.py                # 验证脚本
├── monitor_import.py               # 进度监控脚本
├── PROJECT_STATUS.md               # 项目状态
├── WORK_SUMMARY.md                 # 工作总结
└── USAGE_GUIDE.md                  # 本文档

materials_classified.json           # 材料分类数据
customer_list.txt                   # 客户列表
```

## 技术细节

### 事务管理

每个客户使用独立事务，避免级联失败：

```python
for sheet in all_sheets:
    async with engine.begin() as conn:  # 独立事务
        # 处理这个客户的所有数据
        ...
```

### 错误处理

```python
try:
    # 插入数据
    ...
except Exception as e:
    errors.append(f"行{row_idx}: {str(e)}")
    # 继续下一行，不中断整个导入
```

### 性能优化

- 使用异步数据库操作
- 批量插入（每个客户一个事务）
- 材料映射预加载到内存

## 联系与支持

遇到问题请查看：
1. [WORK_SUMMARY.md](WORK_SUMMARY.md) - 完整需求和业务逻辑
2. [PROJECT_STATUS.md](PROJECT_STATUS.md) - 当前状态和已知问题
3. 导入脚本输出日志 - 详细错误信息

---

**最后更新：** 2026-07-11
**版本：** v1.0
