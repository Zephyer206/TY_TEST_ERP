# 简易成本核算接口契约

2026-10-30。本文件记录已实施 A/B 契约；详细分析、期间价格、应收与零件受控均未开放。路径相对统一 `/api/v1`。注册源为 `shared/api/registry.js`，前端通过 `frontend/src/api/costing.ts` 和唯一请求客户端调用。

所有下列端点 auth=true、lifecycle=active，沿用现有 role_level>=2。当前没有新增客户数据隔离或文控权限体系。

| Key | Method | Path | 作用 |
| --- | --- | --- | --- |
| partTreatments.detail | GET | /parts/{part_id}/surface-treatment | 获取主档当前要求 |
| partTreatments.save | PATCH | /parts/{part_id}/surface-treatment | 独立保存主档及审计 |
| costing.catalog | GET | /costing/catalog | 共用材料价与收费规则 |
| costing.materialPreview | POST | /costing/material-preview | 共用材料计算 |
| costing.quotationPreview | POST | /costing/quotation-preview | 共用报价材料与表面计算 |
| costing.candidates | GET | /costing/candidates | 客户件号/零件/模具/规格候选 |
| costing.tasks.list | GET | /costing/tasks | 最近200个任务，可按客户筛选 |
| costing.tasks.create | POST | /costing/tasks | 新建任务 |
| costing.tasks.detail | GET | /costing/tasks/{task_id} | 明细及最近保存结果 |
| costing.tasks.addItem | POST | /costing/tasks/{task_id}/items | 单个方案幂等加入 |
| costing.context | GET | /costing/items/{item_id}/context | 读取身份和实时来源 |
| costing.preview | POST | /costing/items/{item_id}/preview | 无副作用试算 |
| costing.revisions.create | POST | /costing/items/{item_id}/revisions | 后端重算，追加版本 |
| costing.revisions.list | GET | /costing/items/{item_id}/revisions | 最近100个完整版本快照 |
| costing.importPreview | POST | /costing/imports/preview | 首工作表逐行匹配，不写主档 |
| costing.export | GET | /costing/tasks/{task_id}/export | 固定查询集合的全部保存版本CSV |

## 主档写回

PATCH 请求：`expected_revision`、`surface_treatment: {status,revision,items}`、`source`。status 为 pending/none/required；items 含稳定 item_key、name、requirements、source。required 至少一项，none 项目必须为空。同样内容重复保存不再追加；不同内容的过期版本返回409。行锁下将 parts 主档和 audit_logs 原子保存。响应为 part_id、surface_treatment。

零件详情与核算页使用同一个编辑组件。保存处理要求不依赖材料或费用完整；主档成功与核算版本成功分别显示。旧 spray_status 等字段保留，不擅自从执行状态推导技术要求。未来受控及文控权限未实施。

## 身份与价格来源

候选参数 customer_id、keyword、limit(1..200)、offset；返回 total/items。包括 excluded/needs_review 及原因，只有明确连续模或工程模 eligible 可加入。提交 alias_id、part_id、tooling_id、spec_id，后端复核客户归属、零件模具关系和精确规格；不将 is_continuous=false 当工程模。可带 source_reference 保存导入行依据，不写零件参数。

试算请求为 `price_source`（catalog/quote/supplement）、material_id、quote_item_id、source_note、calculation。catalog 从 material_dict 取密度/原料/废料价格；quote 从精确客户件号的报价组条目取保存价格及利用率；supplement 必须填写依据。服务端重取来源，优先当前零件实测净重，不信任客户端覆盖主档重量。手工重量补充也必须有依据。

`calculation.mode` 仅 basic。material 包含 TWP、density、pieces_per_blank、gross_weight_g、net_weight_g、quoted_gross_weight_g、utilization_pct、material_price、scrap_price；重量g，价格元/kg。服务用 Decimal，结果保留6位。投料金额减废料回收；无实测净重时报价投料重×利用率估算净重并标识 quote_utilization，不回填主档实测值。净重大于投料重、负材料成本等不产生完整合计。

表面费用 treatments 逐项引用主档 item_key；rule_id 引用共用规则，或手工填写 method（piece/net_kg/batch）、rate、quantity、source。共用规则目前支持 manual+元/件、net_weight+元/kg；批次费用手工填写明确分摊数量与依据。pending 不等于无需处理。special_costs 与 tooling_amortization 独立 selected，默认未选；选用后缺金额或依据则 incomplete。模摊首版为有依据的单件金额，未定义自动寿命/年量分摊。

参考售价 reference_price 可空，comparison_basis 未确认时不算有效差额；支持两者含税/两者不含税的显式确认，不做税额自动换算。

## 结果与历史

preview 返回 calculation、context、result、source_token。result 包含 material、surface_amount、optional_costs、known_subtotal、total、completeness、issues、comparison 与 rule_version。未知与未选不当作有效零成本；incomplete 允许保存，total 为空。

保存额外提交 expected_version、request_id、reason 和预览所得 expected_source_token。后端锁明细、重新计算、比较源摘要后追加不可变版本；版本/来源过期409。同一请求标识同内容返回原版本，不同内容409。旧 inputs/result/context 不随主档、价格或规则更新。历史读取不再用当前模具类型过滤。

报价组更新可传 surface_rule_id 和 refresh_surface_rule。保存规则快照；无显式刷新时保留旧快照。原 surface_treatment_fee 作为兼容展示金额，共用按净重收费按各报价条目分别计算。报价与核算调用同一 Decimal 服务。

## 导入导出

导入 multipart file + customer_id，xlsx<=5MB、展开<=30MB、首表<=1000数据行/80列；支持客户件号/原图产品编号/规格型号及模具列。逐行返回 sheet/row、原值、候选和 exact/needs_review。后缀冲突和多方案必须人工核对；使用标准 addItem 逐个确认，不设自动批量覆盖主档接口。原表净重/毛重只可补充本次核算草稿。

导出UTF-8 BOM CSV，查询时固定全部已保存版本集合，包含身份、版本、四类成本、完整性、缺项、来源、重量依据及单位。件号等文本有公式前缀防护。不会导出尚未保存的编辑内容。

## 错误及限制

401未认证；403角色不足；404记录不存在；409版本/来源冲突；413文件过大；422输入、身份、模具资格或文件格式错误。沿用既有错误详情文本，前端保留失败草稿。生产联动和报价技术要求自动回填尚未扩展；本次统一的是 parts 主档和核算/零件详情维护及共用收费规则。
