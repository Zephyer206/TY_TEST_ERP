<!-- SPECKIT CONSTITUTION SYNC REPORT
Version change: 1.1.0 → 1.2.0 (MINOR)
Ratified: 2026-06-20
Last Amended: 2026-06-21
Principles added: 0
Principles strengthened: 1 (VIII-A 升级为"AI 自动 + 用户授权提权"双轨流程)
Templates checked: plan-template.md ✅, spec-template.md ✅, tasks-template.md ✅
TODO: 定期对照 .cursorrules 更新本文件

Amendment 2026-06-21 (v1.2.0): VIII-A 引入双轨提权流程
- 流程 A: AI 自动处理（taskkill + PowerShell Stop-Process）
- 流程 B: 用户明确授权时，AI 可生成自提权脚本（VBS/PowerShell Start-Process -Verb RunAs）
- UAC 弹窗由用户点击确认，AI 不直接获取管理员权限
- 授权识别关键词明确化（"授权管理员权限"等）
- 原因: 用户授权后，AI 仍无法提权，导致流程阻塞
-->
-->

# 云冲压 ERP Constitution

## 核心原则

### I. 中文优先（MUST）

所有对话、代码注释、Git 提交信息必须使用中文。
AI 助手行动前必须先用中文说明：运行什么、为什么。

### II. 技术栈锁定（MUST）

| 层 | 技术 | 禁止 |
|----|------|------|
| 后端框架 | FastAPI + SQLAlchemy async | 同步 ORM 调用 |
| 数据库驱动 | asyncpg + PostgreSQL | psycopg2（新代码） |
| 认证 | JWT Bearer Token | Session Cookie（新代码） |
| Schema 验证 | Pydantic v2 | 手写 dict 校验 |
| 迁移 | Alembic | 直接 DDL |
| 前端（管理后台） | Vue 3 + Element Plus | React / 原生 Jinja2（新功能） |

### III. 算力下推（MUST，不可协商）

统计聚合、逾期判定、吨位分组等计算**必须在 SQL `GROUP BY` / `CASE WHEN` 中完成**，禁止在 Python 层循环累加。

### IV. RBAC 权限模型（MUST）

| role_level | 角色 | 核心权限边界 |
|---|---|---|
| 1 | 操作工 | 仅车间报工 |
| 2 | 模具工程师 | 模具维修、打样 |
| 3 | 组长/主管 | 生产计划、工单 |
| 4 | 设计工程师 | T/W/P 参数、技术审核 |
| 5 | 业务经理 | 报价、发货、样件 |
| 9 | 老板 | 最终审批 |
| 10 | 超级管理员 | 视角切换，切换后隐藏 role_level ≥ 9 按钮 |

权限检查 MUST 通过 `core/permissions.py` 的 `@require_role` 装饰器，不得在路由内硬编码 `if role_level >= X`。

### V. 报价状态机完整性（MUST）

`quotes.approval_status` 只允许在 7 态链内流转：

```
WAITING_FOR_TECH → TECH_APPROVED → DRAFT → PENDING_BOSS → APPROVED
                → TECH_REJECTED                           → REJECTED
```

任何绕过状态机的直接 UPDATE 均为违规。状态变更必须通过 `state_machines/quote_states.py`。

### VI. 定点写入原子性（MUST）

`confirm_nomination()` 必须在同一事务内同步写入 `parts` 表的以下字段：
`customer_product_no`, `vehicle_model`, `mold_number`, `mold_type`, `press_tonnage`, `ppap_no`, `price_snapshot`。

任何单独写 `quotes` 而不同步 `parts` 的 nomination 操作均为违规。

### VII. 数据安全（MUST）

- 数据库密码等敏感信息禁止硬编码，通过 `.env` 注入
- `.env` 文件禁止提交 Git（已在 `.gitignore`）
- 所有 DELETE 操作改为 `is_deleted = true` 软删除（FR-085）
- SQL 查询必须使用参数化，禁止字符串拼接

### VIII. 服务稳定性（MUST）

- **服务端口固定为 `8000`，禁止修改** ⚠️ CRITICAL
  - 严禁通过修改端口号解决端口占用问题
  - 严禁在前端、后端、Docker、nginx 中将 8000 改为其他端口
  - 前端 API baseURL 必须硬编码为 `http://localhost:8000`，禁止通过环境变量绕过
  - 任何端口变更必须修改本宪法并升级 MAJOR 版本

- 修改 `.py` 文件后需完整重启（`reload=True` 不可依赖）
- 只在死锁时手动 kill 进程，禁止频繁重启

### VIII-A. 端口冲突处理流程（强制 + 用户授权双轨）

**核心原则**: AI 严禁自行更改端口，但当用户明确授权时，可协助提权操作。

#### 流程 A - AI 自动处理（无授权）

当 8000 端口被占用，AI 按以下顺序尝试：

1. **查找占用进程**：
   ```bash
   netstat -ano | grep ":8000" | grep LISTENING
   ```

2. **尝试 taskkill 终止**：
   ```bash
   taskkill //PID <pid> //F //T
   ```
   连续尝试 3 次，每次间隔 2 秒。

3. **尝试 PowerShell Stop-Process**：
   ```powershell
   Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```

4. **如果以上都失败**：
   - 生成管理员提权脚本 `force_clean_port8000_admin.bat`
   - **暂停并报告用户**，提供脚本路径和使用方法
   - 严禁擅自使用 8001 等其他端口绕过

#### 流程 B - 用户明确授权提权（特殊场景）

**当用户明确说"授权管理员权限"或"授权提权"时**，AI 可以：

1. **创建自提权 PowerShell 脚本**（使用 `Start-Process -Verb RunAs` 触发 UAC）：
   ```powershell
   Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -Command <清理命令>"
   ```
   UAC 弹窗由**用户点击确认**完成提权（这不违反"AI 不获取管理员权限"原则，因为实际点击是用户行为）。

2. **创建 VBS 自提权包装器**（避免 cmd 窗口闪退）：
   ```vbs
   Set UAC = CreateObject("Shell.Application")
   UAC.ShellExecute "powershell.exe", "-NoProfile -File script.ps1", "", "runas", 1
   ```

3. **绝不允许**:
   - AI 自己点击 UAC "是"按钮（这不可能也不应该）
   - AI 禁用 UAC
   - AI 修改系统安全策略
   - AI 偷偷使用其他端口"先跑起来再说"

#### 授权识别关键词

用户说以下任一表述，AI 可进入流程 B：
- "授权管理员权限"
- "授权提权"
- "用管理员权限清理"
- "force kill"
- "强制终止"
- "I authorize admin"

**未明确授权时，必须走流程 A。**

### VIII-B. 前端端口固定（MUST）

- 前端开发服务器固定端口：`5173`（Vite 默认）
- 前端 API baseURL 固定为：`http://localhost:8000`
- 禁止通过环境变量或配置文件绕过端口设置
- 禁止在 CI/CD、容器化部署中修改这些端口

## 业务数据规则

### 毛重核算公式（唯一真相源）

```
GrossWeight = (T × W × P × Density × cavities) / 1_000_000
Cost = (GrossWeight - ScrapWeight) × material_price - ScrapWeight × scrap_price
```

### 表职责分离

| 表 | 职责 | 禁止存入 |
|----|------|----------|
| `quotes` | 报价阶段唯一数据源 | 模具编号（预报价时未分配） |
| `parts` | 零件主档，定点后填充 | T/W/P、cavities、吨位 |
| `tooling_molds` | 模具台账 | 价格、客户信息 |

### 图纸路径规范

```
static/uploads/drawings/
    _unassigned/{part_id}/drawings/          ← 无客户时临时存放
    {客户名}/{零件名称}/{零件号}/drawings/    ← 标准路径
```

更新 `quotes.customer_id` 从 null → 有值时，MUST 触发 `migrate_drawings_for_quote(quote_id)`。

## 开发自检（每次 PR 前）

1. 统计聚合是否用 SQL `GROUP BY`？
2. 定点写入是否同步写入 parts 模具字段？
3. quotes 状态是否在 7 态链内流转？
4. datetime/Decimal 是否已通过 Pydantic schema 序列化？
5. 多表写入是否在同一事务（`async with session.begin()`）？
6. 新增路由是否注册到 `backend/app/main.py`？
7. 权限检查是否通过 `@require_role` 而非内联判断？
8. 敏感信息是否通过 `.env` 注入？
9. **后端服务是否使用 8000 端口？是否未通过修改端口解决冲突？** ⚠️
10. **前端 baseURL 是否硬编码为 `http://localhost:8000`？是否未通过环境变量绕过？** ⚠️

## Governance

- 本文件是最高治理文档，与代码冲突时以本文件为准
- 修改 MUST 级原则需要在此文件中明确记录，并提供迁移方案
- 新 spec 的 `/speckit.analyze` 必须对照本文件检查 CRITICAL 冲突
- 技术栈变更需 MAJOR 版本递增

**Version**: 1.1.0 | **Ratified**: 2026-06-20 | **Last Amended**: 2026-06-21
