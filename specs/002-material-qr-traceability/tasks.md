# Tasks: 原材料与产品框二维码追溯扩展

**生成日期**：2026-10-22；依据 spec.md、plan.md、data-model.md、contracts/。

旧版30项仅见 [tasks-material-legacy.md](./tasks-material-legacy.md)。新版任务单独验收，历史勾选不计入本清单。测试由计划要求，先写拒绝/并发用例再实现业务；前端任务必须有真实浏览器证据。任务中的路径相对仓库根目录。

当前累计37/59项：完成事务/权限基础、材料回归、32旧端点登记、池/打印/绑定、机台生产，以及固定路线连续流转、材料来源、工艺追溯和同单/跨单拆框的实现及实际浏览器验收；系统/实物打印、异常/通知及后续流程保持待办。每项仅按独立证据勾选，不替代故事或上线验收。

## Setup（计划Phase 0收尾）

**独立验收**：设计完整、任务可执行；不把默认值记成业务回答。

- [x] T001 关闭订单、权限、打印及31个端点合同差异，记录设计基准与上线配置边界；验证脚本覆盖文档一致性：`specs/002-material-qr-traceability/phase0-closeout.md`（FR-001～FR-033；SC-001～SC-010）。
- [x] T002 保留原材料旧任务并生成新版任务和只读覆盖分析：`specs/002-material-qr-traceability/tasks.md`（FR-001～FR-033；SC-001～SC-010）。
- [x] T003 提供独立测试库工厂，随机专用数据库、拒绝业务库写入、仅清理本次创建库且输出脱敏：`backend/tests/qr/conftest.py`（FR-030）。

## Foundational（计划Phase 1数据结构）

**独立验收**：PostgreSQL真实迁移升级→空库降级→重升；结构、外键、CHECK及旧QR兼容通过。

- [x] T004 建立订单/版本路线/产品配置、机台工艺状态/用户上下文和数量来源ORM：`backend/app/models/product_box.py`（FR-008 FR-009 FR-011 FR-024 FR-032）。
- [x] T005 建立二维码池、产品框、关系、事件、异常和转换ORM，主/复合FK及非负/状态约束：`backend/app/models/product_box.py`（FR-004 FR-006 FR-019 FR-021 FR-027 FR-031 FR-033）。
- [x] T006 建立授权集合/授权历史、打印作业项/确认、幂等、收件组、outbox/站内通知/尝试ORM：`backend/app/models/product_box.py`（FR-005 FR-010 FR-023 FR-030 FR-031）。
- [x] T007 注册ORM并增量扩展PFB扫码类型/新操作，创建自包含Alembic迁移及身份/审计不可变保护：`alembic/versions/20261022_product_box_foundation.py`（FR-004 FR-006 FR-007 FR-030）。
- [x] T008 执行测试库迁移、回滚、约束及旧QR读写回归；验证有业务数据时拒绝破坏性降级：`backend/tests/qr/test_foundation.py`（FR-001 FR-002 FR-006 FR-008 FR-021 FR-030）。
- [x] T009 实现服务层一致锁序、持久化幂等/版本冲突和安全错误响应：`backend/app/services/product_box_service.py`（FR-006 FR-013 FR-014 FR-021 FR-030 FR-032 FR-033）。
- [x] T010 实现部门/等级/能力/订单可见性联合权限和配置维护服务，拒绝缺配置：`backend/app/services/qr_permission_service.py`（FR-010 FR-015 FR-023 FR-024 FR-030）。

## US1 原材料回归（P1）

**独立验收**：独立物料100kg分30+20余50，身份/父子/审计守恒；原有机台和工艺卡无回归。

- [x] T011 [US1] 补入库/IQC/分卷/母子扫码/补打/消耗审计与角色回归，使用隔离夹具：`backend/tests/qr/test_material_baseline.py`（FR-001 FR-002；SC-001）。
- [x] T012 [US1] 将基线32个QR端点按当前实际路由补登记并增加domain wrapper/类型映射，不删除旧接口：`shared/api/registry.js`（FR-001 FR-002 FR-003）。
- [x] T013 [US1] 修复基线回归发现的身份/数量/操作者问题，保持旧响应合同：`backend/app/services/material_batch_service.py`（FR-001 FR-002 FR-030）。
- [x] T014 [US1] 实际浏览器验证入库/分卷/台账及旧日期补打，记录会话/URL/观察结果：`specs/002-material-qr-traceability/acceptance-material.md`（FR-001 FR-002；SC-001）。

## US2 二维码池与一框绑定MVP（P1，计划Phase 2/6）

**独立验收**：500项唯一；池外/重复/二订单100%拒绝；补打不变码；真实浏览器绑定≤2分钟。

- [x] T015 [US2] 先写池外/伪造payload/并发绑定/幂等和取消打印不计数合同测试：`backend/tests/qr/test_pool_binding.py`（FR-004 FR-005 FR-006 FR-007 FR-008；SC-002 SC-005）。
- [x] T016 [US2] 实现稳定PFB/v1身份生成/解析、批量上限、池查询与一次绑定事务：`backend/app/services/product_box_service.py`（FR-004 FR-006 FR-007 FR-008 FR-024）。
- [x] T017 [US2] 实现A4打印数据/作业项快照/补打与申请人确认服务：`backend/app/services/qr_print_service.py`（FR-005；SC-002）。
- [x] T018 [US2] 实现池/绑定/打印/扫描schema与路由并挂载，依权限检查；先登记registry：`backend/app/api/product_boxes.py`（FR-004 FR-005 FR-006 FR-007 FR-008）。
- [x] T019 [US2] 实现domain wrapper、registry类型桥接和请求/响应类型：`frontend/src/api/productBoxes.ts`（FR-004 FR-005 FR-006 FR-007）。
- [x] T020 [US2] 实现二维码池/绑定/补打/元数据前端工作区与A4打印样式：`frontend/src/views/product-box-qr/index.vue`（FR-004 FR-005 FR-007 FR-020）。
- [ ] T021 [US2] 执行真实浏览器500项/重复/池外/取消打印/绑定与标签实物扫码，单列未完成证据：`specs/002-material-qr-traceability/acceptance-pool.md`（FR-004 FR-005 FR-006 FR-007 FR-008；SC-002 SC-005）。

## US3 机台生产与数量（P1，计划Phase 3/6）

**独立验收**：多机上下文独立；30→25显示25；过期版本409；完成后工人拒改，主管更正留痕；80分70+10。

- [x] T022 [US3] 先写机台票据/选单/过期/跨用户、覆盖数量、差异完成、更正和并发分配测试：`backend/tests/qr/test_production.py`（FR-003 FR-010 FR-011 FR-012 FR-013 FR-014 FR-015 FR-016 FR-032；SC-006 SC-010）。
- [x] T023 [US3] 实现订单/主配对件/单机目标与版本路线配置，真实缺配置拒绝：`backend/app/services/product_order_service.py`（FR-003 FR-011 FR-024 FR-032）。
- [x] T024 [US3] 实现当前账号票据/30分钟上下文/机台订单状态、再扫完成意向和有效分配核验：`backend/app/services/product_production_service.py`（FR-003 FR-010 FR-011 FR-012）。
- [x] T025 [US3] 实现数量覆盖、首次来源分配、并发剩余需求锁和主管历史更正：`backend/app/services/product_production_service.py`（FR-013 FR-014 FR-015 FR-016 FR-032）。
- [x] T026 [US3] 登记配置/选单/数量/完成/更正/分配registry，同步路由、schema、wrapper和类型：`backend/app/api/product_boxes.py`（FR-003 FR-011 FR-012 FR-013 FR-015 FR-032）。
- [x] T027 [US3] 实现机台→订单→框→数量/差异确认/授权分配与冲突重读交互：`frontend/src/views/product-box-qr/production.vue`（FR-011 FR-012 FR-014 FR-015 FR-016 FR-032）。
- [x] T028 [US3] 真实浏览器验证多机、多单、覆盖、完成、更正、普通工/其他订单拒绝和分配场景：`specs/002-material-qr-traceability/acceptance-production.md`（FR-010 FR-011 FR-012 FR-013 FR-014 FR-015 FR-016 FR-032；SC-006 SC-010）。

## US4 连续工艺与查询（P1，计划Phase 3/6）

**独立验收**：同QR跨合法步骤且历史完整；完成机台后继续；原料可反查，扫码≤3秒、追溯≤5分钟。

- [x] T029 [US4] 先写路线推进/非法跳步/已完成后续流转/来源不重复和反向追溯测试：`backend/tests/qr/test_process_trace.py`（FR-009 FR-017 FR-029；SC-003 SC-004）。
- [x] T030 [US4] 实现下一工艺推进、数量入出快照、原材料来源及分页事件查询：`backend/app/services/product_process_service.py`（FR-009 FR-017 FR-029）。
- [x] T031 [US4] 登记推进/trace/events端点并同步schema、wrapper、类型：`backend/app/api/product_boxes.py`（FR-009 FR-017 FR-029）。
- [x] T032 [US4] 实现工艺推进/当前框/事件及原材料反查详情：`frontend/src/components/product-box-qr/TraceDetail.vue`（FR-009 FR-017 FR-029）。
- [x] T033 [US4] 真实浏览器验证同QR多工艺及原材料反查并记录响应/操作时限：`specs/002-material-qr-traceability/acceptance-trace.md`（FR-009 FR-017 FR-029；SC-003 SC-004）。

## US5 拆框与父子追溯（P1，计划Phase 4/6）

**独立验收**：父100拆30→70/30；用途守恒；超量/池外/并发失败不变；跨单需求校验。

- [x] T034 [US5] 先写同单/跨单/用途/零余量/超量/并发和下游事实拒绝测试：`backend/tests/qr/test_split.py`（FR-008 FR-018 FR-019 FR-020 FR-021；SC-007）。
- [x] T035 [US5] 实现父子/订单需求/池项/来源分配同事务拆框及关系和快照：`backend/app/services/product_split_service.py`（FR-008 FR-018 FR-019 FR-020 FR-021）。
- [x] T036 [US5] 登记拆框及元数据端点，同步schema、wrapper、类型和权限反例：`backend/app/api/product_boxes.py`（FR-018 FR-019 FR-020 FR-021）。
- [x] T037 [US5] 实现扫父→扫子→数量/用途/目标单的拆框交互和父子追溯：`frontend/src/components/product-box-qr/SplitBoxDialog.vue`（FR-018 FR-019 FR-020 FR-021）。
- [x] T038 [US5] 真实浏览器验证父子数量守恒、余量继续流转及权限/边界拒绝：`specs/002-material-qr-traceability/acceptance-split.md`（FR-008 FR-018 FR-019 FR-020 FR-021；SC-007）。

## US6 规格异常与通知（P1，计划Phase 5/6）

**独立验收**：不匹配留痕并通知两组；单人确认；暂停仅对应state；失败按时重试且不改变业务状态。

- [ ] T039 [US6] 先写匹配/异常/缺收件组/确认竞争/暂停恢复及退避去重测试：`backend/tests/qr/test_exceptions_notifications.py`（FR-022 FR-023 FR-031；SC-008）。
- [ ] T040 [US6] 实现服务端规格比较、异常确认/恢复、范围阻断和配置补齐回补：`backend/app/services/product_box_service.py`（FR-022 FR-023 FR-031）。
- [ ] T041 [US6] 实现outbox工作器、站内待办、60秒目标、五次尝试和1/5/15/30退避及人工批次重试：`backend/app/services/notification_service.py`（FR-023 FR-031；SC-008）。
- [ ] T042 [US6] 登记异常/恢复/通知/管理重试端点，同步schema、wrapper与类型：`backend/app/api/product_boxes.py`（FR-022 FR-023 FR-031）。
- [ ] T043 [US6] 实现异常处理/恢复/通知与失败提示界面，确认和投递状态分列：`frontend/src/components/product-box-qr/ExceptionPanel.vue`（FR-022 FR-023 FR-031）。
- [ ] T044 [US6] 真实浏览器核验不匹配继续生产、任一负责人确认、暂停/恢复和通知故障：`specs/002-material-qr-traceability/acceptance-exceptions.md`（FR-022 FR-023 FR-031；SC-008）。

## US7 B/C转换（P1，计划Phase 5/6）

**独立验收**：100全转保留码；部分30→父B70/子C30；未确认/取消不变，失败整体回滚。

- [ ] T045 [US7] 先写B↔C全量/部分/实际数量/预授权/确认取消竞争测试：`backend/tests/qr/test_conversion.py`（FR-024 FR-025 FR-026 FR-027 FR-028 FR-033；SC-009）。
- [ ] T046 [US7] 实现显式目标路线/授权、人工发起与差异步骤内部触发，禁止客户端自授预授权：`backend/app/services/product_box_service.py`（FR-024 FR-025 FR-028）。
- [ ] T047 [US7] 实现操作工上下文确认、全量保码、部分拆框及用途/来源分割和取消事务：`backend/app/services/product_box_service.py`（FR-026 FR-027 FR-033）。
- [ ] T048 [US7] 登记转换创建/确认/取消，同步schema、wrapper、类型和状态响应：`backend/app/api/product_boxes.py`（FR-025 FR-026 FR-027 FR-028 FR-033）。
- [ ] T049 [US7] 实现实际完成数量确认/子码/取消交互，管理账号不能代理实物确认：`frontend/src/components/product-box-qr/ConversionDialog.vue`（FR-025 FR-026 FR-027 FR-028 FR-033）。
- [ ] T050 [US7] 真实浏览器验证两向全量/部分及未确认/取消/无上下文/池外拒绝：`specs/002-material-qr-traceability/acceptance-conversion.md`（FR-024 FR-025 FR-026 FR-027 FR-028 FR-033；SC-009）。

## US8 权限与审计（P2，计划Phase 6/7）

**独立验收**：操作人来自登录；拒绝跨单/错部门/缺能力；所有关键动作可查询，管理级别不代理确认。

- [ ] T051 [US8] 以隔离明确身份写角色/部门/能力/订单/上下文矩阵及历史不可变测试：`backend/tests/qr/test_permissions_audit.py`（FR-010 FR-015 FR-023 FR-030）。
- [ ] T052 [US8] 实现能力集合版本维护、授权撤销历史及全链路安全审计查询：`backend/app/services/qr_permission_service.py`（FR-010 FR-029 FR-030）。
- [ ] T053 [US8] 登记授权管理端点，同步schema/wrapper/类型；禁止日志记录票据/凭据/原始未知扫码：`backend/app/api/product_boxes.py`（FR-010 FR-029 FR-030）。
- [ ] T054 [US8] 实现授权配置和审计查询，权限不足界面清晰可理解：`frontend/src/views/product-box-qr/settings.vue`（FR-010 FR-029 FR-030）。
- [ ] T055 [US8] 真实浏览器用多角色验证允许/拒绝及操作者/时间/前后值：`specs/002-material-qr-traceability/acceptance-permissions.md`（FR-010 FR-015 FR-023 FR-029 FR-030）。

## 联调与上线准备（计划Phase 7）

**独立验收**：33项FR/10项SC有独立证据；配置、备份、回归、性能及现场扫码通过才可上线。

- [ ] T056 执行新增API使用扫描/类型检查/构建，记录既有迁移债务与新增零违规：`specs/002-material-qr-traceability/acceptance-release.md`（FR-001～FR-033）。
- [ ] T057 执行全链路/并发/权限/性能/原材料回归和迁移备份恢复演练：`backend/tests/qr/test_end_to_end.py`（FR-001～FR-033；SC-001～SC-010）。
- [ ] T058 配置真实工艺/差异步骤/左右件目标量/负责人/授权账号并关闭认证绕过，逐项验收：`specs/002-material-qr-traceability/acceptance-release.md`（FR-003 FR-010 FR-011 FR-024 FR-030）。
- [ ] T059 更新操作手册/监控/失败队列/灰度开关/培训和实物标签记录，实现与浏览器结果分开报告：`specs/002-material-qr-traceability/quickstart.md`（FR-001～FR-033；SC-001～SC-010）。

## 依赖、可并行工作与交付策略

Setup T001～T003 → Foundational T004～T008数据结构与迁移验收 → T009～T010服务基础 → US1后端回归T011/T013 → US2后端及客户端模块T015～T019；完整US2 MVP仍依赖T012/T014和T020/T021 → US3生产 → US4流转 → US5拆框 → US6异常 → US7转换 → US8矩阵回归 → 上线准备。US8权限实现从基础阶段起持续执行，不能等到最后才保护业务。

每个故事先测试，随后服务→registry/schema/API→wrapper/type→UI→真实浏览器验收。US2仓库绑定可用已配置测试订单独立验证；US3生产绑定依赖服务端扫码上下文；不为演示绕过权限。

在依赖满足后，各故事测试文件与UI组件草稿可在不同文件同时准备；例：US1的材料测试与US2打印测试，US4 TraceDetail与US5 SplitBoxDialog。所有故事共享 product_box_service.py、路由及registry，同一文件编辑必须顺序进行；可分工处理互不重叠的文件，统一复核后验收。

第一批可用MVP=US1无回归+US2池/打印/仓库绑定；生产现场MVP还需US3上下文/数量和US4连续追溯。每批独立API/DB与浏览器/实物证据，不将模型或编译通过视为功能可用。价格中心成本联动另行细化，未纳入本批编码。

2026-10-23本批验收：T001～T008共8项完成，余51项待实施；23表ORM/迁移基础、35项PostgreSQL测试及脱敏证据见[phase1-acceptance.md](./phase1-acceptance.md)。没有应用业务库迁移，没有前端浏览器或实物标签通过声明。

2026-10-23后续批次：新增T009/T010、T011/T013、T015～T019共9项，累计17/59完成；103项完整测试及最终材料/API相关18项复验通过，IAB客户端模块7项通过。实现、验收与未完成项分别见[phase2-backend-acceptance.md](./phase2-backend-acceptance.md)。T012/T014/T020/T021未完成，不宣称US1/US2故事、业务页面、实物打印或上线通过。业务库未迁移；1个缺原始归属凭证的测试库残留清理单列INCOMPLETE。

2026-10-24工作区批次：新增T012/T014/T020，累计20/59完成；完整127项及最终相关19项复验去重128项通过，32旧端点和4项辅助wrapper检查通过，API扫描0违规、类型/构建通过。Chrome实际页面验收入库/IQC/100→30+20余50/母子台账/旧日期补打，以及500池项/跨页选择/预览关闭不计数/一次绑定/元数据/池外和越权拒绝，错误恢复阻止旧框资料写入新框。详见[phase3-workspace-acceptance.md](./phase3-workspace-acceptance.md)。T021系统/实物打印和整段操作耗时仍未完成；T026/T036仅部分API实现，完整任务不勾选。下一实施阶段T022起；业务库/真实授权仍未变，历史无归属测试库清理仍INCOMPLETE。

2026-10-26机台生产批次：新增T022～T028，累计27/59完成，18/31新端点active；配置47项、生产27项、生产API7项与旧回归合并为209个最终独立通过用例。真实浏览器完成多机/多单、30→25、错单拒绝、重扫差异完工、工人完工后入口关闭、主管更正及原因、本单分配和其他订单不可选；DB只读核对身份与数量，详见[phase4-production-acceptance.md](./phase4-production-acceptance.md)和[acceptance-production.md](./acceptance-production.md)。类型/构建、API扫描及设计检查通过。本批自有库/服务已清理，业务库未迁移，历史无凭证残留清理仍INCOMPLETE。T021与T029起仍待办；下一阶段连续工艺推进与追溯，T036仍仅元数据部分实现。

2026-10-27连续工艺批次：新增T029～T033，累计32/59，21/31端点active。固定下一步流转、数量/材料来源继承、事件游标和追溯查询已完成；完整229项及相关22/兼容3项复验去重231项通过，构建/API扫描/设计检查通过。真实浏览器同码三工艺、原料母子链、回流拒绝、历史翻页、材料核对恢复、订单范围及1.619～1.716秒查询观察见[phase5-trace-acceptance.md](./phase5-trace-acceptance.md)和[acceptance-trace.md](./acceptance-trace.md)。本批自有库/服务已清理，业务库及真实授权未改；T021实物打印、T034起拆框和历史无凭证测试库清理仍未完成。

2026-10-27拆框批次：新增T034～T038，累计37/59，22/31端点active。首次来源余额原子拆分、兼容跨单目标/需求、用途及origin链、一次子绑定、父子余量/快照和来源只读已实现；完整272项及相关84项去重272项通过，构建/API扫描0违规/设计检查通过。实际浏览器15项、只读DB100件守恒及正余量继续FINISH见[阶段报告](./phase6-split-acceptance.md)和[浏览器验收](./acceptance-split.md)。自有UI库OID257276及18124/18125已清理，业务库/真实授权未改；历史无凭证残留清理仍INCOMPLETE。T021及T039起仍待办，下一阶段US6规格异常与通知。
