# 阶段1：part_customer_aliases.customer_part_no 允许 NULL 修复报告

## 执行日期
2026-07-22

## 变更概述

根据唯一权威数据模型 `specs/001-erp-system-architecture/data-model.md` (行 124)，
`part_customer_aliases.customer_part_no` 字段应该声明为 `NOT NULL`，但实际业务场景中，
Excel 导入时可能存在只有模具号和内部件名、但缺少客户件号的记录。

本阶段修复了代码结构，使该字段在整个技术栈中允许 NULL 值，但**未执行数据库写入操作**。

## 修改文件清单

### 1. SQLAlchemy 模型
**文件**: `backend/app/models/part_customer_alias.py`
- **行 25**: 将 `customer_part_no` 从 `nullable=False` 改为 `nullable=True`
- **类型注解**: `Mapped[str]` → `Mapped[Optional[str]]`

```python
# 修改前
customer_part_no: Mapped[str] = mapped_column(String(150), nullable=False)

# 修改后
customer_part_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
```

### 2. Pydantic Schema - 零件详情
**文件**: `backend/app/schemas/part_detail.py`
- **行 21**: `PartCustomerAliasInfo.customer_part_no` 改为 `Optional[str]`

```python
# 修改前
customer_part_no: str

# 修改后
customer_part_no: Optional[str] = None
```

### 3. Pydantic Schema - 客户价格
**文件**: `backend/app/schemas/customer_price.py`
- **行 10**: `PartAlias.customer_part_no` 改为 `Optional[str]`
- **行 19**: `CustomerPartPriceInfo.customer_part_no` 改为 `Optional[str]`
- **行 65**: `CustomerPartYearPrice.customer_part_no` 改为 `Optional[str]`

```python
# 所有三处修改模式相同
# 修改前
customer_part_no: str

# 修改后
customer_part_no: Optional[str] = None
```

### 4. Alembic 数据库迁移
**文件**: `alembic/versions/20260722_allow_null_customer_part_no.py`（新增）
- **revision**: `20260722_allow_null_customer_part_no`
- **down_revision**: `v9_prod_sessions_qa`

**upgrade() 操作**:
- 使用 `op.alter_column()` 将 `customer_part_no` 的 `nullable=False` 改为 `nullable=True`
- PostgreSQL 执行 `ALTER COLUMN ... DROP NOT NULL`

**downgrade() 操作**:
- 回滚前检查是否存在 NULL 值
- 如有 NULL 记录，抛出异常，要求先手动清理
- 仅在无 NULL 数据时才恢复 NOT NULL 约束

## API 逻辑验证

已检查以下 API 端点，确认它们能正确处理 NULL 值：

1. **`backend/app/api/customer_prices.py`**
   - `GET /customer-prices/customers/{customer_id}/parts-with-prices` (行 175-286)
   - `GET /customer-prices/customers/{customer_id}/year-prices` (行 340-468)
   - 查询逻辑使用 LEFT JOIN，NULL 值自动透传到响应 schema

2. **`backend/app/api/parts_detail.py`**
   - `GET /parts/{part_id}/detail` (行 21-136)
   - 直接从数据库读取并映射到 schema，无需特殊处理

## 静态检查结果

### Python 语法检查
```bash
✓ app/models/part_customer_alias.py - 编译成功
✓ app/schemas/part_detail.py - 编译成功
✓ app/schemas/customer_price.py - 编译成功
✓ app/api/customer_prices.py - 编译成功
✓ app/api/parts_detail.py - 编译成功
```

### 模块导入验证
```bash
✓ PartCustomerAlias 模型导入成功
✓ 类型注解验证: Mapped[Optional[str]]
✓ PartCustomerAliasInfo schema 导入成功
✓ PartAlias.customer_part_no 类型验证: Optional[str]
✓ 所有 API 路由导入成功
```

### 迁移文件验证
```bash
✓ Alembic 迁移语法正确
✓ revision ID: 20260722_allow_null_customer_part_no
✓ down_revision: v9_prod_sessions_qa (当前 HEAD)
✓ upgrade/downgrade 函数存在
```

## 数据库唯一约束处理

`part_customer_aliases` 表的唯一约束（来自 `v7_delivery_qa_switch.py` 行 50-51）：

```sql
CONSTRAINT uq_part_customer UNIQUE (part_id, customer_name)
```

**注意**: 原始迁移中的约束是 `(part_id, customer_name)`，而不是权威设计中的 
`(customer_id, customer_part_no, revision)`。这可能需要在后续迁移中修正。

**PostgreSQL NULL 行为**:
- 在 UNIQUE 约束中，NULL 值不参与唯一性检查
- 允许多个 `(customer_id, NULL, revision)` 组合存在
- 这符合 SQL 标准和业务需求

## Excel 导入逻辑验证

**文件**: `backend/app/services/excel_import_service.py`
- **行 59**: `customer_part_no = row_data.get('原图产品编号', '').strip()`
- **行 64**: 验证逻辑允许 `customer_part_no` 为空，只要有 `(internal_name + tooling_number)`

```python
if not customer_part_no and not (internal_name and tooling_number):
    return True  # 空行
```

✓ 导入逻辑已兼容 NULL customer_part_no

## 未执行操作（按用户要求）

以下操作**未在本阶段执行**，等待后续指令：

1. ❌ 未运行 `alembic upgrade head` 执行数据库迁移
2. ❌ 未执行客户关系回填脚本
3. ❌ 未执行 TWP 数据写入
4. ❌ 未清理现有的空字符串占位值（如果存在）

## 执行数据库迁移的命令（待执行）

```bash
# 阶段2执行时运行：
cd /c/Users/WIT_User/Desktop/Zephyr_test_Erp
alembic upgrade 20260722_allow_null_customer_part_no

# 验证迁移结果
psql "$DATABASE_URL" -c "\d part_customer_aliases"
```

## 测试建议

### 单元测试（可选）
```python
# 测试创建 NULL customer_part_no 记录
async def test_create_alias_with_null_customer_part_no():
    alias = PartCustomerAlias(
        part_id=1,
        customer_id=2,
        customer_part_no=None,  # 允许 NULL
        revision='',
    )
    db.add(alias)
    await db.commit()
    assert alias.customer_part_no is None
```

### API 集成测试（可选）
```bash
# 测试 API 响应 NULL 值
curl http://localhost:8000/api/parts/123/detail
# 预期: customer_aliases[].customer_part_no 可能为 null
```

## 与权威设计的差异

### 当前实现 vs. 数据模型规范

| 字段/约束 | 权威设计 (data-model.md) | 当前实现 (v7) | 本次修复后 |
|-----------|-------------------------|--------------|-----------|
| customer_part_no | NOT NULL (行124) | NOT NULL | **NULL allowed** |
| 唯一约束 | (customer_id, customer_part_no, revision) | (part_id, customer_name) | 未修改 |
| customer_name 字段 | 不存在（应用 FK） | VARCHAR(200) NOT NULL | 未修改 |

### 需要后续解决的设计差异

1. **唯一约束不匹配**
   - 权威设计: `UNIQUE(customer_id, customer_part_no, revision)`
   - 当前实现: `UNIQUE(part_id, customer_name)`
   - **影响**: 无法支持同一零件对同一客户有多个修订版本

2. **customer_name 冗余字段**
   - 权威设计: 仅通过 `customer_id` FK 关联
   - 当前实现: 直接存储客户名称字符串
   - **影响**: 数据冗余，客户改名时需要更新多处

3. **customer_part_no NULL 约束**
   - 权威设计: 明确声明 NOT NULL (行124)
   - 业务需求: Excel 导入可能缺少客户件号
   - **本次决策**: 允许 NULL 以适应实际业务，需记录为设计偏差

## 推荐后续操作

### 短期（本次任务完成后）
1. 执行数据库迁移 `alembic upgrade head`
2. 运行完整 Excel 导入测试
3. 验证前端价格管理页面显示正常

### 中期（1-2周内）
1. 修正唯一约束为 `(customer_id, customer_part_no, revision)`
2. 评估是否移除 `customer_name` 冗余字段
3. 更新权威设计文档，记录 `customer_part_no` 允许 NULL 的业务场景

### 长期（下个迭代）
1. 完全对齐 `part_customer_aliases` 表结构与权威设计
2. 统一所有客户关系表的约束模式
3. 建立自动化测试覆盖 NULL 值场景

## 关键约束和原则（已遵守）

✅ 客户件号只能进入 `part_customer_aliases`，不得写入 `parts.internal_part_no`
✅ Excel 是唯一业务来源，不填充占位客户件号
✅ 未泄露密码、SECRET_KEY 或完整连接串
✅ 先阅读现有实现，做最小必要修改
✅ 禁止创建第二份数据库"最终设计"文档
✅ 以 `data-model.md` 为唯一权威设计依据

## 验收标准

- [x] SQLAlchemy 模型 `customer_part_no` 允许 NULL
- [x] 所有 Pydantic schema 使用 `Optional[str]`
- [x] Alembic 迁移文件创建并验证
- [x] Python 语法和导入测试通过
- [x] API 逻辑验证无需修改
- [x] Excel 导入逻辑兼容性确认
- [ ] 数据库迁移执行（待阶段2）
- [ ] 端到端功能测试（待阶段2）

## 技术栈确认

- **ORM**: SQLAlchemy 2.x (async)
- **Schema**: Pydantic V2
- **迁移**: Alembic
- **数据库**: PostgreSQL (UNIQUE 约束中 NULL 值不参与比较)
- **API**: FastAPI

---

**报告生成时间**: 2026-07-22  
**执行人**: Claude Code (Fable 5)  
**下一步**: 等待用户确认后执行阶段2（数据库写入和回填）
