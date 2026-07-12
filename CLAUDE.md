# Claude Code 项目约束

## 数据库设计

数据库、ORM、迁移、API 数据关系和 Excel 导入的唯一权威设计是：

`specs/001-erp-system-architecture/data-model.md`

在修改相关代码前必须先阅读该文件。

## 禁止事项

- 不得从旧 `*-final.md`、Excel 历史报告或 `current-schema.md` 推导新的目标设计。
- 不得创建第二份数据库“最终设计”文档。
- 不得把客户件号写回内部零件编号。
- 不得把模数和穴数混为一谈。
- 不得恢复 Excel 固定列号直接写正式表的方案。
- 不得并行维护 `tooling`、`dies`、`tooling_molds` 多套模具主表。

## 文档职责

- `data-model.md`：目标设计。
- `database-analysis/current-schema.md`：实际数据库现状。
- `database-analysis/gap-analysis.md`：现状与目标的差异。
- 功能 `spec.md`、`plan.md`、`research.md`：需求和实施细节，不得重新定义数据库关系。
