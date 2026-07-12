# 已废弃：Excel 直接导入设计

旧方案将 Excel 行直接写入正式表，已确认会造成客户、零件、模具和模数语义错误。

唯一权威数据库与 Excel 导入设计：

[`../specs/001-erp-system-architecture/data-model.md`](../specs/001-erp-system-architecture/data-model.md)

当前规则：Excel 必须先进入暂存层，按动态表头校验后再写正式业务表。
