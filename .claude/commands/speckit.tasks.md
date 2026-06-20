---
name: speckit.tasks
description: >
  根据设计文档生成可执行、依赖排序的任务列表（tasks.md）。
  当用户说 "/speckit.tasks"、想把计划拆解为可执行任务、创建任务清单时使用。
---

# Speckit Tasks — 任务拆解

从规格和计划文档生成依赖排序的任务列表（`tasks.md`）。

## 前置条件

- `specs/<feature>/spec.md`（带优先级 P1/P2/P3 的用户故事）
- `specs/<feature>/plan.md`（技术栈、库、项目结构）
- 可选：data-model.md、contracts/、research.md、quickstart.md

## 工作流程

### 1. 初始化

从仓库根目录运行 `.specify/scripts/powershell/setup-tasks.ps1 -Json` 获取 FEATURE_DIR 和 TASKS_TEMPLATE。

### 2. 加载设计文档

从 FEATURE_DIR 读取：
- **必须**：plan.md（技术栈）、spec.md（带 P1/P2/P3 优先级的用户故事）
- **可选**：data-model.md、contracts/、research.md、quickstart.md
- **如存在**：`.specify/memory/constitution.md`

### 3. 生成 tasks.md

使用任务模板作为结构，填充：

**阶段结构**：

- 第一阶段：项目初始化（Setup）
- 第二阶段：基础依赖（Foundational，阻塞所有用户故事的前提条件）
- 第三阶段起：按优先级顺序排列的用户故事（P1、P2、P3...）
  - 每个故事内：Models → Services → Endpoints → Integration
- 最后阶段：收尾与跨领域事项（Polish & Cross-Cutting）

### 4. 任务格式（强制）

每个任务必须严格遵循此格式：

```
- [ ] T001 [P] [US1] 在 src/models/user.py 中创建用户模型
```

- 以 `- [ ]`（复选框）开头
- 任务 ID：T001、T002...（顺序编号，执行顺序）
- `[P]` 标记：仅当任务可并行时添加（不同文件，无依赖）
- `[US1]` 标签：仅用户故事阶段任务需要（Setup/Foundational/Polish 不加标签）
- 描述：清晰的动作 + 精确文件路径

**正确示例**：

```
- [ ] T001 按实施计划创建项目结构
- [ ] T005 [P] 在 src/middleware/auth.py 中实现认证中间件
- [ ] T012 [P] [US1] 在 src/models/user.py 中创建用户模型
- [ ] T014 [US1] 在 src/services/user_service.py 中实现用户服务
```

### 5. 依赖图

展示任务完成顺序和可并行执行的任务组。

## 完成报告

汇报：

- `tasks.md` 路径
- 任务总数
- 各用户故事的任务数
- 可并行任务数量
- 各故事的独立测试标准
- 建议的 MVP 范围（通常仅含第一个用户故事）

## 参考资料

完整 speckit.tasks 代理提示：`.github/agents/speckit.tasks.agent.md`
任务模板：`.specify/templates/tasks-template.md`

## 完成标志

- [ ] `tasks.md` 已生成，包含所有阶段、任务 ID 和文件路径
- [ ] 所有任务遵循检查清单格式（复选框、ID、标签、文件路径）
- [ ] 已向用户汇报任务总数和故事拆解情况
