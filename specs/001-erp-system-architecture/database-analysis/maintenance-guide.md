# 数据库文档维护指南

## 文档职责

- [`../data-model.md`](../data-model.md)：唯一权威目标设计。
- `current-schema.md`：数据库实际结构快照。
- `gap-analysis.md`：实际结构与目标设计的差异。

禁止创建新的 `final-design`、`complete-design` 或实体组独立设计文件。

## 数据库结构变更后

1. 更新或重新生成 `current-schema.md`。
2. 对照 `../data-model.md` 更新 `gap-analysis.md`。
3. 检查 ORM 模型与实际表字段、类型、空值和外键是否一致。
4. 检查 Alembic head 和数据库 `alembic_version`。
5. 更新迁移和测试，不修改权威设计来迁就错误实现。

## 新业务决策

当用户确认新的客户、零件、模具、价格或导入规则时：

1. 直接更新 `../data-model.md`。
2. 在相关功能 `spec.md` 记录需求背景。
3. 在 `gap-analysis.md` 记录当前实现差距。
4. 不再复制一份新的数据模型。

## Excel 导入检查

每次导入至少验证：

- 源文件哈希和导入批次。
- Sheet 数、候选行、有效行、失败行。
- 表头和汇总行是否被阻断。
- 客户代码和客户名称是否匹配。
- 客户件号唯一性。
- 材料、T/W/P、重量解析率和错列检测。
- 非连续模步数与穴数是否分离。
- `tooling_parts`、`tooling_steps`、`tooling_customer_links` 是否完整。
- 正式记录能否回溯到源 Sheet 和行号。

## 权威性检查

提交文档变更前运行全文搜索，确保：

- 只有 `../data-model.md` 包含有效目标表定义。
- 旧设计文件只包含废弃声明和跳转链接。
- 功能计划没有 UUID、单客户模具、固定 Excel 列号等冲突设计。
