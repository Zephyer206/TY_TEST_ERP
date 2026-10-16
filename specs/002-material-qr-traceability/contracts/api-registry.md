# API registry / domain wrapper mapping

Implementation must register every endpoint in the shared source `shared/api/registry.js` with key, method, relative path, auth, lifecycle and description. The existing `frontend/src/api/registry.ts` remains the typed bridge. Add a domain wrapper (suggested `frontend/src/api/productBoxes.ts`) and request/response types; pages and components call only that wrapper. Before removing or changing any existing QR endpoint, run `scripts/check_api_usage.ps1 -FailOnViolation` and update all callers and contracts together.

| Registry key | Method | Path | Lifecycle |
|---|---:|---|---|
| `productQrPool.list` | GET | `/product-qr-pool` | active |
| `productQrPool.generateBatch` | POST | `/product-qr-pool/batches` | active |
| `productQrPool.reprint` | POST | `/product-qr-pool/{item_id}/reprint` | active |
| `productBoxes.bind` | POST | `/product-boxes/bind` | active |
| `productBoxes.scan` | POST | `/product-boxes/scan` | active |
| `productBoxes.trace` | GET | `/product-boxes/{box_id}/trace` | active |
| `productBoxes.events` | GET | `/product-boxes/{box_id}/events` | active |
| `productBoxes.saveQuantity` | POST | `/product-boxes/{box_id}/quantities` | active |
| `productBoxes.split` | POST | `/product-boxes/{parent_id}/split` | active |
| `machines.scanProduction` | POST | `/machines/scan-production` | active |
| `machines.productionComplete` | POST | `/machines/{machine_id}/production-complete` | active |
| `coilSpecExceptions.create` | POST | `/coil-spec-exceptions` | active |
| `coilSpecExceptions.confirm` | POST | `/coil-spec-exceptions/{exception_id}/confirm` | active |
| `productConversions.create` | POST | `/product-conversions` | active |
| `productConversions.confirm` | POST | `/product-conversions/{conversion_id}/confirm` | active |
| `notifications.list` | GET | `/notifications` | active |

This table is an implementation inventory, not permission to change the registry before P0 business decisions are closed; final endpoint names and status fields must be frozen in the contract review. Existing material/machine/process-flow QR endpoints require an inventory pass and baseline regression mapping before reuse or deprecation.

## 2026-10-13 已确认业务规则与新增映射草案

FR-031 已确认状态名称及站内通知/待办，FR-032 已确认主管/本订单业务人员可调整分配、无额外审批，FR-033 已确认全量沿用原码、部分拆框并由操作工确认实际数量。正式状态映射见 `product-box-qr.md`；通知投递状态与异常确认状态分列，转换创建只能进入待操作工确认。确认 wrapper 必须传递实际数量、父框版本、幂等键，部分转换还必须带池内未绑定子 QR。

数量分配的接口建议如下；产出来源与订单结构待 D-P004 冻结，尚未写入运行中的 registry 或挂载后端路由。

| Registry key | Method | Relative path | Auth | Target lifecycle | Description |
|---|---|---|---|---|---|
| `production.allocateOutput` | POST | `/production/output-allocations` | true | active | 授权主管或本订单业务人员保存当前订单/备货分配，校验来源数量、剩余需求、版本及幂等，无额外审批 |
| `productConversions.cancel` | POST | `/product-conversions/{conversion_id}/cancel` | true | active | 在授权范围内取消待确认转换，保存审计，产品和数量不变，确认/取消并发只能得到一个终态 |
| `productQrPool.printData` | POST | `/product-qr-pool/print-data` | true | active | 按已存二维码身份生成批量打印数据与持久化作业，尚不确认物理打印成功 |
| `productQrPool.confirmPrint` | POST | `/product-qr-pool/print-confirmations` | true | active | 授权打印人员确认作业项已打印，幂等增加确认次数并保留原身份 |

新增取消接口的角色范围和版本字段仍待 D-P006/合同评审冻结。实施时先登记共享事实源，经 `frontend/src/api/registry.ts` 提供类型桥接，再更新领域 wrapper、请求/响应类型、后端合同及相关测试；本轮仅同步设计文档。

打印工程基准见 [qr-printing.md](./qr-printing.md)，打印授权待 D-P006。默认上限 500、A4 通用模板、系统打印对话框由 D-P005 确定；新领域错误码及幂等/时间/重试约定按 D-P007 和 `product-box-qr.md`。这些是工程选择，不计入业务问答条数。
