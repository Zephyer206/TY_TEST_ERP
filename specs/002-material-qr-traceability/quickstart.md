# Quickstart：二维码追溯系统分阶段验收

本指南覆盖原材料二维码基线和产品框二维码扩展。命令中的 TOKEN、ID 使用测试环境值，禁止写入真实凭据。

## 0. 前置条件

1. 后端、数据库和测试前端已启动。
2. 测试库已执行目标 Alembic 迁移；产品框迁移必须在 P0 业务澄清通过后执行。
3. 已准备仓库/生产操作工、主管、业务人员、管理员账号，以及机台、B/C 订单和合格原材料。
4. 涉及 UI 的验收必须使用真实可控浏览器；API、构建和静态检查不能替代浏览器验收。

## 1. 原材料二维码基线回归

### 1.1 入库赋码

~~~bash
curl -X POST "http://localhost:8000/api/v1/warehouse/material-batches" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <TOKEN>" \\
  -d '{"material_id": <MATERIAL_ID>, "gross_weight": 5000, "thickness": 0.8, "width": 1250}'
~~~

验证：响应 qr_code 非空且全局唯一；批次状态、当前重量和二维码打印数据正确。

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
  -d '{"count":3,"print_batch_no":"TEST-001","payload_version":"v1"}'
~~~

验证：返回唯一池项且状态为 unused；payload 只含稳定身份；补打不生成新身份且增加补打次数。

### 2.2 绑定和重复扫码

~~~bash
curl -X POST "http://localhost:8000/api/v1/product-boxes/bind" \\
  -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \\
  -d '{"public_code":"<PUBLIC_CODE>","order_id":<ORDER_ID>,"product_code":"B","customer_id":<CUSTOMER_ID>,"current_qty":100}'

curl -X POST "http://localhost:8000/api/v1/product-boxes/scan" \\
  -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" \\
  -d '{"qr_payload":"<QR_PAYLOAD>","operation":"query"}'
~~~

验证：池项变为 bound；一个二维码只能绑定一个框和订单；重扫只读当前框。池外、已绑定、产品 A、第二订单均拒绝。

## 3. 机台生产和数量覆盖

~~~bash
curl -X POST "http://localhost:8000/api/v1/machines/scan-production" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"machine_qr":"<MACHINE_QR>"}'
curl -X POST "http://localhost:8000/api/v1/product-boxes/<BOX_ID>/quantities" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"machine_id":<MACHINE_ID>,"order_id":<ORDER_ID>,"current_qty":80,"expected_version":1,"idempotency_key":"qty-test-001"}'
curl -X POST "http://localhost:8000/api/v1/machines/<MACHINE_ID>/production-complete" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"order_id":<ORDER_ID>,"confirm_quantity_difference":true}'
~~~

验证：必须先扫机台再选订单；数量按当前值覆盖而非累加；计划量差异提示但可确认；完成后普通操作工改数被拒绝，主管更正留下前后值审计；二维码仍可进入后续工艺。

## 4. 拆框和父子追溯

~~~bash
curl -X POST "http://localhost:8000/api/v1/product-boxes/<PARENT_BOX_ID>/split" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"child_qr_payload":"<UNUSED_CHILD_QR>","quantity":30,"idempotency_key":"split-test-001"}'
curl "http://localhost:8000/api/v1/product-boxes/<CHILD_BOX_ID>/trace" -H "Authorization: Bearer <TOKEN>"
~~~

验证：父框扣减，子框继承订单、件号、客户和后续工艺；超量、零量、池外 QR 或已绑定 QR 时整笔回滚且父框不变。

## 5. 规格异常和 B/C 转换

~~~bash
curl -X POST "http://localhost:8000/api/v1/coil-spec-exceptions" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"order_id":<ORDER_ID>,"product_box_id":<BOX_ID>,"expected_spec":"0.8x1250","actual_spec":"1.0x1250","continue_production":true}'
curl -X POST "http://localhost:8000/api/v1/product-conversions" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"box_id":<BOX_ID>,"target_product_code":"C","actual_qty":100,"trigger_type":"manual","confirm":false}'
~~~

验证：规格不一致生成异常并通知主管、订单业务人员；任一授权人可确认；全量转换沿用 QR；部分转换必须拆框；未确认自动转换不改变产品和数量。

## 6. 全链路查询和审计

~~~bash
curl "http://localhost:8000/api/v1/product-boxes/<BOX_ID>/events" -H "Authorization: Bearer <TOKEN>"
curl "http://localhost:8000/api/v1/product-boxes/<BOX_ID>/trace" -H "Authorization: Bearer <TOKEN>"
~~~

验证：事件包含扫描、绑定、数量、机台完成、拆框、异常和转换；每条关键记录包含操作者、时间、前后数量和关联框/订单；可反查原材料批次或子卷。

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

## 8. 验收报告格式

每阶段分别报告：实现结果、实际命令和返回、数据库/API/浏览器观察结果、未通过项（incomplete 或 blocked）以及无凭据泄露确认。
