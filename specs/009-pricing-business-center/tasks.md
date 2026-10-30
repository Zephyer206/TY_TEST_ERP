# 简易成本核算实施任务

2026-10-29。范围 A0—B4；详细分析、期间售价、正式应收及零件受控不在本轮。
依据：spec.md、plan.md、data-model.md、contracts/pricing-costs.md。单件模摊首版支持有依据的显式金额，自动分摊另议。阶段完成必须同时有实施和验收证据。

## 基础与主数据

- [x] T001 在 backend/app/schemas/costing.py 和 backend/app/services/costing_calculator.py 实现共用 Decimal 材料及收费计算，验证缺项、利用率、单位与可选项。
- [x] T002 在 backend/app/models/costing.py、backend/app/models/part.py 及 alembic/versions/20261029_simple_costing.py 增加核算持久化和表面处理字段，验证增量迁移不影响旧数据。
- [x] T003 在 backend/app/api/part_treatments.py 实现共用表面处理读取/保存，验证身份、角色、版本、审计和失败原子性。
- [x] T004 在 frontend/src/components/SurfaceTreatmentEditor.vue 和 PartEditorDialog.vue 提供统一录入，验证保存后重开及冲突行为。

## US1 资料关联与共用计价

- [x] T005 [US1] 在 backend/app/api/costing.py 和 backend/app/services/costing_service.py 实现客户别名/零件/模具/规格候选及报价来源，验证范围和关系不可绕过。
- [x] T006 [US1] 在 shared/api/registry.js、frontend/src/api/costing.ts、frontend/src/types/costing.ts 注册并封装契约，覆盖零件处理和核算调用。
- [x] T007 [US1] 在 backend/app/api/quote_groups.py 和 frontend/src/views/projects/QuoteGroupDialog.vue 接入共用计价计算，验证同输入与核算一致。

## US2 核算与版本

- [x] T008 [US2] 在 backend/app/api/costing.py 实现任务、明细、预览、追加版本与重开，验证来源变化、重复请求和历史保留。
- [x] T009 [US2] 在 frontend/src/views/price-management/Costing.vue 实现清单、方案选择、材料/表面/可选特殊与模摊编辑、保存和版本详情。
- [x] T010 [US2] 在 frontend/src/router/index.ts 和 frontend/src/views/layout/index.vue 增加简易成本核算入口，保留现有改动。

## US3 导入与导出

- [x] T011 [US3] 在 backend/app/api/costing.py 和 Costing.vue 实现参考表逐行匹配预览及显式加入，冲突不自动写回主档。
- [x] T012 [US3] 在 backend/app/api/costing.py 实现保存版本明细 CSV 导出，验证来源、空值、单位与文本公式防护。

## 验收

- [x] T013 在 backend/tests/pricing/ 增加业务计算、API/数据关系、并发/幂等及迁移集成验证。
- [x] T014 执行 API 使用扫描、前端类型/build、原零件/报价回归；记录实施与检查结果。
- [x] T015 使用真实浏览器验收零件补录、核算关联/计算/保存/重开/可选项/导入导出，记录 URL、会话与证据到 acceptance.md。

依赖：T001→T002→T003→T004；T002→T005→T006→T007/T008→T009→T010→T011/T012→T013→T014→T015。检查失败则修复并重新验证；仅编译通过不能勾选 UI 验收。

实施与验收证据见 [acceptance.md](acceptance.md)。T015 核心浏览器流程及参考表上传、逐行确认、重复确认、来源保留、待完善/完整版本保存已通过；本次改用应用内浏览器完成文件选择，不修改扩展权限。T014 的旧零件编辑测试失败另列，未声称全部历史测试通过。

## 京西实际任务补充

- [x] T016 复核20行与已有任务，建立任务1并只加入8个明确方案，保存行来源，不补造成本或改主档。
- [x] T017 在核算页显示参考表原值，浏览器核对电镀/重量/行号及未提供状态，构建和API扫描通过。
- [x] T018 形成京西12行待核对及价目缺项清单；组合类型规则尚未获确认，保持原样。
