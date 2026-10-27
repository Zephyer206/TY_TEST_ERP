# 产品框 API registry 实施清单

**基准**：2026-10-27；31项新领域设计清单中共22项已登记并挂载，余9项待实现；已交付22项均为auth=true、lifecycle=active，未向业务库部署。基线32个旧QR端点已全部补齐registry、领域wrapper和请求/响应类型映射，旧接口保留。

新增接口先登记 shared/api/registry.js，再由 frontend/src/api/registry.ts 类型桥接，frontend/src/api/productBoxes.ts 领域模块和 frontend/src/types/productBox.ts 请求/响应类型使用。/api/v1 只在 request client 配置；页面不得直接写路径或调用 axios/fetch。

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

每个端点交付时同步 registry、wrapper、类型、后端路由合同与测试。此表不要求提前将未实现接口放进运行时 active registry；旧接口保持。删除前必须执行 scripts/check_api_usage.ps1 -FailOnViolation。

当前22项的实际类型见 `frontend/src/types/productBox.ts`、`productProduction.ts`、`productTrace.ts`、`productSplit.ts`，调用见 `frontend/src/api/productBoxes.ts`、`productProduction.ts`、`productTrace.ts`、`productSplit.ts`；bigint身份通过字符串往返，旧int4引用保持整数。上一批新增`productBoxes.advance/trace/events`；本批新增`productBoxes.split`，scan增加可选split_parent_id的范围内子标签预览，trace增加拆分动作/版本/目标及父子余量，生产响应增加quantity_locked/can_correct。异常、通知及转换的其余9项仍未交付。选单请求的state_id可显式定位旧版本状态；省略则取产品当前发布路线。

基线B001～B032全部映射到共享registry，旧领域类型集中在 `frontend/src/types/legacyQr.ts`；原材料和扫码日志调用使用 `frontend/src/api/materialQr.ts`，通用二维码使用 `frontend/src/api/qr.ts`，机台和生产/流转卡沿用 `frontend/src/api/machines.ts`、`frontend/src/api/production.ts`。`scripts/verification/verify_legacy_qr_registry.mjs` 将这32项与冻结库存比对，并用实际wrapper及请求构造器检查方法、编码后路径、query和body；`backend/tests/qr/test_legacy_api_contract.py` 再与应用OpenAPI核对。旧机台维修扫码和投料校验的POST参数保持在query，不改成JSON body；旧lookup的HTTP200及found=false语义保留。使用扫描零违规与上述32项覆盖检查分别记录。

原材料页面另使用已登记的 `warehouse.qrMaterials`（GET `/warehouse/materials`）、`warehouse.qrSuppliers`（GET `/warehouse/suppliers`）读取仓库目录，不能混用独立的工程物料主数据；选单可使用 `production.plans`（GET `/production/plans`）读取plan_no。材料目录的 `include_inactive` 默认false，保持既有调用方仅见有效物料；历史目录展示须显式传true。原材料追溯页为历史名称/筛选opt-in读取含停用物料的目录，入库下拉仍只列is_active=true的材料和供应商。这三项辅助旧域入口不计入上表31项新领域清单。

A4软件验收已覆盖500标签、24页PDF；系统打印对话框、实体打印和纸质扫码仍单列未验收，详见 [qr-printing.md](./qr-printing.md)。

权限、订单来源及打印分别以 permissions.md、order-routing.md、qr-printing.md 为准，产品框合同见 product-box-qr.md。所有关键写入有持久化幂等及版本检查。
