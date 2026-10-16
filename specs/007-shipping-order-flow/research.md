# Research: 发货订单业务流程

**Date**: 2026-08-22

## Decision 1: Extend Zephyr instead of adopting a complete ERP

**Decision**: 在现有 Zephyr ERP 中实现发货订单域，不直接引入 ERPNext、Odoo、Tryton 或 Dolibarr 运行时。

**Rationale**:

- Zephyr 已经有客户、客户件号别名、零件、包装记录、成品库存、库存流水和审计基础。
- 用户确认的样件路径、标签人员双确认、未建档客户件号提醒、草稿七天清理等规则不是通用 ERP 的默认流程。
- 现有后端是 FastAPI + SQLAlchemy async，前端是 Vue 3 + Element Plus；替换为外部 ERP 会带来权限、数据迁移和 UI 重建成本。

**Alternatives considered**:

- **ERPNext**：业务对象最接近，但 Frappe 是独立全栈框架；直接复制模块不可行，且仓库为 GPL-3.0。
- **Odoo**：订单、库存移动和分批出库非常成熟，但模块强依赖 Odoo ORM、权限和视图体系，不能作为 Zephyr 的直接插件。
- **Tryton**：Python 模块化程度较好，但仍有独立的服务端/客户端模型，与现有 FastAPI/Vue 不兼容。
- **Dolibarr**：发货对象清楚，但使用 PHP，且与当前 Python 技术栈差异最大。

## Decision 2: Reference ERPNext's document separation

**Decision**: 将 Zephyr 的领域对象分为订单、标签确认、发货记录和物流记录四层。

**Rationale**: ERPNext 将 Sales Order、Pick List、Delivery Note 分开，便于表达“一个订单多次处理”和“每次实际出库独立留痕”。这与本项目的 PO 多明细、部分发货和多物流号需求一致。

**Repository evidence**:

- [ERPNext Sales Order](https://github.com/frappe/erpnext/tree/develop/erpnext/selling/doctype/sales_order)
- [ERPNext Pick List](https://github.com/frappe/erpnext/tree/develop/erpnext/stock/doctype/pick_list)
- [ERPNext Delivery Note](https://github.com/frappe/erpnext/tree/develop/erpnext/stock/doctype/delivery_note)

## Decision 3: Reference Odoo's stock-move separation for quantities

**Decision**: 订单明细的订购数量不被发货操作覆盖；实际发货数量通过独立发货明细累计，取消数量单独记录。

**Rationale**: Odoo 的 `sale_stock` 将销售订单与库存操作关联，库存模块再拆分 picking、move、move line、package 和 lot 等对象。这种分层适合保证部分发货、重复发货和物流历史不互相覆盖。

**Repository evidence**:

- [Odoo sale_stock](https://github.com/odoo/odoo/tree/19.0/addons/sale_stock)
- [Odoo stock models](https://github.com/odoo/odoo/tree/19.0/addons/stock/models)

## Decision 4: Reuse Zephyr customer-part and audit foundations

**Decision**: 客户件号搜索复用 `PartCustomerAlias`，操作历史复用现有 `AuditLog`，订单明细同时保存客户件号和零件名称快照。

**Rationale**:

- `PartCustomerAlias` 已包含客户、零件、客户件号、客户件名、备注和数据质量状态，能够实现“先选客户，再按包含字符查询客户件号”。
- 用户允许业务修改订单中的零件名称，因此必须保存订单快照，不能只在展示时重新读取档案。
- 现有 `AuditLog` 已支持实体、用户、旧值、新值、动作和时间，可覆盖提交、标签确认、取消确认、发货和物流修改。

## Decision 5: Keep inventory and QR integration deferred

**Decision**: 第一阶段只定义正式订单可以从合格成品库存进入待发货的接口边界，不在本计划中实现库存预占、库存扣减、包装扫码或二维码全检任务分配。

**Rationale**: 用户明确要求这些内容等二维码系统和成品库存规则完善后再讨论。提前写入发货订单核心迁移会锁死未确认的业务规则。

## Decision 6: Use an explicit maintenance command for draft retention

**Decision**: 增加可审计的草稿清理命令，由部署环境每日运行；清理条件严格限定为草稿状态且最后修改时间早于七天。

**Rationale**: 当前项目没有通用后台调度框架。显式命令可先 dry-run、可测试、可通过 Windows Task Scheduler 或部署 cron 调度，不影响在线请求。

## Open follow-up topics

- 成品库存预占、释放和扣减的事实来源。
- 二维码扫描与全检任务分配。
- 标签独立流程与标签模板。
- 已发货后的退货、冲销和逆向库存。
