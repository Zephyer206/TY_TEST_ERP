# Tasks: Zephyr_test_ERP

**Input**: Design documents from `/specs/001-erp-system-architecture/`

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `data-model.md`, `contracts/`, `research.md`, `quickstart.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

**Total tasks**: 111

- [x] T001 创建项目目录结构：backend/src/、frontend/、miniprogram/、mobile-h5/
- [x] T002 初始化 Python 后端项目：requirements.txt、.env.example
- [x] T003 初始化 Vue 3 前端项目：package.json、vite.config.ts
- [x] T004 创建 Docker 配置：Dockerfile、docker-compose.yml
- [x] T005 创建 alembic.ini 数据库迁移配置

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### 2.1 Database & Config

- [x] T006 在 backend/src/database.py 中配置 PostgreSQL + asyncpg 连接池
- [x] T007 在 backend/src/config.py 中实现环境变量配置管理（Pydantic Settings）
- [x] T008 配置 Redis 连接（backend/src/redis.py）用于会话存储

### 2.2 Core Models (All User Stories Depend On)

- [x] T009 [P] 创建 backend/src/models/user.py：User + Department 模型
- [x] T010 [P] 创建 backend/src/models/customer.py：Customer 模型
- [x] T011 [P] 创建 backend/src/models/audit.py：AuditLog 模型

### 2.3 Authentication & Security

- [x] T012 在 backend/src/core/security.py 中实现 JWT token 生成与验证
- [x] T013 在 backend/src/core/security.py 中实现密码哈希（bcrypt）
- [x] T014 在 backend/src/api/deps.py 中实现当前用户依赖注入（get_current_user）
- [x] T015 在 backend/src/core/permissions.py 中实现角色权限装饰器（@require_role）
- [x] T016 创建 backend/src/api/auth.py：POST /api/auth/login、GET /api/auth/me

### 2.4 API Routing Infrastructure

- [x] T017 在 backend/src/main.py 中配置 FastAPI 应用骨架、中间件、异常处理
- [x] T018 在 backend/src/core/events.py 中实现审计日志事件总线（写入 audit_logs）

### 2.5 State Machine Base

- [x] T019 创建 backend/src/state_machines/quote_states.py：报价单状态机
- [x] T020 创建 backend/src/state_machines/part_states.py：零件状态机
- [x] T021 创建 backend/src/state_machines/machine_states.py：机台状态机

**Checkpoint**: ✅ Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 — 报价与审批 (Priority: P1) 🎯 MVP

**Goal**: 业务经理能创建报价单、填写技术参数和价格、提交老板审批、定点确认

**Independent Test**: 创建报价单 → 填写价格和技术参数 → 老板审批 → 定点确认（量产/样件路径）

### Models

- [x] T022 [P] [US1] 创建 backend/src/models/quote.py：Quote、QuoteItem 模型
- [x] T023 [P] [US1] 创建 backend/src/schemas/quote.py：QuoteCreate、QuoteUpdate 等 Pydantic schemas

### Services

- [x] T024 [US1] 在 backend/src/services/quote_service.py 中实现报价单业务逻辑（创建、技术审核、价格快照、定点确认，含 nomination_status 定点状态管理；APPROVED 后允许编辑，仅 final_price 变动触发重新审批）

### Endpoints

- [x] T025 [P] [US1] 在 backend/src/api/quotes.py 中实现 POST /api/quotes（创建报价单）
- [x] T026 [P] [US1] 在 backend/src/api/quotes.py 中实现 GET /api/quotes/{id}（获取详情）
- [x] T027 [US1] 实现 PUT /api/quotes/{id}/tech-review（技术审核，依赖 T019 状态机）
- [x] T028 [US1] 实现 PUT /api/quotes/{id}/submit-boss（提交老板审批）
- [x] T029 [US1] 实现 PUT /api/quotes/{id}/boss-approve（老板审批，含价格快照锁定；APPROVED 后编辑时仅 final_price 变动触发重新审批）
- [x] T030 [US1] 实现 POST /api/quotes/{id}/fix（定点确认，含手动输入定点价格；仅当 final_price 变动时触发重新审批）
- [x] T030a [US1] 实现 POST /api/quotes/{id}/revoke-nomination（撤销定点；撤销后 quotes 留在 APPROVED，nomination_status 标记已撤销，审计日志记录 operator_id + operated_at）

### Integration

- [x] T031 [US1] 在 backend/src/services/part_service.py 中实现零件状态变更（Draft → Sampling/MassProduction）
- [x] T032 [US1] 集成 surface_treatments 表（多道表面处理计价）

**Checkpoint**: 报价与审批完整链路可用，可作为 MVP 交付

---

## Phase 4: User Story 9 — 价格台账与年降 (Priority: P0)

**Goal**: 管理每个零件+客户的价格档案，按年录入单价，系统自动追踪年降；定点后模板一键导入零件参数

**Independent Test**: 定点确认 → 模板导入零件参数 → 新建价格档案 → 录入年份单价 → 年降计算验证

> 注：US9 优先级为 P0，在 spec 中被标记为最高优先级，应与 US1 并行实施

### Models

- [x] T033 [P] [US9] 创建 backend/src/models/price.py：PriceAccount、AnnualPriceRecord、PriceAdjustment 模型

### Services

- [x] T034 [US9] 在 backend/src/services/price_service.py 中实现价格档案管理、年降计算（price = base_price × (1 - reduction_pct)^elapsed_years）
- [x] T035 [US9] 在 backend/src/services/file_service.py 中实现图纸文件处理（定点后按「零件名+上传日期」归档）

### Endpoints

- [x] T036 [P] [US9] 实现 POST /api/price-accounts（创建价格档案）
- [x] T037 [P] [US9] 实现 PUT /api/price-accounts/{id}/annual-price（录入年份单价）
- [x] T038 [US9] 实现 POST /api/parts/{id}/import-excel（模板一键导入零件参数）

**Checkpoint**: 价格台账和年降功能完整

---

## Phase 5: User Story 2 — 打样管理与样件跟踪 (Priority: P1)

**Goal**: 对定点后进入样件阶段的零件进行全程跟踪；老板审核确认后启动打样；样件评审通过后切换为量产

**Independent Test**: 创建打样任务 → 老板审核 → 执行打样 → 客户评审通过 → 零件进入量产

### Models

- [x] T039 [P] [US2] 创建 backend/src/models/sampling.py：SamplingTask 模型
- [x] T040 [P] [US2] 创建 backend/src/schemas/sampling.py：SamplingTaskCreate 等 Pydantic schemas

### Services

- [x] T041 [US2] 在 backend/src/services/sampling_service.py 中实现打样任务业务逻辑（创建、老板审核、打样开始/完成、评审）

### Endpoints

- [x] T042 [P] [US2] 实现 POST /api/sampling-tasks（创建打样任务）
- [x] T043 [P] [US2] 实现 GET /api/sampling-tasks（打样任务列表，含加急标记筛选）
- [x] T044 [US2] 实现 PUT /api/sampling-tasks/{id}/boss-approve（老板审核确认）
- [x] T045 [US2] 实现 PUT /api/sampling-tasks/{id}/review（评审结果：passed/failed）
- [x] T046 [US2] 实现 PUT /api/sampling-tasks/{id}/urgent（加急标记）

### Integration

- [x] T047 [US2] 打样评审通过后自动更新零件状态（Sampling → MassProduction）
- [x] T048 [US2] 实现样件跟踪看板 API（按零件编号、客户名称、状态、计划完成时间筛选）

**Checkpoint**: 打样管理完整链路可用

---

## Phase 6: User Story 3 — 模具管理与维修 (Priority: P1)

**Goal**: 管理模具台账；两扫制维修流程（第一次扫码记录维修中，第二次扫码弹出操作选项）

**Independent Test**: 新建模具档案 → 机台报障 → 第一次扫码 → 维修中 → 第二次扫码 → 维修完成/拆模

### Models

- [x] T049 [P] [US3] 创建 backend/src/models/tooling.py：Tooling、ToolingPart、ToolingMaintenanceLog 模型

### Services

- [x] T050 [US3] 在 backend/src/services/tooling_service.py 中实现模具台账管理、两扫制维修逻辑

### Endpoints

- [x] T051 [P] [US3] 实现 POST /api/toolings（新建模具档案）
- [x] T052 [P] [US3] 实现 GET /api/toolings/{id}（模具详情，含父-子关联查询）
- [x] T053 [US3] 实现 PUT /api/machines/{id}/scan（扫码处理：故障上报/第一次扫码维修/第二次扫码操作）
- [x] T054 [US3] 实现 GET /api/toolings/maintenance-pool（待修池列表）

**Checkpoint**: 模具管理完整链路可用

---

## Phase 7: User Story 4 — 生产计划与报工 (Priority: P1)

**Goal**: 创建生产计划并分配机台；扫码原材料+机台验证后开始报工；连续模支持会话模式

**Independent Test**: 创建生产计划 → 分配机台 → 扫码原材料+机台验证 → 报工结账

### Models

- [x] T055 [P] [US4] 创建 backend/src/models/machine.py：Machine、MachineStatusLog 模型
- [x] T056 [P] [US4] 创建 backend/src/models/production.py：ProductionPlan、PlanMachineAssignment、ProductionReport、ProductionSession 模型
- [x] T057 [P] [US4] 创建 backend/src/schemas/production.py：相关 Pydantic schemas

### Services

- [x] T058 [US4] 在 backend/src/services/production_service.py 中实现生产计划管理、机台分配
- [x] T059 [US4] 在 backend/src/services/session_service.py 中实现连续模报工会话（开启/多次报工/结账）
- [x] T060 [US4] 在 backend/src/services/process_flow_service.py 中实现工艺流转单自动生成

### Endpoints

- [x] T061 [P] [US4] 实现 POST /api/production/plans（创建生产计划）
- [x] T062 [P] [US4] 实现 POST /api/production/plans/{id}/assign-machine（分配机台）
- [x] T063 [US4] 实现 POST /api/production/sessions/start（开启报工会话，含原材料-模具匹配校验）
- [x] T064 [US4] 实现 POST /api/production/reports（提交报工，strokes × cavity_count = 产出）
- [x] T065 [US4] 实现 POST /api/production/sessions/{id}/close（结账会话，生成工艺流转单）

**Checkpoint**: 生产计划与报工完整链路可用

---

## Phase 8: User Story 6 — 原材料与批次管理 (Priority: P2)

**Goal**: 管理原材料台账；IQC 检验；QR 码批次追踪；分条操作

**Independent Test**: 新建原材料 → 来料 IQC 检验 → 批次分配 → 分条操作

### Models

- [x] T066 [P] [US6] 创建 backend/src/models/warehouse.py：Supplier、MaterialBatch、MaterialBatchChild 模型

### Services

- [x] T067 [US6] 在 backend/src/services/material_batch_service.py 中实现原材料管理、IQC 检验、分条操作（子卷生成）

### Endpoints

- [x] T068 [P] [US6] 实现 POST /api/warehouse/material-batches（登记原材料，生成批次号）
- [x] T069 [P] [US6] 实现 PUT /api/warehouse/material-batches/{id}/iqc（IQC 检验：合格/不合格）
- [x] T070 [US6] 实现 POST /api/warehouse/material-batches/{id}/split（分条操作，生成子二维码）
- [x] T071 [US6] 实现 GET /api/warehouse/material-batches/{id}/trace（批次流转追溯）

**Checkpoint**: 原材料与批次管理可用

---

## Phase 9: User Story 5 — 质量管控与放行 (Priority: P2)

**Goal**: 首件检验、OQC 出货检验、强行特赦；所有放行操作写入 QA 审计日志

**Independent Test**: 首件检验通过 → 批量生产 → OQC 出货检验 → 发货

### Models

- [x] T072 [P] [US5] 创建 backend/src/models/quality.py：FirstPieceInspection、OQCInspection、QAExemption、PatrolInspection 模型

### Services

- [x] T073 [US5] 在 backend/src/services/quality_service.py 中实现首件检验、OQC 检验、强行特赦

### Endpoints

- [x] T074 [P] [US5] 实现 POST /api/quality/first-piece（首件检验）
- [x] T075 [P] [US5] 实现 POST /api/quality/oqc（OQC 出货检验）
- [x] T076 [US5] 实现 POST /api/quality/exemption（强行特赦，含 role_level >= 2 校验）

**Checkpoint**: 质量管控与放行可用

---

## Phase 10: User Story 7a — 包装管理 (Priority: P2)

**Goal**: 包装扫码、全检入库流程

**Independent Test**: 包装扫码 → 全检入库 → 库存更新

### Models

- [x] T077 [P] [US7a] 创建 backend/src/models/packaging.py：PackagingRecord 模型

### Services

- [x] T078 [US7a] 在 backend/src/services/packaging_service.py 中实现包装扫码、全检入库

### Endpoints

- [x] T079 [P] [US7a] 实现 POST /api/packaging/scan（包装扫码录入）
- [x] T080 [US7a] 实现 POST /api/packaging/inspect（全检合格入库，更新正品库存）

**Checkpoint**: 包装管理可用

---

## Phase 11: User Story 8 — 喷涂表面处理 (Priority: P3)

**Goal**: 管理喷涂配方；扫码执行喷涂报工；物料余额管理

**Independent Test**: 配置喷涂配方 → 扫码喷涂 → 记录产出

### Models

- [x] T081 [P] [US8] 创建 backend/src/models/coating.py：CoatingRecipe、CoatingRecord 模型

### Services

- [x] T082 [US8] 在 backend/src/services/coating_service.py 中实现喷涂配方管理、喷涂报工

### Endpoints

- [x] T083 [P] [US8] 实现 POST /api/coating/recipes（创建喷涂配方）
- [x] T084 [US8] 实现 POST /api/coating/records（喷涂报工）

**Checkpoint**: 喷涂表面处理可用

---

## Phase 12: User Story 10 — 超级管理员视角切换 (Priority: P3)

**Goal**: 超级管理员临时切换部门视角；切换后无老板专用按钮泄露

**Independent Test**: 超级管理员切换业务视角 → 验证无老板审批按钮 → 切换回 admin

### Models

- [x] T085 [P] [US10] 创建 backend/src/models/admin.py：AdminContextSwitch 模型

### Services

- [x] T086 [US10] 在 backend/src/services/admin_service.py 中实现视角切换（生成受限 token，原始 role_level 存入 Redis）

### Endpoints

- [x] T087 [P] [US10] 实现 POST /api/admin/switch-context（切换视角，隐藏 role_level >= 9 按钮）
- [x] T088 [US10] 实现 POST /api/admin/switch-back（恢复 admin 视角）

### Frontend Integration

- [x] T089 [US10] 在 frontend/src/stores/permission.ts 中实现动态按钮权限控制
- [x] T090 [US10] 在 frontend/src/router/index.ts 中实现路由守卫（切换视角期间拦截老板审批页面）

**Checkpoint**: 超级管理员视角切换完整可用

---

## Phase 13: QR Code System (Cross-Cutting)

**Purpose**: 全链路二维码追溯体系，与各用户故事深度集成

### QR Generation

- [x] T091 [P] 在 backend/src/services/qr_service.py 中实现 QR 码生成（qrcode + Pillow）
- [x] T092 [P] 配置云端 OSS（腾讯云COS/阿里云OSS）上传 QR 图片

### QR Endpoints

- [x] T093 实现 GET /api/qr/lookup?code={qr_code}（扫码查询，支持 MAT-/MCN-/PFC- 前缀识别）
- [x] T094 实现 GET /api/qr/material/{batch_id}（原料批次 QR）
- [x] T095 实现 GET /api/qr/machine/{machine_id}（机台 QR）
- [x] T096 实现 GET /api/qr/process-flow/{card_id}（工艺流转单 QR）

### Miniprogram Integration

- [x] T097 在 miniprogram/services/api.js 中封装后端 API 调用
- [x] T098 在 miniprogram/pages/scan/index.js 中实现微信扫码（wx.scanCode）

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: 全局优化、文档、收尾

- [x] T099 [P] 创建 scripts/init_admin.py（初始化超级管理员脚本）
- [x] T100 [P] 配置前端 Element Plus 主题和国际化（中文）
- [x] T101 [P] 实现前端 API 统一错误处理（401 重定向、403 提示）
- [x] T102 实现前端报价管理页面（quotes/views/*.vue）
- [x] T103 实现前端生产计划页面（production/views/*.vue）
- [x] T104 实现前端看板页面（dashboard/views/*.vue）
- [x] T105 配置前端权限控制（根据 role_level 动态渲染按钮）
- [x] T106 软删除实现审计（FR-085：所有 DELETE 操作改为 is_deleted 标记）
- [x] T107 性能优化：数据库索引验证（确保关键查询走索引）
- [x] T108 安全加固：输入校验、SQL 注入防护、CORS 配置
- [x] T109 更新 .github/copilot-instructions.md（反映已实施的技术决策）
- [x] T110 运行 quickstart.md 验证场景，确保端到端可工作

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 + US9 (Phase 3-4)**: Both depend on Foundational — can run in parallel (P1 + P0)
- **US2 + US3 + US4 (Phase 5-7)**: All depend on Foundational + US1 models — can run in parallel
- **US6 + US5 + US7a (Phase 8-10)**: Depend on Foundational — can run in parallel
- **US8 + US10 (Phase 11-12)**: Depend on Foundational — can run in parallel
- **QR System (Phase 13)**: Cross-cutting, integrates with US4/6/7a
- **Polish (Phase 14)**: Depends on all user stories

### Recommended MVP Scope

**MVP = Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US9)**

1. Complete Setup + Foundational
2. Implement US1 (报价与审批) + US9 (价格台账) in parallel
3. Test independently
4. Deploy MVP

---

## Task Summary

| User Story | Phase | Priority | Tasks | Description |
|------------|-------|----------|-------|-------------|
| Foundational | 2 | — | T006-T021 | 基础设施（DB、认证、权限、状态机） |
| US1 | 3 | P1 | T022-T030a | 报价与审批（含撤销定点） |
| US9 | 4 | P0 | T033-T038 | 价格台账与年降 |
| US2 | 5 | P1 | T039-T048 | 打样管理与样件跟踪 |
| US3 | 6 | P1 | T049-T054 | 模具管理与维修 |
| US4 | 7 | P1 | T055-T065 | 生产计划与报工 |
| US6 | 8 | P2 | T066-T071 | 原材料与批次管理 |
| US5 | 9 | P2 | T072-T076 | 质量管控与放行 |
| US7a | 10 | P2 | T077-T080 | 包装管理 |
| US8 | 11 | P3 | T081-T084 | 喷涂表面处理 |
| US10 | 12 | P3 | T085-T090 | 超级管理员视角切换 |
| QR System | 13 | — | T091-T098 | 二维码系统（跨用户故事） |
| Polish | 14 | — | T099-T110 | 收尾与优化 |
| **Total** | | | **111 tasks** | |

**Parallel Opportunities**: 标记为 [P] 的任务可并行执行；Phase 3-12 的用户故事在 Foundational 完成后可并行实施。

---

*Tasks generated. Ready for implementation.*
