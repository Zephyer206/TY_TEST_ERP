---
name: speckit.implement
description: >
  执行实施计划，处理并完成 tasks.md 中定义的所有任务。
  当用户说 "/speckit.implement"、想开始编码、说"开始实现"时使用。
---

# Speckit Implement — 实施执行

执行实施计划，处理 `tasks.md` 中的所有任务。

## 前置条件

- `specs/<feature>/tasks.md` 必须存在
- `specs/<feature>/checklists/` 中的所有检查清单应已完成

## 工作流程

### 1. 检查前置脚本

从仓库根目录运行 `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks`。

### 2. 验证检查清单

检查 `FEATURE_DIR/checklists/`：
- 扫描所有检查清单的完成状态
- 如有未完成：停止并询问用户"部分检查清单未完成，是否继续？（是/否）"
- 全部完成：自动继续

### 3. 加载实施上下文

按顺序读取：
- **必须**：`tasks.md`（完整任务列表）、`plan.md`（技术栈、架构）
- **如存在**：data-model.md、contracts/、research.md、constitution.md、quickstart.md

### 4. 项目初始化验证

根据技术栈创建/验证忽略文件：
- `.gitignore`（通过 `git rev-parse --git-dir` 检测）
- `.dockerignore`、`.eslintignore`、`.prettierignore`（按需）
- 按技术栈的忽略模式：
  - **Node.js/TS**：`node_modules/`、`dist/`、`build/`、`*.log`、`.env*`
  - **Python**：`__pycache__/`、`*.pyc`、`.venv/`、`dist/`

### 5. 分阶段执行

按阶段顺序执行任务：
- **初始化**：创建结构、安装依赖、配置
- **核心开发**：实现 Models、Services、Endpoints
- **集成**：数据库连接、中间件、外部服务
- **收尾**：单元测试、优化、文档

### 6. 进度跟踪

- 每完成一个任务后汇报进度
- 在 tasks 文件中标记已完成任务为 `[X]`
- 遇到非并行任务失败时停止
- 并行任务继续执行成功的，汇报失败者

### 7. 完成验证

- 所有必需任务标记 `[X]`
- 实施结果与规格匹配
- 测试通过，覆盖率达到要求

## 完成报告

汇报最终状态和已完成工作的摘要。

## 参考资料

完整 speckit.implement 代理提示：`.github/agents/speckit.implement.agent.md`

## 完成标志

- [ ] tasks.md 中所有任务已完成并标记 `[X]`
- [ ] 实施结果已通过规格验证
- [ ] 已向用户汇报完成摘要
