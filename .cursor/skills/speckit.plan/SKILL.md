---
name: speckit.plan
description: >
  执行实施计划工作流，使用计划模板生成设计文档（数据模型、接口契约、快速入门指南）。
  当用户说 "/speckit.plan"、想设计技术架构、创建数据模型、定义接口契约时使用。
---

# Speckit Plan — 制定实施计划

执行实施计划工作流，从现有规格说明书生成设计文档。

## 前置条件

- `specs/<feature>/spec.md` 必须存在
- 从仓库根目录运行 `.specify/scripts/powershell/check-prerequisites.ps1 -Json` 获取 FEATURE_DIR

## 工作流程

### 阶段 0：研究与澄清

1. 从规格中提取未知项（标记为 "NEEDS CLARIFICATION"）
2. 为每个未知项分配研究任务
3. 在 `research.md` 中汇总研究成果：
   - Decision（决策）：选择了什么
   - Rationale（理由）：为什么选这个
   - Alternatives considered（考虑的替代方案）：还评估了哪些

### 阶段 1：设计与契约

研究完成后：

1. **数据模型** → `data-model.md`
   - 实体名称、字段、关联关系
   - 来自需求的验证规则
   - 状态转换（如有）

2. **接口契约** → `/contracts/`
   - 识别项目对外暴露的接口
   - 记录 API 端点、CLI 模式或 UI 契约
   - 纯内部项目可跳过

3. **快速入门指南** → `quickstart.md`
   - 可运行的验证场景（端到端证明功能正常）
   - 前置条件、设置命令、测试/运行命令、预期结果
   - **不含**完整实现代码、完整测试套件

4. **更新 Agent 上下文**
   - 更新 `.github/copilot-instructions.md` 中 `<!-- SPECKIT START -->` 与 `<!-- SPECKIT END -->` 之间的内容
   - 指向新建的 `plan.md`

### 核心规则

- 文件系统操作使用绝对路径
- 文档引用使用项目相对路径
- 门控检查失败或未解决的澄清项时报 ERROR
- 宪法检查：对照 `.specify/memory/constitution.md` 原则验证设计

## 完成报告

汇报：

- 分支名称
- `IMPL_PLAN` 路径
- 生成的文档：research.md、data-model.md、/contracts/、quickstart.md

## 参考资料

完整 speckit.plan 代理提示：`.github/agents/speckit.plan.agent.md`
计划模板：`.specify/templates/plan-template.md`

## 完成标志

- [ ] 计划工作流已执行，设计文档已生成
- [ ] research.md 解决了所有 NEEDS CLARIFICATION
- [ ] 已向用户汇报计划路径和文档清单
