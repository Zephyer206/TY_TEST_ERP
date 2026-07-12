# Zephyr ERP 文档索引

## 数据库设计唯一来源

[`specs/001-erp-system-architecture/data-model.md`](specs/001-erp-system-architecture/data-model.md)

该文件是客户、内部零件、客户件号、模具、模具步骤、价格体系和 Excel 导入规则的唯一权威设计。

其他文档不得重新定义数据库实体、字段含义或关系。出现冲突时一律以 `data-model.md` 为准。

## 核心规格

| 文档 | 用途 |
|---|---|
| [ERP 功能规格](specs/001-erp-system-architecture/spec.md) | 业务需求与验收标准 |
| [唯一权威数据模型](specs/001-erp-system-architecture/data-model.md) | 数据库和 Excel 导入目标设计 |
| [实施计划](specs/001-erp-system-architecture/plan.md) | 开发与迁移计划 |
| [任务清单](specs/001-erp-system-architecture/tasks.md) | 实施任务 |
| [API 契约](specs/001-erp-system-architecture/contracts/) | 接口请求与响应定义 |

## 数据库现状与差异

| 文档 | 用途 |
|---|---|
| [数据库分析说明](specs/001-erp-system-architecture/database-analysis/README.md) | 分析文档使用规则 |
| [实际结构快照](specs/001-erp-system-architecture/database-analysis/current-schema.md) | 当前数据库是什么样 |
| [差异分析](specs/001-erp-system-architecture/database-analysis/gap-analysis.md) | 当前数据库与目标设计的差异 |
| [维护指南](specs/001-erp-system-architecture/database-analysis/maintenance-guide.md) | 更新结构快照和差异报告 |

`current-schema.md` 只描述现状，不代表目标设计。

## 功能规格目录

| 目录 | 用途 |
|---|---|
| [ERP 主架构](specs/001-erp-system-architecture/) | 全系统业务与架构 |
| [材料二维码追溯](specs/002-material-qr-traceability/) | 材料批次与追溯功能 |
| [价格管理系统](specs/003-price-management-system/) | 客户价格历史与调价审批 |

各功能目录中的 `data-model.md` 只能指向核心权威设计，不得维护另一套数据库结构。

## Excel 数据

| 路径 | 用途 |
|---|---|
| `excel/五金模具及产品清单表.xls` | 原始 Excel 数据源 |
| `excel/` 中的报告 | 历史导入记录，仅供问题追踪 |
| [唯一权威数据模型](specs/001-erp-system-architecture/data-model.md#9-excel-导入架构) | 当前有效导入规则 |

旧的 `IMPORT_DESIGN.md`、`FINAL_TABLE_DESIGN.md`、`FINAL_IMPORT_PLAN.md` 和字段映射文件只保留跳转入口。

## 开发入口

| 文档 | 用途 |
|---|---|
| [README](README.md) | 项目启动与技术栈 |
| [API Reference](API_REFERENCE.md) | API 使用说明 |
| [结构说明](STRUCTURE.md) | 目录结构 |
| [工具指南](TOOLS_AND_SKILLS_GUIDE.md) | 开发工具和操作说明 |

## 测试与验收

| 文档 | 用途 |
|---|---|
| [验收测试报告](ACCEPTANCE_TEST_REPORT.md) | 价格管理系统验收测试报告 |
| [验收测试截图](screenshots/acceptance-test/) | 功能截图和测试证据 |

## 开发阅读顺序

1. 阅读功能 `spec.md`，明确业务需求。
2. 阅读唯一权威 `data-model.md`，确认数据库关系和字段语义。
3. 阅读 `current-schema.md`，了解当前数据库现状。
4. 阅读 `gap-analysis.md`，确认需要迁移或重构的部分。
5. 编写迁移、模型、服务和 API。
6. 更新差异报告，但不要创建新的数据库“最终设计”文件。
