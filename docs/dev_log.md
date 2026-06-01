# 开发日志

---

## 2026-05-06 上午 — 销售与交付神经系统：件号别名 + 日期追溯 + 对账 API

### 背景

根据 P1-P6 / B1-B5 / T2-T3 违规项，对业务层进行系统性修复：

| 违规项 | 说明 | 修复 |
|--------|------|------|
| P3 / P5 | 件号别名未在界面上显示 | 新增 `get_part_customer_alias()`，应用到发货列表 |
| P1 / P2 | `pkg_shipping_logs` 缺 actual_date / customer_id | 确认 DB 已有字段，补全写入逻辑 |
| B1 / B2 | 同上 | 确认 DB 已有字段，补全写入逻辑 |
| B5 / T2 / T3 | 前端 JS 计算对账数量 | 新增 `/api/pkg/reconciliation` 后端 API |
| P4 | 发货缺少件号映射有效性校验 | `check_pkg_shipping_eligibility` 增加 P4 警告 |
| P6 | 发货确认单元号显示格式不统一 | `pkg_shipping.html` 改为双格式显示 |

---

### 1. 数据库字段核查

| 表 | 字段 | 状态 |
|----|------|------|
| `pkg_packaging_logs` | `actual_date` | ✅ 已存在（DATE NOT NULL） |
| `pkg_shipping_logs` | `actual_date` | ✅ 已存在（DATE NOT NULL） |
| `pkg_shipping_logs` | `customer_id` | ✅ 已存在（INTEGER FK） |

---

### 2. db_service.py 新增函数

#### `get_part_customer_alias(internal_part_id, customer_id=None)` — 新增

```python
# 优先取该客户的别名；无映射则返回内部件号
alias = get_part_customer_alias(part_id, customer_id)
# → 'Z101 2102'  或  '大陆 1403'（无映射时）
```

#### `get_pkg_reconciliation(part_id, target_date=None)` — 新增

```python
# 后端对账 API 数据源
{
  "production_total":     1200,   # 某日冲压 approved 良品总数
  "packaging_total":      980,   # 某日已全检合格总数
  "pending_inspection":    220,   # 待全检余量 = prod - pkg
  "shipped_total":        450,   # 某日累计发货数
  "ready_to_ship":        530,   # 可发货库存 = pkg - shipped
}
```

**注意**：`pkg_packaging_logs` 全检数统计改用 `actual_date`（修复 B5：原用 `packed_at` 会导致跨天补录统计错误）。

#### `get_part_alias_map(part_ids, customer_id=None)` — 新增

批量查询件号别名，返回 `{part_id: alias}` 字典，用于列表页批量展示。

---

### 3. db_service.py 修改函数

#### `get_pkg_ready_inventory(customer_id=None)` — 重构

- 新增 `customer_id` 参数
- 返回结果增加 `customer_alias` 字段
- 配合 `pkg_shipping.html` 双格式件号显示

#### `submit_shipping_log(...)` — 升级

- 新增参数：`actual_date=None`, `customer_id=None`
- `actual_date` 写入发货记录的业务日期字段（支持 Back-dating）
- `customer_id` 写入客户关联字段

#### `submit_pkg_entry(...)` — 升级

- `pkg_packaging_logs` INSERT 增加 `actual_date` 字段（使用 `op_date`）
- `pkg_shipping_logs` INSERT 增加 `actual_date` 字段（使用 `op_date`）

#### `check_pkg_shipping_eligibility(part_id, qty, customer_id=None)` — 升级

- 新增 `customer_id` 参数
- 三重 Safety Guard（保持不变）
- **P4 规则（新增）**：若客户存在但无件号映射，返回 `(True, warning_msg)` — 警告不阻止

---

### 4. main.py 新增路由

#### `GET /api/pkg/reconciliation` — 新增

```
输入参数：part_id (int), date_str (YYYY-MM-DD)
输出：JSON {production_total, packaging_total, pending_inspection, shipped_total, ready_to_ship}

修复 B5：
- 全检数统计使用 DATE(actual_date)，而非 DATE(packed_at)
- 严禁前端 JS 计算，后端返回真实数据
```

#### `POST /pkg/shipping` — 升级

- 新增 `customer_id` 表单参数
- 通过 `check_pkg_shipping_eligibility` 的 warning 写日志
- 调用 `submit_shipping_log` 时传递 `actual_date` 和 `customer_id`

---

### 5. templates/pkg_shipping.html — 升级

**件号显示格式**（P6 修复）：

```
有别名时 → 客户件号（内部：内部件号）  例：Z101 2102（内部：大陆 1403）
无别名时 → 内部件号                    例：大陆 1403
```

---

### 文件变更清单

|| 文件 | 变更 |
||------|------|
| `db_service.py` | 新增 `get_part_customer_alias`、`get_pkg_reconciliation`、`get_part_alias_map`；升级 `get_pkg_ready_inventory`、`submit_shipping_log`、`submit_pkg_entry`、`check_pkg_shipping_eligibility` |
| `main.py` | 新增 `/api/pkg/reconciliation` 路由；升级 `/pkg/shipping` 提交处理 |
| `templates/pkg_shipping.html` | 件号双格式显示 |
| `docs/dev_log.md` | 本条目 |

### 待办 / 风险

- [ ] `part_aliases` 表为空，需要业务人员录入初始映射数据
- [ ] 发货扫码页面（`pkg_shipping.html`）目前未传递 `customer_id`，建议在销售订单中记录客户信息后传入
- [ ] `/api/pkg/reconciliation` 的 `date_str` 参数应支持 `?date_str=` 查询（已在实现中）

---

## 2026-05-05 下午（续3）— 机台维修逻辑并轨：状态机接入业务层

### 背景

会话断开后重启第一阶段，逐一核对已完成的 Schema 变更并修复 Alembic 依赖链。

---

### 1. MachineStateMachine 状态机

**文件**：`app/services/state_machine.py`

**结论**：✅ 无需修改。文件已完整实现以下内容：

- 四种状态：`running` / `pending_check` / `repairing` / `offline`
- 完整跳转矩阵：apply_repair / tech_intervene / complete_repair_online / confirm_mold_offline / force_reset
- 角色白名单校验
- `STATE_META` 颜色规范（绿/运行、蓝/维修、黄/警告、灰/停机）
- `is_production_locked()` / `is_running()` / `available_actions()` 等查询方法

---

### 2. Alembic 依赖链修复

#### 问题 1：`patch_position_levels_34.py` 缺少 revision 声明

- **现象**：`py -m alembic history` 报错 "Could not determine revision id"
- **根因**：该文件是独立数据迁移脚本（非 Alembic），被错误放在 `alembic/versions/` 目录
- **修复**：加入标准 Alembic revision 声明

```python
revision = 'p001patch_levels34'
down_revision = 'a1b2c3d4e5f6'
```

#### 问题 2：`tech_manager_refactor.py` down_revision 写错

- **根因**：`down_revision = 'patch_position_levels_34'` 写成了文件名而非 revision ID
- **修复**：`down_revision = 'p001patch_levels34'`

#### 最终依赖链（Alembic 完整）

```
<base>                                    → a1b2c3d4e5f6（users dept+position）
a1b2c3d4e5f6                             → p001patch_levels34
p001patch_levels34                        → xyz999tech_manager（tech_manager）
xyz999tech_manager                        → abc123tech_twoscan
abc123tech_twoscan                        → def456tech_pending_pool
def456tech_pending_pool                   → ghi789part_aliases
ghi789part_aliases                       → jkl012pkg_actual_date
jkl012pkg_actual_date                    → mno345pkg_shipping_customer
mno345pkg_shipping_customer              → spr0001spray_module  ← 新 head
```

---

### 3. 数据库 Schema 核对

| 检查项 | 文件 | 状态 |
|--------|------|------|
| `part_aliases` 表 | `alembic/versions/part_aliases_table.py` | ✅ 已创建（revision: `ghi789part_aliases`） |
| `pkg_packaging_logs.actual_date` | `alembic/versions/pkg_log_actual_date.py` | ✅ 已添加（revision: `jkl012pkg_actual_date`） |
| `pkg_shipping_logs.actual_date` | 同上 | ✅ 已添加 |
| `pkg_shipping_logs.customer_id` | `alembic/versions/pkg_shipping_customer.py` | ✅ 已添加（revision: `mno345pkg_shipping_customer`） |
| spray 模块 | `upgrade_spray_module.py` + `spr0001spray_module` | ✅ 已执行 + Alembic 存根已创建 |

---

### 4. spray 模块 Alembic 存根

**文件**：`alembic/versions/spray_module_migration.py`

**理由**：spray 模块通过独立脚本 `upgrade_spray_module.py` 部署，不走 Alembic。为了让 Alembic 历史与数据库实际状态同步，并成为新 head，新建存根迁移。

所有对象均用 `IF NOT EXISTS` 幂等保护，可安全重复执行。

---

### 文件变更清单

|| 文件 | 变更 |
||------|------|
| `alembic/versions/patch_position_levels_34.py` | 加入 Alembic revision 变量 `p001patch_levels34`，升级为合规迁移脚本 |
| `alembic/versions/tech_manager_refactor.py` | 修正 `down_revision` 为 `p001patch_levels34` |
| `alembic/versions/spray_module_migration.py` | **新建**：spray 模块 Alembic 存根迁移 |

---

### 待办 / 风险

- [x] 执行 `alembic upgrade head` 将 Alembic 历史同步到最新 head `spr0001spray_module` ✅
- [x] 状态机 `MachineStateMachine` 接入 `db_service.py` 维修函数 ✅（见下一节）
- [ ] `submit_pkg_packaging_log()` / `submit_shipping_log()` 需增加 `actual_date` 参数
- [ ] `part_aliases` 表的 CRUD 路由（`/parts/alias/...`）待实现

---

## 2026-05-05 下午（续3）— 机台维修逻辑并轨：状态机接入业务层

### 背景

将 `MachineStateMachine` 从纯"状态定义层"接入业务逻辑层，完成从"裸 UPDATE"到"状态机管控"的彻底迁移。

### 1. db_service.py 维修函数（已完成状态机并轨）

#### `request_machine_repair(machine_id, reporter_id)` — ✅ 已完成

- 调用 `MachineStateMachine("running").trigger("apply_repair", "prod_worker")`
- 校验：当前状态必须为 running，pending_check/repairing/offline 均拒绝
- 动作：状态 → `pending_check`，记录 `fault_reported_at`

#### `start_machine_repair(machine_id, tech_id)` — ✅ 已完成

- 调用 `MachineStateMachine(status).trigger("tech_intervene", "tech")`
- 校验：pending_check/running/offline 均可介入（直接扫），repairing 拒绝
- 动作：状态 → `repairing`，记录 `tech_arrival_time` / `diagnosing_start_time`

#### `finalize_repair_decision(machine_id, tech_id, decision)` — ✅ 已完成

- decision=`'online_fix'` → 触发 `complete_repair_online`，状态 → `running`
- decision=`'offline'` → 触发 `confirm_mold_offline`，状态 → `offline`
- 动作：清空所有维修时间戳；offline 时断开 `active_plan_id` 关联

#### `reset_machine_fault(machine_id, reset_by)` — ✅ 升级

- 调用 `MachineStateMachine(status).trigger("force_reset", "prod_leader")`
- 允许从 `pending_check` / `offline` 强制恢复为 `running`
- 清空全部维修时间戳和故障记录

#### `submit_production_log(...)` — ✅ 报工硬锁

```python
sm = MachineStateMachine(row['status'])
if sm.is_production_locked():
    raise Exception("机台状态为【{label}】，报工已锁定")
```

`is_production_locked()` 等价于：`pending_check ∨ repairing ∨ offline`

### 2. main.py 路由对齐

#### `/machines/{id}/fault`（POST）— ✅ 修复

- `fault_reason` 表单字段从必填（`Form(...)`）改为可选（`Form("")`）
- 底层调用 `request_machine_repair`（running → pending_check）

#### `/machines/{id}/request-offline`（POST）— ✅ 重构

- 从表单提交（重定向）改为 **JSON API**（AJAX 调用）
- 返回格式：`{"ok": true, "message": "..."}` 或 `{"ok": false, "message": "错误原因"}`
- 供 `operator_ui.html` AJAX 调用，无页面刷新

#### `/machines/{id}/fault-reset`（POST）

- `reset_machine_fault()` 返回 `(bool, str)`，函数已升级支持状态机

### 3. templates/operator_ui.html — ✅ 申请修理 AJAX 化

- 移除 `<form method="post" action="...">` 表单提交
- 新增 `doRequestRepair()` JS 函数，AJAX POST `/machines/{id}/request-offline`
- 成功后：全屏绿色反馈动画（800ms）→ 自动跳转回操作页面
- 失败后：内联红色 Banner 提示（5s 后自动消失）

**申请修理按钮显示条件**（底部固定栏）：
```
machine.status not in ('pending_check', 'repairing', 'offline')
```
即：仅 running / idle 时显示。

### 4. get_machines_with_faults() — ✅ 查询升级

- WHERE 条件从 `status = 'fault'` 扩展为 `status IN ('pending_check', 'repairing', 'offline')`
- 覆盖所有维修锁定状态，供管理端看板高亮

### 文件变更清单

|| 文件 | 变更 |
||------|------|
| `db_service.py` | `reset_machine_fault()` 接入状态机 force_reset；`get_machines_with_faults()` 扩展查询范围 |
| `main.py` | `/request-offline` 改为 JSON；`/fault` 移除 fault_reason 必填 |
| `templates/operator_ui.html` | 申请修理改为 AJAX + 全屏反馈动画 |
| `docs/dev_log.md` | 本条目 |

### 待办 / 风险

- [ ] `operator_ui.html` 中 repairing/offline 状态下的操作引导（显示"等待维修"或跳转提示）
- [ ] `tech/staff` 页面（模修员工端）尚未接入 `finalize_repair_decision`，仍使用旧路由 `/tech-complete` / `/tech-offline`
- [ ] 建议在维修完成时增加 `operation_logs` 维修事件记录，供追溯分析

---

## 2026-05-05 下午（续）— 状态机 + Schema 重构

### 背景

依据 `.cursorrules V3.0` 规范执行以下底层基础设施重构：

1. **状态机**：建立 `MachineStateMachine` 类，统一管理机台四种状态的合法跳转路径
2. **零件别名表**：`part_aliases` 支持一物多码（内部件号 ↔ 客户件号映射）
3. **日期追溯字段**：`pkg_packaging_logs` / `pkg_shipping_logs` 新增 `actual_date`，实现 Back-dating 补录
4. **发货客户关联**：`pkg_shipping_logs` 新增 `customer_id`，支持发货单按客户自动解析别名件号

---

### 1. 状态机：MachineStateMachine

#### 文件

`app/services/state_machine.py`（新建）

#### 四种状态定义

| 状态值 | 中文 | 颜色 | 说明 |
|--------|------|------|------|
| `running` | 运行中 | 绿 | 机台正常运行 |
| `pending_check` | 待修理 | 黄/橙 | 操作工已申请修理，等待技术人员到场（生产锁定） |
| `repairing` | 维修中 | 蓝 | 技术人员到场，扫码介入，开始维修（生产锁定） |
| `offline` | 停机 | 灰 | 模具已拆下，机台停止运行 |

#### 跳转矩阵

| 当前状态 | 动作 | 角色 | 目标状态 | 说明 |
|----------|------|------|----------|------|
| 任意 | `apply_repair` | prod_worker | `pending_check` | 操作工申请修理 |
| `pending_check` / `running` / `offline` | `tech_intervene` | tech | `repairing` | 技术人员到场介入（扫码即维修） |
| `repairing` | `complete_repair_online` | tech | `running` | 在线修复完成 |
| `repairing` | `confirm_mold_offline` | tech | `offline` | 确认拆模下线 |
| `pending_check` / `offline` | `force_reset` | prod_leader | `running` | 组长强制重置 |

#### 核心 API

```python
from app.services.state_machine import MachineStateMachine

sm = MachineStateMachine("pending_check")

# 技术人员到场介入
ok, msg, next_state = sm.trigger("tech_intervene", actor="tech")
# → (True, "技术人员到场介入", MachineState.REPAIRING)

# 维修完成
ok, msg, next_state = sm.trigger("complete_repair_online", actor="tech")
# → (True, "在线修复完成", MachineState.RUNNING)

# 查询
sm.is_production_locked()   # True  （pending_check/repairing/offline 均锁定）
sm.available_actions("tech") # ["tech_intervene", "complete_repair_online", ...]
```

#### 设计约束

- 状态变更必须经由 `MachineStateMachine.trigger()`，禁止直接在业务代码中 `UPDATE machines.status`
- 维修时间戳（`tech_arrival_time` / `diagnosing_start_time` / `mold_offline_time`）由状态机内部管理，业务层按需调用
- 角色白名单：`_check_role()` 基础校验，业务层可覆盖

---

### 2. 数据库 Migration：part_aliases 表

#### 文件

`alembic/versions/part_aliases_table.py`

#### 迁移链依赖

```
patch_position_levels_34
  ↓
tech_manager_refactor
  ↓
tech_twoscan_workflow
  ↓
tech_pending_pool  (旧 head)
  ↓
part_aliases_table  ← 新增
```

#### 表结构

```sql
CREATE TABLE IF NOT EXISTS part_aliases (
    id                    SERIAL PRIMARY KEY,
    internal_part_id      INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    customer_id           INTEGER NOT NULL REFERENCES tooling_customers(id) ON DELETE CASCADE,
    alias_part_number     VARCHAR(100) NOT NULL,
    alias_name            VARCHAR(200),
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_part_alias_part_customer UNIQUE (internal_part_id, customer_id),
    CONSTRAINT uq_alias_part_number UNIQUE (alias_part_number)
);
```

#### 索引

- `idx_part_alias_internal_part` ON `(internal_part_id)`
- `idx_part_alias_customer` ON `(customer_id)`

---

### 3. 数据库 Migration：actual_date 字段

#### 文件

`alembic/versions/pkg_log_actual_date.py`

#### 迁移链依赖

```
...（part_aliases_table 旧 head）
  ↓
pkg_log_actual_date  ← 新增
```

#### 变更

**pkg_packaging_logs**

```sql
ALTER TABLE pkg_packaging_logs
  ADD COLUMN actual_date DATE NOT NULL DEFAULT CURRENT_DATE;

ALTER TABLE pkg_packaging_logs
  ADD CONSTRAINT chk_pkg_packaging_actual_date
  CHECK (actual_date <= CURRENT_DATE);
```

**pkg_shipping_logs**

```sql
ALTER TABLE pkg_shipping_logs
  ADD COLUMN actual_date DATE NOT NULL DEFAULT CURRENT_DATE;

ALTER TABLE pkg_shipping_logs
  ADD CONSTRAINT chk_pkg_shipping_actual_date
  CHECK (actual_date <= CURRENT_DATE);
```

#### 旧数据迁移

```sql
UPDATE pkg_packaging_logs SET actual_date = CAST(created_at AS DATE) WHERE actual_date IS NULL;
UPDATE pkg_shipping_logs  SET actual_date = CAST(created_at AS DATE) WHERE actual_date IS NULL;
```

---

### 4. 数据库 Migration：pkg_shipping_logs.customer_id

#### 文件

`alembic/versions/pkg_shipping_customer.py`

#### 迁移链依赖

```
...（pkg_log_actual_date 旧 head）
  ↓
pkg_shipping_customer  ← 新增
```

#### 变更

```sql
ALTER TABLE pkg_shipping_logs ADD COLUMN customer_id INTEGER REFERENCES tooling_customers(id);
CREATE INDEX idx_pkg_shipping_customer ON pkg_shipping_logs(customer_id);
```

#### 说明

- 设为 NULLABLE，历史发货记录在补录时可能无法确定客户
- 业务层提交发货时可强制要求必填（编辑页面需注意）

---

### 文件变更清单

| 文件 | 变更 |
|------|------|
| `app/services/state_machine.py` | **新建** — `MachineStateMachine` 类及状态跳转逻辑 |
| `alembic/versions/part_aliases_table.py` | **新建** — `part_aliases` 建表迁移 |
| `alembic/versions/pkg_log_actual_date.py` | **新建** — `pkg_packaging_logs` / `pkg_shipping_logs` 新增 `actual_date` |
| `alembic/versions/pkg_shipping_customer.py` | **新建** — `pkg_shipping_logs` 新增 `customer_id` |
| `docs/dev_log.md` | 本条目 |

### 待办 / 风险

- [ ] 状态机 `MachineStateMachine` 需逐步接入现有 `db_service.py` 中的 `tech_intervene()` / `tech_complete_fix()` 等函数
- [ ] `submit_pkg_packaging_log()` / `submit_shipping_log()` 需增加 `actual_date` 参数
- [ ] `part_aliases` 表的 CRUD 路由（`/parts/alias/...`）待实现

---

## 2026-05-05 下午 — 喷涂模块 (Spraying)：多工序流转与参数化喷涂管理

### 背景

建立从冲压到喷涂再到全检的完整 WIP 流转链条，并实现喷涂物料消耗的量化核算。

### 数据库变更

#### 新增表

| 表名 | 用途 |
|------|------|
| `spraying_recipes` | 喷涂工艺配方（零件级别） |
| `spraying_logs` | 喷涂报工记录 |
| `spraying_material_consumption` | 物料消耗流水（溯源） |

#### `spraying_recipes` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `part_id` | INTEGER FK | 关联零件 |
| `sand_material` | VARCHAR(200) | 喷砂原料名 |
| `sand_dosage` | NUMERIC(10,4) | 喷砂单件定额 (kg/件) |
| `coating_material` | VARCHAR(200) | 涂料名 |
| `coating_dosage` | NUMERIC(10,4) | 涂料单件定额 (kg/件) |
| `surface_type` | VARCHAR(30) | 单面/双面/局部 (single/double/partial) |
| `coating_color` | VARCHAR(100) | 涂料颜色描述 |

#### `spraying_logs` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `part_id` | INTEGER FK | 关联零件 |
| `quantity` | INTEGER | 产出数量 |
| `operator_id` | INTEGER FK | 报工操作员（员工端） |
| `manager_id` | INTEGER FK | 补录主管（管理端） |
| `actual_date` | DATE | 实际生产日期（跨日补录） |
| `is_calculated` | BOOLEAN | 是否已按配方计算物料消耗 |
| `remark` | TEXT | 备注 |

#### `parts` 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `spray_status` | VARCHAR(30) | 工序状态：pending/stamped/qc_passed/pkg_ready/shipped |
| `spray_stamped_at` | TIMESTAMP | 喷涂完成时间 |

#### 迁移脚本

`upgrade_spray_module.py` — 执行 `py upgrade_spray_module.py`

### 核心业务逻辑

#### 入口 A（员工移动端）：极简扫码报工

- 页面：`/spray/scan`
- 仅输入【产量】，自动取当天日期
- 工艺要求展示（单面/双面/局部 + 涂料颜色）
- 允许在未配置 `spraying_recipes` 的情况下报工（`is_calculated=FALSE`）

#### 入口 B（管理端补录）：批量跨日报工

- 页面：`/spray/manager`
- 支持主管按【实际日期】批量录入多款零件的总产量
- 按日期查询和补录

#### 库存联动

- 喷涂报工成功后，`parts.spray_status` → `'stamped'`
- 喷涂报工作为 `pkg` 入口的数据源之一（衔接全检包装）

#### 工艺参数管理与追溯计算

- 页面：`/spray/recipe`
- 主管可随时新增或修改零件的喷砂/涂料定额
- 【同步历史消耗】按钮：扫描零件所有 `is_calculated=FALSE` 记录，按最新参数计算物料消耗
- 计算公式：`物料消耗 = 产出数量 × 单件定额`

#### 物料消耗溯源表

` spraying_material_consumption`：
- 记录每次计算的消耗明细（material_name / material_type / consumed_qty / total_cost）
- 支持与仓库实际领料对账

### 工序看板

页面：`/spray/kanban`（老板和业务可见）

状态节点流转：
```
【已冲压】 → 【已喷涂】 → 【已全检】 → 【已发货】
```

数据来源：`parts.spray_status` + `production_logs`（冲压）+ `pkg_packaging_logs`（全检）+ `pkg_shipping_logs`（发货）

### 物料统计看板

页面：`/spray/material`（spraying / whse / admin 可见）

- 汇总各型号喷砂、涂料的理论累计消耗量
- 零件明细：每个零件的喷涂产出 + 喷砂消耗 + 涂料消耗
- 未同步警告：显示有待计算消耗的零件列表

### API / 路由

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/spray/scan` | GET | spraying/admin Lv.1+ | 员工扫码报工页 |
| `/spray/scan/submit` | POST | spraying/admin | 员工提交报工 |
| `/spray/manager` | GET | spraying/admin | 管理端批量补录页 |
| `/spray/manager/submit` | POST | spraying/admin | 管理端补录提交 |
| `/spray/recipe` | GET | spraying/admin | 工艺配方管理页 |
| `/spray/recipe/save` | POST | spraying/admin | 保存/更新配方 |
| `/spray/recipe/sync` | POST | spraying/admin | 同步历史消耗 |
| `/spray/kanban` | GET | admin/sales Lv.5+ | 工序流转看板 |
| `/spray/material` | GET | spraying/whse/admin | 物料统计看板 |
| `/spray/part/{id}` | GET | spraying/admin | 零件喷涂详情页 |

### 权限设计

- 喷涂报工：dept in ('spraying', 'admin')
- 工艺配方维护：dept in ('spraying', 'admin')
- 工序看板：dept in ('admin', 'sales', 'spraying') 或 Lv.5+
- 物料统计看板：dept in ('admin', 'spraying', 'whse') 或 Lv.5+

### UI 设计

| 页面 | 风格 |
|------|------|
| `spray_scan.html` | 深色背景，员工极简化大按钮，配方工艺要求横幅，数字键盘 |
| `spray_recipe.html` | 紫色主题，配方卡片 + 同步消耗按钮，Tab 切换 |
| `spray_manager.html` | 绿色主题，日期选择 + 补录表单 + 记录列表 |
| `spray_kanban.html` | 深色背景，节点状态栏 + 工序卡片进度条 |
| `spray_material.html` | 棕色主题，物料消耗卡片 + 零件明细表格 |
| `spray_part_detail.html` | 紫色主题，零件详情 + 配方参数 + 报工记录 |

### 文件变更清单

| 文件 | 变更 |
|------|------|
| `upgrade_spray_module.py` | 新建，数据库迁移脚本 |
| `db_service.py` | 新增 13 个喷涂相关函数 |
| `main.py` | 新增 14 个喷涂路由 + 权限守卫函数；home 路由新增 spraying 分支 |
| `templates/spray_scan.html` | 新建，员工极简扫码报工页 |
| `templates/spray_recipe.html` | 新建，工艺配方管理页 |
| `templates/spray_manager.html` | 新建，管理端批量补录页 |
| `templates/spray_kanban.html` | 新建，工序流转看板 |
| `templates/spray_material.html` | 新建，物料统计看板 |
| `templates/spray_part_detail.html` | 新建，零件喷涂详情页 |
| `templates/index.html` | spraying 部门视图 + admin Lv.5+ 快捷入口 |
| `.cursorrules` | 1.1 节新增 spraying 部门定义 |
| `docs/dev_log.md` | 本条目 |

### 待办风险

- [ ] 需在数据库创建 `spraying` 部门用户并分配 `dept='spraying'`
- [ ] 库存联动：`spray_status` 与 `pkg` 全检入口的衔接逻辑待在实际使用中验证
- [ ] 涂料单价（`unit_cost`）字段目前默认 0，物料对账时尚未计算成本金额

---

## 2026-05-05 上午 — 技术部待修池自动流转与模糊搜索重构

### 背景

重构技术部维修流程，从"扫码即触发"升级为"待修池 + 模糊搜索 + 维修限制"：

1. **自动流转**：师傅在机台端点击"确认拆模下线"，系统自动在 `mold_offline_records` 创建一条 `pending_offline_repair` 状态记录，出现在师傅的待修池列表中
2. **模糊搜索**：师傅可在待修池顶部搜索框，通过模具号（mold_number）、零件名（part_name）进行模糊匹配（ILIKE）
3. **维修限制**：同一时间一名师傅只能"正在维修"一套模具，防止数据混乱
4. **状态闭环**：正在维修的模具卡片置顶显示，点击"维修完成"弹出确认框，状态更新为 `ready_to_use`

### 数据库变更

#### 1. `mold_offline_records.maintenance_status` CHECK 约束扩展

```sql
ALTER TABLE mold_offline_records DROP CONSTRAINT IF EXISTS chk_maintenance_status;
ALTER TABLE mold_offline_records ADD CONSTRAINT chk_maintenance_status
CHECK (maintenance_status IN (
    'waiting_parts', 'major_repair', 'offline',
    'pending_offline_repair',  -- ★ 新增：自动流转进入待修池
    'in_repair', 'ready_to_use', 'reinstalled'
));
```

#### 2. 全文搜索索引（GIN Trigram）

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_offline_mold_number_trgm ON mold_offline_records USING gin (mold_number gin_trgm_ops);
CREATE INDEX idx_offline_mold_name_trgm   ON mold_offline_records USING gin (mold_name gin_trgm_ops);
```

#### 3. 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `assigned_tech_id` | INTEGER | 维修责任人（FK → users） |
| `repair_start_time` | TIMESTAMP | 维修开始时间 |
| `repair_end_time` | TIMESTAMP | 维修结束时间 |
| `current_part_number` | VARCHAR(100) | 当前生产零件号 |
| `current_part_name` | VARCHAR(200) | 当前生产零件名 |

### API / 路由

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/tech/pool` | 师傅端待修池页面（HTML） |
| GET | `/tech/pool/json` | 待修池数据接口，支持 `?search=` 模糊搜索 |
| POST | `/tech/pool/start` | 师傅点击【开始维修】，`record_id` 参数 |
| POST | `/tech/pool/complete` | 师傅点击【维修完成】，`record_id` 参数 |
| POST | `/tech/pool/confirm-offline` | 机台端师傅【确认拆模下线】，`machine_id` 参数 |
| GET | `/tech/scan/query` | `status_display` 增加 `pending_offline_repair` 映射 |

### 核心逻辑

#### 状态流转图

```
机台端：
  机台运行中（running）
      ↓ 师傅点击"确认拆模下线"
  mold_offline_records: pending_offline_repair（自动创建）

师傅端待修池：
  pending_offline_repair（待修池）
      ↓ 师傅点选 + 点击"开始维修"
  in_repair（维修中）★ 限制：同一时间每人只能有一条 in_repair
      ↓ 师傅点击"维修完成"
  ready_to_use（已修好待装机）
```

#### 维修限制逻辑（`tech_start_repair`）

```python
# 1. 检查是否已有 in_repair 记录
existing = SELECT id FROM mold_offline_records
           WHERE assigned_tech_id = %s AND maintenance_status = 'in_repair'
if existing:
    return False, f"您正在维修 {existing.mold_number}，无法同时接单"

# 2. 验证目标状态
if record.maintenance_status != 'pending_offline_repair':
    return False, "当前状态不允许开始维修"

# 3. 更新
UPDATE mold_offline_records
SET maintenance_status = 'in_repair',
    repair_start_time = NOW(),
    assigned_tech_id = %s
WHERE id = %s
```

#### 模糊搜索（`get_pending_repair_pool`）

```sql
WHERE mor.maintenance_status = 'pending_offline_repair'
  AND (
      mor.mold_number    ILIKE %s   -- 模具号
      OR mor.mold_name   ILIKE %s  -- 模具名
      OR mor.current_part_name ILIKE %s  -- 零件名
      OR mor.current_part_number ILIKE %s  -- 零件号
  )
```

### UI 设计

#### 师傅端待修池页面 `/tech/pool`（tech_pool.html）

- **顶部**：师傅姓名 + 角色标签
- **置顶卡片**（正在维修）：蓝色渐变大卡片，模具号居中，离线总时长计时器，绿色"维修完成"大按钮
- **搜索栏**：支持回车搜索 + 清空按钮
- **待修列表**：每张卡片左侧红色边框，模具号、等候时长（超过2小时显示渐变红）、零件信息
- **确认弹层**：简约遮罩弹框，仅"取消"和"确认"两按钮
- **实时性**：每15秒自动刷新，下拉可手动刷新

#### 机台端师傅页面（tech_staff.html 改造）

- "确认拆模下线"按钮从 `<form submit>` 改为 AJAX 调用 `/tech/pool/confirm-offline`
- 操作成功后 Toast 提示"已加入待修池"，1.5秒后自动刷新页面

### 文件变更

| 文件 | 变更 |
|------|------|
| `alembic/versions/tech_pending_pool.py` | 新增 migration 脚本 |
| `db_service.py` | 新增 5 个函数 |
| `main.py` | 新增 5 个路由 |
| `templates/tech_pool.html` | 新建师傅端待修池页面 |
| `templates/tech_staff.html` | 改造"确认拆模下线"按钮为 AJAX |
| `templates/tech_scan.html` | 扫码成功结果增加"进入待修池"按钮 |
| `templates/index.html` | 首页快捷入口增加"待修池" |

---

## 2026-05-05 凌晨（续）— 技术部"极简两扫制"维修闭环

### 背景

简化技术部模具维修流程，实现"扫码即触发"的极简操作。师傅只需两扫：

1. **第一扫**：待维修模具 → 开始维修
2. **第二扫**：维修中模具 → 完成维修

### 核心逻辑

#### 两扫制状态机

```
offline（待维修）
  ↓ 第一扫（自动记录开始时间，关联责任人）
in_repair（维修中）
  ↓ 第二扫（仅限同一人，自动记录结束时间）
ready_to_use（已修好待装机）
  ↓ 装机后
reinstalled（已装机）
```

#### 扫码解析逻辑

支持多种扫码输入：
1. `mold_offline_records.id` - 直接记录ID
2. `模具编号` - 通过 molds 表关联机台
3. `机台编号` - 直接定位机台

### 数据库变更

**mold_offline_records 表扩展**

| 字段 | 类型 | 说明 |
|------|------|------|
| `repair_start_time` | TIMESTAMP | 维修开始时间 |
| `repair_end_time` | TIMESTAMP | 维修结束时间 |
| `current_part_number` | VARCHAR | 当前加工零件编号 |
| `current_part_name` | VARCHAR | 当前加工零件名称 |

**maintenance_status CHECK 约束扩展**

```sql
CHECK (maintenance_status IN (
    'waiting_parts',    -- 待件（保留）
    'major_repair',   -- 大修中（保留）
    'offline',        -- 下线待修（新增）
    'in_repair',      -- 维修中（新增）
    'ready_to_use',   -- 已修好待装机（新增）
    'reinstalled'     -- 已装机（保留）
))
```

### API / 路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/tech/scan` | GET | 员工扫码页面 |
| `/tech/scan/process` | POST | 两扫制处理接口 |
| `/tech/scan/query` | GET | 查询模具状态（非技术部人员） |

### 两扫制处理逻辑

```python
def tech_twoscan_process(mold_key, tech_user_id):
    # 1. 解析扫码内容
    resolve_result = resolve_mold_by_key(mold_key)
    
    # 2. 获取下线记录
    record = get_offline_record(resolve_result)
    
    # 3. 状态机判断
    if current_status == 'offline':
        # 第一扫：开始维修
        update('in_repair', repair_start_time=NOW(), assigned_tech_id=tech_user_id)
        return '开始维修'
    
    elif current_status == 'in_repair':
        if assigned_tech_id != tech_user_id:
            return '不是责任人，无法操作'  # 权限拦截
        # 第二扫：完成维修
        update('ready_to_use', repair_end_time=NOW())
        return '维修完成'
```

### 权限拦截

**技术部员工**（dept='tech' 或 is_tech=TRUE）：
- 可进行扫码操作
- 触发状态变更

**非技术部人员**：
- 仅可查询模具当前状态
- 不触发任何状态变更

### UI 设计

#### 员工端（tech_scan.html）

**首页**：
- 全屏深蓝背景
- 巨大的绿色扫码按钮（200px 圆形）
- 脉冲动画
- 手动输入框作为补充

**结果页**：
- 全屏渐变色背景（根据状态变色）
- 大图标 + 醒目标题
- 模具信息卡片
- "继续扫码"按钮

#### 管理端（tech_manager.html）

**三列看板**：
- ⏳ 待维修（红色边框）
- 🔧 维修中（蓝色边框）
- ✅ 已修好（绿色边框）

**绩效统计**：
- 师傅工时排行
- 高频故障模具排行

### 文件变更清单

| 文件 | 变更 |
|------|------|
| `alembic/versions/tech_twoscan_workflow.py` | **新建** - 数据库迁移脚本 |
| `db_service.py` | 新增 4 个函数 |
| `main.py` | 新增 3 个路由 |
| `templates/tech_scan.html` | **新建** - 员工扫码页面 |
| `templates/tech_manager.html` | 重写任务池看板 + 绩效统计 |
| `templates/index.html` | 更新技术部入口 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-05-05 凌晨 — 技术部管理端（主管/课长）重构：效率统计与异常预警

### 背景

重构技术部管理端（主管/课长视角）UI/UX，核心需求：实时监控 + 敏捷调度 + 故障分析。

### 需求规格

1. **实时维修雷达 (Real-time Radar)**
   - 展示所有当前异常机台的卡片（fault/pending_check/repairing/offline）
   - 时效标识：自动计算并展示等待时长（当前时间 - 报修时间）
   - 状态穿透：点击卡片可查看是哪位师傅在修，以及该师傅本月的平均维修效率
   - 渐变红视觉提醒：超时未响应任务（等待>60分钟）卡片背景变为渐变红

2. **修模间任务池 (Offline Molds Queue)**
   - 专门建立一个列表，管理所有已拆模（status='offline'）的模具
   - 状态维护：允许主管更新下线模具的维修节点（待件/大修中/已修好待装机/已装机）
   - 无弹窗设计：状态更新通过下拉选择框直接提交

3. **模具故障分析 (Root Cause Analysis)**
   - Top 5 易损模具：按报修频率排序
   - 维修时长趋势：按天/周统计平均停机时长

4. **权限与入口**
   - 此页面仅限 dept='tech' 且 position='manager' 访问
   - 或 is_tech=TRUE 且 role_level >= 5

5. **视觉约束**
   - 取消所有弹窗
   - 超时未响应任务通过卡片背景色变为渐变红进行视觉提醒

### 数据库 Schema 变更

**新增表：mold_offline_records**
```sql
CREATE TABLE mold_offline_records (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER NOT NULL,
    mold_number VARCHAR(100),
    mold_name VARCHAR(200),
    fault_reason TEXT,
    offline_time TIMESTAMP NOT NULL DEFAULT NOW(),
    maintenance_status VARCHAR(50) NOT NULL DEFAULT 'waiting_parts',
    status_updated_at TIMESTAMP DEFAULT NOW(),
    status_updated_by INTEGER,
    assigned_tech_id INTEGER,
    remark TEXT,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**新增字段：machines.tech_user_id**
- 记录当前维修责任人（模修师傅）

### 路由变更

| 路由 | 方法 | 说明 |
|------|------|------|
| `/tech/manager` | GET | 技术部管理端主页（权限卡控） |
| `/tech/manager/json` | GET | 实时数据 API（轮询刷新） |
| `/tech/manager/offline-status` | POST | 更新下线模具维修节点 |
| `/tech/manager/create-offline-record` | POST | 创建下线记录 |
| `/tech/manager/machine/{id}/detail` | GET | 机台详情（含维修日志+责任人效率） |
| `/tech/manager/tech/{id}/efficiency` | GET | 指定师傅月度效率 |

### 权限判定逻辑

```python
def is_tech_manager(user):
    dept = user.get('department') or user.get('dept') or ''
    position = user.get('position') or ''
    return (
        (dept == 'tech' and position == 'manager') or
        (user.get('is_tech', False) and user.get('role_level', 0) >= 5)
    )
```

### 维修节点状态枚举

| 状态值 | 含义 | 前端显示 |
|--------|------|----------|
| `waiting_parts` | 待件 | 待件 |
| `major_repair` | 大修中 | 大修中 |
| `ready_to_install` | 已修好待装机 | 已修好待装机 |
| `reinstalled` | 已装机 | 已装机 |

### 视觉约束实现

**渐变红卡片（超时>60分钟）**
```css
.radar-card.overdue {
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    border-color: #ef4444;
    animation: pulse-danger 2s ease-in-out infinite;
}
@keyframes pulse-danger {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
}
```

**无弹窗设计**
- 详情面板：侧边栏展开（从右侧滑入）
- 状态更新：下拉框 + onchange 直接提交表单

### 文件变更清单

| 文件 | 变更 |
|------|------|
| `migrate_tech_manager.py` | 数据库迁移脚本 |
| `db_service.py` | 新增 6 个数据服务函数 |
| `main.py` | 新增 7 个路由 + 权限函数 |
| `templates/tech_manager.html` | 新建：技术部管理端页面 |
| `templates/index.html` | 新增 tech 部门入口 |
| `docs/dev_log.md` | 本条目 |

### 待办风险

- [x] 权限校验需区分 dept='tech' position='manager' vs is_tech + role_level >= 5
- [x] 机台状态需前端轮询刷新（当前 30 秒自动刷新）
- [x] 状态更新需无弹窗设计（下拉框 + 表单提交）

---

## 2026-05-05 上午（第六轮）— 生产部管理端（主管/组长）UI/UX 重构

### 背景

重构生产部管理端（主管/组长视角）UI/UX，核心需求：实时监控 + 敏捷调度。

### 需求规格

1. **首页逻辑：车间实时网格 (Workshop Grid)**
   - 以机台为单位展示磁贴，实时抓取 `Machine.status`
   - `running`：显示零件名 + 进度条
   - `request_offline`：红色闪烁图标，显示"待修理"
   - `offline`：显示"开发人员修理中"
   - 点击穿透：弹出操作菜单【下发任务】【异常干预】【强制完工】

2. **待产任务池 (Order Pool)**
   - 侧边栏展示业务部同步过来的所有订单
   - 支持拖拽或一键分配至机台，分配后自动更新机台的 `active_plan_id`

3. **维修时效监控**
   - 针对"申请修理"和"修理中"机台，显示已耽误分钟数计时器

4. **生产汇总看板**
   - 今日全组累计良品数，与昨日对比
   - 当前部门平均开工率（基于吨位分类）

5. **权限卡控**
   - 仅限 `dept='prod'` 且 `position='manager'` 或 `position='supervisor'` 访问

### 数据库 Schema

- `machines` 表已含 `status`, `active_plan_id`, `fault_reason`, `fault_reported_at`, `tech_arrival_time`, `diagnosing_start_time`
- 新增 API：`GET /prod/manager/json`（实时数据）、`POST /prod/manager/assign`（分配任务）、`POST /prod/manager/intervene`（异常干预）、`POST /prod/manager/force-complete`（强制完工）、`GET /prod/manager/repair-log/{id}`（维修日志）

### 待办风险

- [x] 权限校验需区分 Lv.5（组长）和 Lv.9（主管/经理）
- [x] 机台状态需前端轮询或 WebSocket 刷新（当前轮询 5s）
- [x] 任务池分配需事务保证 `active_plan_id` 原子更新

---

## 2026-05-05 上午（第六轮第三次）— 模修员工端重构：合并诊断阶段

### 背景

简化机台维修状态机，模修员工端 UI 从"诊断+维修两阶段"合并为"单阶段维修"。

### 变更内容

#### 1. 状态机精简
- **删除 `diagnosing`（诊断中）状态**
- 新流程：`pending_check` → 扫码介入 → `repairing`（维修中）→ `running` / `offline`

#### 2. `db_service.py` 关键变更
- `tech_intervene()`：状态改为 `repairing`，保留 `diagnosing_start_time` 列名不变（列名不改动，保持 DB Schema 兼容）
- `tech_complete_fix()`：WHERE 条件从 `diagnosing` → `repairing`
- `tech_confirm_mold_offline()`：`repairing` 状态时，清空 `current_mold_id`、`active_plan_id`、`current_part_id`（生产计划断联）
- `intervene_machine()`：prod 主管干预逻辑同步更新
- `get_manager_dashboard_data()`：`repairing` 替换 `diagnosing`
- `get_tonnage_dashboard()`：`repairing` 替换 `diagnosing`
- `get_machine_repair_log()`：维修时间线蓝点（到场+修理）

#### 3. 模修员工首页 (`/tech/staff`)
- 顶部大按钮【扫码维修】+ 手动输入编号入口
- 待维修清单（`pending_check` 状态机台）：报修时间 + 等候分钟数 + 接单按钮
- 权限：`is_tech=TRUE` 用户专属

#### 4. 维修决策界面（repairing 状态）
- 蓝色主题：`#1e3a5f → #2563eb` 渐变
- 显示：机台编号、故障描述、模具/零件/操作员
- **已维修计时器**（蓝色数字，HH:MM:SS 格式）
- 两个大按钮（适配手机端）：
  - 【✅ 在线修复完成】→ `running`
  - 【🔧 确认拆模下线】→ `offline`（同时解绑生产计划）

#### 5. 模板更新
- `templates/prod_manager_dashboard.html`：`diagnosing` → `repairing`（状态角标蓝、呼吸灯动画）
- `templates/machines.html`：CSS 类 + Jinja2 条件
- `templates/tech_analytics.html`：状态行显示

### 变更内容

1. **状态角标动态化**（替换旧居中弹窗）
   - `pending_check`：红色闪烁角标 + 红点动画 + 文字"待诊"
   - `repairing`（维修中）：蓝色呼吸灯角标 + 蓝点动画 + 文字"维修中"
   - `offline`：灰色静态角标 + 文字"停机"

2. **响应计时器 15 分钟阈值**
   - 维修计时器超 15 分钟：背景变红 + 数字加粗（移除旧 30/60 分钟档）
   - JS 每 10 秒刷新秒数

3. **维修日志滑出侧边栏**
   - 点击异常机台磁贴 → 操作菜单 → 【维修日志】
   - 右侧滑出面板（320px），显示：
     - 当前状态摘要（状态/故障原因/操作员/模具）
     - 维修时间线（红点=报障、蓝点=到场修理、绿点=完工、灰点=其他）
   - 数据来源：`machines` 表 + `operation_logs` + `production_logs`
   - 新 API：`GET /prod/manager/repair-log/{machine_id}`
   - 面板内提供"异常干预"快捷按钮

---

## 2026-05-05 上午（第五轮）— 生产部机台操作端 UI/UX 极简与防错

### 背景

重构生产部（机台操作端）UI/UX，遵循"极简与防错"原则，面向车间一线操作工在移动端使用。

### 需求规格

1. **首页：扫码优先模式**
   - 仅保留占据屏幕主要面积的【扫码启动】大按钮
   - 移除次要链接和文字说明

2. **报工界面（核心）**
   - 顶部大字显示【内部零件名】和【机台号】
   - 进度条可视化完成百分比
   - 报工输入框点击后弹出**全屏大数字键盘**
   - 报工成功后弹出全屏 0.5 秒绿色勾选反馈，自动重置输入框

3. **异常处理**
   - 屏幕下方显著位置放置【申请拆模】红色大按钮
   - 点击后弹窗确认，实时更新机台状态为 `request_offline`

4. **移动端适配**
   - Mobile-First，所有按钮高度 ≥ 60px
   - 隐藏侧边栏/页头/页脚，最大化操作区域

5. **语言约束**
   - 使用车间通用词汇：报工、修模、拆模

### Schema / 逻辑变更

- 新增机台状态 `request_offline`：操作员申请拆模，维修人员处理
- `update_machine()` 支持写入 `status='request_offline'`
- 新增路由 `POST /machines/<id>/request-offline`

### 文件变更

- `templates/operator_scan.html` — 完全重写，极简扫码入口
- `templates/operator_ui.html` — 完全重写，核心 UX 改造
- `db_service.py` — `update_machine()` 已支持 status 参数
- `main.py` — 新增 `request_offline` 路由

---

## 2026-05-04 下午（第四轮）— 原材料来料质量卡控

### 背景

原材料入库后必须经品质部审核"合格"才能投入生产，防止来料不良流入车间。本次升级在原材料表增加 `material_status` 字段，并在报工提交时强制校验。

### Schema 变更

**新增字段**
- `materials.material_status`：VARCHAR(20)，默认 `'pending'`，CHECK 约束 `IN ('pending','qualified','rejected')`
- `production_logs.material_id`：INTEGER FK → materials(id)，记录报工时使用的原材料卷号

**material_status 流转**

```
入库（add_material）→ pending（待检）
    ↓ QC 来料审核
├→ qualified（合格）→ 可用于生产报工
└→ rejected（拒收）→ 严禁用于生产报工
子料（自动分条）→ qualified（继承合格母卷，无需重复审核）
```

### 核心逻辑

**报工防错流程**

```
POST /operator/report { part_id, machine_id, material_id }
POST /report_production { part_id, material_id }
    ↓
check_material_qualified(material_id)
    ├─ material_id == NULL → 放行（未扫码）
    ├─ material_status == 'qualified' → 放行
    ├─ material_status == 'pending' → HTTP 400 "尚未完成来料审核"
    └─ material_status == 'rejected' → HTTP 400 "已被判定为不合格，严禁用于生产"
```

**QC 来料审核流程**

```
POST /iqc/incoming/submit { material_id, result, iqc_result }
    ↓
submit_iqc() 同时更新：
  - iqc_status / iqc_result / iqc_by / iqc_at
  - material_status（result=qualified → qualified; result=rejected → rejected）
```

### 数据库迁移

| 文件 | 变更 |
|------|------|
| `upgrade_v6.py` | materials 表新增 `material_status`；子料默认 qualified |
| `upgrade_v7.py` | production_logs 表新增 `material_id` FK |

### 后端变更

#### db_service.py

| 函数 | 变更 |
|------|------|
| `add_material()` | INSERT 增加 `material_status='pending'` |
| `submit_iqc()` | 同时更新 `material_status = result` |
| `get_materials_for_iqc_incoming()` | **新建**，来料审核专用列表 |
| `check_material_qualified()` | **新建**，原材料状态校验（含 pending/rejected 三种消息） |
| `submit_production_log()` | 新增 `material_id` 参数，INSERT 到 production_logs |

#### main.py

| 路由 | 变更 |
|------|------|
| `GET /iqc/incoming` | **新建**，QC 来料审核列表页面 |
| `POST /iqc/incoming/submit` | **新建**，审核合格/拒收 |
| `POST /report_production` | 新增 `material_id` Form 参数 + `check_material_qualified` 校验 |
| `POST /operator/report` | 新增 `material_id` Form 参数 + `check_material_qualified` 校验 |

### 前端变更

#### templates/iqc_incoming.html（新建）
- 顶部说明条：强调"待检→合格"质量卡控逻辑
- 三栏统计卡：待检数 / 合格数 / 拒收数
- 四标签过滤：全部 / 待检 / 合格 / 拒收
- 物料卡片：状态色带（pending=橙/qualified=绿/rejected=红）+ 核心参数 + 操作按钮
- 合格弹窗：备注输入
- 拒收弹窗：原因下拉（外观缺陷/尺寸不合格/材质不符/标识不清/其他）

#### templates/index.html
- QC 主管快捷入口首位新增「来料审核 📦」入口

### 待办 / 风险

- [ ] 报工页面（detail.html / operator_ui.html）需增加原材料扫码输入框，供操作工录入 material_id；目前 API 虽已支持但前端入口待完善
- [ ] 建议在 `sync_plan_progress` 同步进度时，将 `production_logs.material_id` 一起记录到 `production_plans` 便于正向溯源

---

## 2026-05-04 下午（第三轮）— 机台任务锁定 + 报工防错校验

### 背景

组长切换机台任务后，旧页面缓存导致操作工仍向旧零件报工。本次升级通过 `active_plan_id` 字段在数据库层锁定机台当前任务，强制报工时校验零件匹配。

### Schema 变更

**新增字段**
- `machines.active_plan_id`：INTEGER FK → production_plans(id)，记录机台当前正在执行的计划
- 迁移时从 `plan_machines.status='active'` 自动初始化已有数据

### 核心逻辑

**防错校验流程**

```
员工扫码 → /operator?machine_id=N
    ↓
报工 POST /operator/report { part_id, machine_id }
    ↓
check_machine_active_plan(machine_id, part_id)
    ├─ active_plan_id == NULL → 放行
    ├─ active_part_id == part_id → 放行
    └─ active_part_id != part_id → HTTP 400 "任务已切换，请刷新页面"
```

**组长切换任务流程**

```
POST /machines/{machine_id}/set-plan { plan_id }
    ↓
set_machine_active_plan(machine_id, plan_id, operator_id)
    ├─ 旧 plan_machines.status → 'inactive'
    ├─ 新 plan_machines → INSERT 或 UPDATE status='active'
    ├─ machines.active_plan_id → 新 plan_id
    └─ machines.current_part_id → 新零件 ID
```

### 后端变更

#### db_service.py

| 函数 | 变更 |
|------|------|
| `get_all_machines()` | JOIN production_plans，新增 `active_part_number/name`、`active_plan_total_qty/progress_qty` |
| `get_machine_by_id()` | 同上 |
| `assign_plan_to_machine()` | 新增 `active_plan_id` 更新（分配时自动设置当前任务） |
| `cancel_plan()` | 取消计划时同步清空 `machines.active_plan_id` |
| `get_machine_plans()` | 查询增加 `progress_qty` 字段（用于前端进度条） |
| `set_machine_active_plan()` | **新建**，组长切换任务的核心逻辑 |
| `check_machine_active_plan()` | **新建**，报工前置防错校验 |

#### main.py

| 路由 | 变更 |
|------|------|
| `POST /machines/{machine_id}/set-plan` | **新建**，组长切换任务入口，权限 prod/admin Lv.5+ |
| `POST /operator/report` | 新增 `check_machine_active_plan()` 校验，匹配失败返回 400 |
| `GET /api/plans` | **新建**，JSON 接口，供机台列表页 AJAX 下拉框使用 |

### 前端变更

#### templates/machines.html
- 每张机台卡片新增「当前任务」信息行（零件号 / 目标量 / 已完成）
- Lv.5+ 新增「切换任务」按钮 → 弹窗 → AJAX 加载可切换计划下拉框
- 新增「切换任务弹窗」HTML + JS

#### templates/operator_ui.html
- 当前任务卡片新增累计产出进度条（已完成/目标总量）
- 报工表单顶部新增绿色信息条，实时显示当前零件 + 目标 + 完成进度
- 报工改为 AJAX 提交（XHR），不刷新页面
- 400/403/500 错误显示内联红色提示 Banner，不跳转（"任务已切换，请刷新页面"）

### 待办 / 风险

- [ ] 组长切换后，操作工旧页面需要手动刷新才能看到新任务（符合预期）
- [ ] 计划完成后 `active_plan_id` 需在审核时同步清空（已在 `audit_production_log` 中通过 `sync_plan_progress` 间接处理，待验证）

---

## 2026-05-04 下午（第二轮）— 多机台指派 + 每日进度看板

### 背景

在"机台排产系统"基础上，升级为真正的多机台指派模型，并新增"每日进度总览看板"。

### Schema 变更

**新增表**
- `plan_machines`：`plan_id + machine_id` 关联表（多对多），`status IN ('active','inactive')`，替代原来的 `production_plans.machine_id` 单字段指派。

**新增字段**
- `production_plans.progress_qty`：`INTEGER`，从 `production_logs` 汇总的累计良品产出。
- `production_logs.machine_id` + `plan_id`：已有，通过 `plan_machines` 做多机台关联。

### 关键 API / 路由

| 路由 | 说明 |
|------|------|
| `GET /progress` | 每日进度总览看板（prod/sales/admin 可访问）|
| `POST /plans/{plan_id}/assign` | 通过 `plan_machines` 关联机台（多机台支持）|
| `POST /plans/{plan_id}/unassign` | 从计划中移除机台关联 |
| `GET /operator?machine_id=N` | 扫码进入，显示当前任务队列 |
| `POST /operator/report` | 一键报工（自动记录 machine_id + plan_id）|

### 核心业务逻辑

**多机台指派**
- 一个 `production_plan` 可通过 `plan_machines` 关联多个 `machines`（一对多）。
- 每台机台同时只能关联一个活跃计划（`plan_machines.status='active'`），切机台时旧关联自动变为 `inactive`。
- 报工记录 `machine_id + plan_id`，通过 LATERAL 子查询汇总多机台产出。

**每日进度看板排序**
```
ORDER BY
  force_order DESC,              -- 业务强制优先
  urgency = 'critical' DESC,     -- 紧急其次
  urgency = 'urgent' DESC,       -- 加急再次
  plan_order ASC,                -- 手动排序
  due_date 临近逾期 DESC         -- 交期快到的优先
```

**进度同步机制**
- `audit_production_log` / `batch_audit_production_log` 在审核通过后调用 `sync_plan_progress`，将 `production_logs` 的 approved 良品汇总更新到 `production_plans.progress_qty`。

### 待办 / 风险

- [ ] `production_plans.progress_qty` 初始为 0，后续报工审核后自动同步；如需补录历史数据，可手动触发。
- [ ] `operator_ui.html` 中前端 JS 需要从 `active_plan`（由 main.py 传入的队列第一项）预填充报工表单。

---

## 2026-05-04 下午 — 机台排产系统 + IQC 来料检双重赋码模块

### 背景

基于"机台二维码"的排产系统及"双重赋码"的来料检模块，实现：

1. **物料入库 IQC**：whse + qc 双部门赋码，橙色=待检，绿色=合格可用
2. **机台与模具绑定**：machines 表，机台二维码，模具绑定
3. **生产计划排产**：业务部创建计划，生产部分配机台，拖拽排序
4. **机台操作终端**：扫机台码 → 显示当前任务 → 一键报工
5. **业务部强制干预**：sales Level 5+ 可强制插队（force_order=TRUE）

### 部门职能边界

| 角色 | IQC 赋码 | 机台管理 | 排产 | 机台终端 |
|------|---------|---------|------|---------|
| whse 仓管 | 录入入库（待检橙色） | 查看 | — | — |
| qc 品质 | 审核（合格/不合格） | — | — | — |
| prod 生产 | — | 绑定模具/状态切换 | 分配机台 | 扫码报工 |
| sales 业务 | — | — | 创建计划/强制插队 | — |
| admin 老板 | 查看全部 | 全部 | 全部 | — |

### 数据库变更

#### 新增表

| 表名 | 用途 |
|------|------|
| `machines` | 机台台账（编号/吨位/状态/当前模具/当前零件/当前操作员） |
| `production_plans` | 生产计划（零件/交期/紧急度/机台分配/排序/业务强制插队） |

#### 升级表

| 表名 | 变更 |
|------|------|
| `materials` | + `iqc_status`(pending/qualified/unqualified)，+ `iqc_result/by/at`，+ `supplier_name` |
| `production_logs` | + `machine_id` FK → machines，+ `plan_id` FK → production_plans |

#### IQC 状态流转

```
仓管录入 → iqc_status='pending' (橙色) → 品质审核
                                              ├→ qualified (绿色) → 生产可见可用
                                              └→ unqualified (红色) → 拒收
```

### 后端路由

| 路由 | 方法 | 权限 | 功能 |
|------|------|------|------|
| `/machines` | GET | prod/admin Lv.2+ | 机台列表页（带二维码） |
| `/machines/add` | POST | prod Lv.5+ | 新增机台 |
| `/machines/{id}/bind-mold` | POST | prod Lv.5+ | 绑定模具到机台 |
| `/machines/{id}/update` | POST | prod Lv.5+ | 更新机台状态/备注 |
| `/plans` | GET | prod/sales/admin | 生产计划列表（支持过滤） |
| `/plans/add` | POST | prod/sales Lv.5+ | 新建生产计划 |
| `/plans/{id}/assign` | POST | prod Lv.5+ | 分配计划至指定机台 |
| `/plans/{id}/reorder` | POST | prod Lv.5+: 普通排序；sales Lv.5+: force=1 强制插队 |
| `/plans/{id}/cancel` | POST | prod Lv.5+ | 取消计划 |
| `/operator` | GET | prod Lv.1+ | 机台终端（扫码入口） |
| `/operator?machine_id=N` | GET | prod Lv.1+ | 机台任务视图+一键报工 |
| `/operator/report` | POST | prod Lv.1+ | 一键报工（含 machine_id/plan_id） |
| `/materials/iqc` | GET | whse/qc/admin | IQC 来料检验列表 |
| `/materials/iqc/submit` | POST | whse/qc Lv.1+ | 提交 IQC 审核结果 |
| `/qrcode/{id}?type=machine` | GET | 全部 | 机台二维码（指向 /operator?machine_id=N） |

### 业务部强制干预 API 实现

```
POST /plans/{id}/reorder
  new_order: int       ← 目标排序位置
  force: "1"           ← 仅当 department='sales' AND role_level >= 5 时有效

服务端逻辑（plans_reorder）：
  force_order = (force == "1") and (
      user['role_level'] >= 5 and user.get('department') == 'sales'
  )
  db_service.update_plan_order(plan_id, new_order, force=force_order)

数据库效果：
  UPDATE production_plans
  SET plan_order = new_order,
      force_order = TRUE,   ← 紫色标识，前端显示"业务强制"
      updated_at = NOW()
  WHERE id = plan_id;

前端 UI（plans.html）：
  - sales Lv.5+ 显示"🔥 强制优先"按钮
  - 计划卡片显示紫色 force-badge
  - 排序时 force_order=TRUE 的计划排在最前
```

### 机台二维码与 production_logs 外键关联逻辑

```
production_logs.machine_id → machines.id

溯源链路：
  production_logs.id
    → machine_id → machines.machine_number  （在哪台机生产）
    → part_id    → parts.part_number         （生产哪个零件）
    → worker_id  → users.real_name           （谁操作）
    → plan_id    → production_plans.urgency  （是否紧急件）
    → auditor_id → users.real_name          （谁审核）

约束：
  - machine_id 可为空（支持非机台录入的补录）
  - plan_id 可为空（支持紧急计划外的临时报工）
  - 同一时刻一台机器（machine_id）只能有一个 in_progress 计划
    （assign_plan_to_machine 时自动将旧任务设为 cancelled）
```

### 修改文件清单

| 文件 | 变更 |
|------|------|
| `upgrade_v3.py` | 数据库迁移脚本（新增表/列） |
| `db_service.py` | 新增 machines/plans/IQC 函数；升级 submit_production_log |
| `main.py` | 新增路由；升级 qrcode 端点支持机台类型 |
| `templates/machines.html` | 机台管理列表（含二维码/绑定模具/状态切换） |
| `templates/plans.html` | 生产计划排产（含强制干预/业务插队 UI） |
| `templates/operator_ui.html` | 机台终端（扫码/任务/一键报工） |
| `templates/operator_scan.html` | 机台扫码入口页 |
| `templates/materials_iqc.html` | IQC 来料检验列表（颜色标识/合格判定） |
| `templates/materials.html` | 升级：IQC 状态徽章/供应商字段 |
| `templates/index.html` | prod 部门增加机台/计划/终端快捷入口 |

## 2026-05-04 下午 — qc 与 pkg 部门拆分：品质部 vs 全检包装部

### 背景

车间实际业务流中，"品质部"与"全检包装部"是两个独立环节：
- **qc (品质部)**：介入生产过程中（样件确认、机台巡检），是出货前的品质门卫
- **pkg (全检包装部)**：介入生产完成后（100% 全检、包装入箱、发货扫码），依赖 QC 通过

关键约束：**pkg 发货 Safety Guard**：零件必须先通过生产报工 + QC 巡检卡控解除，才能发货。

### 部门职能边界

|| 部门 | 主管 (Lv.5+) | 员工 (Lv.1) |
||-------|-------------|------------|
|| **qc** | 出货报告 OQC 审核+生成 / 制程异常报警看板 / 巡检验单审核 | 样件/首件确认入口 / 机台巡检扫码录入 |
|| **pkg** | 包装待发货库存看板 / 包装防错日志+异常监控 | 全检合格入箱扫码 / 成品发货扫码 |

### Safety Guard 物理隔离规则

```
pkg 发货前置条件（必须同时满足）：
1. 该零件有已审核的生产报工 (production_logs.status='approved')
2. 该零件无未解除的 QC 巡检卡控 (qc_inspection_logs.is_blocked=FALSE)
3. 该零件无未解除的全检不合格卡控 (pkg_packaging_logs.is_blocked=FALSE)
```

违反以上规则时，系统：
- 阻止发货操作，记录 `pkg_error_logs`
- 前端提示具体卡控原因（如"该零件被品质部巡检验异常卡控，禁止发货"）

### 数据库变更

#### 新增表

| 表名 | 用途 |
|------|------|
| `qc_inspection_logs` | 巡检记录（样件确认、机台巡检、出货检验 OQC） |
| `pkg_packaging_logs` | 包装记录（全检入箱） |
| `pkg_shipping_logs` | 发货记录（扫码发货） |
| `oqc_reports` | 出货报告 OQC（状态：草稿/待审/已通过/驳回） |
| `pkg_error_logs` | 包装防错日志 |
| `qc_logs` | 质检记录（新增 `is_blocked` 字段） |

### 后端路由

|| 路由 | 方法 | 权限 | 功能 |
|------|------|------|------|
| `/qc/inspect` | GET | qc 全部 | 巡检扫码录入页（样件/机台） |
| `/qc/inspect` | POST | qc 全部 | 提交巡检记录 |
| `/qc/oqc` | GET | qc Lv.5+ | OQC 出货报告列表 |
| `/qc/oqc` | POST | qc Lv.5+ | 生成/审核 OQC 报告 |
| `/qc/unblock` | POST | qc Lv.5+ | 解除卡控 |
| `/pkg/scan` | GET | pkg 全部 | 全检+包装扫码页 |
| `/pkg/scan` | POST | pkg 全部 | 提交包装记录 |
| `/pkg/shipping` | GET | pkg 全部 | 发货扫码页 |
| `/pkg/shipping` | POST | pkg Lv.1+ | 提交发货（含 Safety Guard 校验） |

### 修改文件

|| 文件 | 变更 |
||------|------|
| `upgrade_qc_pkg_split.py` | 新建，全部新表迁移 |
| `db_service.py` | 新增 ~15 个 QC/PKG 函数 |
| `main.py` | home 路由新增 pkg 分支；新增 9 个业务路由 |
| `templates/index.html` | qc/pkg 独立视图（含嵌套 {% if %}) |
| `templates/qc_inspection.html` | 新建，巡检扫码录入页 |
| `templates/pkg_scan.html` | 新建，全检包装+发货扫码 |
| `.cursorrules` | 新增 qc/pkg 部门定义 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-05-04 上午 — 品质部 (qc) 差异化逻辑：主管 vs 全检员

### 背景

根据 `.cursorrules V2.0` 部门+职级双维权限模型，品质部需区分两个视角：
- **主管 (Level 5+)**：合格率走势、重大质量异常审核
- **全检员 (Level 1)**：全检扫码录入、待检产品列表

### 权限矩阵

|| Level | 视角 | 功能入口 |
||-------|------|---------|
|| 9 | 主管 | 合格率走势图 + 重大异常审核 + 全功能 |
|| 5 | 主管 | 合格率走势图 + 重大异常审核 |
|| 1 | 全检员 | 全检扫码录入 + 待检产品列表 |

### 数据库变更

#### 新建表 `qc_logs`（质检记录）

```sql
CREATE TABLE IF NOT EXISTS qc_logs (
    id              SERIAL PRIMARY KEY,
    part_id         INTEGER REFERENCES parts(id),
    operator_id     INTEGER REFERENCES users(id),
    qty_checked     INTEGER NOT NULL DEFAULT 0,
    qty_passed      INTEGER NOT NULL DEFAULT 0,
    qty_failed      INTEGER NOT NULL DEFAULT 0,
    result          VARCHAR(20) DEFAULT 'pass',
                        -- pass / fail / rework / pending
    defect_reason   TEXT,
    remark          TEXT,
    checked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_major        BOOLEAN DEFAULT FALSE,
                        -- TRUE = 重大异常（需主管审核）
    audit_status    VARCHAR(20) DEFAULT 'approved',
                        -- approved / pending_review / rejected
    auditor_id      INTEGER REFERENCES users(id),
    audited_at      TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_qc_part_id   ON qc_logs(part_id);
CREATE INDEX IF NOT EXISTS idx_qc_checked_at ON qc_logs(checked_at);
```

### 后端变更

#### main.py home 路由（QC 分支）

```python
elif user.get('department') == 'qc':
    if user['role_level'] >= 5:
        # 主管：合格率走势 + 重大异常
        context["qc_pass_rate_trend"] = db_service.get_qc_pass_rate_trend(days=30)
        context["qc_major_anomalies"]  = db_service.get_major_qc_anomalies()
    else:
        # 全检员：待检列表 + 扫码录入入口
        context["pending_parts_for_qc"] = db_service.get_pending_parts_for_qc()
```

#### db_service.py 新增函数

|| 函数 | 用途 | 调用方 |
||------|------|--------|
|| `get_qc_pass_rate_trend(days=30)` | 近N天每日合格率列表 | 主管视图 |
|| `get_major_qc_anomalies()` | 重大异常待审列表 | 主管视图 |
|| `get_pending_parts_for_qc()` | 待检产品列表（全检员） | 全检员视图 |
|| `submit_qc_log()` | 提交质检记录 | 全检员扫码录入 |
|| `audit_qc_log()` | 主管审核重大异常 | 主管审核 |

### 前端变更（templates/index.html）

```html
{% if user.department == 'qc' %}
    {% if user.role_level >= 5 %}
        <!-- 主管视图：合格率走势图 + 重大异常 -->
        <div class="stat-row">
            <div class="stat-box stat-box-purple">
                <div class="stat-num" style="color:#9333ea;">{{ pass_rate_today }}%</div>
                <div class="stat-lbl">今日合格率</div>
            </div>
            ...
        </div>
        <!-- 走势图 SVG -->
        <!-- 重大异常审核卡片列表 -->
    {% else %}
        <!-- 全检员视图：极致简单 -->
        <a href="/qc/scan" class="scan-btn">📋 扫码录入</a>
        <!-- 待检产品列表（编号+提交按钮） -->
    {% endif %}
{% endif %}
```

### UI 准则

- Level 1 界面：减少文字，突出"扫码"和"提交"按钮
- 主管视图：图表 + 数据看板 + 审核操作
- 全检员视图：大按钮 + 简洁列表 + 一键提交

### 修改文件

|| 文件 | 变更 |
||------|------|
|| `upgrade_qc_logs.py` | 新建，qc_logs 表迁移 |
|| `db_service.py` | 新增 5 个 QC 函数 |
|| `main.py` | home 路由 QC 分支按 Level 分流 |
|| `templates/index.html` | QC 区域嵌套 {% if %} 实现差异化视图 |
|| `docs/dev_log.md` | 本条目 |

---

## 2026-05-01 — Department + Level 矩阵权限体系

### 背景

系统从纯 Level 权限升级为 Department + Level 矩阵权限体系，支持更细粒度的部门隔离和权限控制。

### 权限矩阵

| Level | Department | Position | 权限说明 |
|-------|------------|----------|---------|
| 9 | admin | 老板 | 唯一拥有审批权限，可修改所有数据 |
| 5 | sales | 业务经理 | 仅能修改待审单价（pending_price） |
| 5 | prod | 组长 | 负责指派任务和初审报工 |
| 2 | admin | 开发工程师 | 可查看所有模具（含多穴数据），不可修改单价 |
| 1 | prod | 操作工 | 仅能查看指派给自己的零件并报工 |

### 数据库迁移

**迁移脚本：** `migrate_level_matrix.py`

| 原 Level | 迁移后 Level | Department | Position |
|----------|-------------|------------|----------|
| 9 | 9 | admin | 老板 |
| 4 | 5 | sales | 业务经理 |
| 3 | 5 | prod | 组长 |
| 1 | 1 | prod | 操作工 |

### 核心组件

#### 1. permissions.py（新建）

| 组件 | 说明 |
|------|------|
| `UserContext` | 用户上下文类，包含 department/position 字段 |
| `get_current_user_v2()` | 增强版用户获取，支持 Cookie 兼容 |
| `check_permission()` | 权限判断函数 |
| `require_permission()` | FastAPI 依赖项工厂 |
| `PermissionPresets` | 常用权限配置预设 |

#### 2. main.py（更新）

- `get_current_user()`: 新增 department/position 字段
- `do_login()`: 登录时写入 department/position 到 Cookie
- `can_see_all_molds()`: 更新为 Level 9/5/2

### 权限拦截器示例

```python
from permissions import require_permission, UserContext

# 方式1: 使用依赖项
@app.get("/sales_only")
def sales_only(user: UserContext = Depends(
    require_permission(
        allowed_departments=["sales", "admin"],
        min_level=5
    )
)):
    return {"message": "仅销售/管理层可见"}

# 方式2: 使用预设
@app.get("/boss_only")
def boss_only(user: UserContext = Depends(
    require_permission(**PermissionPresets.BOSS_ONLY)
)):
    return {"message": "仅老板可见"}
```

### 测试验证

**测试脚本：** `test_permissions.py`

所有测试用例通过：
- UserContext 类方法（is_boss, is_sales_manager, is_leader, has_min_level, in_departments）
- check_permission 函数（部门过滤、Level 过滤、老板超级权限）
- Cookie 解析（旧版兼容、新版兼容）

### 修改文件

| 文件 | 变更 |
|------|------|
| `migrate_level_matrix.py` | 新建，数据库迁移脚本 |
| `permissions.py` | 新建，权限校验模块 |
| `test_permissions.py` | 新建，测试脚本 |
| `main.py` | 更新登录逻辑、权限注解、首页路由 |
| `db_service.py` | 新增 `get_material_alerts()` 函数 |
| `templates/index.html` | 完全重写，Department 分流视图 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-05-01 — 前端首页 Department 分流改造

### 背景

根据新的 Department + Level 矩阵权限体系，重构首页模板，不再使用 `if user.level == X`，改为 `if user.department == 'X'` 进行权限分流。

### 部门视图设计

#### whse（仓库部门）
- 橙色主题问候卡
- 部门功能入口：原材料库、全检入库、发货管理
- 快捷链接：物料台账、报废日志
- 库存预警卡片

#### prod（生产部门）
- 绿色主题问候卡
- 大号扫码报工按钮（动画效果）
- 今日统计：负责零件数、今日良品数
- 任务卡片列表

#### sales（销售部门）
- 蓝色主题问候卡
- 部门功能入口：单价提报、订单进度、模具台账
- 今日看板统计
- 加急订单监控

#### admin（管理部门）
- 老板（Level 9）：经营看板（本周/本月）、加急订单、待审单价审批
- 组长（Level 5 + 组长）：异常报警、待审核报工、任务分派区
- 开发（Level 2）：模具台账入口

### 技术实现

#### main.py 路由重构
- 按 `user.department` 分流查询不同数据
- 仓库部门：`get_material_alerts()` 获取库存预警
- 销售部门：`get_daily_dashboard_stats()` + `get_all_urgent_parts()`
- 生产部门：`get_my_parts()` 获取指派零件
- 管理部门：按 Level 进一步分流

#### db_service.py 新增函数
- `get_material_alerts()`: 查询即将触及阈值的物料预警

#### 模板变更
- 移除 `user.role_level == X` 判断，改为 `user.department == 'X'`
- 部门品牌色 CSS 变量：`.dept-{admin|sales|prod|whse}`
- 移动端优先：`.page-body` max-width 480px

### Mobile First 设计要点
- 页面宽度最大 480px（手机端居中）
- 桌面端可扩展至 960px（`.container`）
- 统计数字响应式缩放
- 触摸友好的按钮尺寸

### 待办
- [ ] 其他页面模板的 Department 改造
- [ ] 权限拦截器 `require_permission` 在业务 API 中的应用

### 待办

- [ ] 业务 API 权限校验重构（使用新的 require_permission 依赖项）
- [ ] 前端模板根据 department/position 差异化显示

---

## 2026-04-29 — 首页"千人千面"功能 (Role-Based Dashboard)

### 背景
系统已有 Level 权限体系，但首页未根据角色差异化展示数据。本次重构让不同岗位登录后看到最相关的业务信息。

### 各角色首页逻辑分支

#### Lv.9（老板）
- 顶部：本週/本月累计（生产/包装/发货）
- 主体：加急订单三色进度条列表 + 待审核单价审批
- context: `period_summary`, `urgent_parts`, `parts`（待审核单价）

#### Lv.4（业务经理）
- 顶部：今日看板（生产良品/包装/发货）
- 主体：加急订单三色进度条列表
- context: `dashboard_stats`, `urgent_parts`

#### Lv.3（组长）
- 顶部：今日异常报工提醒（报废记录高亮）
- 主体：待审核报工列表 + 任务分派区（指派零件列表）
- context: `scrap_alerts`, `pending_logs`, `my_assigned_parts`

#### Lv.2（开发）
- 模具台账入口
- 无专属首页数据块

#### Lv.1（员工）
- 顶部：大号【扫码报工】快捷入口
- 主体：我的今日任务（assignments 表指派的零件卡片）
- context: `my_parts`（含今日报工统计）

### 核心变更

#### 后端 main.py 首页路由重构
- 按 role_level 分支查询不同数据，避免无用查询
- 新增 context 字段：`pending_logs`, `my_parts`, `my_today_stats`
- 新增 db_service 函数：`get_my_parts(user_id)`、`get_pending_logs_for_dashboard()`、`get_my_today_stats(user_id)`

#### 前端 index.html 重写
- 移动优先（Mobile First）卡片布局
- 管理层：顶部统计卡片网格 + 加急进度列表
- 组长：异常报警 + 待审核报工卡片
- 员工：大号扫码报工按钮 + 任务卡片
- 全局：顶部导航栏 + Tailwind 风格

### 修改文件
| 文件 | 变更 |
|------|------|
| `main.py` | 首页路由按 role_level 分支，传入不同 context |
| `db_service.py` | 新增 3 个首页辅助函数 |
| `templates/index.html` | 完全重写，移动优先卡片布局 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-29 — 加急订单"生产-包装-发货"可视化进度条

### 背景
老板需要在看板上直观看到加急订单的实时流转状态，补齐"订单总数"作为进度条分母。

### 核心变更

#### 数据库：parts 表新增 target_count 字段
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target_count` | INTEGER | 10000（旧数据迁移） / 0（新记录） | 零件订单目标总数 |

**迁移逻辑**：旧数据的 target_count 默认设为 10000，防止除以零错误。

#### 后端：进度百分比计算（db_service.py）
- `get_all_urgent_parts()` 返回每个加急零件时，附带计算：
  - `prod_pct` = (total_good / target_count) * 100
  - `pack_pct` = (total_packaged / target_count) * 100
  - `ship_pct` = (total_shipped / target_count) * 100
- 安全校验：target_count == 0 时进度设为 0；百分比最大不超过 100%

#### 前端（index.html）
- 加急订单监控区使用列表卡片展示每个加急零件
- 卡片头部：零件号、名称、目标数量
- 三根并排细长进度条（h-2, rounded-full）：
  - 生产进度：bg-green-500
  - 包装进度：bg-blue-500
  - 发货进度：bg-purple-500
- 视觉警示：加急状态卡片右上角有 animate-pulse 红色圆点

### 修改文件
| 文件 | 变更 |
|------|------|
| `upgrade_target_count.py` | 新建，迁移脚本（新增字段+旧数据默认值） |
| `db_service.py` | `get_all_urgent_parts()` 增加 target_count 查询和百分比计算 |
| `templates/index.html` | 加急订单卡片重写，含三色进度条和红点警示 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-27 — 质量闭环：良品/报废分项追踪

### 背景
目前"总产量报工"无法区分良品与不良品，无法支撑成本核算和模具维保分析。
本次升级将单一数量输入改为良品数+报废数双项，并强制要求记录报废原因。

### 核心变更

#### 数据库：production_logs 表结构变更
| 字段 | 变更类型 | 说明 |
|------|---------|------|
| `count` | 重命名 → `good_count` | 良品数量（Integer，默认 0） |
| `scrap_count` | 新增 | 报废数量（Integer，默认 0） |
| `scrap_reason` | 新增 | 报废原因（String，可空），下拉选项 |

**迁移逻辑**：历史记录中 `count` 值平移至 `good_count`，`scrap_count` 初始为 0，`scrap_reason` 初始为 NULL。

**scrap_reason 选项列表**：
- 模具故障
- 材料不良
- 冲压刮伤
- 定位偏移
- 其他

#### 接口层（db_service.py / main.py）
- `submit_production_log()` 参数从 `quantity` 改为 `good_count` + `scrap_count` + `scrap_reason`
- **硬性防错**：若 `scrap_count > 0` 且 `scrap_reason` 为空，拒绝提交并返回错误提示

#### 前端（detail.html）
- 员工报工表单改造：
  - 【合格产出数】大号绿色输入框
  - 【报废数】大号红色输入框（默认 0）
  - 报废数 > 0 时动态显示报废原因下拉框（JS 实现）
- 报工记录表增加"良品 / 报废 / 原因"三列

#### 前端（index.html）
- 报工记录表列从"产量"拆分为"良品 / 报废"

### 修改的文件
| 文件 | 变更 |
|------|------|
| `upgrade_quality.py` | 数据库迁移脚本（新增字段 + 历史数据迁移） |
| `db_service.py` | 参数名 `quantity` → `good_count/scrap_count/scrap_reason` |
| `main.py` | `report_production` 路由增加 scrap_reason 硬性校验 |
| `templates/detail.html` | 报工表单 + JS 动态下拉 + 记录表列更新 |
| `templates/index.html` | 记录表列更新 |
| `docs/dev_log.md` | 本条目 |

### 待办
- [ ] 后续可按 scrap_reason 统计报废原因分布，辅助模具维保决策

---

## 2026-04-28 下午 — 看板分级展示：本月本周 / 今日，Lv.9 隐藏零件列表

### 需求变更
- Lv.9 老板：看本周/本月统计数据（不含零件主列表）
- Lv.4 业务经理：保留今日生产/包装/发货看板
- Lv.9 隐藏零件主列表（项目进度看板）

### 变更文件
| 文件 | 变更 |
|------|------|
| `db_service.py` | 删除重复 get_dashboard_summary，新增 get_period_summary（本周/本月统计） |
| `main.py` | Lv.9 专属传入 period_summary，Lv.4 保留 dashboard_stats |
| `templates/index.html` | 看板分三级展示，Lv.9 零件列表加 {% if role_level < 9 %} 包裹 |
| `docs/dev_log.md` | 本条目 |

### 关键逻辑
- 本周：DATE_TRUNC('week', CURRENT_DATE) → CURRENT_DATE
- 本月：DATE_TRUNC('month', CURRENT_DATE) → CURRENT_DATE（本月结束日前均显示当月累计）

---

## 2026-04-28 — 老板经营看板：包装/发货/加急调度系统

### 新表结构

```sql
-- 新增 is_urgent 字段
ALTER TABLE parts ADD COLUMN is_urgent BOOLEAN DEFAULT FALSE;

-- 包装记录表
CREATE TABLE IF NOT EXISTS packaging_logs (
    id          SERIAL PRIMARY KEY,
    part_id     INTEGER NOT NULL REFERENCES parts(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    qty         INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 发货记录表
CREATE TABLE IF NOT EXISTS shipping_logs (
    id          SERIAL PRIMARY KEY,
    part_id     INTEGER NOT NULL REFERENCES parts(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    qty         INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 防错规则
- 包装数 ≤ 该零件累计 approved 良品总数
- 发货数 ≤ 该零件累计包装数（PACKAGED - SHIPPED）

### 看板指标（Level 4+ 可见）
| 卡片 | 数据来源 |
|------|---------|
| 今日生产总计 | SUM(approved qty_good) |
| 今日包装总计 | SUM(packaging_logs qty) WHERE DATE=今天 |
| 今日发货总计 | SUM(shipping_logs qty) WHERE DATE=今天 |
| 待处理加急订单 | COUNT(parts WHERE is_urgent=true) |

### 加急件进度条逻辑
- 生产进度 = SUM(approved qty_good) / 目标量（暂无目标量则按最大100%）
- 包装进度 = SUM(packaged) / SUM(approved qty_good)
- 发货进度 = SUM(shipped) / SUM(packaged)

### 修改文件
| 文件 | 变更 |
|------|------|
| `db_service.py` | 新增 packaging_logs/shipping_logs 表初始化 + 7个函数 |
| `main.py` | 新增 4 个路由（提交包装/发货/加急开关/详情页) |
| `templates/detail.html` | 增加包装表单 + 发货表单 + 加急切换按钮 |
| `templates/index.html` | 四卡片看板 + 加急件进度条列表 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-28 — 动态产值大屏与报废预警 (Phase 2)

### 实现思路

#### 数据层 `db_service.py`
新增 `get_daily_dashboard_stats()` — 单次 SQL JOIN 统计：
- 今日总产值 = SUM(approved qty_good × parts.current_price)
- 今日报废损失 = SUM(approved qty_bad × parts.current_price)
- 全厂平均良率 = SUM(qty_good) / (SUM(qty_good) + SUM(qty_bad))
- 仅统计 `status = 'approved'` 的记录（已审核通过才算有效产出）
- 仅统计当天 DATE(report_time) = CURRENT_DATE 的记录

#### 组长异常提醒 `db_service.py`
新增 `get_today_scrap_logs()` — 返回今日有报废的报工记录（含报废原因），
供 Level 3 组长在首页红色高亮提示。

#### 路由层 `main.py`
- `GET /` 调用 `get_daily_dashboard_stats()` 和 `get_today_scrap_logs()`
- 将统计数据传入 `index.html` 的 context

#### 前端 `index.html`
- Level 4+：顶部三个并排数据卡片（今日产值 / 今日报废损失 / 全厂良率）
- Level 3：顶部红色异常报工提醒列表

### 修改文件
| 文件 | 变更 |
|------|------|
| `db_service.py` | 新增 `get_daily_dashboard_stats()` + `get_today_scrap_logs()` |
| `main.py` | `GET /` 路由新增数据查询并传入模板 |
| `templates/index.html` | 看板数据卡片 + 组长异常提醒 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-28 — 报工审核增加批量通过/驳回功能

### 背景
待审核记录较多时，逐条点击效率低，组长需要一个批量操作入口。

### 核心变更

#### 后端 `db_service.py`
- 新增 `batch_audit_production_log(log_ids, leader_id, approved)` 函数
- 使用 SQL `WHERE id IN (...) AND status = 'pending'` 原子批量更新，避免重复审核
- 返回实际更新的行数

#### 后端 `main.py`
- 新增 `POST /audit_production/batch` 路由
- 接收 `log_ids`（逗号分隔字符串，如 `"10,11,12"`）+ `action` 参数
- 权限要求同单条审核：Level 3 及以上

#### 前端 `audit.html`
- 页面顶部增加"批量操作条"（复选框 + 全选 + 批量通过 + 批量驳回）
- 每条待审核记录左侧增加复选框，已审核记录不显示
- 全选复选框联动 JS 计数器，批量操作条在有勾选时才显示
- 点击"批量通过/驳回"弹出确认框，确认后提交到 `/audit_production/batch`

### 验证结果
- 批量通过 ID=14、ID=16 两条记录，2 秒内全部更新为 `approved`
- auditor_id 正确记录为执行人（李组长 ID=3）

### 修改的文件
| 文件 | 变更 |
|------|------|
| `db_service.py` | 新增 `batch_audit_production_log()` |
| `main.py` | 新增 `/audit_production/batch` 路由 |
| `templates/audit.html` | 复选框 + 批量操作条 + JS |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-28 — 修复报工审核 500 错误（auditor_id 字段缺失）

### 问题现象
点击"✅ 通过"按钮时报 **HTTP 500 Internal Server Error**，服务器报错：
```
psycopg2.errors.UndefinedColumn: column "auditor_id" does not exist
LINE 3: SET status = 'approved', auditor_id = 3
```

### 根本原因
`db_service.py` 中 `audit_production_log()` 函数尝试写入 `auditor_id` 字段，
但数据库 `production_logs` 表从未创建该列，导致 SQL 执行失败。

### 修复方案
新建 `upgrade_auditor_id.py` 迁移脚本，给 `production_logs` 表新增 `auditor_id INTEGER REFERENCES users(id)` 字段，
记录审核人 ID（可为空，支持历史数据兼容）。

### 修改的文件
| 文件 | 变更 |
|------|------|
| `upgrade_auditor_id.py` | 新建，迁移脚本 |
| `docs/dev_log.md` | 本条目 |

### 验证结果
- 迁移后 8 条报工记录全部正常
- ID=10 的记录成功从 `pending` 变为 `approved`，`auditor_id=3` 正确记录

---

## 2026-04-28 — Lv.1 极简化改造（员工视角）

### 背景
员工反馈"无法操作"、"不需要看到太多资料"。原界面 Lv.1 和其他角色混在一起，显示了大量业务信息（单价状态、模具台账入口等），造成干扰。

### 核心变更

#### index.html：双视图分离
- **手机端（Lv.1）**：极简卡片列表，每张卡片只显示零件编号+名称+状态+一个橙色大按钮"填报今日产量"，顶部有统计栏"负责零件 N 个"
- **桌面端 / Lv.2+**：保留原有完整表格视图（审批中心、零件看板、模具台账入口等）

#### detail.html：Lv.1 扫码后极简化
- 手机端只显示：零件信息卡 + 报工表单 + 历史记录
- 去掉了所有 Lv.1 不需要的区块（单价审批、业务经理表单、技术文档等）
- 桌面端保留原有完整内容

#### 技术实现
- CSS `@media (max-width: 767px)` 媒体查询区分手机/桌面视图
- `{% if user.role_level == 1 %}` 分支保留手机视图
- `{% else %}` 分支保留桌面完整视图
- 无需 JS，纯粹 CSS + 模板逻辑切换

### 修改的文件
| 文件 | 变更 |
|------|------|
| `templates/index.html` | 重写，手机/桌面双视图分离 |
| `templates/detail.html` | 重写，Lv.1 手机视图极简化 |
| `docs/dev_log.md` | 本条目 |

### 待办
- [ ] 考虑在 Lv.1 首页加"今日已完成报工数"统计（需 session 记录当天日期）

---

## 2026-04-27 — 质量闭环：良品/报废分项追踪

### 背景
用户提供的参考界面中有 4 个模具状态按钮：模具制作中 / 待产 / 生产中 / 修模中。

### 关键逻辑
- 新增 `tooling_molds.mold_status` 字段，取值固定为上述 4 种。
- 原有 cavity_status（多穴审核状态）保留不动。
- mold_status 过滤对所有登录用户生效（不限权限级别）。
- 未来可扩展更多状态值（如已完成等），按钮 UI 预留扩展位。

### 核心变更
- `upgrade_mold_status.py`：ALTER TABLE 添加 mold_status 列，默认值 '生产中'。
- `db_service.py`：
  - `get_all_tooling_molds()` / `count_tooling_molds()`：`status_filter` → `mold_status`，按 tooling_molds.mold_status 过滤。
  - 新增 `count_mold_status_all()`：返回各 mold_status 的数量（前端按钮数量提示）。
- `main.py` `/tooling` 路由：`status_filter` → `mold_status`。
- `tooling.html`：
  - 去掉 Level 9/4 权限限制，4 个按钮对所有用户可见。
  - 选中按钮（.active）统一红色高亮。
  - 卡片红色标记逻辑改为：cavity_count > 1 且 cavity_status ≠ '已确认'。

### 待办/风险
- mold_status 值的未来扩展（"已完成"等）：按钮 UI 需同步更新，建议在模板中硬编码当前 4 个值。
- 已有记录的 mold_status 默认为 '生产中'，如需批量初始化需单独脚本。

## 2026-04-27 — 模数(mold_count)与穴数(cavity_count)分离

### 背景

用户发现 tooling_molds 表中 cavity_count 字段被混用了：
- 原 cavity_count = "4套" 表示的是"模具套数/步骤数"，而非"穴数"
- TYBE-Q0006：4套模具（非4穴），是典型的工程模（有M1/M2/M3/M4多个步骤）

用户明确：穴数和模数是**两个独立平行**的概念：
- **穴数**：1次冲压出几个零件（"1出N"）
- **模数**：需要几套模具/几个步骤（步数）

### 核心变更

#### 数据库
- `tooling_molds` 新增字段：`mold_count INTEGER`（模数/步骤数）
- 原有 cavity_count 数据迁移：
  - "X套" → mold_count = X，cavity_count 改为规范格式
  - spec_twph / remark 中有 "1出N" 的 → cavity_count 改为对应格式
  - 其余全部改为 "1出1"

#### 迁移结果（2026-04-27）
- mold_count 分布：1步649条、2步468条、3步57条、4步38条、5步10条、6步3条、7步2条、8步3条、9步7条、15步1条
- cavity_count 分布：1穴783条、2穴429条、3穴20条、4穴6条
- TYBE-Q0006：mold_count=4，cavity_count=1出1

#### 代码
- `main.py`：新增 Jinja2 过滤器 `cavity_cn`（"1出N" → "N穴"）
- `db_service.py`：`adjust_price_by_cavities()` 保持不变，cavity_count 仍按穴数逻辑处理
- `templates/tooling.html`：卡片同时展示穴数 badge（绿色）和模数 badge（橙色，仅 mold_count>1 时显示）
- `templates/tooling_detail.html`：详情页穴数后加模数行（仅 mold_count>1 时显示）
- `templates/cavity_review.html`：审核页加模数行
- `templates/mold_link.html`：穴数说明处改用 |cavity_cn 过滤器

#### 显示规则
- 穴数：始终显示（用 cavity_cn 过滤器转为"1穴"/"2穴"格式）
- 模数：仅当 mold_count > 1 时显示，显示为"N步"（橙色）

### 待审核
- 仍有部分记录 spec_twph 中有"1出N"但 cavity_count 可能解析错误，需在审核页逐一核对

---

## 2026-04-27 — Level 体系调整 + 多穴数据审核功能

### 背景

用户反馈现有 tooling_molds 中的 cavity_count 数据来源混乱（多人维护导致人工错误），
要求对多穴数据（cavity_count ≥ 3）建立人工审核机制，仅在经过审核后才向低权限用户展示。

---

### 变更一：权限 Level 体系调整

**调整前：**

| 职位 | Level |
|------|-------|
| 老板 | 9 |
| 业务经理 | 3 |
| 组长 | 2 |
| 普通员工 | 1 |

**调整后：**

| 职位 | Level |
|------|-------|
| 超级系统管理员（原 admin） | 9 |
| 业务经理 | 4 |
| 组长 | 3 |
| 开发 | 2（新增部门） |
| 普通员工 | 1 |

**影响：**
- `admin` 账号用户名改为 `超级系统管理员`，dept 保持 `老板`，role_level 保持 9
- 新增账号：`dev001` / 密码 `dev123456` / Level 2 / dept `开发`
- 所有 role_level 判断阈值已迁移：报工审核从 Level 2 → Level 3；提报单价从 Level 3 → Level 4；模具管理维持 Level 2

---

### 变更二：tooling_molds 新增 cavity_status 字段

**字段：** `cavity_status VARCHAR(16) DEFAULT '待审核'`

**三种状态含义：**

| 状态 | 含义 | 向 Level 1/3 可见 |
|------|------|-------------------|
| `已确认` | 人工确认过多穴数据真实 | ✅ |
| `待确认` | spec_twph 或 remark 中含"1出N"字样，需人工复审 | ❌ |
| `待审核` | cavity_count ≥ 3 但无明确依据，需逐条审核 | ❌ |

**初始化结果（2026-04-27）：**
- `已确认`：1117 条（原 cavity_count 为 1套/2套 的记录）
- `待确认`：26 条（spec_twph 或 remark 含"1出N"）
- `待审核`：5052 条（cavity_count ≥ 3 但无明确依据）

---

### 变更三：可信判定规则（cavity_status 初始化逻辑）

仅当 `spec_twph` 或 `remark` 中明确写明"1出N"（N≥2）时，
才将 cavity_count ≥ 3 的记录标为"待确认"；其余全部标为"待审核"。

正则匹配：`r'1[出去](\d+)套?|1[出去](\d+)'`（支持"1出3"、"1出3套"、"1出3套"等写法）

---

### 变更四：API 层权限控制（db_service.py）

`get_all_tooling_molds()` 新增 `user_role_level` 参数：
- Level 9 / 4 / 2：返回全部（含 cavity_status 字段）
- Level 3 / 1：仅返回 `cavity_status = '已确认'` 的记录

`get_tooling_mold_by_id()` 同步增加权限过滤。

---

### 变更五：多穴审核入口（合并至模具台账）

**最终方案：审核功能合并至 `/tooling` 模具台账页面内，不再独立路由。**

Level 9 / Level 4 权限用户在模具台账中看到：
- 状态快速筛选栏（全部 / 待审核 / 待确认 / 已确认）
- 每张卡片显示 cavity_status 标签
- 未确认的卡片底部直接出现"确认"按钮，无需跳转页面
- 摘要栏显示各状态剩余数量（待审核 N 条 / 待确认 N 条）

Level 2（开发）用户：可看到全部模具及审核状态，但无确认权限。
Level 3 / Level 1：仅看到 cavity_status = '已确认' 的模具。

---

### 变更六：Bug 修复

- **cookie 中文编码问题**：`get_current_user()` 中 `quote()/unquote()` 处理 `username`、`real_name`、`dept` 的 URL 编码，解决中文字符无法存入 latin-1 cookie 的 `UnicodeEncodeError`
- **`user['role_level']` 访问**：main.py 中多处 `user.role_level` 改为 `user['role_level']`，避免 `AttributeError`

---

### 修改的文件清单

| 文件 | 变更 |
|------|------|
| `.cursorrules` | 新增 1.1/1.2 节，权限宪法更新；新增人类确认规则 |
| `migrate_levels.py` | 新建，一次性数据库迁移脚本 |
| `fix_null_status.py` | 新建，修复 cavity_status NULL 记录 |
| `main.py` | 所有 role_level 判断适配新级别；cookie 中文编码修复；新增 `get_cavity_review_counts` 调用 |
| `db_service.py` | 新增 `_can_see_all_molds()`、`get_cavity_review_counts()`；`get_all_tooling_molds()` 增加 status_filter 筛选；`get_tooling_mold_by_id()` 增加权限过滤 |
| `templates/tooling.html` | 完全重写，合并多穴审核功能（状态筛选+审核按钮+统计数） |
| `templates/index.html` | Level 色值补全；模具入口保留；新增"多穴审核"入口（仅 Level 9/4）|
| `templates/cavity_review.html` | 新建（审核路由仍保留，可作备份页面） |
| `docs/dev_log.md` | 本文件 |

---

## 2026-04-30 — 物料台账模块（Materials）新增

### 背景

冲压工厂需要管理卷料/板料等原料的宽度追踪和分条作业。新增 `materials` 表及相关 CRUD 功能。

### 新增字段说明

在 `materials` 表中增加以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `original_width` | NUMERIC(10,2) | 入库初始总宽度（入库后不可变） |
| `current_width` | NUMERIC(10,2) | 动态剩余宽度（随分条动作扣减） |
| `parent_id` | INTEGER (FK→materials) | 分条子料指向原始大卷的父料 ID |
| `scrap_threshold` | NUMERIC(10,2) | 报废阈值（剩余宽度低于此值时自动结案） |
| `is_active` | BOOLEAN | TRUE=使用中，FALSE=已结案/耗尽 |

### 核心功能

#### 1. 新增入库（Lv.4+）
- 填写物料编号/名称/类型/原始宽度/报废阈值
- `original_width` 写入后永不改动，`current_width` 初始化等于 `original_width`

#### 2. 分条操作（Lv.4+）
- 从母卷上切下指定宽度，创建子料记录
- 扣减母卷的 `current_width`，子料的 `parent_id` 指向母卷
- **自动结案**：若扣减后母卷 `current_width <= scrap_threshold`，自动将 `is_active` 置为 FALSE

#### 3. 手动结案（Lv.4+）
- 结案后不再出现在默认列表（需切换到"已结案"标签）

#### 4. 宽度可视化
- 详情页显示已用/剩余双段进度条 + 阈值警戒线标记

#### 5. 预警机制
- 首页统计显示即将触及阈值的物料（current_width <= scrap_threshold）

### 权限设计

| 角色 | 权限 |
|------|------|
| Lv.9/4 | 查看全部 + 新增/分条/编辑/结案 |
| Lv.3/2 | 仅查看使用中的物料，无操作权限 |
| Lv.1 | 无访问权限 |

### 变更的文件清单

| 文件 | 变更 |
|------|------|
| `upgrade_materials.py` | 新建，数据库迁移脚本（建表+字段+索引） |
| `db_service.py` | 新增 10 个函数 |
| `main.py` | 新增 7 个物料路由 |
| `templates/materials.html` | 新建，物料列表页 |
| `templates/materials_detail.html` | 新建，物料详情页 |
| `templates/index.html` | 首页快捷入口新增"物料台账"按钮（Lv.2+可见） |
| `docs/dev_log.md` | 本文件 |

### 索引

| 索引名 | 字段 | 用途 |
|--------|------|------|
| `idx_materials_parent_id` | `parent_id` | 母子关联查询加速 |
| `idx_materials_is_active` | `is_active` | 默认过滤使用中物料加速 |

---

## 2026-04-30 (下午) — process_slitting 批量分条逻辑重构

### 背景

将原有的单条分条（`slit_material`）升级为批量分条（`process_slitting`），支持一次性从母卷切出多条子料，并引入重量追踪。

### 新增数据库字段（通过 `upgrade_materials_v2.py` 迁移）

| 字段 | 类型 | 说明 |
|------|------|------|
| `thickness` | NUMERIC(10,4) | 厚度（mm） |
| `batch_no` | VARCHAR(100) | 批次号 |
| `current_weight` | NUMERIC(12,4) | 当前重量（kg），随分条按比例扣减 |
| `status` | VARCHAR(30) | 物料状态（待入库/使用中/待领用/已耗尽） |

### 核心函数 `process_slitting` 逻辑

```
输入: parent_id, target_width, count, child_numbers[]

校验:
  - target_width > 0
  - count > 0
  - 总消耗宽度 = target_width * count ≤ current_width（否则抛 ValueError）
  - 父料必须存在且 is_active=TRUE

扣减动作:
  - 消耗重量 = (总消耗宽度 / current_width) * current_weight
  - current_width -= total_consumed_width
  - current_weight -= consumed_weight
  - 若扣减后 current_width <= scrap_threshold，自动结案（is_active=FALSE, status='已耗尽'）

产出动作:
  - 创建 count 条子料
  - 子料 status = '待领用'
  - 子料自动继承父料的 material_type / thickness / batch_no
  - 子料 original_width = current_width = target_width

返回: (True/False, 消息, 新增子料ID列表)
```

### 前端变更

- **列表页 `materials.html`**：分条弹窗改为批量模式（单条宽度 + 条数 + 前缀），实时预览生成编号，超宽时红色警告
- **详情页 `materials_detail.html`**：同上，弹窗自动填入母卷编号作为子料前缀
- **列表/详情卡片**：展示新字段（status/thickness/batch_no/current_weight）
- **入库表单**：新增厚度/批次号/初始重量输入框

### 变更的文件清单

| 文件 | 变更 |
|------|------|
| `upgrade_materials_v2.py` | 新建，迁移脚本（thickness/batch_no/current_weight/status） |
| `db_service.py` | 新增 `process_slitting`（核心批量逻辑）；重构 `slit_material` 为其包装器；`add_material` 增加 thickness/batch_no/current_weight 参数 |
| `main.py` | `/materials/add` 增加新字段参数；`/materials/{id}/slit` 改为批量分条路由 |
| `templates/materials.html` | 批量分条弹窗；列表卡片展示新字段；入库表单增加新字段 |
| `templates/materials_detail.html` | 批量分条弹窗；详情页展示新字段 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-30 (下午) — 自动结案与手动清理余料

### 背景

分条后若剩余宽度低于报废阈值，需自动结案并将剩余重量归零，记录到专门的报废日志表。同时仓库人员应能手动发起余料清理。

### 新增表 `production_scrap`

| 字段 | 类型 | 说明 |
|------|------|------|
| `material_id` | INTEGER FK | 关联物料 |
| `material_number` | VARCHAR | 物料编号快照 |
| `scrap_type` | VARCHAR | `auto_close`=自动结案 / `manual_cleanup`=手动清理 |
| `scrap_width` | NUMERIC | 报废时的剩余宽度（mm） |
| `scrap_weight` | NUMERIC | 报废时的剩余重量（kg），归零前快照 |
| `reason` | TEXT | 原因描述 |
| `operator_id` | INTEGER FK | 操作人（仅 manual_cleanup 有值） |
| `operator_name` | VARCHAR | 操作人姓名快照 |

索引：`idx_scrap_material_id`、`idx_scrap_type`

### 核心逻辑变更

#### 自动结案（`process_slitting`）
- 判定条件：`new_width <= scrap_threshold` 时触发
- 动作：`current_width = 0`；`current_weight = 0`；`is_active = FALSE`；`status = '已耗尽'`；写入 `production_scrap`（`scrap_type='auto_close'`）

#### 手动清理（`scrap_material`）
- 仓库人员填写清理原因（必填），归零并结案，写入 `production_scrap`（`scrap_type='manual_cleanup'`），含操作人快照

### 新增函数

| 函数 | 用途 |
|------|------|
| `scrap_material()` | 手动清理余料，归零+写日志 |
| `get_scrap_logs()` | 查询报废日志列表（分页） |
| `count_scrap_logs()` | 统计报废日志总数 |
| `get_scrap_summary()` | 报废统计摘要（按类型分计宽度/重量） |

### 新增路由

| 路由 | 方法 | 用途 |
|------|------|------|
| `/materials/{id}/scrap` | POST | 手动清理余料 |
| `/materials/scrap-logs` | GET | 报废日志页面（Lv.4+） |

### UI 变更

- **详情页**：结案按钮改为「🗑 手动清理余料」，弹窗必须填写清理原因，显示当前剩余宽/重量
- **列表页**：卡片操作栏显示「清理」按钮（仅剩余>0的物料可见）
- **物料台账列表**：快捷入口新增「报废日志」按钮（Lv.4+）
- **新页面 `scrap_logs.html`**：自动/手动双栏统计 + 明细表格 + 分页

### 变更的文件清单

| 文件 | 变更 |
|------|------|
| `upgrade_scrap_log.py` | 新建，创建 production_scrap 表及索引 |
| `db_service.py` | `process_slitting` 自动结案逻辑重构（归零重量+写日志）；`scrap_material` 新增；`get_scrap_logs`/`count_scrap_logs`/`get_scrap_summary` 新增 |
| `main.py` | `/materials/{id}/scrap` 路由；`/materials/scrap-logs` 页面路由 |
| `templates/materials.html` | 「清理」按钮；弹窗改为手动清理（含原因必填） |
| `templates/materials_detail.html` | 同上 |
| `templates/scrap_logs.html` | 新建，报废日志统计+明细页面 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-30 (下午) — 扫码卡片 UI 与子料编号格式优化

### 扫码详情页重构

详情页改为扫码导向设计（手机扫码后第一屏）：

**扫码英雄卡片（`scan-hero`）**：
- 深蓝渐变背景，突出物料编号（大字）+ 物料名称
- 三大核心数据并列：原始宽度 / 当前剩余宽度 / 报废阈值
- 双段宽度进度条（已用红色 / 剩余绿色）
- 阈值警戒条（低于阈值时显示橙色警告）

**溯源链（`trace-card`）**：
- 从母卷到当前物料再到子料的完整链路
- 每级用不同颜色圆点标识（母卷橙 / 当前蓝 / 子料绿）
- 点击母卷可跳转查看

**子料列表**：
- 编号 / 规格 / 批次 / 状态一目了然
- 每条可点击跳转详情

**其他信息折叠区**：批次号、厚度、入库时间等次要信息

### 极简分条弹窗

- 仅需输入「本次宽度」和「条数」两个数字
- **实时预览区域**（双行布局）：母卷剩余 / 本次消耗 / 分条后剩余
- 超额时红色警告 + 按钮禁用
- 子料编号由后端自动生成，无需前端输入

### 子料编号格式变更

- **旧格式**：用户输入前缀，如 `SLIT-001`, `SLIT-002`（可重复）
- **新格式**：后端自动生成 `{父料编号}-S{序号}`，例如 `MAT-001-S1`, `MAT-001-S2`
- 优势：全局唯一，可直接从编号追溯母卷来源

### 变更的文件清单

| 文件 | 变更 |
|------|------|
| `templates/materials_detail.html` | 完全重构为扫码导向设计（深蓝英雄卡+溯源链+子料列表+极简分条弹窗） |
| `templates/materials.html` | 分条弹窗移除前端子料编号输入，改为后端自动生成；实时预览改为消耗/剩余双行布局 |
| `db_service.py` | `process_slitting` 子料编号改为 `{parent_num}-S{seq}` 格式；移除前端传参 `child_numbers` |
| `main.py` | slit 路由移除 `child_prefix` 参数 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-04-30 — Alembic 迁移：users 表部门化重构

### 背景

`users` 表从旧权限体系（纯 role_level）升级为 `.cursorrules V2.0` 定义的 **部门 (dept) + 职务 (position)** 双维模型。

### 存量数据状态

| 字段 | 迁移前 | 迁移后 |
|------|--------|--------|
| `dept` | 中文值（老板/业务/生产/仓库） | 英文标准缩写（admin/sales/prod/whse） |
| `position` | 不存在 | 新增，回填职务 |

### 迁移文件结构

```
alembic/
├── alembic.ini          # Alembic 主配置
├── env.py              # 数据库连接上下文
├── script.py.mako      # 迁移脚本模板
└── versions/
    ├── a1b2c3d4e5f6_add_department_and_position_to_users.py   # 主迁移
    └── patch_position_levels_34.py                              # 补充脚本
```

### dept 映射规则

| 旧值（中文） | 新值（英文） |
|-------------|-------------|
| 老板 | `admin` |
| 业务 | `sales` |
| 生产 | `prod` |
| 仓库 | `whse` |

### position 回填规则

| role_level | dept | position |
|------------|------|---------|
| 9 | `admin` | 部门负责人 |
| 4 | `sales` | 业务经理 |
| 3 | `prod` | 生产组长 |
| 2 | `admin` | 开发工程师 |
| 1 | `prod` | 员工 |

### 存量数据结果

| id | username | dept | role_level | position |
|----|----------|------|------------|---------|
| 1 | admin | admin | 9 | 部门负责人 |
| 2 | sales_mgr | sales | 4 | 业务经理 |
| 3 | prod_leader | prod | 3 | 生产组长 |
| 4 | worker01 | prod | 1 | 员工 |
| 5 | dev001 | admin | 2 | 开发工程师 |

### 迁移命令

```bash
# 执行迁移
py -m alembic upgrade head

# 查看历史
py -m alembic history

# 回滚（如需）
py -m alembic downgrade -1
```

### 变更的文件清单

| 文件 | 变更 |
|------|------|
| `alembic/alembic.ini` | 新建，Alembic 主配置 |
| `alembic/env.py` | 新建，数据库连接上下文 |
| `alembic/script.py.mako` | 新建，迁移脚本模板 |
| `alembic/versions/a1b2c3d4e5f6_...py` | 新建，主迁移脚本 |
| `alembic/versions/patch_position_levels_34.py` | 新建，补充 level 3/4 的 position |
| `docs/dev_log.md` | 本条目 |
﻿---

## 2026-05-04 下午（续）— 防错校验 + Level 1 UI 极致化

### 背景

三个部门的 Level 1 核心诉求：
- **pkg**：员工关注"通过率"与"出货"
- **qc**：员工关注"标准"与"异常"
- **prod**：员工关注"产量"

业务防错校验：
1. **包装防错**：pkg 包装数严禁超过生产报工良品总数
2. **发货防错**：只有"已包装"库存才能发货

### 防错校验（后端）

| 函数 | 说明 |
|------|------|
| `check_pkg_packaging_eligibility` | 包装防错 Guard |
| `check_pkg_shipping_eligibility` | 发货 Safety Guard 三重校验 |
| `get_pkg_today_summary` | 重构：加入 `today_pass_rate` |
| `get_qc_today_summary` | 新增：QC 主管看板汇总 |
| `get_pkg_ready_inventory` | SQL 新增 `total_shipped` 和 `ready_to_ship` |

### 路由变更（main.py）

- `/pkg/scan` POST：改用 `check_pkg_packaging_eligibility`
- `/pkg/shipping` POST：改用 `check_pkg_shipping_eligibility`
- Home 路由：QC Level 5+ 传入 `qc_summary`

### 模板变更

- **pkg Level 1**：两个全宽超级大按钮；通过率看板；只显示 `ready_to_ship > 0`
- **qc Level 1**：两个全宽超级大按钮：首件确认单 + 巡检扫码录入
- **prod Level 1**：全宽超级大扫码报工按钮
- **pkg Level 5+**：新增合格率看板
- **qc Level 5+**：新增今日合格率统计
- `pkg_scan.html`：完全重写，展开式表单 + 实时防错
- `pkg_shipping.html`：完全重写，Safety Guard Banner

### 变更的文件清单

| 文件 | 变更 |
|------|------|
| `db_service.py` | 新增 2 个 Guard 函数，重构 2 个汇总函数，SQL 扩展 2 个字段 |
| `main.py` | 两路由改用新 Guard；Home 增加 `qc_summary` |
| `templates/index.html` | 三个 Level 1 Mobile First 极致化；Level 5+ 看板优化 |
| `templates/pkg_scan.html` | 完全重写，展开式表单 + 实时防错 |
| `templates/pkg_shipping.html` | 完全重写，Safety Guard 说明 + 只显可发货库存 |
| `docs/dev_log.md` | 本条目 |
﻿---

## 2026-05-04 下午（续2）— 全局进度看板 + 文员补录模块

### 背景

用户要求建立一个以"全局进度"为核心、由文员集中录入的包装发货管理模块：
- 监控零件的"全检状态"与"出货状态"，不统计全检工人个人产量
- 操作模式：线下手工单 + 文员 PC 端集中录入
- 约束放宽：取消"包装数必须小于等于生产报工数"的硬性拦截，改为看板数据对比提醒

### 数据库逻辑（db_service.py）

**进度看板视图** `get_pkg_progress_view(target_date=None)`：
- 按选定日期，对每个零件 SUM(production_logs.qty_good)、SUM(pkg_packaging_logs.qty_passed)、SUM(pkg_shipping_logs.qty)
- 计算 alert_status：missed（全检 < 生产）、pending（待发库存 > 0）、ok（完成）
- HAVING 过滤掉三表都无数据的零件

**文员补录** `submit_pkg_entry(...)`：
- 一次性提交包装记录 + 发货记录
- 熔断日志：INSERT operation_logs 记录所有变更内容
- 发货数校验：hist_passed - hist_shipped >= qty_ship
- qty_bad > 0 → is_blocked=TRUE（卡控）

**每日汇总** `get_pkg_daily_summary(target_date=None)`：
- 返回 prod_total / pkg_total / pkg_failed / ship_total / pass_rate / missed_count

**待检参考** `get_pkg_parts_pending_inspection(target_date=None)`：
- 返回已生产但当日未全检的零件（prod - pkg > 0）

### 路由（main.py）

| 路由 | 方法 | 说明 |
|------|------|------|
| `/pkg/progress` | GET | 全局进度看板，参数 date=YYYY-MM-DD，默认今日 |
| `/pkg/progress/fetch` | POST | AJAX 日期切换，返回 JSON |
| `/pkg/entry` | GET | 文员补录工作台 |
| `/pkg/entry` | POST | 提交补录 |

权限约束：dept in ('pkg', 'admin')

### 模板

**pkg_progress.html**：日期选择条 + 六格汇总看板 + PC 表格（响应式隐藏/显示）+ Mobile 卡片视图。alert_status 行颜色：missed=黄色、pending=绿色、ok=白底。

**pkg_entry.html**：零件选择 + 参考提示条（待检参考数）+ 日期 + 三格数字输入（合格/报废/发货）+ 全额发货勾选 + 不良原因下拉 + 箱号/车牌 + 快捷提交。Enter 键触发提交。

### 快捷入口（index.html pkg Level 5+）

在"全检包装/发货扫码"后新增：
- 📊 全局进度看板 → `/pkg/progress`
- 📋 文员补录 → `/pkg/entry`

### 变更的文件清单

| 文件 | 变更 |
|------|------|
| `db_service.py` | 新增 5 个函数（进度视图、文员录入、待检参考、零件列表、每日汇总） |
| `main.py` | 新增 4 个路由（含 AJAX JSON 端点）；权限检查 dept in ('pkg','admin') |
| `templates/index.html` | pkg Level 5+ 快捷入口新增 2 个链接 |
| `templates/pkg_progress.html` | 新建：全局进度看板 |
| `templates/pkg_entry.html` | 新建：文员补录工作台 |
| `docs/dev_log.md` | 本条目 |

## 2026-05-04 下午（第五轮）— 原材料双重确认（仓库 + 品质）

### 背景

原材料可用性由单一 `material_status` 改为 **"仓库确认 + 品质确认"** 双重门禁。
- 可用条件：`is_whse_confirmed = TRUE` OR `is_qc_confirmed = TRUE`
- 任一部门确认即可，双重确认更安全
- 报工扫码时校验，未确认的物料拒绝使用并提示："该物料未经仓库或品质确认，禁止使用"

### Schema 变更（`upgrade_v8.py`）

**新增字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `materials.is_whse_confirmed` | BOOLEAN DEFAULT FALSE | 仓库确认标志 |
| `materials.is_qc_confirmed` | BOOLEAN DEFAULT FALSE | 品质确认标志 |
| `materials.whse_confirmed_by` | INTEGER FK → users(id) | 仓库确认人 |
| `materials.qc_confirmed_by` | INTEGER FK → users(id) | 品质确认人（复用 `iqc_by` 字段） |

**可用性规则**

```
is_whse_confirmed = TRUE  OR  is_qc_confirmed = TRUE  →  可用于生产
Else                                             →  拒绝，提示"未经仓库或品质确认"
```

### API / 路由变更

| 路由 | 方法 | 说明 |
|------|------|------|
| `/materials/whse-confirm` | GET | 仓库确认页面 |
| `/materials/{id}/whse-confirm` | POST | 仓库确认动作（whse + admin） |
| `/iqc/incoming/submit` | POST | 品质确认（qualifed → is_qc_confirmed=TRUE） |
| `/operator/report` | POST | 改用字符串 material_id，支持扫码卷号 |

### 核心逻辑变更

- **`check_material_qualified(material_id)`**：从单一 `material_status='qualified'` 改为双字段校验
- **`submit_iqc()`**：提交合格时同步设置 `is_qc_confirmed=TRUE` 和 `qc_confirmed_by`
- **`confirm_material_whse()`**：新增，设置 `is_whse_confirmed=TRUE` 和 `whse_confirmed_by`
- **`resolve_material_id_by_number()`**：新增，通过物料卷号字符串解析为 ID（支持扫码）
- **`get_materials_for_iqc_incoming()`**：支持按双重确认状态过滤（both/whse_only/qc_only/none）
- **`get_materials_for_whse_confirmation()`**：新增，仓库确认页面专用查询

### 模板变更

| 文件 | 变更 |
|------|------|
| `templates/materials_whse_confirm.html` | 新建：仓库确认页面（卡片 + 双重确认图标 + 一键确认按钮） |
| `templates/iqc_incoming.html` | 重写：改用双重确认图标和状态（蓝=仓库、紫=品质、绿=双重、红=未确认） |
| `templates/materials.html` | 列表卡片新增确认图标badge |
| `templates/operator_ui.html` | 报工表单新增物料卷号扫码输入框，隐藏表单增加 material_id 字段 |
| `templates/index.html` | whse 部门新增「仓库确认」快捷入口 |

### 文件清单

| 文件 | 说明 |
|------|------|
| `upgrade_v8.py` | 新建：数据库迁移（4个新字段） |
| `db_service.py` | 修改 `check_material_qualified`、`submit_iqc`；新增 4 个函数 |
| `main.py` | 新增 2 个路由；修改 `/operator/report` 签名和解析逻辑 |
| `templates/materials_whse_confirm.html` | 新建 |
| `templates/iqc_incoming.html` | 重写 |
| `templates/materials.html` | 列表确认图标 |
| `templates/operator_ui.html` | 物料扫码输入 |
| `templates/index.html` | whse 部门入口 |
| `docs/dev_log.md` | 本条目 |

## 2026-05-04 下午（第六轮）— 超产支持 + 计划结案

### 背景

1. **进度看板**：进度计算允许结果超过 100%；超产时进度条显示紫色
2. **计划结案**：`production_plans.status` 新增 `'closed'` 值，结案后机台解除关联
3. **超产统计**：结案报告中展示超产数量和百分比，供业务部平衡库存

### Schema 变更

| 变更 | 说明 |
|------|------|
| `production_plans.status` CHECK 约束 | 新增 `'closed'` 值（`upgrade_v9.py`） |

**Status 完整枚举**：`planned`, `in_progress`, `completed`, `cancelled`, `closed`

### 进度看板变更

- `get_progress_dashboard()`：移除 `completion_pct` 的 `LEAST(..., 100.0)` 封顶，允许显示超过 100%
- 新增 `overproduction_qty` 字段：`(累计产出 - 目标总量)`，最小为 0
- 新增 `overproduction_pct` 字段：超产百分比
- 新增 `'closed'` 到 dashboard WHERE 条件，结案计划也在看板上显示

### 核心逻辑变更

| 函数 | 变更 |
|------|------|
| `get_progress_dashboard()` | 移除 100% 封顶；新增 overproduction 字段 |
| `close_plan(plan_id, operator_id)` | 新增：将 status → 'closed'；解除所有机台关联 |
| `get_plan_close_report(plan_id)` | 新增：返回计划信息 + 超产统计 + 机台明细 |

### 路由变更

| 路由 | 方法 | 说明 |
|------|------|------|
| `/plans/{id}/close` | POST | 结案计划 → 重定向到结案报告页 |
| `/plans/{id}/close-report` | GET | 结案报告 HTML 页面 |
| `/plans/{id}/close-report-json` | GET | 结案报告 JSON API（AJAX） |

### UI 变更

| 文件 | 变更 |
|------|------|
| `templates/progress.html` | 超产进度条紫色（`.pg-over`）；超产标记badge；累计数字紫色 |
| `templates/plans.html` | 超产badge（紫色）；结案按钮（新状态 'closed' 时显示报告链接）；结案确认弹窗 |
| `templates/operator_ui.html` | 进度条超产时紫色；超产badge |
| `templates/plan_close_report.html` | 新建：结案报告页（超产大字/横幅 + 机台明细） |

### 文件清单

| 文件 | 说明 |
|------|------|
| `upgrade_v9.py` | 新建：CHECK 约束添加 'closed' |
| `db_service.py` | 修改 dashboard；新增 `close_plan()`、`get_plan_close_report()` |
| `main.py` | 新增 3 个结案路由 |
| `templates/plan_close_report.html` | 新建 |
| `templates/progress.html` | 紫色超产条 |
| `templates/plans.html` | 结案按钮 + 弹窗 + 超产badge |
| `templates/operator_ui.html` | 紫色进度条 |
| `docs/dev_log.md` | 本条目 |

## 2026-05-04 下午（第七轮）— 机台异常状态与生产预警

### 背景

- 机台发生故障时，工人可在报工页面一键报修，机台状态置为 `fault`
- 全局看板（进度看板 + 计划列表）醒目显示故障机台所在计划
- 组长（Lv.5+）可在机台管理页面重置故障机台为 `running`

### Schema 变更（`upgrade_v10.py`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `machines.fault_reason` | TEXT DEFAULT '' | 故障原因描述 |
| `machines.fault_reported_at` | TIMESTAMP | 报修时间 |
| `machines.status` CHECK | 新增 `'fault'` | 状态枚举新增故障值 |

**Status 枚举**：`idle`, `running`, `fault`, `maintenance`, `offline`

### 核心逻辑变更

| 函数 | 说明 |
|------|------|
| `report_machine_fault(machine_id, reason, reporter_id)` | 设置 status='fault'，记录原因和时间 |
| `reset_machine_fault(machine_id, reset_by)` | 恢复 status='running'，清空故障信息 |
| `get_machines_with_faults()` | 返回所有故障机台列表 |
| `update_machine()` | 新增 `fault_reason` 和 `clear_fault` 参数 |
| `get_progress_dashboard()` | 新增 `has_fault`（布尔）和 `fault_count`（数量）字段 |
| `get_all_plans()` | 新增 `has_fault` 和 `fault_machines` 字段 |

### 路由变更

| 路由 | 方法 | 说明 |
|------|------|------|
| `/machines/{id}/fault` | POST | 工人报修（Lv.1+） |
| `/machines/{id}/fault-reset` | POST | 组长重置（Lv.5+） |
| `/machines/fault-list` | GET | 故障机台列表（JSON） |

### UI 变更

| 文件 | 变更 |
|------|------|
| `templates/operator_ui.html` | 故障横幅（红色）、异常报修按钮（正常时）、故障原因弹窗 |
| `templates/progress.html` | 故障计划红色背景、顶部预警横幅、故障数量badge |
| `templates/plans.html` | 故障计划红色卡片、故障标签、机台标签红显 |
| `templates/machines.html` | 故障机台红色卡片、故障原因显示、重置按钮 |

### 文件清单

| 文件 | 说明 |
|------|------|
| `upgrade_v10.py` | 新建：fault_reason + fault_reported_at + CHECK 约束 |
| `db_service.py` | 新增 3 个函数；修改 3 个查询函数 |
| `main.py` | 新增 3 个路由 |
| `templates/operator_ui.html` | 报修按钮 + 弹窗 |
| `templates/progress.html` | 故障预警横幅 + 红色卡片 |
| `templates/plans.html` | 故障卡片 + 标签 |
| `templates/machines.html` | 故障状态显示 + 重置按钮 |
| `docs/dev_log.md` | 本条目 |



---

## 2026-05-04 下午（第六轮）— 模修流程：扫码介入与权限诊断

### 背景

机台故障处理流程需要更细粒度的状态管理和权限分层。本次升级新增两种机台状态（`pending_check` / `diagnosing`），支持开发人员扫码介入、诊断分流，以及时效统计分析。

### 业务逻辑

```
fault（工人报修）
  ↓ 组长可"标记待诊"（pending_check）
pending_check（等待开发到场）
  ↓ 开发人员扫码介入（dept='tech', is_tech=TRUE）
diagnosing（诊断中）
  ↓ 【修复完成】→ running（恢复正常）
  ↓ 【确认拆模】→ offline（模具下线）
```

### Schema 变更（upgrade_v11.py）

**machines 新增字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `tech_arrival_time` | TIMESTAMP | 开发人员到场时间 |
| `diagnosing_start_time` | TIMESTAMP | 诊断开始时间 |
| `mold_offline_time` | TIMESTAMP | 模具下线时间 |

**machines.status CHECK 约束扩展**

`'idle','running','fault','pending_check','diagnosing','maintenance','offline'`

**users 新增字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_tech` | BOOLEAN NOT NULL DEFAULT FALSE | 标识开发人员身份 |

### db_service.py 变更

**新增函数**

| 函数 | 说明 |
|------|------|
| `set_machine_pending_check(machine_id)` | 组长将故障机台标记为待诊 |
| `tech_intervene(machine_id, tech_user_id)` | 开发扫码介入：到场+状态→diagnosing |
| `tech_complete_fix(machine_id)` | 【修复完成】：状态→running，清空维修时间戳 |
| `tech_confirm_mold_offline(machine_id)` | 【确认拆模】：状态→offline，保留时间线 |
| `get_tech_time_analytics()` | 时效统计数据（响应时间 + 处理时间） |

**修改函数**

| 函数 | 变更 |
|------|------|
| `update_machine()` | 支持 tech_arrival_time / diagnosing_start_time / mold_offline_time / clear_tech_timestamps |
| `reset_machine_fault()` | 重置时清空所有维修时间戳 |
| `get_all_machines()` | SELECT 新增 tech_arrival_time / diagnosing_start_time / mold_offline_time |
| `get_progress_dashboard()` | fault_count/has_fault → anomaly_count/has_anomaly（含 pending_check/diagnosing） |

### main.py 路由变更

| 路由 | 方法 | 说明 |
|------|------|------|
| `/machines/{id}/pending-check` | POST | 组长标记待诊（Lv.5+） |
| `/machines/{id}/tech-intervene` | POST | 开发扫码介入（is_tech=TRUE） |
| `/machines/{id}/tech-complete` | POST | 修复完成（is_tech=TRUE，diagnosing 状态） |
| `/machines/{id}/tech-offline` | POST | 确认拆模（is_tech=TRUE，diagnosing 状态） |
| `/tech/analytics` | GET | 时效分析页面（HTML） |
| `/tech/analytics-json` | GET | 时效统计数据（JSON） |
| `get_current_user()` | — | 查询 users.is_tech，注入 user.is_tech 字段 |

### UI 变更

| 文件 | 变更 |
|------|------|
| `templates/operator_ui.html` | pending_check 横幅（橙色）、diagnosing 横幅（紫色）+ 修复/拆模按钮；非开发用户仅显示维修中提示 |
| `templates/machines.html` | pending_check（橙色）、diagnosing（紫色）卡片样式；故障卡片新增"标记待诊"按钮 |
| `templates/progress.html` | has_fault → has_anomaly；异常机台均红色背景 |
| `templates/tech_analytics.html` | **新建**：时效统计卡片 + 响应/处理时间明细表 |

### 权限拦截逻辑

- `pending_check` 页面：非 tech 用户看到"维修中"提示 + "仅开发人员可操作"灰框
- `diagnosing` 页面：非 tech 用户看到"维修中"提示 + "仅开发人员可操作"灰框
- `is_tech` 判定：`get_current_user()` 从数据库查询 users.is_tech，注入 session

### 文件清单

| 文件 | 说明 |
|------|------|
| `upgrade_v11.py` | 新建：pending_check/diagnosing 字段 + CHECK 约束 + is_tech |
| `db_service.py` | 新增 5 个函数；修改 4 个函数/查询 |
| `main.py` | 新增 6 个路由；修改 get_current_user |
| `templates/operator_ui.html` | pending_check + diagnosing 横幅 + tech 按钮 |
| `templates/machines.html` | pending_check/diagnosing 样式 + 标记待诊按钮 |
| `templates/progress.html` | has_anomaly 字段 |
| `templates/tech_analytics.html` | 新建：时效分析页面 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-05-06 上午（续） — 仓库模块重构：父子料分条与溯源逻辑

### 背景

根据 .cursorrules V3.0 仓库模块规范，重构物料分条逻辑，实现：
1. 精确重量追踪（`original_weight` / `current_weight` 双轨）
2. 分条溯源日志（`material_slitting_logs`）
3. 仓库员手动报废（`close_material_item`）
4. 精细分条接口（`execute_material_slitting`，支持精确指定重量）
5. UI 层增强（父子关系树标识、原始重量进度条、精密分条弹窗）

### Schema 变更

#### 迁移文件：`alembic/versions/material_slitting_logs.py`（revision: `mat0001slitting_logs`）

**materials 表补充字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `original_weight` | NUMERIC(12,4) | 入库初始重量（永不修改） |

历史数据自动回填：`UPDATE materials SET original_weight = current_weight WHERE original_weight IS NULL`

**新建表：`material_slitting_logs`（分条溯源日志）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | |
| `parent_id` | INTEGER FK→materials | 母卷 ID |
| `child_id` | INTEGER FK→materials | 子卷 ID（可 NULL） |
| `operator_id` | INTEGER FK→users | 操作人 |
| `operator_name` | VARCHAR(100) | 操作人快照 |
| `slit_width` | NUMERIC(12,4) | 单条宽度（mm） |
| `slit_count` | INTEGER | 本次分条条数 |
| `slit_weight` | NUMERIC(12,4) | 本次分条总消耗重量（kg） |
| `parent_consumed_width` | NUMERIC(12,4) | 母卷本次消耗宽度 |
| `parent_remain_width` | NUMERIC(12,4) | 母卷分条后剩余宽度 |
| `parent_auto_closed` | BOOLEAN | 是否触发自动结案 |
| `created_at` | TIMESTAMP | 操作时间 |

索引：`idx_slit_parent(parent_id)`，`idx_slit_child(child_id)`

幂等设计：`CREATE TABLE IF NOT EXISTS`（可安全重复执行）

### 业务逻辑变更

#### `db_service.py` 新增函数

| 函数 | 说明 |
|------|------|
| `execute_material_slitting(parent_id, slit_width, slit_weight, operator_id, operator_name, remark)` | 精密分条：单次分出一条，重量可精确指定或按比例自动推算；写入 `material_slitting_logs` |
| `close_material_item(material_id, operator_id, operator_name, reason)` | 仓库员手动标记余料为报废（status='scrapped'），归零重量，写入 `material_slitting_logs` + `production_scrap` |

#### `db_service.py` 修改函数

| 函数 | 修改内容 |
|------|---------|
| `process_slitting` | 新增 `original_weight` / `current_weight` 字段写入；追加 `material_slitting_logs` 溯源日志 |
| `add_material` | 新增物料时同步写入 `original_weight = current_weight = 初始重量` |
| `scrap_material` | 已在旧版中实现，继续有效 |

#### `main.py` 新增路由

| 路由 | 说明 |
|------|------|
| `POST /materials/{material_id}/close` | 调用 `close_material_item` |
| `POST /materials/{material_id}/slit-fine` | 调用 `execute_material_slitting` |

### UI 变更

#### `templates/materials.html`（物料台账列表页）

- 物料卡片新增「来自母卷」树状关系标识（橙色箭头 + 链接）
- 新增原始重量（`original_weight`）显示行（蓝色标注）
- 新增重量进度条（蓝色进度条，单独一行）
- 操作区新增【精密分条】按钮（橙色）
- 新增精密分条弹窗（宽度 + 重量双输入，实时预览消耗与剩余）

#### `templates/materials_detail.html`（物料详情页）

- 扫码卡片新增原始重量（`original_weight`）数据格
- 新增重量进度条（蓝色，区分于宽度的绿色）
- 操作区新增【精密分条】按钮
- 新增精密分条弹窗（与列表页一致，支持精确指定重量）
- 原有「批量分条」按钮重命名为「批量分条」

### 文件清单

| 文件 | 说明 |
|------|------|
| `alembic/versions/material_slitting_logs.py` | 新建：original_weight 字段 + material_slitting_logs 表 |
| `db_service.py` | 新增 2 个函数；修改 3 个函数 |
| `main.py` | 新增 2 个路由 |
| `templates/materials.html` | 树状关系标识 + 原始重量 + 精密分条弹窗 |
| `templates/materials_detail.html` | 原始重量卡片 + 重量进度条 + 精密分条弹窗 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-05-06 中午 — 喷涂管理模块完善：参数驱动物料核算

### 背景

根据 .cursorrules V3.0 喷涂工艺规范，完善喷涂管理模块，实现：

1. **工艺库维护接口**：`upsert_spraying_recipe` 增加追溯计算检测与返回信息
2. **自动化成本核算**：`recalculate_spraying_consumption` + `/api/spray/recalc` API
3. **管理看板增强**：待完善工艺预警 + 物料平衡表

### 数据库层变更

**无新增表/字段**。本次为纯逻辑增强，复用已有表：

- `spraying_recipes` — 配方参数（`sand_material`, `sand_dosage`, `coating_material`, `coating_dosage`）
- `spraying_logs` — 报工记录（`is_calculated` 标记是否已核算）
- `spraying_material_consumption` — 物料消耗明细

### 业务逻辑变更

#### `db_service.py` 函数增强

| 函数 | 修改内容 |
|------|---------|
| `upsert_spraying_recipe` | 返回值从 `int(recipe_id)` 改为 `dict`，新增 `is_new` / `has_uncalc` / `uncalc_count`，保存配方后能告知前端是否存在待计算记录 |
| `sync_spraying_consumption` | 返回值从 `int` 改为 `dict`，新增 `total_sand` / `total_coat` / `has_recipe`，反映追溯计算详细结果 |
| `recalculate_spraying_consumption` | **新增**：语义别名，调用 `sync_spraying_consumption`，强调"重新核算"场景 |

#### `db_service.py` 新增函数

| 函数 | 说明 |
|------|------|
| `get_parts_without_recipe()` | 查询已有报工记录但无配方的零件列表，供管理看板预警 |
| `get_spraying_material_balance(start_date, end_date)` | 物料平衡表：统计日期范围内各原料的理论消耗汇总 |
| `get_spraying_balance_by_part(part_id, ...)` | 按零件维度统计喷涂产出与物料消耗明细 |

### API 层变更

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/spray/recalc` | POST | 自动化成本核算 API：输入 part_id，返回 `updated_logs / total_sand / total_coat / skipped / has_recipe` |
| `/api/spray/balance` | GET | 物料平衡表 API：输入 start_date / end_date，返回各原料消耗汇总 |
| `/api/spray/recipe/{part_id}` | GET | 配方详情 API：用于前端编辑表单预填充 |
| `/spray/recipe/save` | POST | `trigger_recalc` 参数控制保存后是否自动触发追溯计算 |
| `/spray/recipe/sync` | POST | 返回值结构更新为 `dict`（`updated_logs / total_sand / total_coat`） |

### UI 层变更

#### `templates/spray_recipe.html`（工艺配方管理页）

- **保存时检测待计算记录**：配方保存后，若该零件存在 `is_calculated=FALSE` 的记录，后端返回 `has_uncalc=True`，前端弹出「追溯确认弹窗」
- **追溯确认弹窗**（橙色主题）：显示待计算记录数量，提供「立即追溯计算」和「稍后手动同步」两个选项
- **编辑功能完善**：`editRecipe()` 改为通过 `/api/spray/recipe/{part_id}` 获取完整配方数据后填充编辑表单
- **同步按钮结果更丰富**：显示喷砂/涂料消耗量（kg）

#### `templates/spray_manager.html`（喷涂管理页，完全重写）

- **待完善工艺预警横幅**（红色）：顶部显示所有已有报工但无配方的零件，一键跳转配置
- **标签页切换**：报工补录 / 物料平衡表 两个视图
- **物料平衡表**：日期范围筛选（默认最近30天），按原料（喷砂/涂料）分组展示理论消耗量，底部总计行

### 文件清单

| 文件 | 说明 |
|------|------|
| `db_service.py` | 增强 2 个函数、新增 4 个函数 |
| `main.py` | 新增 3 个 API 路由、更新 2 个已有路由 |
| `templates/spray_recipe.html` | 追溯确认弹窗 + 完善编辑功能 |
| `templates/spray_manager.html` | 完全重写：待完善工艺预警 + 物料平衡表 |
| `docs/dev_log.md` | 本条目 |

---

## 2026-05-06 上午（续2）— 材料基准价格设置中心

### 背景

根据 .cursorrules V3.0 规范，建立材料基准价格中心，支持：

1. **数据库**：`material_base_prices` 表（材料牌号主键）+ `parts.material_name` 字段关联
2. **后端 CRUD**：仅限 sales 组长或 admin 角色访问
3. **同步逻辑**：修改单价时自动检测 Draft 零件，弹窗询问是否同步
4. **预设值**：8 种常用材料（SUS301、SUS304、SPCC、SECC、SGCC、SK5、6061、5052）

### Schema 变更

#### 迁移 1：`alembic/versions/material_base_prices.py`（revision: `mbp0001_material_base_prices`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `material_name` | VARCHAR(100) PK | 材料牌号 |
| `default_density` | NUMERIC(6,3) | 密度 g/cm³ |
| `default_price` | NUMERIC(10,4) | 含税单价 元/kg |
| `scrap_price` | NUMERIC(10,4) | 废料回收价 元/kg |
| `updated_at` | TIMESTAMP | 最后修改时间 |

**预设数据**（迁移时幂等注入）：

| 牌号 | 密度 | 单价（元/kg） | 废料回收价 |
|------|------|-------------|-----------|
| SUS301 | 7.93 | 21.00 | 12.00 |
| SUS304 | 7.93 | 20.50 | 12.00 |
| SPCC | 7.85 | 6.50 | 1.80 |
| SECC | 7.85 | 7.80 | 1.80 |
| SGCC | 7.85 | 6.20 | 1.80 |
| SK5 | 7.85 | 9.50 | 2.00 |
| 6061 | 2.70 | 32.00 | 18.00 |
| 5052 | 2.68 | 30.00 | 16.00 |

#### 迁移 2：`alembic/versions/mbp0002_parts_material_name.py`（revision: `mbp0002_parts_material_name`）

为 `parts` 表增加 `material_name` VARCHAR(100) 字段，用于关联 `material_base_prices`。

### 后端逻辑

#### `db_service.py` 新增函数

| 函数 | 说明 |
|------|------|
| `get_all_material_base_prices()` | 获取全部材料基准价格列表 |
| `get_material_base_price(name)` | 按牌号查询单条 |
| `upsert_material_base_price(...)` | 核心 UPSERT：返回 `action / old_price / new_price / draft_parts` |
| `delete_material_base_price(name)` | 删除（被零件引用时拒绝） |
| `get_parts_using_material(name)` | 获取使用某材料的所有零件（用于同步弹窗列表） |
| `sync_material_price_to_parts(name)` | 将基准价格同步到所有 Draft 零件的 `pending_price` |

#### 同步流程

```
upsert_material_base_price() 返回 draft_parts > 0
    → 前端弹出同步确认弹窗（显示 Draft 零件列表）
    → 用户确认 → POST /api/materials/prices/sync-draft
    → sync_material_price_to_parts() 将 pending_price 更新为新基准价
    → price_status 保持 'Draft'（由价格审核流程推进）
```

### API 路由

| 路由 | 方法 | 说明 |
|------|------|------|
| `/materials/prices` | GET | 材料参数中心页面 |
| `/api/materials/prices` | GET | 获取材料列表 JSON |
| `/api/materials/prices` | POST | 新增/更新材料（含 sync_draft 参数） |
| `/api/materials/prices/{name}` | DELETE | 删除材料 |
| `/api/materials/prices/{name}/parts` | GET | 获取使用某材料的零件列表 |
| `/api/materials/prices/sync-draft` | POST | 将基准价格同步到 Draft 零件 |

### 权限控制

- `_price_admin_guard()`：仅 `department in ('sales', 'admin')` 或 `role_level >= 5` 可访问
- 删除时做引用检查：被零件引用的材料不可删除

### 前端 UI

**`templates/material_prices.html`**：独立材料参数中心页面

- 顶部绿色主题导航
- 统计摘要卡片（材料种类数等）
- 卡片列表展示密度/单价/废料回收价
- **新增材料**：牌号可编辑（唯一键）
- **编辑材料**：牌号只读，显示同步提示（橙色警告）
- **删除**：二次确认，被引用时后端返回错误
- **同步确认弹窗**：橙色主题，显示旧/新单价差异 + Draft 零件列表 + 「确认同步」/「暂不同步」

### 文件清单

| 文件 | 说明 |
|------|------|
| `alembic/versions/material_base_prices.py` | 新建：表 + 预设数据 |
| `alembic/versions/mbp0002_parts_material_name.py` | 新建：parts.material_name 字段 |
| `db_service.py` | 新增 6 个函数 |
| `main.py` | 新增 6 个路由 |
| `templates/material_prices.html` | 新建：材料参数中心页面 |
| `docs/dev_log.md` | 本条目 |





---

## 2026-05-22 | 领域解耦重构影响分析报告（待执行）

**执笔人：** 首席架构师（Claude Sonnet 4.6）
**任务背景：** 将"工程零件数据"与"商业报价数据"彻底分离，建立 `parts`（工程主数据）与 `quotes`（报价单）的清晰边界。

---

### 一、现状诊断：解耦已完成 80%，但存在残留耦合

经过全局代码扫描，**好消息是**：本项目已经历过一次 `split_parts_and_quotes_v2` 迁移，`parts` 表中的大部分价格字段（`pending_price`、`current_price`、`price_status`、`stamping_fee`、`surface_fee`、`profit_margin` 等）已被删除，`quotes` 表已建立并投入使用。

**坏消息是**：仍存在以下四类残留耦合问题，需要本次重构彻底清除。

---

### 二、残留耦合问题清单

#### 问题 A：`PartCreateRequest` Schema 混入了报价字段

**文件：** `app/models/schemas.py`

**现状：** `PartCreateRequest` 包含以下本应属于 `QuoteCreateBody` 的字段：
```
stamping_fee, surface_fee, profit_margin,
final_price_override, pricing_mode, referenced_part_id,
material_utilization, machine_type, press_tonnage
```

**影响路由：**
- `POST /api/parts/create`（`api_create_part` 函数）
- `POST /sales/parts/new`（`sales_part_new` 函数）

**修复方案：** `PartCreateRequest` 只保留工程字段；创建零件时同步创建 `Quote` 的逻辑已存在（`create_part_with_mold_and_pricing` 三表原子事务），只需确保 Schema 分层清晰，前端传参路径正确。

---

#### 问题 B：`create_part_with_pricing` 函数缺少 quote 创建步骤

**文件：** `app/services/db_service.py`

**现状：** `create_part_with_pricing(...)` 函数：INSERT `parts` 时写入 `thickness, width, press_stroke, cavities, mold_tonnage`，但**没有同步创建对应的 `quotes` 记录**（仅创建了 part，未创建 quote）。

相比之下，`create_part_with_mold_and_pricing` 已正确实现三表原子事务（parts + molds + quotes）。

**修复方案：** `create_part_with_pricing` 必须同步创建 `quotes` 记录（DRAFT 状态）。

---

#### 问题 C：前端模板中存在通过 `p.approval_status` 读取报价状态的越界引用

**文件：** `templates/sales/part_pricing.html`（第 243 行）、`templates/material_prices.html`（第 429 行）

**现状：**
```jinja2
{{ p.approval_status }}  {# 第 243 行，p 是 Part 对象，但 approval_status 属于 quotes 表 #}
```
这是一个**越界读取**——`parts` 表中已无此字段，此处能工作只因为后端查询时通过 JOIN 将 `quotes.approval_status` 混入了 `part` 对象返回给模板。

**修复方案：** 将模板中的 `p.approval_status` 改为 `quote.approval_status`，并确保后端路由传递独立的 `quote` 对象给模板，而非将 quote 字段混入 part 对象。

---

#### 问题 D：重复路由定义（需清理）

**文件：** `app/api/sales.py`

**现状：** `/sales/parts` 路径被定义了两次：
- `sales_parts_list_page`（先注册，FastAPI 实际生效）
- `sales_part_list_page`（后注册，被覆盖，实际无效）

同样，报价工作流存在两套重复路由（单数 vs 复数形式）：
- `/api/quote/{id}/submit` 和 `/api/quotes/{id}/submit`
- `/api/quote/{id}/approve` 和 `/api/quotes/{id}/approve`
- `/api/quote/{id}/reject` 和 `/api/quotes/{id}/reject`

**修复方案：** 统一使用复数形式 `/api/quotes/{id}/...`，删除单数形式的旧路由，同步更新 `api_config.js`。

---

### 三、本次重构的具体执行范围

#### 第一阶段：数据库与模型层

| 序号 | 操作 | 文件 | 具体内容 |
|------|------|------|----------|
| 1.1 | 清理 `PartCreateRequest` | `app/models/schemas.py` | 将 `stamping_fee, surface_fee, profit_margin, final_price_override, pricing_mode, referenced_part_id, material_utilization, machine_type, press_tonnage` 从 `PartCreateRequest` 中移除，改为独立的 `QuoteInitBody` |
| 1.2 | 修复 `create_part_with_pricing` | `app/services/db_service.py` | 确保该函数在创建 part 后同步创建 DRAFT 状态的 quote 记录 |

#### 第二阶段：后端服务与路由层

| 序号 | 操作 | 文件 | 具体内容 |
|------|------|------|----------|
| 2.1 | 清理重复路由 | `app/api/sales.py` | 删除单数形式 `/api/quote/{id}/...` 旧路由，统一使用 `/api/quotes/{id}/...` |
| 2.2 | 清理重复页面路由 | `app/api/sales.py` | 删除 `sales_part_list_page`（无效的第二个 `/sales/parts` 定义） |
| 2.3 | 同步更新 `api_config.js` | `static/js/api_config.js` | 确认所有前端调用指向复数形式路由 |
| 2.4 | 重构 `get_part_detail` 返回结构 | `app/api/sales.py` | 确保返回 `{part: {...}, quote: {...}}` 分层结构，而非将 quote 字段混入 part 对象 |

#### 第三阶段：前端模板层

| 序号 | 操作 | 文件 | 具体内容 |
|------|------|------|----------|
| 3.1 | 修复越界引用 | `templates/sales/part_pricing.html` 第 243 行 | `p.approval_status` → `quote.approval_status` |
| 3.2 | 修复越界引用 | `templates/material_prices.html` 第 429 行 | `p.approval_status` → `quote.approval_status` |
| 3.3 | 审查 `part_create.html` | `templates/sales/part_create.html` | 确认创建零件时的报价字段（stamping_fee 等）通过独立的 quote 创建接口提交，而非混入 part 创建请求 |

---

### 四、不需要修改的部分（已正确实现）

以下内容**已经符合领域解耦原则**，本次重构不触碰：

1. **`quotes` 表的完整 CRUD 路由**（`/api/quotes/{id}` 系列）——已正确实现
2. **报价审批状态机**（`DRAFT → PENDING_BOSS → APPROVED/REJECTED`）——已正确实现
3. **白盒核算引擎**（`calc_pricing` 接口）——已基于 `quotes` 参数计算，无需修改
4. **`get_part_pricing_summary`**——已通过 JOIN 正确聚合 part + quote + material 三表数据
5. **`create_part_with_mold_and_pricing`**——已实现三表原子事务（parts + molds + quotes）
6. **`templates/sales/part_pricing.html` 中的大部分 quote 字段引用**——已正确通过 `quote.xxx` 访问

---

### 五、风险评估

| 风险项 | 等级 | 说明 |
|--------|------|------|
| Schema 修改影响前端表单 | 中 | `PartCreateRequest` 字段变更需同步修改 `part_create.html` 的提交逻辑 |
| 重复路由清理影响现有调用 | 低 | 单数形式路由在 `api_config.js` 中未登记，前端已使用复数形式 |
| `p.approval_status` 越界引用 | 低 | 目前通过 JOIN 混入能工作，但语义错误，需修正 |
| `create_part_with_pricing` 缺少 quote 创建 | 中 | 若此函数被调用，会产生无 quote 的孤立 part，影响后续定价流程 |

---

### 六、执行顺序建议

```
1. 先修复 db_service.py（create_part_with_pricing 补充 quote 创建）
2. 再修复 schemas.py（PartCreateRequest 字段分层）
3. 再修复 sales.py（清理重复路由，重构 get_part_detail 返回结构）
4. 最后修复模板（p.approval_status 越界引用）
5. 全程不需要新建迁移文件（数据库 schema 已正确，无需变更表结构）
```

---

*报告生成时间：2026-05-22*
*下一步：等待架构师确认后开始执行*
