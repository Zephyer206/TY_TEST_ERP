# Tasks: gaibo 售后统一档案

**Input**: Design documents from `/specs/005-gaibo-after-sales/`

**Implementation rule**: 页面中展示的业务字段必须可在详情编辑并保存；系统审计时间、数据库主键和自动生成的来源元数据为只读。所有成功写操作必须产生修改历史。

## Phase 1: Setup

- [x] T001 Confirm current Alembic head, legacy after-sales row counts, and API/frontend baselines in `backend/scripts/verify_after_sales_gaibo.py`
- [ ] T002 [P] Add gaibo migration/import verification fixtures in `backend/tests/test_after_sales_migration.py`
- [x] T003 [P] Document feature branch and migration observation rules in `specs/005-gaibo-after-sales/quickstart.md`

## Phase 2: Foundational

- [x] T004 Create gaibo tables, foreign keys, check constraints, indexes, and reversible migration in `alembic/versions/*_gaibo_after_sales.py`
- [x] T005 [P] Add SQLAlchemy gaibo entities and relationships in `backend/app/models/gaibo.py`
- [x] T006 [P] Add Pydantic request/response schemas for workspaces, single parts, requirements, packages, documents, routes, and history in `backend/app/schemas/gaibo.py`
- [x] T007 Add gaibo service transaction helpers, field validation, soft-deactivation, and audit recording in `backend/app/services/after_sales_service.py`
- [x] T008 Add role capability mapping and route dependencies for after-sales permissions in `backend/app/api/after_sales.py` and `backend/app/api/gaibo_after_sales.py`
- [x] T009 [P] Add migration import and old/new comparison scripts in `backend/scripts/import_after_sales_gaibo.py` and `backend/scripts/verify_after_sales_gaibo.py`
- [ ] T009a [P] Require an explicit customer/workspace target for installation-package imports; validate the source batch customer scope, isolate unknown or mixed-customer rows, and preserve the current ZF Mexico batch boundary.
- [ ] T009b [P] Add company ownership and capability checks: classify workspaces under Tianyue or Gaibo, keep current `parts` data Tianyue-owned, and reject installation-package routes/imports for Tianyue workspaces.

## Phase 3: User Story 1 - 按客户查看售后档案 (Priority: P1)

**Goal**: 以客户为入口展示单件和安装包，使用同一页面结构并支持筛选。

**Independent Test**: 两个客户各有单件/安装包时，客户页面只显示自身数据，可切换类型和状态筛选。

- [x] T010 [US1] Add workspace list/detail and customer record query endpoints in `backend/app/api/gaibo_after_sales.py`
- [ ] T011 [US1] Add customer workspace and record list views in `frontend/src/views/after-sales/index.vue` and `frontend/src/views/after-sales/customer.vue`
- [ ] T011a [US1] Return and display the resolved customer identity for installation packages in list/detail/search responses; derive it from the bound workspace and reject conflicting client-supplied customer values.
- [ ] T011b [US1] Add company-first navigation and capability-aware views: Tianyue shows customer single parts only; Gaibo shows customer single parts plus installation packages.
- [ ] T012 [US1] Add reusable dense record table, filters, loading, empty, and error states in `frontend/src/components/after-sales/RecordSearch.vue`
- [x] T013 [US1] Register customer-first after-sales routes without adding unapproved business menu entries in `frontend/src/router/index.ts` and `frontend/src/views/layout/index.vue`
- [ ] T014 [US1] Add API integration tests for workspace isolation and record-type filtering in `backend/tests/test_after_sales_workspaces.py`

## Phase 4: User Story 2 - 全局售后查询 (Priority: P1)

**Goal**: 跨客户搜索单件和安装包，结果显示客户、类型和四个核心字段。

**Independent Test**: 使用 IBI、客户件号和天越内部组成搜索，能跨客户返回准确记录并按类型筛选。

- [ ] T015 [P] [US2] Add global search contract tests in `backend/tests/test_after_sales_search.py`
- [x] T016 [US2] Implement SQL-backed global search with pagination and status filters in `backend/app/api/gaibo_after_sales.py`
- [x] T017 [US2] Expose global search endpoint and response mapping in `backend/app/api/gaibo_after_sales.py`
- [x] T018 [US2] Connect global search UI and result navigation in `frontend/src/views/after-sales/index.vue`
- [ ] T019 [US2] Verify search performance and cross-customer result labeling in `backend/tests/test_after_sales_search.py`

## Phase 5: User Story 3 - 在统一零件中维护售后要求 (Priority: P1)

**Goal**: 以经确认的物理零件 `parts.id` 作为可共享身份；天越和盖博可用不同客户件号关联同一零件，但别名、价格、图纸和工艺按公司/客户隔离；禁止静默跨公司合并。

**Independent Test**: 同一单件建立客户 A/B 需求，分别修改价格、图纸和工艺，双方详情保持隔离。

- [ ] T020 [P] [US3] Add single-part and customer-requirement CRUD contract tests in `backend/tests/test_after_sales_single_parts.py`
- [ ] T021 [US3] Implement company/customer-scoped requirement CRUD keyed by confirmed `part_id`, with explicit cross-company sharing approval, identity validation, and audit, in `backend/app/services/after_sales_service.py`
- [ ] T021a [US3] Audit `part_customer_aliases` and add/confirm company scope so different Tianyue/Gaibo customer part numbers can point to one `part_id` without overwriting aliases.
- [x] T022 [US3] Expose single-part library and requirement endpoints in `backend/app/api/gaibo_after_sales.py`
- [ ] T023 [US3] Build an after-sales view over unified parts and its customer-requirement editor in `frontend/src/views/after-sales/single-parts.vue` and `frontend/src/components/after-sales/RecordDossier.vue`; do not create a second part master
- [ ] T024 [US3] Add customer-isolation integration tests for prices, drawings, and processes in `backend/tests/test_after_sales_customer_isolation.py`

## Phase 6: User Story 4 - 管理安装包及其单件组成 (Priority: P1)

**Goal**: 安装包引用单件或暂存未建档组成，所有展示的组成业务字段都可编辑。

**Independent Test**: 安装包包含已关联和未关联组成，数量、顺序、IBI、内部组成、状态和备注均可保存。

- [ ] T025 [P] [US4] Add package/item CRUD and validation tests in `backend/tests/test_after_sales_packages.py`
- [ ] T026 [US4] Implement package and package-item services with linked/unlinked state checks in `backend/app/services/after_sales_service.py`
- [x] T027 [US4] Expose package/item endpoints and detail response in `backend/app/api/gaibo_after_sales.py`
- [ ] T028 [US4] Replace FMG-only detail editing with editable package dossier in `frontend/src/views/after-sales/package-detail.vue`
- [ ] T029 [US4] Add editable component rows, status controls, and unsaved-change protection in `frontend/src/components/after-sales/RecordDossier.vue`
- [ ] T030 [US4] Verify every displayed package business field has a detail editor and audit entry in `frontend/src/tests/after-sales/package-edit.spec.ts`

## Phase 7: User Story 5 - 查看和维护客户图纸及工艺 (Priority: P1)

**Goal**: 客户单件详情中可查看和编辑图纸版本、工艺路线、步骤及参数，客户之间完全隔离。

**Independent Test**: 客户 A/B 同一单件分别保存不同路线和图纸，详情只显示当前客户版本。

- [ ] T031 [P] [US5] Add drawing/process/document contract tests in `backend/tests/test_after_sales_documents_process.py`
- [ ] T032 [US5] Implement drawing versions, process routes/steps, and current-version transaction rules in `backend/app/services/after_sales_service.py`
- [ ] T033 [US5] Expose drawing, process-route, and document-status endpoints in `backend/app/api/after_sales.py`
- [ ] T034 [US5] Add editable drawing and process sections with version controls in `frontend/src/components/after-sales/ProcessRouteEditor.vue` and `frontend/src/components/after-sales/RecordDossier.vue`
- [ ] T035 [US5] Add customer-specific document status/date/remark editors and status validation in `frontend/src/components/after-sales/RecordDossier.vue`

## Phase 8: User Story 6 - 编辑核心信息并保留追溯 (Priority: P1)

**Goal**: 详情页编辑所有业务显示字段，成功保存记录操作者、时间、旧值和新值。

**Independent Test**: 修改客户字段、组成、价格、图纸、工艺、状态和备注，逐项在历史中看到前后值；取消编辑不产生记录。

- [ ] T036 [P] [US6] Add audit-history API and immutable-history tests in `backend/tests/test_after_sales_history.py`
- [ ] T037 [US6] Add unified change-log writes to every gaibo mutation service in `backend/app/services/after_sales_service.py`
- [ ] T038 [US6] Expose history filtering endpoint with actor and before/after values in `backend/app/api/after_sales.py`
- [x] T039 [US6] Add change history panel and field-level save feedback in `frontend/src/views/after-sales/index.vue`
- [ ] T040 [US6] Add keyboard, focus, validation, and unsaved-change browser acceptance in `frontend/src/tests/after-sales/editability.spec.ts`

## Phase 9: Polish and Cross-Cutting Validation

- [ ] T041 [P] Add API permission matrix tests in `backend/tests/test_after_sales_permissions.py`
- [ ] T042 [P] Add frontend type-check/build and responsive layout checks in `frontend/src/tests/after-sales`
- [ ] T043 Run migration comparison and quickstart validation in `backend/scripts/verify_after_sales_gaibo.py`
- [ ] T044 Run real browser acceptance on desktop and mobile viewport and record results in `BROWSER_ACCEPTANCE_TEST_REPORT.md`
- [ ] T045 Update `.github/copilot-instructions.md` managed context and mark completed tasks in this file

> 验收记录（2026-08-18）：本地前端 `http://127.0.0.1:5173` 可访问，浏览器已实际加载登录页并提交 `admin` 登录；后端登录接口因远程 PostgreSQL `124.222.29.229:5432` 与 SSH `22` 均不可达而返回服务器错误，未进入数据页，因此 T044 保持未完成，不能宣称详情编辑验收通过。

## Dependencies and Execution Order

- Phase 1 has no feature dependency; T001 is the baseline gate.
- Phase 2 depends on T001 and blocks all user stories.
- US1 and US2 depend on the foundational workspace/query resources; US2 may begin after T007/T008.
- US3 depends on the foundational models and can proceed with US1/US2 once shared API registration is stable.
- US4 depends on US3 requirement identifiers for linked package items.
- US5 depends on US3 customer requirements; US6 depends on all mutation endpoints from US3-US5.
- Phase 9 depends on the completed stories and migration comparison.

## Parallel Opportunities

- T002, T003, T005, T006, and T009 can run in parallel after the baseline.
- T015, T020, T025, T031, and T036 are independent test suites once shared fixtures exist.
- Frontend component work can proceed in parallel with backend tests when API response shapes are frozen.

## Implementation Strategy

1. Complete baseline and gaibo schema/migration without deleting legacy tables.
2. Deliver US1 + US2 as the first usable customer-first query surface.
3. Deliver US3 + US4 for single-part and package editing; verify every displayed business field is editable.
4. Add customer-specific drawings/processes and unified audit history.
5. Run API, build, migration, and real-browser acceptance; only then plan legacy endpoint/table retirement separately.
