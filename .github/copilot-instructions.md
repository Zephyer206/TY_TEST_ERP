<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/005-gaibo-after-sales/plan.md
<!-- SPECKIT END -->

---

## 已实施的技术决策

### 1. 报价单状态机 (7态)

```
WAITING_FOR_TECH → TECH_APPROVED
    ↓ (驳回)
TECH_REJECTED
    ↓
DRAFT → PENDING_BOSS → APPROVED
    ↓ (驳回)
REJECTED
```

### 2. 零件状态机 (4态)

```
DRAFT → SAMPLING → MASS_PRODUCTION → OBSOLETE
```

### 3. 模具状态机

```
AVAILABLE → MOUNTED → PRODUCING → FAULT → REPAIRING → AVAILABLE
                        ↓
                      PENDING_CHECK → AVAILABLE
```

### 4. 定点确认数据写入规则

quotes → parts 同步写入：

| quotes 字段 | parts 字段 |
|------------|-----------|
| customer_product_no | customer_product_no |
| vehicle_model | vehicle_model |
| mold_number | mold_number |
| mold_type | mold_type |
| press_tonnage | press_tonnage |
| ppap_no | ppap_no |
| price_snapshot | price_snapshot |

### 5. 数据库规范

- 使用 `psycopg2` + `RealDictCursor` 替代 ORM
- 所有查询使用 `.get()` 取值（避免 AttributeError）
- 事务必须包含 `commit()` / `rollback()`
- 统计聚合必须在 SQL 中完成（禁止 Python 循环累加）
- datetime/Decimal 使用 `isinstance` 预序列化

### 6. 角色权限表 (RBAC)

| role_level | 角色 | 部门 |
|------------|------|------|
| 1 | 操作工 | 生产部 |
| 2 | 模具工程师 | 开发部-模具组 |
| 3 | 组长/主管 | 生产/仓库/包装/品管 |
| 4 | 设计工程师 | 开发部-设计组 |
| 5 | 业务经理 | 业务部 |
| 9 | 老板 | - |
| 10 | 超级管理员 | admin |

### 7. 二维码前缀体系

| 前缀 | 实体类型 |
|------|----------|
| MAT | 原料批次 |
| MCN | 机台 |
| PFC | 工艺流转单 |
| PRT | 零件 |
| TLG | 模具工装 |
| PKG | 包装 |
| COT | 喷涂记录 |

### 8. API 前缀规范

| 前缀 | 模块 |
|------|------|
| sales.* | 业务部 |
| tech.* | 技术部 |
| prod.* | 生产部 |
| pkg.* | 包装发货 |
| mold.* / die.* | 模具管理 |
| qc.* / qa.* | 质检 |
| spray.* | 喷涂 |
| whse.* | 仓库 |
| admin.* | 管理员 |

### 9. 已实现模块清单

#### 后端 API

- `api/auth.py` - 认证登录
- `api/quotes.py` - 报价管理
- `api/parts.py` - 零件管理
- `api/price_accounts.py` - 价格台账
- `api/sampling_tasks.py` - 打样管理
- `api/toolings.py` - 模具管理
- `api/production.py` - 生产计划
- `api/machines.py` - 机台管理
- `api/warehouse.py` - 仓库管理
- `api/quality.py` - 质量管控
- `api/packaging.py` - 包装发货
- `api/coating.py` - 喷涂管理
- `api/admin.py` - 管理员（视角切换）
- `api/qr.py` - 二维码系统

#### 前端页面

- `views/login/` - 登录页
- `views/dashboard/` - 看板
- `views/quotes/` - 报价管理
- `views/parts/` - 零件管理
- `views/production/` - 生产计划
- `views/machines/` - 机台管理
- `views/warehouse/` - 仓库管理
- `views/quality/` - 质量管控

### 10. 超级管理员视角切换

- 切换时原始 `role_level` 存入数据库
- 切换期间 `role_level >= 3` 按钮必须隐藏
- 切换有效期 1 小时
- 切换历史可追溯

### 11. 软删除规范

- 所有 DELETE 操作改为 `is_deleted` 标记
- 查询时自动过滤 `is_deleted=True` 的记录

### 12. 安全规范

- 输入校验：XSS、SQL 注入防护
- JWT Token：24小时有效期
- CORS：仅允许配置的域名
- 敏感操作：记录审计日志
