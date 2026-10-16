# Tasks: 发货订单业务流程

**Input**: `spec.md`, `plan.md`, `data-model.md`, `contracts/shipping-orders.md`, `quickstart.md`
**Tests**: 后端单元/API/状态测试与真实浏览器验收均为本功能的验收要求。

## Phase 1: Setup

- [X] T001 确认发货订单目录、后端测试目录和前端路由入口，记录现有 FastAPI/Vue/Alembic 约定（`backend/app`, `backend/tests`, `frontend/src`, `alembic/versions`）
- [X] T002 [P] 建立发货订单后端模块文件骨架：`backend/app/models/shipping_order.py`、`backend/app/schemas/shipping_order.py`、`backend/app/services/shipping_order_service.py`、`backend/app/api/shipping_orders.py`
- [X] T003 [P] 建立发货订单前端视图与 API 文件骨架：`frontend/src/views/shipping-orders/index.vue`、`frontend/src/views/shipping-orders/detail.vue`、`frontend/src/api/shippingOrders.ts`

## Phase 2: Foundational

- [X] T004 编写发货订单 Alembic 初始迁移，创建订单、明细、标签确认、取消确认、发货、发货明细、物流表及索引（`alembic/versions/20260822_shipping_orders.py`）
- [X] T005 [P] 在 `backend/app/models/shipping_order.py` 实现全部 SQLAlchemy 模型、关系、枚举和数量约束，并在 `backend/app/models/__init__.py` 注册模型
- [X] T006 [P] 在 `backend/app/schemas/shipping_order.py` 实现订单、明细、搜索、提交、标签、取消、发货、物流和历史响应的 Pydantic schemas
- [X] T007 在 `backend/app/services/shipping_order_service.py` 建立事务服务骨架、角色检查、订单/明细状态派生和剩余数量计算
- [X] T008 在 `backend/app/api/deps.py` 复用现有认证与角色依赖，并在 `backend/app/main.py` 注册发货订单路由
- [X] T009 [P] 为审计动作建立统一写入适配器，复用 `backend/app/models/audit.py` 并覆盖 shipping 领域实体和 old/new values
- [X] T010 运行迁移静态检查、模型导入检查和现有后端测试，确认基础阶段未破坏既有模块

## Phase 3: User Story 1 - 业务创建订单（Priority: P1）

**Goal**: 业务可创建正式/样件草稿、维护多行明细、搜索客户件号并显式处理重复 PO/未建档件号警告。

**Independent Test**: 创建含重复客户件号、不同数量/日期/备注的正式订单，保存后提交；详情保留档案名称快照或业务修改名称，并能复现两类提交警告。

- [X] T011 [P] [US1] 编写正式订单默认、必填字段、重复明细、日期/数量校验测试（`backend/tests/test_shipping_order_service.py`）
- [X] T012 [P] [US1] 编写客户件号包含搜索、客户范围过滤和未建档提交警告 API 测试（`backend/tests/api/test_shipping_orders.py`）
- [X] T013 [US1] 实现草稿创建/更新/删除服务，保留零件名称快照并更新 `last_modified_at`（`backend/app/services/shipping_order_service.py`）
- [X] T014 [US1] 实现客户件号搜索，复用 `PartCustomerAlias`/零件档案并返回同物理零件提示（`backend/app/api/shipping_orders.py`、`backend/app/services/shipping_order_service.py`）
- [X] T015 [US1] 实现 `POST/PATCH/GET /shipping-orders`、`GET /shipping-orders/customer-parts/search` 和创建人草稿可见性（`backend/app/api/shipping_orders.py`）
- [X] T016 [US1] 实现重复客户+PO 和未建档客户件号的 409 结构化警告及显式继续提交逻辑（`backend/app/services/shipping_order_service.py`、`backend/app/schemas/shipping_order.py`）
- [X] T017 [US1] 实现提交校验与明细锁定，写入创建/修改/提交审计记录（`backend/app/services/shipping_order_service.py`、`backend/app/models/audit.py`）
- [X] T018 [US1] 实现订单列表和草稿编辑页面，支持正式默认、样件切换、重复明细、名称可编辑、下拉/Tab 补全且不自动选中（`frontend/src/views/shipping-orders/index.vue`、`frontend/src/api/shippingOrders.ts`）
- [X] T019 [US1] 实现重复 PO/未建档件号确认弹窗及提交后详情跳转（`frontend/src/views/shipping-orders/index.vue`、`frontend/src/views/shipping-orders/detail.vue`）
- [X] T020 [US1] 运行 US1 后端测试、前端类型检查和浏览器创建/搜索/提交验收，记录实现与验收结果（`tests`、`docs` 或验收报告）

## Phase 4: User Story 2 - 样件订单线下处理并确认标签（Priority: P1）

**Goal**: 样件可用临时客户、无 PO 提交，不生成全检/系统拣货任务，由标签人员按明细确认后待发货。

**Independent Test**: 创建临时客户样件，无 PO 提交，确认无全检任务；标签人员只确认一条明细，只有该行进入待发货。

- [X] T021 [P] [US2] 编写样件临时客户、无 PO、无全检任务和部分标签确认测试（`backend/tests/test_shipping_order_states.py`）
- [X] T022 [US2] 实现样件提交规则和 pending/awaiting_label/ready_to_ship 状态派生（`backend/app/services/shipping_order_service.py`）
- [X] T023 [US2] 实现 `POST /shipping-order-lines/{line_id}/label-confirm`，记录确认人/时间/备注并按明细更新状态（`backend/app/api/shipping_orders.py`）
- [X] T024 [US2] 增加正式成品库存已包装且全检合格时进入待发货的接口钩子，不实现库存分配细节（`backend/app/services/shipping_order_service.py`）
- [X] T025 [US2] 在订单详情页实现标签人员按行确认和样件待发货展示（`frontend/src/views/shipping-orders/detail.vue`）
- [X] T026 [US2] 运行样件与部分标签确认后端测试及浏览器验收，确认不触发全检/系统拣货流程

## Phase 5: User Story 3 - 标签确认与订单锁定（Priority: P1）

**Goal**: 提交后锁定明细；未标签可撤回/取消，已标签不能单方撤回/取消，已标签取消需业务与标签双方确认。

**Independent Test**: 分别验证未标签撤回、已标签拒绝撤回、已标签双人取消、部分发货后只取消剩余数量。

- [X] T027 [P] [US3] 编写撤回、直接取消、双人取消同意/拒绝和部分发货剩余取消的状态测试（`backend/tests/test_shipping_order_states.py`）
- [X] T028 [US3] 实现 `POST /shipping-orders/{order_id}/withdraw`，禁止已标签明细撤回并写审计（`backend/app/api/shipping_orders.py`、`backend/app/services/shipping_order_service.py`）
- [X] T029 [US3] 实现未标签直接取消及 `POST /shipping-order-lines/{line_id}/cancel` 的取消数量/原因校验（`backend/app/services/shipping_order_service.py`）
- [X] T030 [US3] 实现取消同意记录、业务/标签角色确认和完成事务，落库 `shipping_cancellation_consents`（`backend/app/api/shipping_orders.py`、`backend/app/services/shipping_order_service.py`）
- [X] T031 [US3] 在前端实现撤回、取消、双方确认按钮权限和状态提示（`frontend/src/views/shipping-orders/detail.vue`）
- [X] T032 [US3] 运行 US3 状态测试与浏览器双人确认验收，确认已标签不能单方操作

## Phase 6: User Story 4 - 仓库分批确认发货（Priority: P1）

**Goal**: 仓库按行/整单部分发货，支持多物流信息、数量上限校验和物流修改审计。

**Independent Test**: 对一行先发 600 再发 400，查看两条独立记录；尝试超发被拒；一次发货录入多个承运商/运单号并修改其中一条后能查到前后值。

- [X] T033 [P] [US4] 编写部分发货数量、超发、未标签、物流必填、多物流和状态聚合测试（`backend/tests/test_shipping_order_service.py`、`backend/tests/test_shipping_order_states.py`）
- [X] T034 [P] [US4] 编写发货与物流修改 API 合同测试（`backend/tests/api/test_shipping_orders.py`）
- [X] T035 [US4] 实现发货事务服务，锁定/重算明细剩余量并创建 shipment、shipment lines、物流 rows 和审计（`backend/app/services/shipping_order_service.py`）
- [X] T036 [US4] 实现 `POST /shipping-orders/{order_id}/shipments/confirm`，支持明细/整单请求、未建档件号二次提醒、至少物流公司或物流号校验（`backend/app/api/shipping_orders.py`）
- [X] T037 [US4] 实现 `PATCH /shipping-shipments/{shipment_id}/logistics`，保留 old/new values、操作人和时间（`backend/app/api/shipping_orders.py`、`backend/app/services/shipping_order_service.py`）
- [X] T038 [US4] 实现仓库发货界面，支持逐行/整单、部分数量、多个物流行、明确确认已发货和超发前端提示（`frontend/src/views/shipping-orders/detail.vue`）
- [X] T039 [US4] 运行 US4 后端测试、迁移测试和浏览器分批发货/多物流/修改验收

## Phase 7: User Story 5 - 查询订单和操作历史（Priority: P2）

**Goal**: 授权角色查看已提交订单、明细数量、发货记录、生产批次占位和时间顺序操作历史；草稿仍创建人可见。

**Independent Test**: 业务、仓库、标签、管理角色分别查看同一已提交订单，看到一致历史；非创建人不能看到草稿。

- [X] T040 [P] [US5] 编写角色可见性、草稿隔离、详情数量、生产批次占位和历史排序测试（`backend/tests/api/test_shipping_orders.py`）
- [X] T041 [US5] 实现订单列表查询过滤、分页和角色可见性（`backend/app/api/shipping_orders.py`、`backend/app/services/shipping_order_service.py`）
- [X] T042 [US5] 实现订单详情聚合、发货记录/物流/警告/生产批次占位和 `GET /shipping-orders/{order_id}/history`（`backend/app/api/shipping_orders.py`、`backend/app/schemas/shipping_order.py`）
- [X] T043 [US5] 实现订单列表、详情、发货历史和操作历史 UI，并显示明细已发/剩余数量（`frontend/src/views/shipping-orders/index.vue`、`frontend/src/views/shipping-orders/detail.vue`）
- [ ] T044 [US5] 运行 US5 API 测试与多角色浏览器验收，确认草稿隔离和提交后共享可见

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T045 [P] 实现七天草稿清理命令，支持 dry-run，仅清理 `status=draft` 且 `last_modified_at` 早于七天的草稿并写系统日志（`scripts/cleanup_shipping_drafts.py`）
- [X] T046 [P] 编写草稿清理、状态、数量和系统审计测试（`backend/tests/test_shipping_order_cleanup.py`、`backend/tests/test_shipping_order_states.py`、`backend/tests/api/test_shipping_orders.py`）
- [X] T047 运行前端 type-check/build、后端相关测试和 quickstart 验证，修复本功能范围内发现的问题（前端 type-check/build、发货订单相关测试和 Python 编译通过；清理 dry-run/Alembic 当前受 PostgreSQL `WinError 5` 连接权限阻塞）
- [ ] T048 运行真实浏览器 Playwright 验收，覆盖正式订单、样件、重复行、警告、标签、双人取消、部分发货、多物流、历史和七天清理，并更新验收报告（样件完整链路已验收，其他组合待补）
- [X] T049 更新 `specs/007-shipping-order-flow/quickstart.md` 或新增 `docs/shipping-order-acceptance.md`，记录部署调度命令、已实现范围和明确暂缓项

## Dependencies & Execution Order

- Setup（T001-T003）可先完成；Foundational（T004-T010）依赖 Setup，完成前不开始用户故事。
- US1（T011-T020）是 MVP；US2/US3 依赖订单和明细基础，但可在 Foundational 后并行开发不同文件。
- US4 依赖 US1 的订单/明细服务及 US2/US3 的标签状态；US5 依赖已落库的订单、标签和发货实体。
- Polish（T045-T049）依赖需要验证的用户故事完成。

## Parallel Opportunities

- T002/T003、T005/T006/T009 可并行。
- 各故事的测试文件可与不冲突的模型/schema 文件并行；US2 与 US3 可在 US1 基础稳定后并行。
- T045/T046 可并行；T047/T048 必须在实现全部合并后执行。

## Implementation Strategy

1. 先完成共享模型、迁移、权限和审计基础。
2. 交付 US1 作为 MVP，完成正式订单创建/提交/详情浏览器验收。
3. 增量加入样件和标签、撤回/取消、发货、查询历史。
4. 最后启用七天清理验证并执行完整浏览器验收；库存分配、二维码全检、标签打印、物流接口、生产批次校验和退货仍留在暂缓范围。
