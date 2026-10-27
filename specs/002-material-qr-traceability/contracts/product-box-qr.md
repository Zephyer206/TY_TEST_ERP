# 产品框二维码 API 契约

**实施基准**：2026-10-27。按已有三条业务确认及可评审默认方案整理；没有新增业务回答。池、打印、绑定、扫描、元数据、配置读写、机台生产、工艺推进/追溯、拆框和能力维护共22个端点已在代码中挂载，其余9项仍为设计清单；基线32个旧QR端点已完成登记和typed wrapper映射。业务库尚未迁移，尚未上线。

路径相对 /api/v1；API 清单和请求字段如下。所有端点要求认证，服务端逐次检查部门、等级、显式能力、订单范围、实体状态及需要时的扫码上下文；完整规则见 [permissions.md](./permissions.md)。低等级、其他订单业务及无上下文的管理账号不能绕过规则。

## 状态

| 对象/字段 | 允许值 | 含义 |
|---|---|---|
| 池 pool_status | unused/bound/void | 本期仅unused→bound；void保留，无作废入口 |
| 异常 status | pending_confirmation/confirmed | 确认是负责人决定，不表示规格差异消除 |
| 异常 resolution | accept_continue/pause/reconfirm_coil | 与确认及通知状态分列 |
| 转换 confirmation_status | pending_operator_confirmation/confirmed/cancelled | 未确认和取消不改框产品/数量 |
| 机台工艺 production_status | pending/in_progress/completed | 完成不关闭框后续工艺或全局计划 |
| 通知 delivery_status | pending/sent/failed | 投递或已读不确认业务异常 |

## 端点与请求

| Key | Method | Relative path | Description / request |
|---|---|---|---|
| `productQrPool.list` | GET | `/product-qr-pool` | 按查询范围列出池项；pool_status/print_batch_no/page/page_size |
| `productQrPool.generateBatch` | POST | `/product-qr-pool/batches` | 生成稳定身份；{count,print_batch_no?,idempotency_key}，默认上限500 |
| `productQrPool.reprint` | POST | `/product-qr-pool/{item_id}/reprint` | 原身份补打；{template_code?,idempotency_key}；返回作业及当前确认次数 |
| `productQrPool.printData` | POST | `/product-qr-pool/print-data` | {item_ids,template_code?,idempotency_key}；发放数据和快照，不确认物理成功 |
| `productQrPool.confirmPrint` | POST | `/product-qr-pool/print-confirmations` | {print_job_id,confirmed_item_ids,idempotency_key}；仅申请人确认，每项每作业一次 |
| `productBoxes.bind` | POST | `/product-boxes/bind` | {qr_payload,order_product_id,context_id?,idempotency_key}；一次绑定，数量初始0，配置推导订单/件号/产品/路线 |
| `productBoxes.scan` | POST | `/product-boxes/scan` | {qr_payload,split_parent_id?}；验证完整存储身份；未绑定返回身份和允许绑定动作，已绑定只返回当前框及允许动作 |
| `productBoxes.trace` | GET | `/product-boxes/{box_id}/trace` | 当前框/订单/路线、工艺数量/原料祖先链、最近业务事件及父子/异常/转换；page/page_size分页关联事实，按账号范围 |
| `productBoxes.events` | GET | `/product-boxes/{box_id}/events` | page_size/before_id；按occurred_at/id倒序游标查询事实，含操作者、前后量及来源 |
| `productBoxes.saveQuantity` | POST | `/product-boxes/{box_id}/quantities` | {context_id,current_qty,material_batch_id?,expected_version,state_version,idempotency_key}；覆盖当前值；首次可记录真实材料来源 |
| `productBoxes.metadata` | PATCH | `/product-boxes/{box_id}/metadata` | {customer_name_snapshot?,customer_part_no?,next_process_code?,expected_version,idempotency_key}；不改身份/订单/实际产品/历史 |
| `productBoxes.correctQuantity` | POST | `/product-boxes/{box_id}/quantity-corrections` | {state_id,current_qty,reason,expected_version,state_version,idempotency_key}；主管历史更正，不覆写下游 |
| `productBoxes.advance` | POST | `/product-boxes/{box_id}/advance` | {context_id,expected_version,state_version,idempotency_key}；仅合法下一步骤，记录出入量快照 |
| `productBoxes.split` | POST | `/product-boxes/{parent_id}/split` | {child_qr_payload,quantity,order_qty,stock_qty,expected_version,allocation_version,target_order_product_id?,target_state_id?,target_state_version?,idempotency_key}；同单/跨单原子拆框 |
| `machines.scanProduction` | POST | `/machines/scan-production` | {machine_qr,context_id?}；初扫返回当前用户票据/有效分配，再扫明确上下文返回完成意向 |
| `machines.selectProduction` | POST | `/machines/production-contexts` | {scan_ticket,assignment_id,order_product_id,process_code,state_id?,idempotency_key}；建立用户/机台/单/工艺上下文；state_id显式选择旧版本状态 |
| `machines.productionComplete` | POST | `/machines/{machine_id}/production-complete` | {context_id,confirm_quantity_difference,expected_version,idempotency_key}；版本指机台工艺状态 |
| `production.qrContext` | GET | `/production/plans/{order_id}/qr-context` | 配置、version和missing_configuration，仅当前账号可见订单 |
| `production.saveQrContext` | PUT | `/production/plans/{order_id}/qr-context` | {business_owner_id,products,machine_process_targets,expected_version,idempotency_key}；首次版本0，配置原子保存 |
| `production.allocateOutput` | POST | `/production/output-allocations` | {source_quantity_id,order_qty,stock_qty,expected_version,idempotency_key}；来源/剩余需求由服务端查询 |
| `coilSpecExceptions.create` | POST | `/coil-spec-exceptions` | {context_id,material_batch_id,product_box_id?,continue_production,idempotency_key}；服务端比较订单/卷料事实 |
| `coilSpecExceptions.confirm` | POST | `/coil-spec-exceptions/{exception_id}/confirm` | {resolution,remark?,expected_version,idempotency_key}；任一授权负责人确认，备注可空 |
| `coilSpecExceptions.resume` | POST | `/coil-spec-exceptions/{exception_id}/resume` | {rechecked_material_batch_id,reason,expected_version,idempotency_key}；独立解除，不覆盖原处理结果 |
| `productConversions.create` | POST | `/product-conversions` | {box_id,target_order_product_id,proposed_qty?,expected_version,idempotency_key}；人工发起仅manual，预授权由服务端内部触发 |
| `productConversions.confirm` | POST | `/product-conversions/{conversion_id}/confirm` | {context_id,actual_qty,confirm:true,child_qr_payload?,expected_version,conversion_version,idempotency_key}；仅当前操作工实物确认 |
| `productConversions.cancel` | POST | `/product-conversions/{conversion_id}/cancel` | {context_id?,conversion_version,reason?,idempotency_key}；仅待确认，确认/取消竞争只允许一个终态 |
| `notifications.list` | GET | `/notifications` | delivery_status/unread_only；仅本人，异常状态与投递/已读状态分列 |
| `qrAdmin.capabilities` | GET | `/qr-admin/capabilities` | LV4+qr.admin，授权维护所需字段 |
| `qrAdmin.saveCapabilities` | PUT | `/qr-admin/capabilities/{user_id}` | {capabilities,expected_version,idempotency_key}；LV4+qr.admin，授权/撤销保留审计 |
| `qrAdmin.deliveries` | GET | `/qr-admin/notification-deliveries` | LV4+qr.admin，失败投递及安全错误码 |
| `qrAdmin.retryDelivery` | POST | `/qr-admin/notification-deliveries/{delivery_id}/retry` | {expected_version,idempotency_key}；LV4+qr.admin，新重试批次保留历史 |

## 身份、绑定和打印

已实现的22个key为 `productQrPool.list/generateBatch/reprint/printData/confirmPrint`、`productBoxes.bind/scan/metadata/saveQuantity/correctQuantity/advance/trace/events/split`、`production.qrContext/saveQrContext/allocateOutput`、`machines.scanProduction/selectProduction/productionComplete`、`qrAdmin.capabilities/saveCapabilities`。严格请求/响应定义见 `backend/app/schemas/product_box.py` 和 `frontend/src/types/productBox.ts`、`productProduction.ts`、`productTrace.ts`、`productSplit.ts`：新领域bigint ID输出十进制字符串，引用既有订单/用户/件号的int4 ID仍输出整数；请求可用规范正整数或十进制字符串传新ID，拒绝bool、浮点和前导零。数量必须为整数，请求禁止额外字段，操作者只能取有效登录账号，幂等键为8～120位字母数字及 `._:-`。生成、打印数据、补打、绑定、选单和拆框返回201，其余已实现端点成功响应返回200。

PFB:v1:<pool_item_id>:<public_code> 完整校验；编号PFB-YYYYMMDD-至少六位数据库ID，Asia/Hong_Kong创建日持久化。身份/编号唯一且不可修改，绑定最多一次；池外404、再次绑定409。人工检索只解析已有身份，不能绕过池、权限及绑定校验。直接绑定的实际产品必须是订单主件/配对件，产品仅B/C，禁止A。

生成默认最多500项，失败无半批次；绑定一框一订单，不可追加第二订单或改绑。查询已有绑定框不返回绑定入口。二维码池 bound_box_id 从框的唯一FK派生，不存双向可变绑定字段。

A4 3×7和系统打印出口按 [qr-printing.md](./qr-printing.md)；打印数据、作业项快照、用户确认分开持久化。取消对话框不增加次数，补打不生成新身份；确认人必须是作业申请人且有qr.print，每作业每项只确认一次。

产品打印页面的软件PDF验收已验证500标签生成24页A4；这是版式和分页证据。系统打印对话框、实体打印及纸质扫码尚未验收，不能由PDF或操作者确认计数推定通过。

PFB的通用扫码日志 `QRScanLog.entity_id` 指池项ID；对应框从唯一 `qr_pool_item_id` 查找，不能假设池项ID等于框ID。旧MAT/MCN/PFC/PRT实体语义保留。原材料补打及扫码图像编码已存 `qr_code`，不会按补打当天日期重新编码；原材料补打沿用QUERY操作并在notes记明补打。

原材料仓库目录GET `/warehouse/materials`的 `include_inactive` 默认false；历史追溯目录可显式传true读取停用项以显示历史名称及筛选，原材料入库选择仍只提供有效材料。旧32项的registry/wrapper/类型位置和合同检查见 [api-registry.md](./api-registry.md)。

## 订单、上下文与数量

order_id=production_plans.id，明确负责人和实际产品/路线/单机目标量，缺配置返回缺失项并拒绝生产写入。配置请求结构和来源见 [order-routing.md](./order-routing.md)。直接产品与显式转换目标分开，转换目标不能直接绑定/跨单占用需求。

已实现的GET `/production/plans/{order_id}/qr-context`只读当前账号可见订单的持久化配置，返回订单/主配对件、负责人、配置version和missing_configuration，以及实际产品、已发布路线及机台工艺目标；每个产品包含binding_allowed、can_bind和自身缺失项。无配置返回明确缺失项及version=0，不凭旧计划数据补造默认负责人或路线。PUT原子保存完整配置，各工艺机台份额合计须等于该产品目标量；已发布路线内容不可覆盖，新版本仅用于新框。

已实现的PATCH `/product-boxes/{box_id}/metadata`只接受至少一个客户名称、客户件号或后续工艺快照字段，加expected_version和idempotency_key。字段可显式null；长度上限分别为200、150、50。仅active/empty框允许编辑，按当前qr.metadata能力和订单范围校验；版本冲突409，成功递增框版本并追加前后快照审计。非空next_process_code须属于本框固定路线尚未经过的后续步骤，编辑快照不执行工艺推进，也不修改身份、订单、实际产品或既有历史。

首次扫码机台只给当前用户票据；选单核验有效机台分配并建立context_id。30分钟无业务写入失效，机台状态完成或分配关闭立即失效，不同机台互不覆盖。再次扫同机台须有明确当前选单上下文，不能自动完成第一单或全部单；完成接口还须校验该次扫码意向及有效版本。

机台候选响应包含实际route_code/route_revision，不能把数据库ID显示成版本。选单省略state_id时使用产品当前发布路线；显式state_id可选择已有旧路线状态并校验该固定路线，已有框仍可登记，旧路线不能绑定新框。主管或本单负责人可建立只读选单用于更正/用途分配，不因此获得普通登记或完成权限。客户端各机台上下文只存页面内存，刷新后重新扫码选单。

在产数量使用覆盖值current_qty，不累加扫描；锁状态及框，校验state_version与expected_version。完成后普通登记拒绝，主管更正使用独立入口、非空reason及历史版本；后续工艺开始后不改其当前框/下游事实。完成时按该机台工艺份额比较目标量，数量差异提示但可确认完成。

产出只在首次产出步骤建立来源；source_quantity_id→BoxProcessQuantity，订单/实际产品/框由来源推导。默认订单量=min(实际可分配量,剩余需求)，余量备货；授权主管/本单业务可调，无额外审批。两项非负整数、合计available_qty，订单量不超服务端计算剩余需求。当前分配排除旧值再计算余量，锁实际产品需求防重复占用。数量变更与分配同事务；已人工调整且新量无法满足时冲突，不静默恢复默认。

## 工艺推进、拆框与转换

推进只允许固定路线合法下一步，记录出入量和原料，不产生第二份产出。next_process_code编辑不能跳过推进校验。

已实现advance的context_id指向目标机台、订单产品和下一步骤。当前框须active且已有正数工艺数量；来源和目标暂停时均拒绝。允许上一机台工艺已经完成，其关闭的上下文不会阻止新的目标上下文流转。事务锁产品需求→按ID排序状态→框，校验框/目标状态版本，新增目标BoxProcessQuantity的input_qty与上一工艺出量快照，继承material_batch_id/source_quantity_id。首次产出工艺仍只在保存数量时初始化订单用途；不能在同一道工艺的其他机台重复建立来源。

数量首次保存可提供有效material_batch_id（既有int4整数）；旧调用可省略。已有工艺来源不可替换，后续工艺只继承。此关联不扣原材料重量，不代替US6规格比较。trace返回missing_material_source及material_lineage_incomplete，历史缺失、循环、断链不得伪造完整来源；历史无物料主数据/余重允许null。

scan额外返回latest_event（最近非scan业务事件）；events保留包括scan在内的全部事实，按(occurred_at,id)倒序、before_id定位同框游标，每页1～100默认50。trace初始含最近5条事件及next_cursor，其他历史通过events继续读取；quantities/relations/exceptions/conversions使用page/page_size，均返回总数。跨订单父子关系仅在两边订单均可见时返回；不通过快照泄漏隐藏订单。

拆框数量>0且<=父框当前量；子QR池内unused，用途order_qty+stock_qty=quantity且不超父余额；同单子框继承来源。跨单仅主管/源单负责人选择兼容且剩余需求足够的目标产品配置，父保留原单，子一次绑定目标单，记录来源/目标及快照。已有下游工艺/转换/出库事实时禁止直接改旧用途或跨单转移；失败全部回滚。父余量0不能作为有数量框流转或再拆，余量>0允许。

已实现split返回201，校验父框expected_version及来源allocation_version；跨单还必须显式给出target_state_id与target_state_version，服务端再次核对需求、有效机台分配和固定路线。只拆首次产出步骤尚未进入下游的有效余额；允许此前已拆过的正余量继续拆，父零余量保留身份并置empty。来源/目标订单都须在账号可见范围，跨单要求实际part_id、B/C产品及完整已发布steps_json与首次产出步骤一致，不只比较工艺名称。

同单每个份额建立自身source_quantity_id及用途记录，子分配的origin_allocation_id指父分配，继承材料和固定路线版本；父当前数量、来源余额、用途同步减少。跨单子数量全部计入目标需求，不新造制造产量；source_snapshot记录源/目标状态、来源数量及拆前用途。锁顺序为排序后的需求→状态→父框→子池项→来源用途，关系/事件/审计/二维码日志和完成意向失效同事务，失败整体回滚，幂等重放不重复扣量。

拆后的首次产出余额禁止普通数量覆盖和历史更正，production行返回quantity_locked/can_correct；进入后续工艺后可登记该新工艺当前数量。最新后续工艺主管更正只更新当前物理量，不回写源用途、其他框或入量快照。trace.split返回允许动作、来源用途版本及分页兼容接收状态，关系附双方当前余量及来源快照。扫码携带split_parent_id时，只向有源框拆分/主管权限的账号核对unused子标签，返回box=null与空allowed_actions；不扩大未绑定池读取或直接绑定权限。

转换create只建立pending_operator_confirmation，proposed_qty默认当前全部，actual_qty待确认前为空。人工manual与服务端pre_authorized都不能直接改产品；目标须明确配置、版本路线和转换授权，不能用客户端trigger_type冒充预授权。全量actual_qty=current_qty原QR保留；部分0<actual_qty<current_qty须有效child_qr_payload，同事务拆子框并转换，父产品和余量不变。来源框版本expected_version和记录conversion_version均检查；确认与取消只产生一个终态。操作工确认必须匹配上下文，管理员不能仅凭等级代理实物确认。

## 异常、暂停与通知

规格由服务端订单和实际卷料事实比较，匹配不建异常；不匹配可确认继续且必须创建异常/两组收件人/outbox。主管或明确订单业务任一确认，remark可空。pause/reconfirm_coil仅阻断该state_id新的数量登记、完成及推进；不控制物理机台。独立resume记录复核卷料和依据，不改原resolution；同状态其他未解除异常仍阻断。

收件组缺负责人或主管时保留pending_configuration，补配置后幂等回补；不得丢弃或随机群发。正常工作器首投递目标60秒内，最多5次自动尝试，四次退避为前次失败后1、5、15、30分钟；超限保留failed及人工重试入口。站内待办有唯一outbox来源，持久化后才标sent；尝试历史不能擦除。

## 错误、幂等和时间

新领域错误{code,message,details?,request_id?}；422保持现有字段验证格式{detail,errors}，旧QR lookup的HTTP200+found=false保留。

| HTTP | code | 条件 |
|---|---|---|
| 400 | INVALID_QR / INVALID_QUANTITY / INVALID_PRODUCT / ORDER_MISMATCH | 身份/数量/产品/归属校验失败 |
| 400 | INVALID_TEMPLATE / INVALID_CAPABILITY / INVALID_IDEMPOTENCY_KEY | 服务层模板、能力集合或请求键无效；schema字段错误仍为422 |
| 401 | 现有认证detail格式 | 缺少/失效/非access票据或账号不存在 |
| 403 | FORBIDDEN | 部门/等级/能力/订单/上下文无权限 |
| 404 | QR_NOT_IN_POOL / ENTITY_NOT_FOUND | 有效完整身份不在池或实体不存在 |
| 409 | QR_ALREADY_BOUND / STALE_BOX_VERSION | 重复绑定或过期框版本，重读后再确认 |
| 409 | IDEMPOTENCY_CONFLICT / STATE_CONFLICT | 同键异请求，或配置/状态/版本冲突 |
| 503 | STATE_CONFLICT | 新QR域遇到AUTH_DISABLED或数据库暂不可用；不返回数据库异常细节 |

关键写入按操作者/动作/实体/请求键唯一持久化内容摘要和结果，同事务提交；同键同请求重放已提交结果，同键异内容409，未完成不能当成功。重放前仍重新检查当前权限；先按用户ID排序取得权限事务锁，再取得请求锁，多实体同类锁按ID排序，需求→状态→框→池项→分配的顺序全域一致。新时间为UTC毫秒及带偏移ISO8601，前端按Asia/Hong_Kong展示。日志只记安全错误码，不输出原始未知扫码、票据、认证头或连接设置。

现有前端认证绕过配置仍是上线前置整改项；本轮没有修改真实账号授权或全局认证开关。浏览器和API验收使用独立数据库、合成账号及真实JWT；页面软件行为、A4 PDF、系统打印对话框和实物扫码分别记录，不以客户端接口测试或PDF代替物理打印验收。
