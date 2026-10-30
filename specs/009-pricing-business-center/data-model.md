# 数据模型与后续设计

> 2026-10-30 实施说明：当前使用 `costing_tasks`、`costing_items`、`costing_revisions` 三表；明细保留 source_reference，版本以 JSON 固定 inputs/result/context。`parts.surface_treatment` 和 `quote_groups.surface_rule_snapshot` 为新增 JSON。本文其余扩展实体及 finalized/superseded 工作流仍属后续规划；实际请求/响应以 [接口契约](contracts/pricing-costs.md) 和 schemas/costing.py 为准。

配套：[计划](plan.md)。此文描述拟新增模型，不代表数据库已经迁移。字段类型及表名在实施时结合现有迁移链确认。

**当前范围**：首版简易核算含材料、表面处理、可选特殊成本及可选模摊；旧术语 basic/基础成本对应该模式。comprehensive/综合成本为后续详细分析预留，首版不开放；C/D/E/F 模型为后续设计，不要求随首版建表。

## 共享计价规则与重量依据

报价和核算引用同一材料价格/废料价及表面收费资料和共用计价服务，每次保存 price_source_id/version、rule_id/version、适用单位和币种税口径及来源值快照。已有 material_dict、treatment_dict、customer_*_prices、报价组快照按业务含义适配，先盘点有效数据与缺项，不复制出另一套核算专属价目，也不将字典参考价静默写入历史报价。

重量输入保存 gross_weight、gross_weight_unit/source、allocation_basis、actual_net_weight、quoted_gross_weight、quoted_utilization_pct、quote_group_item_id/quote_id、net_weight_basis（measured/quote_utilization）、derived_net_weight。实际净重优先；缺实际值时用报价重量及利用率推算并标明估算。派生净重不自动写 parts。共用规则识别克/kg、百分数及已分摊重量；缺利用率或费率不采用前端空值兜底。

## 复用的身份关系

`Customer → PartCustomerAlias → Part → ToolingPart → Tooling`；`PartToolingSpec` 绑定具体 `(part_id, tooling_id)`。成本明细保存所选身份，不以名称或去掉后缀的件号做持久主键。

`Quote.part_id/customer_id`、`PriceAccount.part_id/customer_id` 为来源候选；必须核对归属。客户件号一对多零件时，各方案成本分别计算；客户销量不能随方案数量放大。

## 零件表面处理主数据（parts 扩展）

新增 `parts.surface_treatment`（拟 JSONB），承载统一的当前处理要求，建议结构：

```json
{
  "status": "pending",
  "revision": 1,
  "items": []
}
```

- status：pending（待确认）、none（明确无需处理）、required（需要处理）；既有无资料零件迁移为 pending，不能默认 none。
- items：每项包含稳定 item_key、sequence、method_code/name、requirements（颜色、膜厚及单位、标准等适用资料）、remark、source（图纸/导入/人工及来源位置）。字段随处理方式校验，不强制所有方式填写相同技术参数。
- none 时不得有活动处理项；required 时至少一项且处理方式明确；pending 可保留尚未确认的候选要求。删除项的旧 item_key 不复用于另一种处理。
- revision 为处理要求版本；沿用零件编辑器 updated_at 乐观锁和变更历史，一次事务更新主数据与审计。JSON 通过 Pydantic 类型和数据库基本结构约束验证。
- 当前要求唯一数据来源为 parts；零件编辑与成本核算页都可写入，复用同一服务、字段权限、updated_at 并发校验与审计。报价/生产界面展示引用，不另建当前要求副本。
- 核算页“保存表面处理”仅提交明确的处理资料变更，后端在同一事务更新 parts、requirements revision 与审计；返回完整规范化处理项和新版本。审计含核算 task_id/item_id（有时）及变更前后值。零件编辑权限按既有规则检查，核算读取权限不能自动获得主档写权限。
- 处理要求独立保存，不依赖材料价等成本资料是否完整；成功后当前核算草稿更新引用，草稿未保存状态单独保留。关闭/取消成本草稿不回滚已保存的主数据，旧核算版本不随之变化。
- 客户端只提交用户修改字段；新增、修改、删除须有明确意图，未加载或空白表单不能替换整个现有列表。版本冲突不自动合并或覆盖，返回当前版本供人工核对；同一请求重试不得重复追加处理项。
- 成本/报价费用引用 part_id、treatment_item_key、requirements_revision，并保存要求快照、报价/补充计价来源。多项处理可分别计费；技术项有记录不表示费用已知。变更项目集合后旧费用不自动转挂新项目。
- 喷涂实际进度、完成时间和批次保留在生产处理记录，不写入技术要求 status。旧 spray_status/spray_stamped_at 先核对使用与语义再迁移；默认 pending 不能推断需要喷涂、无需处理或处理完成。
- 已有 prices.surface_treatment、quotes.treatment_items、备注及导入表中的技术要求先按零件汇总来源；费用与技术要求分开映射。有冲突时保留原值供核对，不以最新记录直接覆盖。
- 旧报价/台账中历史要求继续作为快照读出；不再作为当前要求的可编辑主数据。移除旧字段前检查全部调用方并验证兼容路径。

## 量产方案核算资格

所选 Tooling 必须属于已确认的连续模或工程模量产方案。用明确的 mold_type 分类映射，不以 is_continuous=false 等价工程模，也不以零件量产状态代替模具分类。分类字段相互矛盾或参考来源冲突，返回 needs_review；明确其他类型返回 excluded；只有 eligible 可新增、试算或保存新核算。历史类型别名需有明确映射，不通过“名称包含工程模”等模糊规则放行混合类型。

资格为服务层统一派生值，候选响应提供 eligibility/status/reason/source；版本 identity_snapshot 固定 mold_type、is_continuous、eligibility_basis。原始类型变更后保留旧版本，复制或重新核算按当前资格检查；不从参考表直接更新模具主档分类。

## A/B：核算任务、明细与版本

### CostingTask（拟表 costing_tasks）

- id、task_no（唯一）、name、customer_id、as_of_date、remark。
- status：draft / archived；version（乐观锁）、created_by/at、updated_by/at。
- 一个任务一个客户；跨客户分析通过查询汇总，不在同一明细静默改客户。

### CostingItem（拟表 costing_items）

- id、task_id、part_id、part_customer_alias_id、tooling_id、tooling_spec_id（可空，但自动计算所需字段必须齐全）、scheme_key。
- quote_id、price_account_id 等明确来源引用，可空；remark、version、latest_revision_id。
- 同任务中同一身份与方案的重复加入由幂等键和唯一约束阻止；不同有效方案允许并存。
- 验证 alias.customer_id 与任务客户相同，alias.part_id 等于所选零件；tooling_parts 存在对应关系；spec.part_id/tooling_id 一致。已删除、失效或待复核对象不自动确认。

### CostingRevision（拟表 costing_revisions）

- id、item_id、revision_no（组合唯一）、previous_revision_id、created_by/at、reason、rule_version。
- mode：首版仅 basic，界面称“简易成本核算”；comprehensive 作为未来详细分析方向，当前不开放。workflow_status：draft / finalized / superseded。
- completeness：complete / incomplete；missing_fields 和 issue_codes，与 workflow_status 分开。
- identity_snapshot：当次客户件号、本厂名称、模具和规格展示信息。
- inputs_snapshot：材质、规格、毛重/投料重、净重、单位、密度、分配方式、单价、费用及各自来源。
- results_snapshot：分项、已知小计、完整合计、舍入规则、可选售价及差额、成本范围。
- 已保存版本不可就地改输入/金额；修改通过新版本，原来源失效也保留快照。
- finalized 仅允许所选范围完整且适用业务门槛通过；补充资料资格未确认时可保存草稿版本。

### CostingInputSource / CostingExpense（拟子表）

- Source：revision_id、field_path、source_type（part/tooling_spec/quote/price_account/material_dict/import/manual）、source_id、source_version/updated_at、source_sheet/row/cell、captured_value、unit、captured_at、note。
- Expense：revision_id、category、name、selection_state（excluded/not_applicable/known/unknown）、calculation_method、quantity、quantity_unit、rate、rate_unit、amount、currency、tax_basis、source_ref。
- 表面处理 Expense 额外保存 part_id、treatment_item_key、requirements_revision 及要求快照，关联到 parts 的对应处理项；部分旧报价只有总额时明确标记 aggregate_quote，不擅自分摊为多个项目金额。
- 首版 Expense category 为 material / surface_treatment / special_cost / tooling_amortization。特殊成本逐项说明原因与依据，模摊独立类别和选用状态，不重复归入特殊成本；两者均允许 excluded 且金额 null，不影响完成。选用后金额/分摊依据未知仍为 incomplete。模摊拟保留 tooling_id、source_amount、allocation_qty、unit_amount、basis，但具体计算方式须确认后启用；不默认读取模具寿命或年销量作分母。完整性不依赖详细分析分类。
- 原始、补充来源均可保留，但 applied_source 必须唯一明确；表面处理替换项通过 replaces_expense_key 关联，同项只算一次。
- equipment_bundle_id / included_categories 表明综合设备费率已包含哪些项，和拆项互斥或明确扣除。
- 金额用 Decimal/Numeric，禁止浮点金额计算；未知保存 null，不转换为 0。单位/税/币种不兼容时完整合计与差额率为空，并附具体原因。

## 导入预览（A/B）

ImportPreview：id、owner_id、file_hash、created_at、expires_at、status。

ImportRow：sheet、row_no、raw_cells、candidate_identity_ids、matched_identity、match_status（exact/ambiguous/unmatched/conflict）、field_differences、chosen_sources。

提交时再校验候选归属、权限和源版本；所有有效行一次事务写入任务，失败无部分提交。幂等键绑定预览与选择摘要；相同重试复用结果，换选择需新提交版本。未决行必须明确保留或跳过并返回行级结果。上传限制、临时文件保留与清理策略在实现时配置；不把原始 Excel 任意文本解释成命令或外部路径。

## D：期间销售价格（拟新增，保留旧年度表）

SalesPricePeriod：id、customer_id、commercial_identity_id、unit、currency、tax_basis、unit_price、effective_from、effective_to、approval_status、source、previous_price_id、version、created_by/at。

commercial_identity_id 为新增明确的客户销售身份：绑定客户件号/版本及允许的零件集合。初版可用唯一已确认 alias；同件号多零件共享售价必须显式建立映射，不能仅按字符串自动合并。该实体用于统一售价、销量与多工艺方案之间的关系；成本方案不是销量汇总键。

- 同一销售身份及计价口径的已确认有效区间不重叠；用数据库约束或事务锁同时防止并发冲突。
- 待审批申请单可以重叠；批准并形成适用价格前必须检查冲突。
- 既有年度价格保留 legacy_annual 来源标记；不能无依据自动生成 1 月 1 日至 12 月 31 日的正式区间。
- 旧调价审批是否可复用以其操作对象为准；现有材料/表面处理调价不直接当作产品销售价审批。
- 价格确认权限与日期边界受 R6，精度/税口径受 R7 控制。

## E：发货计价与修正

ShipmentPricingBasis：id、shipment_line_id、revision_no、is_current、commercial_identity_id、sales_price_period_id、pricing_date、quantity、unit_price、amount、currency、tax_basis、status、missing_reason、price_snapshot、created_by/at。

- quantity 来自 shipping_shipment_lines.qty，客户与零件来自订单及订单行，实际确认时间来自 shipping_shipments.confirmed_at；转换成本地计价日时明确时区。
- 每条发货明细最多一份当前计价依据；汇总按当前依据或修正差额口径计算，不能同时累加新旧版本。
- status：priced / pending_identity / pending_price / conflict / free_confirmed；free_confirmed 需免费依据；未知售价的 amount 为 null。
- 修正追加 ShipmentPricingCorrection，引用旧依据、新依据、原因及差额；原发货、原依据不删除。

## F：现场成本来源及分配

CostEventAllocation：revision_id、event_type、event_id、event_revision、order_product_id、process_id、machine_id、tooling_id、time_category、duration/unit、output_source_id、allocated_qty、allocation_basis、allocation_fraction。

- 现场总跨度、净生产、人工投入、维修和等待独立记录，不互相推定。
- 单个来源对同一核算版本的分配引用唯一；多个对象共享来源时，分配比例合计不得超 1，数量不得超有效产出。
- 反复扫码和拆框不增加有效来源总量；来源更正通过新版本与差异记录反映，不改旧快照。

## 数据演进与保护

远期受控构想仅作设计备注：受控后参数由文控人员更新，具体字段范围与角色方案未来再设计。本轮不增加 control_status、文控角色/权限表或受控校验；现有 part_status 不代表受控。未来若启用，在所有 parts 写入入口共用的服务中统一校验，并复用审计与快照；不提前改变当前核算页写回行为。

新增核算表和增量关系，不批量覆盖 parts/tooling/quotes/prices。历史字段单位核对后再设计转换；迁移前在副本验证行数、外键、金额及旧查询。回退先关闭新功能入口，保留已录核算数据；任何会删除真实业务数据的降级迁移需另行授权。
