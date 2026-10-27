# 数据模型：产品框二维码扩展

本模型新增产品框追溯域与必要支持记录；原材料 `material_batches`、`MaterialBatchChild`、`parent_batch_id` 作为既有来源保留，待基线迁移评估后再决定兼容清理。所有表使用现有 SQLAlchemy async/Alembic 约定，关键写入在服务层事务中完成。订单、权限及暂停方案是设计默认值，见 [订单合同](./contracts/order-routing.md) 和 [权限合同](./contracts/permissions.md)，本模型是迁移实施基准，建表状态以独立验收记录为准。

## 1. ProductQrPoolItem（产品二维码池项）

表建议：`product_qr_pool_items`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | bigint | PK |
| public_code | varchar(80) | NOT NULL、全局 UNIQUE、不可变；PFB-创建日-至少六位数据库 ID 流水 |
| payload_version | varchar(16) | NOT NULL，初始 `v1` |
| qr_payload | varchar(200) | NOT NULL、全局 UNIQUE；只含稳定身份 |
| pool_status | varchar(20) | `unused`/`bound`/`void`; 仅服务层迁移 |
| print_batch_no | varchar(50) | 生成/打印批次 |
| printed_at | timestamp | 首次用户确认已打印时间；不代表打印机遥测 |
| print_count | integer | 默认 0；首次/补打确认后递增，取消对话框不增加 |
| bound_box_id | 派生只读字段 | 从 product_boxes.qr_pool_item_id 唯一关系查询，不冗余存双向FK |
| created_by | bigint | FK users |
| created_at/updated_at | timestamp | 审计时间 |

索引：`(pool_status, created_at)`、`public_code`、`qr_payload`、`print_batch_no`。批量生成默认服务端上限 500，编号使用数据库身份序列并有唯一保护；补打只读取原项。打印作业/数据发放/确认需持久化审计，具体支持结构随迁移评审；打印合同见 [contracts/qr-printing.md](./contracts/qr-printing.md)。

## 2. ProductBox（产品框）

表建议：`product_boxes`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | bigint | PK |
| qr_pool_item_id | bigint | FK、UNIQUE、NOT NULL |
| box_no | varchar(80) | 可读编号；与二维码身份分离 |
| order_id | bigint | NOT NULL、FK production_plans.id；绑定后不可改 |
| order_product_id | bigint | FK product_order_products.id；实际产品及目标量 |
| product_code | varchar(40) | 仅允许 B/C，禁止 A 正式件号 |
| part_id | bigint nullable | FK parts；保存产品引用 |
| product_name_snapshot | varchar(200) | 绑定/转换时快照 |
| customer_id | bigint nullable | FK customers |
| customer_name_snapshot | varchar(200) nullable | 可编辑快照 |
| customer_part_no | varchar(150) nullable | 可编辑快照 |
| route_revision_id | bigint | FK product_route_revisions.id；绑定时版本，历史不可覆盖 |
| current_process_code | varchar(50) nullable | 当前工艺，来自固定路线版本 |
| next_process_code | varchar(50) nullable | 后续工艺，仅路线允许值可授权编辑 |
| current_qty | integer | NOT NULL、>=0；当前值覆盖 |
| version | integer | NOT NULL 默认 1；乐观并发控制 |
| lifecycle_status | varchar(30) | `active`/`empty`/`closed`/`scrapped` |
| bound_at/bound_by | timestamp/bigint | 绑定审计 |
| created_at/updated_at | timestamp | 时间 |

约束：一个二维码只能有一个 ProductBox；一个 ProductBox 只能有一个订单；`current_qty >= 0`。order_product_id 必须属于 order_id；实际件号必须是计划主件或配对件。跨单拆框只创建新子框并记录来源/目标，不更新已有框的订单。转换保留 order_id，更新为已配置的目标产品/路线并留原快照。

## 3. ProductFlowEvent（产品框工艺事件）

表建议：`product_flow_events`。事件为追加事实，不更新历史。字段：`id`、`product_box_id`、`event_type`（bind/scan/qty_save/quantity_correction/metadata_edit/process_start/process_complete/split/cross_order_split/allocation/conversion/exception/resume）、`process_code`、`machine_id`、`order_id`、`order_product_id`、`state_id`、`context_id nullable`、`material_batch_id nullable`、`operator_id`、`before_qty`、`after_qty`、`box_version`、`before_snapshot/after_snapshot`、`status`、`remark`、`occurred_at`。仅查阅历史时不保存一条伪造生产事实。

索引：`(product_box_id, occurred_at)`、`(order_id, occurred_at)`、`(machine_id, occurred_at)`。与 AuditLog 互补：FlowEvent 是业务事实，AuditLog 是权限和变更审计。

## 4. ProductBoxRelation（父子框关系）

表建议：`product_box_relations`。字段：`id`、`parent_box_id`、`child_box_id`、`relation_type`（split/cross_order_split/partial_conversion）、`quantity` (>0)、`source_product_code`、`target_product_code`、`source_order_id`、`target_order_id`、`source_order_product_id`、`target_order_product_id`、`source_snapshot`、`order_qty`、`stock_qty`、`created_by`、`created_at`。普通拆框/部分转换来源与目标订单相同，跨单拆框不同；两类用途拆出量合计为 quantity。

约束：父子不能相同；child_box_id UNIQUE；同一拆分请求使用幂等键；子二维码在该关系提交前必须为池内 unused。索引父、子、来源/目标订单和时间。来源产出与用途记录同步分割，父子数量及来源守恒。

## 5. CoilSpecException（卷料规格异常）

表建议：`coil_spec_exceptions`。字段：`id`、`order_id`、`product_box_id nullable`、`state_id`、`material_batch_id`、`expected_spec`、`actual_spec`、`status`（`pending_confirmation` / `confirmed`，对应 2026-10-13 已确认的待确认/已确认）、`resolution`（`accept_continue` / `pause` / `reconfirm_coil`）、`remark nullable`、`created_by`、`confirmed_by`、`confirmed_at`、`created_at`。确认状态与处理结果分列，confirmed 不代表差异消除；通知投递成功不改变确认状态。pause/reconfirm_coil 对该 state_id 建立阻断，不改全局订单或物理设备。

增加 `version`（默认 1）用于异常确认/修改冲突检查；幂等重放不产生第二次确认或审计事件。

增加 `released_by/released_at/resume_reason/rechecked_material_batch_id`，恢复不覆盖原确认结果。同状态存在其他未解除阻断时仍不能恢复生产。以状态、实际卷料及规格快照摘要生成活动异常去重键，不能只凭订单把不同机台的异常合并。

## 6. ProductConversionRecord（B/C 转换记录）

表建议：`product_conversion_records`。字段：`id`、`product_box_id`、`order_id`、`source_product_code`、`target_product_code`、`source_process_code`、`target_process_code`、`actual_qty`（可空，已确认时 >0）、`trigger_type`（manual/pre_authorized/exception）、`confirmation_status`（`pending_operator_confirmation` / `confirmed` / `cancelled`，对应已确认状态）、`confirmed_by`、`confirmed_at`、`relation_id nullable`、`remark`、`created_at`。

创建时提议数量另外保存 `proposed_qty`，`actual_qty` 在待确认/取消状态为空，confirmed 时才保存正数最终数量；新增 `version`（默认 1）、`cancelled_by`、`cancelled_at` 和可空取消原因。确认同时检查来源框 expected_version 与转换 conversion_version，取消只检查 conversion_version；版本/状态不符拒绝，确认/取消竞争只有一个终态。

2026-10-13 已确认 FR-033：实际完成数量等于框当前数量时，全量转换 relation_id 为空且原二维码不变；实际数量小于当前数量时，必须关联 relation_id 和池内未绑定二维码子框，子框为新产品及实际数量，父框保留原产品及余量。实际数量须大于 0 且不超过当前值；人工/预授权均须操作工确认，待确认及已取消记录不改变 ProductBox 产品和数量，取消记录保留。

部分确认事务必须同时校验父框版本与子 QR 池状态，锁父框/子池项，创建并绑定子框、扣减父框、写关系/转换/事件/审计后一次提交；任一失败整体回滚。相同确认请求幂等，不重复拆框；框数量或版本改变后必须重新读取并由操作工确认，不能沿用旧的默认全量值。

## 7. QRScanLog 扩展

沿用现有 `qr_scan_logs`，新增 `PFB`（产品框）扫描类型和必要操作值（bind/qty_save/split/complete/conversion/exception）。保留当前登录 `operator_id`，不新增操作工二维码依赖。只记录成功解析的身份与安全错误码，不把原始未知扫描内容、票据或令牌直接写日志。

## 8. Notification/Outbox（站内通知渠道已确认）

表建议：`notification_outbox`：`id`、`dedupe_key UNIQUE`、`recipient_user_id`、`event_type`、`entity_type/id`、`payload_json`、`status`（pending/sent/failed）、`attempts`、`next_retry_at`、`last_error`、`created_at`、`sent_at`。规格异常事务只写 outbox；发送器投递至站内通知/待办。按事件/收件人/渠道去重，站内待办另有唯一来源键；投递状态与异常确认独立。工作器正常时首投递目标 60 秒内，总计 5 次自动尝试，四次重试在前次失败后 1、5、15、30 分钟；超过上限保留失败队列及尝试记录，授权人工重试不擦除历史。

## 9. 订单配置、工艺状态与数量分配（设计基准）

以下支持记录独立于六个核心实体，迁移按依赖顺序创建，均有真实 FK 及适合查询的索引：

| 实体/表 | 主要字段及约束 |
|---|---|
| ProductOrderContext / product_order_contexts | order_id FK production_plans UNIQUE、business_owner_id FK users、version、配置人/时间 |
| ProductOrderProduct / product_order_products | order_id、part_id、product_code、target_qty 非负整数、route_revision_id、转换授权、binding_allowed、conversion_source_id；直接项为计划主件/配对件，显式转换目标不可直接绑定且target_qty=0；同订单/实际产品唯一，配对件单独配置 |
| ProductRouteRevision / product_route_revisions | route_code、revision、product_code、steps_json、首次产出步骤；(route_code, revision) UNIQUE，发布使用后不可覆盖；步骤引用实际字典并校验机台能力 |
| MachineOrderProcessState / machine_order_process_states | assignment_id、order_product_id、route_revision_id、process_code、target_qty、production_status、version、完成人/时间/差异确认；前四项工艺范围唯一，待生产/生产中/已完成与旧计划状态分离 |
| MachineProductionContext / machine_production_contexts | user_id、machine_id、scan_ticket_digest、scanned_at、state_id nullable、last_activity_at、expires_at、closed_at、version；扫码票据摘要持久化且一次选单，不存认证令牌 |
| BoxProcessQuantity / box_process_quantities | state_id、box_id、current_qty、version、material_batch_id、来源引用及入量快照；(state_id, box_id) UNIQUE、quantity >=0，多次保存覆盖 |
| ProductOutputAllocation / product_output_allocations | source_quantity_id UNIQUE、order_id、order_product_id、box_id、origin_allocation_id nullable、available_qty、remaining_order_qty_snapshot、order_qty、stock_qty、version、assigned_by/at；两项非负整数且合计 available_qty |

来源只在首次产出工艺初始化；后续工艺关联来源，不重复新增产出。普通拆框/转换按父子分割来源分配；跨单拆框新子分配有 origin_allocation_id 并原子减少源分配，不复制原数量。需求锁按订单产品 ID 排序；调整当前记录时从已分配合计中排除自身旧值再算剩余。已有下游事实时禁止直接改旧用途，更正历史数量不自动覆写下游或当前框。

2026-10-27连续工艺实现：BoxProcessQuantity.material_batch_id在首次数量登记时可明确关联实际批次，之后不可替换；推进复制material_batch_id与source_quantity_id，并将当前框量保存为目标input_qty。ProductFlowEvent.process_start的before_snapshot保存源步骤/状态/出量，after_snapshot保存目标步骤/状态/入量/首次来源；不把进入后续工艺当作新产出。材料关联不扣卷料重量；历史缺材料保持null，查询按真实parent_batch_id上溯并标示断链、循环或深度限制。

机台 target_qty 明确配置，单件/单机不能直接借联合订单 total_qty。source_quantity_id、order_id、order_product_id、box_id 与源事实必须一致，由服务端推导而非客户端拼接。涉及人工分配的数量变化必须同事务提交有效分配，不能静默恢复默认覆盖用户选择。

## 10. 权限、通知与打印支持记录

- QrCapabilityGrant / qr_capability_grants：user_id、capability、granted_by/at、revoked_at；有效用户/能力唯一，未配置拒绝；本轮不回填真实授权。
- ExceptionRecipientGroup / exception_recipient_groups：exception_id、group_type（supervisor/business_owner）、resolution_status（pending_configuration/resolved）、recipient_ids、missing_reason、resolved_at；异常/组别唯一，配置补齐后幂等回补 outbox。
- QrPrintJob / qr_print_jobs：申请人、模板、申请类型、项集合、创建时间；QrPrintJobItem / qr_print_job_items 保存作业、池项及发放快照，(job_id,pool_item_id) UNIQUE；QrPrintConfirmation / qr_print_confirmations：作业、池项、确认人/时间，(job_id, pool_item_id) UNIQUE。同作业任一项只确认一次，新补打作业可再次计数。
- QrIdempotencyRecord / qr_idempotency_records：操作者、动作、实体、请求键、规范化内容摘要、结果/HTTP 状态、创建时间；业务结果与记录同事务，组合唯一，不保存凭据或敏感请求头。
- QrNotificationAttempt / qr_notification_attempts：outbox_id、attempt_no、触发类型、结果、安全错误码、时间；人工重试独立批次，不擦除先前五次自动尝试。

这些表的具体 SQL 类型、循环 FK 建立次序及不可变保护在 Phase 1 迁移验收时验证；记录逻辑与来源已固定，不把本设计当作实际数据库约束存在的证据。

## 状态与事务规则

- 二维码池：本期可调用动作仅 `unused -> bound`，`bound` 不可回退；void 为保留状态，没有本期作废写入入口，不能借普通更新设置。
- 数量保存：锁定 ProductBox，校验 `expected_version`，写新当前值、FlowEvent、AuditLog 后 version+1。
- 拆框：锁父框与子 QR 池项，校验数量，再创建子框、关系、事件并一次提交。
- 订单完成：锁定当前机台/订单实际产品/工艺状态及数量快照；与并发数量保存共用状态锁。操作工不能写已完成状态，主管修正写前后值与原因，不能自动修改已开始的下一工艺。
- 所有失败必须回滚父子数量、绑定状态、关系和事件。
- 新事件使用 UTC、至少毫秒精度，API 返回带时区 ISO 8601，前端按 Asia/Hong_Kong 展示；旧无时区字段单独兼容。
- 关键操作幂等记录按操作者/动作/实体/请求键持久化规范化请求摘要与业务结果，结果同事务提交；同键异内容冲突。表/支持记录随迁移评审，不使用进程内存作为事实源。


## Phase 1 SQL 实施约定（2026-10-22）

新实体bigint identity，旧表FK沿用integer；新时间TIMESTAMP WITH TIME ZONE及数据库CURRENT_TIMESTAMP默认值。version>=1、数量非负、B/C及状态CHECK保护；路线步骤和快照用JSONB，持久化关联用真实FK。

ProductBox的(order_product_id,order_id,part_id,product_code)复合FK匹配订单实际产品，(route_revision_id,product_code)复合FK匹配路线。池绑定只存product_boxes.qr_pool_item_id，bound_box_id为查询字段。身份、既有框订单、使用中的路线和追加事件使用数据库触发器保护，服务层仍执行权限/锁/业务校验。转换目标配置保存binding_allowed=false、conversion_source_id、target_qty=0，不新增原单需求；分配按源产品需求归属核算。

新增QrNotification/qr_notifications(outbox_id UNIQUE,recipient_user_id,payload_json,read_at,created_at)，站内写入后才标sent。新增QrCapabilitySet/qr_capability_sets(user_id PK,version)保护授权集合版本，grants保留撤销历史。通知尝试增加retry_batch，同outbox/retry_batch/attempt_no唯一，人工批次保留原五次尝试。

qr_scan_logs现有PostgreSQL scantype/scanoperation先核对实际标签，再增量添加PFB及新动作；保留旧标签。空测试库降级保留新增枚举标签；已有产品身份或事件时拒绝破坏性降级。单独测试升级→空库降级→重升、约束/不可变保护及旧QR无回归，不以metadata建表代替迁移执行。

2026-10-23实现补充：QrPrintJob(id,requested_by)与打印确认(job_id,confirmed_by)通过复合FK匹配申请人；NotificationOutbox(id,recipient_user_id)与站内通知通过复合FK匹配收件人。父子框关系的来源/目标订单与框、实际产品用复合FK匹配，转换的两端产品与原订单匹配。PFB扫码及新动作审计也阻止不兼容降级。23表和迁移限定验收见phase1-acceptance.md；本段不是业务库已建表的声明。

## 2026-10-27 已实现拆框余额

首次来源未进入下游时拆框，同事务减少父ProductBox、首次BoxProcessQuantity.current_qty及ProductOutputAllocation余额；同单/跨单子份额均创建自身来源量和分配，origin_allocation_id指向父分配。原始制造数量由不可变qty_save和split快照追溯，不能将各份额再相加为新增制造产量。子入量保存拆出量，原料来源继承；重复拆分保留分配链，零父框保留绑定并置empty。锁需求/状态/父框/子池项/用途，expected_version、allocation_version及跨单target_state_version全部校验。

首次来源拆后禁止覆盖或历史更正，防止重复恢复已拆数量；下一工艺新量仍可覆盖，最新后续工艺更正更新当前框，保留来源分配、兄弟框和入量。trace派生双方当前余量，relation.source_snapshot不变；跨单双方订单不可见时不显示关系和快照。
