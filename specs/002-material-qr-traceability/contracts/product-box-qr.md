# 产品框二维码 API 契约

所有路径相对于现有 `/api/v1`。以下是产品框扩展的新增契约；实现前须同步写入 `shared/api/registry.js`，由 `frontend/src/api/registry.ts` 提供类型桥接，再由 `frontend/src/api/qrTraceability.ts` 或领域模块调用。页面不得直接使用 axios/fetch。

## 已确认业务状态（2026-10-13）

| 对象/响应字段 | 业务显示 | 技术值 |
|---|---|---|
| 规格异常 `status` | 待确认、已确认 | `pending_confirmation`, `confirmed` |
| 异常 `resolution` | 接受继续生产、暂停生产、重新确认卷料 | `accept_continue`, `pause`, `reconfirm_coil` |
| 转换 `confirmation_status` | 待操作工确认、已确认、已取消 | `pending_operator_confirmation`, `confirmed`, `cancelled` |
| 机台/订单/工艺 `production_status` | 待生产、生产中、已完成 | `pending`, `in_progress`, `completed` |
| 通知 `delivery_status` | 待发送、已发送、发送失败 | `pending`, `sent`, `failed` |

异常已确认仅表示负责人作出处理决定，不能表示差异已经消除；暂停的具体操作影响待角色/流程决定。通知采用站内通知/待办，投递状态与异常确认状态独立；工作器正常时首投递目标 60 秒内，总计 5 次自动尝试（首次 + 前次失败后 1、5、15、30 分钟的四次重试），超过上限保留失败及人工重试入口。FR-032 数量分配和 FR-033 实际完成数量转换规则已确认。本契约为设计文档，尚未挂载新增端点。

## QR 池

### `POST /product-qr-pool/batches`

- 权限：管理员/授权主管（正式角色级别待 P0 冻结）
- 请求：`{count, print_batch_no?, payload_version?, idempotency_key}`
- 响应：批次、生成数量、`[{id, public_code, qr_payload, pool_status}]`
- 规则：count > 0 且不超过服务端配置上限（默认 500）；类型 PFB、版本 v1，编号/完整 payload 全局唯一；编号、打印模板和确认合同见 [qr-printing.md](./qr-printing.md)。

### `POST /product-qr-pool/{item_id}/reprint`

- 权限：授权仓库/主管
- 响应：原身份、二维码图片/打印作业数据、已有累计确认次数。
- 规则：不得创建新池项或改变绑定；申请补打与用户确认已打印分开，取消打印对话框不增加打印确认次数，见 [qr-printing.md](./qr-printing.md)。

### `GET /product-qr-pool`

- 权限：登录用户
- 参数：`pool_status`、`print_batch_no`、`page`、`page_size`

## 产品框绑定与查询

### `POST /product-boxes/bind`

- 权限：授权生产/仓库人员
- 请求：`{qr_payload|public_code, order_id, product_code, part_id?, customer_id?, customer_part_no?, next_process_code?, idempotency_key}`
- 响应：产品框当前信息、二维码身份和首次事件。
- 拒绝：池外、已绑定、无效产品 A、订单不存在、同框二次订单、权限不足。重复提交应返回已存在身份或明确 `409 QR_ALREADY_BOUND`，不能覆盖。

### `POST /product-boxes/scan`

- 权限：登录用户
- 请求：`{qr_payload, operation}`
- 响应：当前框、当前订单/产品/工艺/数量、允许动作。
- 规则：池外拒绝；已绑定只读查询，不返回绑定入口。

### `GET /product-boxes/{box_id}/trace`

- 权限：登录用户，字段按角色脱敏
- 响应：当前框、全部 FlowEvent、父子关系、异常、转换、原材料批次/子卷反查。

## 机台生产与数量

### `POST /machines/scan-production`

- 权限：生产操作工及以上
- 请求：`{machine_qr}`
- 响应：机台状态、当前工艺、可选已绑定订单列表；每项包含该机台/订单/工艺范围的 `production_status`，不能用全局订单完成状态替代。

### `POST /product-boxes/{box_id}/quantities`

- 权限：生产操作工；已完成机台仅主管/更高
- 请求：`{machine_id, order_id, current_qty, expected_version, idempotency_key}`
- 响应：新数量、版本、事件。
- 规则：先扫机台并选择订单；current_qty 为覆盖值；版本冲突返回 `409 STALE_BOX_VERSION`，调用方必须重读。

### `POST /machines/{machine_id}/production-complete`

- 权限：生产操作工及以上
- 请求：`{order_id, confirm_quantity_difference, expected_version, idempotency_key}`；版本指当前机台/订单/工艺生产状态，具体来源记录待 D-P004 冻结。
- 响应：`production_status=completed`、计划量/框汇总量、差异提示。允许差异确认；机台完成不关闭二维码后续流转。

## 订单量/备货量分配（FR-032 已确认，结构待 D-P004 冻结）

### 建议 `POST /production/output-allocations`

- 权限：授权生产主管或该订单业务人员；普通操作工只登记产量，不可提交分配调整。无额外审批。
- 请求草案：`{order_id, source_ref, order_qty, stock_qty, expected_version, idempotency_key}`；产出来源及订单主表待 D-P004 冻结，来源数量与剩余需求由服务端查询，不采信客户端提供的可分配总量。
- 响应草案：当前有效分配、实际可分配数量、订单剩余需求、版本和操作审计。
- 默认：订单量为实际可分配数量与订单剩余需求中的较小值，剩余作为备货。主管/本订单业务人员可调整。
- 校验：两项均为非负整数，合计等于实际可分配量，订单量不超过剩余需求；无权限、超量、重复占用及并发版本冲突不能改变已保存分配。
- 审计：操作者、时间、前后订单量/备货量；重复同请求返回原结果，不重复分配。不更改订单计划量。
- 验收例子：80 个实际可分配量、订单剩余 70，默认 70+10；授权调整 60+20 成功；70+20、订单量超过 70、负数/小数及普通工调整拒绝。

## 拆框

### `POST /product-boxes/{parent_id}/split`

- 权限：授权生产/仓库/主管
- 请求：`{child_qr_payload, quantity, expected_version, idempotency_key}`；版本指父框当前版本。
- 响应：父框、子框、父子关系和事件。
- 拒绝：数量 <= 0、超过父当前数量、子二维码池外/已绑定、父数量为 0；失败整笔回滚。

## 规格异常

### `POST /coil-spec-exceptions`

- 权限：生产现场
- 请求：`{order_id, product_box_id?, expected_spec, actual_spec, continue_production, idempotency_key}`；订单/实际卷料来源必须在服务端核验。
- 响应：异常 `status=pending_confirmation` 和独立的通知投递状态。规格一致不得创建异常；不一致允许继续但必须留痕，写站内通知/待办 outbox。

### `POST /coil-spec-exceptions/{exception_id}/confirm`

- 权限：主管或该订单业务人员
- 请求：`{resolution, remark?, expected_version, idempotency_key}`；版本指该异常记录，确认与其他修改竞争必须检查最新状态。
- 响应：确认人/时间、`status=confirmed`、处理结果 `resolution=accept_continue` / `pause` / `reconfirm_coil`。任一合格角色确认即可；备注可空，重复确认不得产生第二次状态变更。已确认不等于规格差异消除。

## B/C 转换

### `POST /product-conversions`

- 权限：业务或主管手动发起；预授权差异工艺可由系统创建待确认记录
- 请求：`{box_id, target_product_code, actual_qty?, trigger_type, expected_version, idempotency_key}`；创建时 actual_qty 仅为提议数量，最终值以操作工确认请求为准，版本指来源框。
- 响应：`confirmation_status=pending_operator_confirmation` 的待确认转换记录；操作工通过专用确认动作完成，创建请求不能直接跳过确认。
- 规则：人工发起与预授权触发均先建待确认记录，默认带出当前框全部数量供操作工确认或修改，不能直接改产品/数量。记录原订单、原工艺与来源框，保存时的默认数量不能替代确认时的最新框版本。

### `POST /product-conversions/{conversion_id}/confirm`

- 权限：当前操作工/主管按规则
- 请求：`{actual_qty, confirm: true, child_qr_payload?, expected_version, conversion_version, idempotency_key}`；expected_version 指来源框版本，conversion_version 指转换记录版本；子二维码在部分转换时必填，全量时不需要新二维码。
- 响应：`confirmation_status=confirmed`、转换记录、父框当前产品和数量，以及部分转换的子框/新二维码身份/父子关系。
- 全量：`actual_qty == current_qty`，原框变更为目标产品，数量及二维码身份保持，记录原订单、原工艺和转换方向。
- 部分：`0 < actual_qty < current_qty`，子 QR 必须为池内未绑定；先拆框再在同一事务内转换子框，父框保留原产品及余量。子框继承原订单及追溯来源，保存父子和转换记录。
- 拒绝与并发：数量 <= 0、超量、子 QR 缺失/池外/已绑定、权限不足或父框版本冲突时，整笔回滚；相同幂等请求不重复拆框，版本改变须重读并重新确认。

### 建议 `POST /product-conversions/{conversion_id}/cancel`

- 权限：取消待确认记录的角色与订单范围由 D-P006 冻结；已确认结果不得通过取消回退，反向转换须新建独立记录并由操作工确认。
- 请求：`{conversion_version, idempotency_key, reason?}`；版本指待确认转换记录，取消只改变此记录状态，不修改框。
- 响应：`confirmation_status=cancelled`，保存取消人/时间/可选原因，保留原转换记录，框当前产品和数量不变。
- 规则：仅待确认记录可以取消，已确认记录须拒绝此动作；取消/确认并发只能有一个终态，失败不得改变框。重复取消同请求幂等。

## 审计与通知

### `GET /product-boxes/{box_id}/events`

- 权限：登录用户
- 响应：扫描、绑定、数量、拆框、完成、异常、转换事件，含操作者和前后数量。

### `GET /notifications`

- 权限：登录用户
- 参数：`status`（通知投递 `pending` / `sent` / `failed`）、`unread_only`。
- 响应：仅当前用户有权查看的站内通知/待办，分别包含 `delivery_status` 及关联异常的 `exception_status`；已读/送达不能自动确认业务异常。
- 用于查看规格异常通知及失败重试状态；自动尝试上限与退避按 D-P007，业务确认状态不随重试改变。

## 错误契约

产品框新领域错误使用 `{code, message, details?, request_id?}`，旧 QR lookup 的 200 + found=false 保留。字段缺失/类型错误保持现有 HTTP 422 `{detail, errors}` 验证格式，领域 wrapper 同时识别两种格式。

| HTTP | code | 条件 |
|---|---|---|
| 400 | `INVALID_QR` | 格式、类型、版本或完整身份校验错误 |
| 400 | `INVALID_QUANTITY` | 非正转换/拆框数量、超量或分配合计错误等业务数量边界 |
| 400 | `INVALID_PRODUCT` / `ORDER_MISMATCH` | 无效产品 A 或当前订单/框归属不匹配 |
| 403 | `FORBIDDEN` | 等级、部门、能力或订单范围无权限 |
| 404 | `QR_NOT_IN_POOL` / `ENTITY_NOT_FOUND` | 完整有效 QR 不在池，或订单/机台/框等实体不存在 |
| 409 | `QR_ALREADY_BOUND` | 再次绑定/改绑或已绑定子二维码 |
| 409 | `STALE_BOX_VERSION` | 框版本已改变，必须重读并重新确认 |
| 409 | `IDEMPOTENCY_CONFLICT` | 同操作者/动作/实体请求键对应不同请求内容 |
| 409 | `STATE_CONFLICT` | 当前状态不允许操作或确认/取消终态冲突 |

关键写入请求均携带幂等键；同键同请求重用已提交结果，未完成请求不能重放为成功。新增事件时间为带时区 ISO 8601 UTC、至少毫秒精度。异常与领域操作不打印令牌或连接设置。
