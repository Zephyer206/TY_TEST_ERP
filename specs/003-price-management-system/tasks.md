# Tasks: Price Management System Backend

**Input**: Design documents from `/specs/003-price-management-system/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: 测试任务已包含（规格明确要求后端测试，覆盖率80%+）

**Organization**: 任务按用户故事分组，每个故事可独立实现和测试

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 任务所属用户故事（如 US1, US2, US3）
- 包含精确文件路径

## Path Conventions

本项目使用 Web 应用结构：
- 后端：`backend/app/`（models, schemas, api, services）
- 数据迁移：`backend/scripts/migrations/`
- 测试：`backend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 项目结构初始化和基础配置

- [ ] T001 按实施计划确认项目结构（backend/app/已存在）
- [ ] T002 [P] 确认 Python 3.11 + FastAPI + asyncpg 环境就绪
- [ ] T003 [P] 确认测试框架 pytest + pytest-asyncio 已配置

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 核心基础设施，必须在任何用户故事前完成

**⚠️ CRITICAL**: 所有用户故事工作必须等此阶段完成

### Stage 2.1: Database Schema & Migration Scripts

- [ ] T004 在 backend/scripts/migrations/001_create_treatment_dict.py 中创建 treatment_dict 表迁移脚本
- [ ] T005 [P] 在 backend/scripts/migrations/002_create_customer_material_prices.py 中创建 customer_material_prices 表迁移脚本
- [ ] T006 [P] 在 backend/scripts/migrations/003_create_customer_treatment_prices.py 中创建 customer_treatment_prices 表迁移脚本
- [ ] T007 [P] 在 backend/scripts/migrations/004_create_price_adjustments.py 中创建 price_adjustments 表迁移脚本
- [ ] T008 在 backend/scripts/migrations/005_migrate_material_base_prices.py 中创建材料价格数据迁移脚本
- [ ] T009 在 backend/scripts/migrations/006_migrate_treatment_dicts.py 中创建工序字典数据迁移脚本
- [ ] T010 在 backend/scripts/migrations/007_drop_legacy_tables.py 中创建旧表删除迁移脚本

### Stage 2.2: SQLAlchemy Models

- [ ] T011 [P] 在 backend/app/models/price.py 中扩展并新增 CustomerMaterialPrice 模型
- [ ] T012 [P] 在 backend/app/models/price.py 中新增 CustomerTreatmentPrice 模型
- [ ] T013 [P] 在 backend/app/models/price.py 中新增 TreatmentDict 模型
- [ ] T014 [P] 在 backend/app/models/price.py 中新增 PriceAdjustment 模型（替换占位符）
- [ ] T015 在 backend/app/models/__init__.py 中导出新模型

### Stage 2.3: Pydantic Schemas

- [ ] T016 [P] 在 backend/app/schemas/price.py 中新增 CustomerMaterialPriceCreate/Response schemas
- [ ] T017 [P] 在 backend/app/schemas/price.py 中新增 CustomerTreatmentPriceCreate/Response schemas
- [ ] T018 [P] 在 backend/app/schemas/price.py 中新增 PriceAdjustmentCreate/Response/ApprovalRequest schemas
- [ ] T019 [P] 创建 backend/app/schemas/treatment.py 并定义 TreatmentDictCreate/Update/Response schemas

**Checkpoint**: 基础层就绪 - 用户故事实现可并行开始

---

## Phase 3: User Story 1 - 查询客户材料历史价格 (Priority: P1) 🎯 MVP

**Goal**: 业务经理查询客户的材料价格历史（最近3次），用于报价参考

**Independent Test**: 业务经理选择客户和材质，系统返回最近3次成交价格，如无历史则返回材料字典默认价格

### Tests for User Story 1

> **NOTE: 先写测试，确保失败后再实现**

- [ ] T020 [P] [US1] 在 backend/tests/test_api_customer_prices.py 中创建材料价格历史查询 API 测试（空历史、有历史、限制3条）
- [ ] T021 [P] [US1] 在 backend/tests/test_migrations_price_system.py 中创建数据迁移测试（验证 material_base_prices 迁移）

### Implementation for User Story 1

- [ ] T022 [US1] 在 backend/app/services/customer_price_service.py 中实现 get_material_price_history 方法（查询+排序+限制）
- [ ] T023 [US1] 在 backend/app/services/customer_price_service.py 中实现兜底逻辑（无历史时返回 material_dict.default_price）
- [ ] T024 [US1] 在 backend/app/api/customer_prices.py 中实现 GET /api/customer-prices/materials 端点（role_level >= 5）
- [ ] T025 [US1] 在 backend/app/api/customer_prices.py 中添加查询参数验证（customer_id, material_id, limit 默认3最大20）
- [ ] T026 [US1] 在 backend/app/main.py 中注册 customer_prices 路由

**Checkpoint**: US1 完成 - 业务经理可查询材料价格历史并获得兜底建议

---

## Phase 4: User Story 2 - 新增客户材料价格历史记录 (Priority: P1) 🎯 MVP

**Goal**: 业务经理在报价定点后，记录本次使用的材料单价到客户历史

**Independent Test**: 业务经理创建材料价格记录（含客户、材质、单价、废料价），系统保存并可立即查询

### Tests for User Story 2

- [ ] T027 [P] [US2] 在 backend/tests/test_api_customer_prices.py 中创建材料价格历史新增 API 测试（正常、缺字段、重复）

### Implementation for User Story 2

- [ ] T028 [US2] 在 backend/app/services/customer_price_service.py 中实现 create_material_price_record 方法（INSERT 操作）
- [ ] T029 [US2] 在 backend/app/services/customer_price_service.py 中添加业务验证（unit_price > 0, customer/material 存在性检查）
- [ ] T030 [US2] 在 backend/app/api/customer_prices.py 中实现 POST /api/customer-prices/materials 端点（role_level >= 5）
- [ ] T031 [US2] 在 backend/app/api/customer_prices.py 中添加请求校验和错误处理（404 客户不存在、400 价格无效）

**Checkpoint**: US2 完成 - 业务经理可记录材料价格历史，配合 US1 形成完整价格参考流程

---

## Phase 5: User Story 3 - 查询客户工序历史价格 (Priority: P1) 🎯 MVP

**Goal**: 业务经理查询客户的工序价格历史（最近3次），用于工序费用报价

**Independent Test**: 业务经理选择客户和工序，系统返回最近3次成交价格和计价方式快照

### Tests for User Story 3

- [ ] T032 [P] [US3] 在 backend/tests/test_api_customer_prices.py 中创建工序价格历史查询 API 测试（空历史、有历史、快照验证）

### Implementation for User Story 3

- [ ] T033 [US3] 在 backend/app/services/customer_price_service.py 中实现 get_treatment_price_history 方法（查询+排序+限制）
- [ ] T034 [US3] 在 backend/app/services/customer_price_service.py 中实现兜底逻辑（无历史时返回 treatment_dict.default_rate）
- [ ] T035 [US3] 在 backend/app/api/customer_prices.py 中实现 GET /api/customer-prices/treatments 端点（role_level >= 5）
- [ ] T036 [US3] 在 backend/app/api/customer_prices.py 中添加查询参数验证（customer_id, treatment_id, limit）

**Checkpoint**: US3 完成 - 业务经理可查询工序价格历史

---

## Phase 6: User Story 4 - 新增客户工序价格历史记录 (Priority: P1) 🎯 MVP

**Goal**: 报价单中使用的工序费用记录到客户历史，快照计价方式

**Independent Test**: 业务经理创建工序价格记录（含快照 calc_mode 和 unit），系统保存并可查询

### Tests for User Story 4

- [ ] T037 [P] [US4] 在 backend/tests/test_api_customer_prices.py 中创建工序价格历史新增 API 测试（正常、快照验证）

### Implementation for User Story 4

- [ ] T038 [US4] 在 backend/app/services/customer_price_service.py 中实现 create_treatment_price_record 方法（INSERT + 快照逻辑）
- [ ] T039 [US4] 在 backend/app/services/customer_price_service.py 中实现快照机制（从 treatment_dict 自动获取 calc_mode 和 unit）
- [ ] T040 [US4] 在 backend/app/api/customer_prices.py 中实现 POST /api/customer-prices/treatments 端点（role_level >= 5）
- [ ] T041 [US4] 在 backend/app/api/customer_prices.py 中添加快照字段验证（calc_mode_snapshot, unit_snapshot）

**Checkpoint**: US4 完成 - 工序价格历史记录功能完整，快照机制保护历史真实性

---

## Phase 7: User Story 5 - 数据迁移：废弃旧材料价格表 (Priority: P1) 🎯 MVP

**Goal**: 清理遗留表，迁移数据到新表结构

**Independent Test**: 运行迁移脚本，旧表数据迁移到新表，旧表删除，现有 API 不受影响

### Tests for User Story 5

- [ ] T042 [P] [US5] 在 backend/tests/test_migrations_price_system.py 中创建 treatment_dicts 迁移测试（白名单、脏数据过滤）
- [ ] T043 [P] [US5] 在 backend/tests/test_migrations_price_system.py 中创建旧表删除测试（确认表不存在）

### Implementation for User Story 5

- [ ] T044 [US5] 在迁移脚本 005 中实现冲突检测和日志记录（material_base_prices 与 material_dict 冲突）
- [ ] T045 [US5] 在迁移脚本 006 中实现白名单机制（只迁移10条真实工序名称）
- [ ] T046 [US5] 在迁移脚本 007 中实现前置检查（全局搜索旧表引用，确认无引用）
- [ ] T047 [US5] 执行完整迁移流程（T004-T010 脚本按顺序运行，验证数据完整性）
- [ ] T048 [US5] 在 backend/scripts/migrations/ 中创建回滚脚本（备份旧表数据，支持迁移失败回滚）

**Checkpoint**: US5 完成 - 数据迁移成功，旧表废弃，新表结构生效

---

## Phase 8: User Story 6 - 价格调整审批流程 (Priority: P2)

**Goal**: 业务经理提交调价申请，老板审批，通过后价格自动更新

**Independent Test**: 业务经理提交调价申请，老板审批通过，price_accounts 价格自动更新，审批历史可追溯

### Tests for User Story 6

- [ ] T049 [P] [US6] 在 backend/tests/test_api_price_adjustments.py 中创建调价申请 API 测试（正常、价格无效、权限检查）
- [ ] T050 [P] [US6] 在 backend/tests/test_api_price_adjustments.py 中创建审批流程测试（通过、驳回、原子性验证）

### Implementation for User Story 6

- [ ] T051 [P] [US6] 在 backend/app/services/price_adjustment_service.py 中实现 create_adjustment_request 方法（创建申请）
- [ ] T052 [P] [US6] 在 backend/app/services/price_adjustment_service.py 中实现 get_pending_adjustments 方法（待审批列表）
- [ ] T053 [US6] 在 backend/app/services/price_adjustment_service.py 中实现 approve_adjustment 方法（审批通过 + 事务原子性）
- [ ] T054 [US6] 在 backend/app/services/price_adjustment_service.py 中实现 reject_adjustment 方法（审批驳回）
- [ ] T055 [US6] 在 backend/app/api/price_adjustments.py 中实现 POST /api/price-adjustments 端点（role_level >= 5）
- [ ] T056 [US6] 在 backend/app/api/price_adjustments.py 中实现 GET /api/price-adjustments/pending 端点（role_level >= 9）
- [ ] T057 [US6] 在 backend/app/api/price_adjustments.py 中实现 POST /api/price-adjustments/{id}/approve 端点（role_level >= 9）
- [ ] T058 [US6] 在 backend/app/api/price_adjustments.py 中实现 POST /api/price-adjustments/{id}/reject 端点（role_level >= 9）
- [ ] T059 [US6] 在 backend/app/main.py 中注册 price_adjustments 路由
- [ ] T060 [US6] 在审批服务中添加状态机验证（pending → approved/rejected，禁止其他转换）
- [ ] T061 [US6] 在审批服务中添加并发控制（使用行锁防止重复审批）

**Checkpoint**: US6 完成 - 价格调整审批流程完整，原子性保证，审计可追溯

---

## Phase 9: User Story 7 - 价格台账批量查询和筛选 (Priority: P2)

**Goal**: 业务经理和财务查看价格台账，支持按客户、材质、价格区间筛选

**Independent Test**: 查询价格台账，按客户筛选，按材质筛选，按价格区间筛选，分页返回

### Tests for User Story 7

- [ ] T062 [P] [US7] 在 backend/tests/test_api_price_accounts.py 中创建批量查询测试（无筛选、单条件、多条件组合）

### Implementation for User Story 7

- [ ] T063 [US7] 在 backend/app/api/price_accounts.py 中扩展 GET /api/price-accounts 端点，添加筛选参数（customer_id, material, min_price, max_price）
- [ ] T064 [US7] 在 backend/app/api/price_accounts.py 中实现分页逻辑（page, page_size 默认20）
- [ ] T065 [US7] 在 backend/app/api/price_accounts.py 中实现动态 SQL 构建（根据筛选条件组合 WHERE 子句）
- [ ] T066 [US7] 在数据库中添加索引（如不存在）：price_accounts(customer_id), price_accounts(material), price_accounts(current_price)

**Checkpoint**: US7 完成 - 价格台账批量查询功能完整，支持灵活筛选

---

## Phase 10: User Story 8 - 工序字典管理 (Priority: P3)

**Goal**: 超级管理员维护工序字典（新增、修改、停用工序）

**Independent Test**: 管理员新增工序，修改费率，停用工序，验证前端下拉列表变化

### Tests for User Story 8

- [ ] T067 [P] [US8] 在 backend/tests/test_api_treatments.py 中创建工序 CRUD API 测试（新增、修改、停用、权限检查）

### Implementation for User Story 8

- [ ] T068 [P] [US8] 在 backend/app/services/treatment_service.py 中实现 create_treatment 方法
- [ ] T069 [P] [US8] 在 backend/app/services/treatment_service.py 中实现 update_treatment 方法
- [ ] T070 [P] [US8] 在 backend/app/services/treatment_service.py 中实现 deactivate_treatment 方法（is_active = false）
- [ ] T071 [P] [US8] 在 backend/app/services/treatment_service.py 中实现 get_active_treatments 方法（查询激活的工序）
- [ ] T072 [US8] 在 backend/app/api/treatments.py 中实现 GET /api/treatments 端点（role_level >= 1，所有人可查询）
- [ ] T073 [US8] 在 backend/app/api/treatments.py 中实现 POST /api/treatments 端点（role_level >= 10）
- [ ] T074 [US8] 在 backend/app/api/treatments.py 中实现 PUT /api/treatments/{id} 端点（role_level >= 10）
- [ ] T075 [US8] 在 backend/app/api/treatments.py 中实现 PATCH /api/treatments/{id} 停用端点（role_level >= 10）
- [ ] T076 [US8] 在 backend/app/main.py 中注册 treatments 路由
- [ ] T077 [US8] 在工序服务中添加唯一性验证（工序名称不能重复）

**Checkpoint**: US8 完成 - 工序字典管理功能完整

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: 跨用户故事的改进和完善

- [ ] T078 [P] 在 backend/tests/ 中添加单元测试（服务层独立测试，覆盖率目标80%+）
- [ ] T079 [P] 在 backend/tests/test_e2e_price_system.py 中创建端到端测试（完整业务流程验证，参考 quickstart.md）
- [ ] T080 [P] 在 specs/003-price-management-system/ 中更新 API 契约文档（contracts/ 目录，各端点详细说明）
- [ ] T081 运行性能测试（价格历史查询 < 2s，审批操作 < 1s，并发50请求）
- [ ] T082 执行 quickstart.md 中的6个验证场景（数据迁移、价格历史、审批流程、权限验证、性能测试）
- [ ] T083 代码审查和重构（清理重复代码，优化 SQL 查询，统一错误处理）
- [ ] T084 更新 backend/README.md 和 API 文档（新增端点说明，迁移脚本使用方法）
- [ ] T085 生产环境迁移准备（备份脚本、回滚方案、迁移检查清单）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖 - 可立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成 - 阻塞所有用户故事
- **User Stories (Phase 3-10)**: 全部依赖 Foundational 完成
  - US1-US5 为 P1 优先级（MVP核心功能），可并行（如人力充足）或按顺序
  - US6-US7 为 P2 优先级，可在 P1 完成后并行开发
  - US8 为 P3 优先级，最后开发
- **Polish (Phase 11)**: 依赖所有期望的用户故事完成

### User Story Dependencies

- **US1 (查询材料价格历史)**: Phase 2 完成后可开始 - 无其他故事依赖
- **US2 (新增材料价格记录)**: Phase 2 完成后可开始 - 与 US1 配套但独立可测
- **US3 (查询工序价格历史)**: Phase 2 完成后可开始 - 无其他故事依赖
- **US4 (新增工序价格记录)**: Phase 2 完成后可开始 - 与 US3 配套但独立可测
- **US5 (数据迁移)**: Phase 2 完成后可开始 - 独立流程，不阻塞其他故事
- **US6 (审批流程)**: Phase 2 完成后可开始 - 独立功能，不依赖价格历史
- **US7 (批量查询)**: 扩展现有 price_accounts API，Phase 2 完成后可开始
- **US8 (工序字典管理)**: Phase 2 完成后可开始 - 独立管理功能

### Within Each User Story

- 测试先于实现（先写测试，确保失败）
- Models 先于 Services
- Services 先于 API Endpoints
- 核心实现先于集成
- 故事完成后再进入下一优先级

### Parallel Opportunities

- Phase 1: 所有 [P] 标记任务可并行
- Phase 2: 
  - Stage 2.1 中 T005-T007 可并行（不同表的迁移脚本）
  - Stage 2.2 中 T011-T014 可并行（不同模型）
  - Stage 2.3 中 T016-T019 可并行（不同 schema 文件）
- Phase 2 完成后，所有用户故事可并行（如团队人力允许）
- 同一用户故事内，标记 [P] 的任务可并行（如测试、不同模型）

---

## Parallel Example: Foundational Phase

```bash
# Stage 2.1: 并行创建不同表的迁移脚本
Task T005: customer_material_prices 表迁移脚本
Task T006: customer_treatment_prices 表迁移脚本
Task T007: price_adjustments 表迁移脚本

# Stage 2.2: 并行创建不同模型
Task T011: CustomerMaterialPrice 模型
Task T012: CustomerTreatmentPrice 模型
Task T013: TreatmentDict 模型
Task T014: PriceAdjustment 模型

# Stage 2.3: 并行创建不同 schema
Task T016: CustomerMaterialPrice schemas
Task T017: CustomerTreatmentPrice schemas
Task T018: PriceAdjustment schemas
Task T019: TreatmentDict schemas
```

---

## Implementation Strategy

### MVP First (US1-US5 核心功能)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational（关键 - 阻塞所有故事）
3. 完成 Phase 3-7: US1-US5（价格历史查询/记录 + 数据迁移）
4. **STOP and VALIDATE**: 独立测试 US1-US5
5. 部署/演示 MVP

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. US1-US2 → 材料价格历史功能 → 测试 → 部署（子MVP）
3. US3-US4 → 工序价格历史功能 → 测试 → 部署
4. US5 → 数据迁移 → 测试 → 部署（MVP完整）
5. US6 → 审批流程 → 测试 → 部署
6. US7-US8 → 批量查询 + 工序管理 → 测试 → 部署（功能完整）

### Parallel Team Strategy

多开发人员并行：

1. 团队一起完成 Setup + Foundational
2. Foundational 完成后：
   - 开发者 A: US1-US2（材料价格历史）
   - 开发者 B: US3-US4（工序价格历史）
   - 开发者 C: US5（数据迁移）
   - 开发者 D: US6（审批流程）
3. 各故事独立完成并集成

---

## Task Summary

- **总任务数**: 85
- **Setup 任务**: 3
- **Foundational 任务**: 12（关键阻塞点）
- **US1 任务**: 7（查询材料价格历史）
- **US2 任务**: 4（新增材料价格记录）
- **US3 任务**: 4（查询工序价格历史）
- **US4 任务**: 4（新增工序价格记录）
- **US5 任务**: 7（数据迁移）
- **US6 任务**: 13（审批流程 - 最复杂）
- **US7 任务**: 4（批量查询）
- **US8 任务**: 10（工序字典管理）
- **Polish 任务**: 8（测试、文档、性能优化）
- **可并行任务**: 约40个（标记 [P]）

### MVP Scope (建议)

**最小可行产品包含 US1-US5**（Phase 3-7，共26个任务）:
- 材料价格历史查询和记录
- 工序价格历史查询和记录
- 数据迁移（废弃旧表）

这构成完整的价格参考系统基础，业务经理可正常报价并积累历史数据。

审批流程（US6）、批量查询（US7）、工序管理（US8）可在 MVP 后迭代添加。

---

## Notes

- [P] 任务 = 不同文件，无依赖，可并行
- [Story] 标签 = 任务追溯到具体用户故事
- 每个用户故事独立可完成和测试
- 测试优先：实现前先写测试并确保失败
- 每个任务或逻辑组完成后提交
- 在任何检查点停止以独立验证故事
- 避免：模糊任务、同文件冲突、跨故事依赖破坏独立性
- 遵循宪法：asyncpg、SQL聚合、@require_role、审计完整性
