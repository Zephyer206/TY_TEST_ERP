# Quickstart：二维码追溯系统分阶段验收

本指南覆盖原材料二维码基线和产品框二维码扩展。命令中的 TOKEN、ID 使用测试环境值，禁止写入真实凭据。

2026-10-27当前范围：31项新领域设计端点中22项已挂载为active，另9项仍待实现；基线32个旧QR端点已补齐共享registry、领域wrapper和请求/响应类型。已实现订单配置、机台生产、连续工艺推进、材料追溯及拆框。500标签的A4软件PDF已验证为24页；系统打印对话框、实体打印和纸质扫码尚未验收。下方现场流程使用另行准备且已迁移的测试环境，业务库尚未部署新迁移。

测试入口：在仓库根目录设置`PYTHONPATH=backend`，使用项目`backend/.venv/Scripts/python.exe -m pytest backend/tests/qr/ -q --tb=short`。夹具创建并按名称/OID验证清理专用测试库，不升级业务库；依赖及边界见[测试说明](../../backend/tests/qr/README.md)。数据结构证据见[phase1-acceptance.md](./phase1-acceptance.md)，上一批后端池/打印/绑定及客户端模块证据保留在[phase2-backend-acceptance.md](./phase2-backend-acceptance.md)，不把历史报告视作本轮页面或物理打印验收。

## 0. 前置条件

本批机台生产入口为“制造执行 → 机台生产”（`/product-box-production`）。先由获授权的配置人员通过PUT订单qr-context保存完整产品/负责人/版本路线及各机台份额；嵌套字段见[订单配置合同](./contracts/order-routing.md)，不从旧计划自动猜测配置。

操作工先扫机台，再明确选择订单、产品和工艺；扫描unused产品框后一次绑定。每次保存数量覆盖本框当前值，例30→25得到25。页面按机台保存独立选单，刷新会清除内存上下文，需重扫。冲突时先“重新读取”，核对当前数量及版本后再提交，不自动重放写入。

完成前再次扫描当前机台建立完成意向，核对已保存数量和本机份额；有差异须勾选确认。完成只关闭所选机台工艺，普通数量入口关闭。生产主管用“更正数量”填写实物复核量和原因；主管/本单负责人可“分配用途”，订单量与备货量合计必须等于有效产出，服务端校验剩余需求。完成后仍可查询该状态；不把配置权限或管理等级当作代操作工权限。

隔离验收可用 `serve_qr_ui_acceptance.py --production-fixture` 配合18124专用Vite；101为工人、102为主管、104为401负责人、105为另一订单负责人，入口`/acceptance/<actor>?path=/product-box-production`。票据/JWT只在内存，不保存页面源码。真实业务库迁移、真实账号授权和现场打印另行验收。

1. 后端、数据库和测试前端已启动。
2. 测试库已执行目标 Alembic 迁移；产品框迁移必须在Phase 0收尾通过后先执行独立测试库演练；当前任务与历史清单分别见tasks.md和tasks-material-legacy.md。
3. 已准备仓库/生产操作工、主管、业务人员、管理员账号，以及机台、B/C 订单和合格原材料。
4. 涉及 UI 的验收必须使用真实可控浏览器；API、构建和静态检查不能替代浏览器验收。
5. 新QR域要求启用认证并使用真实登录账号；AUTH_DISABLED返回503，现有前端认证绕过配置必须在上线准备阶段整改。本批诊断验收使用独立服务、合成账号及真实JWT，不修改全局认证或真实授权。

已实现的22项为池list/generateBatch/reprint/printData/confirmPrint，框bind/scan/metadata/saveQuantity/correctQuantity/advance/trace/events/split，production.qrContext/saveQrContext/allocateOutput，machines.scanProduction/selectProduction/productionComplete，以及qrAdmin.capabilities/saveCapabilities。完整清单见[API登记合同](./contracts/api-registry.md)，未实现的设计端点不能直接作为可用入口。

## 1. 原材料二维码基线回归

### 1.1 入库赋码

~~~bash
curl -X POST "http://localhost:8000/api/v1/warehouse/material-batches" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <TOKEN>" \\
  -d '{"material_id": <MATERIAL_ID>, "gross_weight": 5000, "thickness": 0.8, "width": 1250}'
~~~

验证：响应 qr_code 非空且全局唯一；批次状态、当前重量和二维码打印数据正确。

原材料页面的物料与供应商必须来自仓库目录，不混用工程物料主数据。GET `/warehouse/materials`保持 `include_inactive=false` 默认值；仅在历史名称/筛选展示时显式使用 `include_inactive=true`。追溯页读取历史目录后，入库选择仍按is_active=true筛出有效材料和供应商。目录使用skip/limit分页，避免只加载首50项导致旧批次名称缺失。

### 1.2 扫码、流转和分卷

~~~bash
curl "http://localhost:8000/api/v1/warehouse/material-batches/scan/<BATCH_ID>" -H "Authorization: Bearer <TOKEN>"
curl "http://localhost:8000/api/v1/warehouse/material-batches/<BATCH_ID>/trace" -H "Authorization: Bearer <TOKEN>"
curl -X POST "http://localhost:8000/api/v1/warehouse/material-batches/<BATCH_ID>/split" \\
  -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \\
  -d '{"splits":[{"width":400,"weight":1600},{"width":400,"weight":1600}]}'
~~~

验证：每个子卷有独立二维码；母卷扣减；父子、同胞和扫码日志完整；超量、零量和重复操作被拒绝且数据不变。

## 2. 产品二维码池和一框绑定

### 2.1 批量生成和打印

~~~bash
curl -X POST "http://localhost:8000/api/v1/product-qr-pool/batches" \\
  -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \\
  -d '{"count":3,"print_batch_no":"TEST-001","idempotency_key":"generate-test-001"}'
~~~

验证：返回唯一池项且状态为unused；payload只含稳定身份。生成、打印数据、补打请求均不增加已确认次数；只有作业申请人的打印确认增加次数。新领域ID输出为字符串。

~~~bash
curl -X POST "http://localhost:8000/api/v1/product-qr-pool/print-data" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"item_ids":["<POOL_ITEM_ID>"],"idempotency_key":"print-test-001"}'
curl -X POST "http://localhost:8000/api/v1/product-qr-pool/print-confirmations" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"print_job_id":"<PRINT_JOB_ID>","confirmed_item_ids":["<POOL_ITEM_ID>"],"idempotency_key":"confirm-test-001"}'
~~~

软件版式检查：选择500个标签，A4 3×7每页21张，应生成24页，末页17张；软件PDF结果已验证。现场验收还须实际打开并取消一次系统打印对话框，确认取消后计数不变，再由授权用户选择现场设备打印、确认及扫描纸质标签。系统对话框和实体操作当前尚未验收，不能将导出PDF或确认按钮操作视作出纸证明。

### 2.2 绑定和重复扫码

~~~bash
curl -X POST "http://localhost:8000/api/v1/product-boxes/bind" \\
  -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \\
  -d '{"qr_payload":"<QR_PAYLOAD>","order_product_id":"<ORDER_PRODUCT_ID>","idempotency_key":"binding-test-001"}'

curl -X POST "http://localhost:8000/api/v1/product-boxes/scan" \\
  -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \\
  -d '{"qr_payload":"<QR_PAYLOAD>"}'
~~~

验证：上述为warehouse+qr.bind绑定；生产绑定另需本人有效context_id。订单、产品、客户和路线由服务端配置推导，数量从0开始；池项变为bound，一个二维码只能绑定一个框和订单，重扫只读当前框。池外、已绑定、产品A、第二订单均拒绝。

### 2.3 订单配置读取和标签快照编辑

绑定前读取可见订单的二维码配置；返回的products包含实际B/C产品、路线、机台工艺目标、missing_configuration和can_bind。没有配置时应展示缺失项，不为旧订单猜测路线或负责人；获授权人员可通过PUT配置完整内容及expected_version。

~~~bash
curl "http://localhost:8000/api/v1/production/plans/<ORDER_ID>/qr-context" -H "Authorization: Bearer <TOKEN>"
curl -X PATCH "http://localhost:8000/api/v1/product-boxes/<BOX_ID>/metadata" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"customer_part_no":"TEST-CUSTOMER-PART","expected_version":1,"idempotency_key":"metadata-test-001"}'
~~~

expected_version使用扫码响应中当前框版本。验证：授权账号只可编辑客户名称、客户件号和合法后续工艺快照，成功后版本递增并保留前后值；同键重放不重复审计，过期版本409，越权账号403，二维码、原订单和实际产品保持原值。该操作不执行工艺推进。

## 3. 机台生产和数量覆盖

本节机台生产和数量已实现并完成隔离浏览器验收，见[机台生产验收](./acceptance-production.md)。第4节拆框已实现，第5节异常/转换仍为后续设计验收；第6节工艺追溯已实现。

~~~bash
curl -X POST "http://localhost:8000/api/v1/machines/scan-production" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"machine_qr":"<MACHINE_QR>"}'
curl -X POST "http://localhost:8000/api/v1/machines/production-contexts" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"scan_ticket":"<SCAN_TICKET>","assignment_id":<ASSIGNMENT_ID>,"order_product_id":"<ORDER_PRODUCT_ID>","process_code":"<PROCESS_CODE>","idempotency_key":"context-test-001"}'
curl -X POST "http://localhost:8000/api/v1/product-boxes/<BOX_ID>/quantities" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"context_id":"<CONTEXT_ID>","current_qty":80,"expected_version":1,"state_version":1,"idempotency_key":"qty-test-001"}'
curl -X POST "http://localhost:8000/api/v1/machines/<MACHINE_ID>/production-complete" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"context_id":"<CONTEXT_ID>","confirm_quantity_difference":true,"expected_version":1,"idempotency_key":"complete-test-001"}'
~~~

验证：必须先扫机台再选订单；数量按当前值覆盖而非累加；计划量差异提示但可确认；完成后普通操作工改数被拒绝，主管更正留下前后值审计；二维码仍可进入后续工艺。

### 3.1 连续工艺与材料来源（已实现）

首次登记前可扫描实际MAT原材料或子卷，核对完整存储身份；数量请求可提供material_batch_id。材料输入一经修改，先重新核对再保存；不带材料时明确保留“未记录来源”，不从旧计划猜测。已有工艺来源不可替换，材料关联不扣台账重量，也不代替规格异常处理。

后续工艺先扫描目标机台并明确选择订单/产品/步骤，再扫同一产品框，点击“进入所选工艺”并核对入量。advance的context_id为目标选单，只接受固定版本路线的下一步，不能借修改next_process_code快照跳步。上一机台已完成不会关闭产品框；入量与上一工艺出量形成快照，继承同一材料和首次产出来源。后续数量变化不建立第二份订单产量，表中用途明确标为来源用途。

独立查询入口为“制造执行 → 工艺流转”（`/product-box-trace`），扫描后显示当前产品/订单/数量、路线、各机台数量、材料母子来源和历史事件。“读取更早事件”通过时间/ID游标读取全部历史；失败查询清空旧详情。原材料未记录、断链或循环会明确标示。

隔离验收启动参数`serve_qr_ui_acceptance.py --trace-fixture`，包含三步路线及材料子卷/母卷，使用101操作工与105订单负责人。真实浏览器步骤与1.619～1.716秒实测见[连续工艺验收](./acceptance-trace.md)。本地合成单用户结果不代表现场负载或实体扫码器性能。

## 4. 拆框和父子追溯（已实现）

~~~bash
curl -X POST "http://localhost:8000/api/v1/product-boxes/<PARENT_BOX_ID>/split" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"child_qr_payload":"<UNUSED_CHILD_QR>","quantity":30,"order_qty":30,"stock_qty":0,"expected_version":2,"allocation_version":1,"idempotency_key":"split-test-001"}'
curl "http://localhost:8000/api/v1/product-boxes/<CHILD_BOX_ID>/trace" -H "Authorization: Bearer <TOKEN>"
~~~

验证：父框扣减，子框继承订单、件号、客户和后续工艺；超量、零量、池外 QR 或已绑定 QR 时整笔回滚且父框不变。

在工艺流转页面扫描父框，点击“拆分产品框”。先核对子标签，再输入数量和从来源订单用途中拆出的件数，核对预计父余量。仓库只提供同单；主管/源单负责人可选择账号可见的兼容目标订单和明确接收工艺。目标需求不足、标签已用/池外、超量或版本冲突均不能提交。取消不绑定、不扣量；冲突后点“重新读取父框”并重新核对子标签，不自动重试旧值。

跨单请求另提供target_order_product_id、target_state_id、target_state_version，源/目标均须可见。只能拆尚未进入下游的首次来源余额；拆后首次数量行只读，正余量可继续下一工艺，零余量保留追溯。关联记录分别显示拆出量、双方当前余量及用途，可查看父框/子框；标签编号和快照折叠为辅助信息。浏览器步骤见[拆框验收](./acceptance-split.md)。

## 5. 规格异常和 B/C 转换

~~~bash
curl -X POST "http://localhost:8000/api/v1/coil-spec-exceptions" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"context_id":"<CONTEXT_ID>","material_batch_id":<MATERIAL_BATCH_ID>,"product_box_id":"<BOX_ID>","continue_production":true,"idempotency_key":"exception-test-001"}'
curl -X POST "http://localhost:8000/api/v1/product-conversions" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"box_id":"<BOX_ID>","target_order_product_id":"<TARGET_ORDER_PRODUCT_ID>","proposed_qty":100,"expected_version":1,"idempotency_key":"conversion-test-001"}'
~~~

验证：规格不一致生成异常并通知主管、订单业务人员；任一授权人可确认；全量转换沿用 QR；部分转换必须拆框；未确认自动转换不改变产品和数量。

创建转换只产生待确认记录；另按合同调用confirm接口，由本人有效上下文提交actual_qty、confirm=true及框/转换版本。客户端不能自传trigger_type取得预授权。

## 6. 工艺事件和追溯查询（已实现）

~~~bash
curl "http://localhost:8000/api/v1/product-boxes/<BOX_ID>/events" -H "Authorization: Bearer <TOKEN>"
curl "http://localhost:8000/api/v1/product-boxes/<BOX_ID>/trace" -H "Authorization: Bearer <TOKEN>"
~~~

验证：事件包含扫描、绑定、数量、机台完成、拆框、异常和转换；每条关键记录包含操作者、时间、前后数量和关联框/订单；可反查原材料批次或子卷。

trace/events读取已持久化事实；已提供拆框入口；异常处理与B/C转换业务入口仍待实施，不用空关联列表宣称这些流程已完成。授权管理与全链路审计UI仍按US8后续任务验收。

## 7. 前端验收与扫描

在真实可控浏览器中验证二维码池、绑定、机台扫码、数量保存、拆框、异常确认、B/C 转换、追溯详情和越权提示，并记录浏览器、URL、账号、步骤和观察结果。

~~~powershell
cd frontend
npm run type-check
npm run build
cd ..
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_api_usage.ps1 -FailOnViolation
~~~

新增 API 违规必须为 0；已有违规单独记录为迁移债务。

旧32项库存覆盖另用 `node scripts/verification/verify_legacy_qr_registry.mjs` 验证；该脚本执行实际wrapper和统一请求构造器，但替换为内存transport，不发HTTP、不操作数据库或外部上传。配套 `backend/tests/qr/test_legacy_api_contract.py` 核对真实挂载OpenAPI及两条POST query合同；这些合同检查不能替代本节真实页面验收。

## 8. 验收报告格式

每阶段分别报告：实现结果、实际命令和返回、数据库/API/浏览器观察结果、未通过项（incomplete 或 blocked）以及无凭据泄露确认。

2026-10-24展示原则调整：导航入口为“原材料台账”和“产品框管理”，现有URL保持兼容。先查看物料/产品、重量/数量、状态、订单与工艺；扫码定位、标签生成/补打及追溯标识在辅助入口使用。未绑定标签管理保留编号核对，纸质二维码仍按原尺寸输出。具体真实浏览器证据见[hierarchy-acceptance.md](./hierarchy-acceptance.md)，不替代现场实体打印验收。
