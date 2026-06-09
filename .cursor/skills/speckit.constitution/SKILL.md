---
name: speckit.constitution
description: >
  从交互式或提供的原则输入创建或更新项目宪法。
  当用户说 "/speckit.constitution"、想定义项目原则和治理规则时使用。
---

# Speckit Constitution — 项目宪法

从原则和约束创建或更新项目宪法（`.specify/memory/constitution.md`）。

## 核心概念

宪法是最高治理文档，包含所有其他文档（规格、计划、任务）必须遵守的项目原则。

## 工作流程

### 1. 加载现有宪法

读取 `.specify/memory/constitution.md`（如存在）。

识别所有占位符令牌：`[ALL_CAPS_IDENTIFIER]`

### 2. 收集值

每个占位符：
- 用户在对话中提供了值 → 使用该值
- 否则从现有仓库上下文推断（README、文档、以往版本）
- `RATIFICATION_DATE`：原始采用日期
- `LAST_AMENDED_DATE`：如有变更则为今天
- `CONSTITUTION_VERSION`：语义化版本递增
  - MAJOR：向后不兼容的原则移除或重新定义
  - MINOR：新增原则或实质性扩展指导
  - PATCH：澄清、用词、拼写修正

### 3. 起草宪法内容

将每个占位符替换为具体文本：
- 不留括号令牌（除非有意保留 — 为每个保留项提供理由）
- 保持标题层级
- 每条原则：小节名称、不可协商的规则、明确理由
- 治理章节：修订程序、版本政策、审查期望

### 4. 一致性传播

检查所有依赖模板是否对齐：
- `.specify/templates/plan-template.md` — 宪法检查章节
- `.specify/templates/spec-template.md` — 强制章节
- `.specify/templates/tasks-template.md` — 任务分类
- `.specify/templates/commands/*.md` — 过时引用

### 5. 同步影响报告

更新后以 HTML 注释形式添加到宪法文件顶部：
- 版本变更：旧 → 新
- 修改的原则
- 新增/删除的章节
- 需要更新的模板（✅ 已更新 / ⚠ 待处理）
- 延后的 TODO

### 6. 保存前验证

- 无遗留的解释性括号令牌
- 版本行与报告一致
- 日期为 ISO 格式 YYYY-MM-DD
- 原则是声明式的、可测试的
- 无模糊用语（"应该" → 在适当时替换为 MUST/SHOULD）

### 7. 写入宪法

覆盖写入 `.specify/memory/constitution.md`

### 8. 输出摘要

汇报：
- 新版本及递增理由
- 标记为需手动跟进的文件
- 建议的提交信息

## 核心原则

- 宪法是**不可协商**的 — 分析中的宪法冲突为 CRITICAL
- 不得稀释、重新解释或静默忽略原则
- 如需变更原则，必须明确在此进行
- 严格遵循语义化版本规则

## 参考资料

完整 speckit.constitution 代理提示：`.github/agents/speckit.constitution.agent.md`
宪法模板：`.specify/templates/constitution-template.md`

## 完成标志

- [ ] 宪法已更新，所有占位符已填充
- [ ] 同步影响报告已生成
- [ ] 模板已检查对齐情况
- [ ] 已向用户汇报版本递增和提交信息
