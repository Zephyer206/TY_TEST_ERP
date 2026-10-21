---
name: "source-command-speckit-specify"
description: "根据自然语言描述创建功能规格说明书，采用规格驱动开发（Spec-Driven Development）方法。 当用户说\"specify\"、\"我要做XXX功能\"、\"定义需求\"、\"写规格\"、\"写规范\"时使用。"
---

# source-command-speckit-specify

Use this skill when the user asks to run the migrated source command `speckit.specify`.

## Command Template

# Speckit Specify — 编写功能规格说明书

根据自然语言描述创建功能规格说明书，遵循规格驱动开发（Spec-Driven Development）原则。

## 核心概念

Speckit 是一套规格驱动的开发工作流。本命令根据用户描述生成 `specs/<feature>/spec.md`。
**不涉及任何实现细节** — 只描述用户需要什么（WHAT）和为什么需要（WHY）。

## 工作流程

### 1. 生成功能名称

创建 2-4 个词的简短名称（动名词格式，保留英文缩写）：

```
"我要做用户登录认证"        → "user-auth"
"集成 OAuth2 单点登录"      → "oauth2-api-integration"
"创建一个数据分析仪表盘"      → "analytics-dashboard"
```

### 2. 创建功能目录

规格文档存放在 `specs/` 下，自动编号或时间戳前缀：

```
specs/001-user-auth/
specs/002-oauth2-api-integration/
```

从仓库根目录运行此 PowerShell 脚本来解析编号：

```powershell
. .specify/scripts/powershell/setup-tasks.ps1 -Json 2>$null
```

### 3. 读取模板

解析当前激活的 `spec-template` 并复制为 `SPEC_FILE = specs/<dir>/spec.md`。

### 4. 加载宪法（如存在）

读取 `.specify/memory/constitution.md` 获取项目原则和治理约束。

### 5. 编写规格说明书

用用户描述中的具体细节填充模板：

- **概述（Overview）**：这是什么功能，为什么重要
- **用户与角色（Actors & Users）**：谁会使用这个功能
- **用户故事（User Stories）**：主要流程与验收标准（P1、P2、P3 优先级）
- **功能需求（Functional Requirements）**：编号需求（FR-001、FR-002...），需可测试、具体明确
- **边界情况（Edge Cases）**：错误状态、边界条件、异常流程
- **成功标准（Success Criteria）**：可衡量的、技术无关的结果（指标、时间、容量）
- **假设条件（Assumptions）**：记录使用的所有合理默认值

### 6. 质量验证

编写完成后，按检查清单标准验证：

- 无实现细节（不含技术栈、框架名称）
- 所有需求可测试且无歧义
- 成功标准可衡量，无需了解实现方式
- 所有验收场景均已定义
- 最多 3 个 [NEEDS CLARIFICATION] 标记 — 仅用于影响重大的歧义决策
- 未解决问题不超过 3 个；其余使用合理推断

### 7. 处理澄清问题

如存在 [NEEDS CLARIFICATION] 标记（最多 3 个）：

将每个标记呈现为多选题表格（附带推荐选项），然后用用户回答更新规格。

### 8. 创建需求检查清单

生成 `specs/<dir>/checklists/requirements.md`：

```
# 规格质量检查清单：[功能名称]

## 内容质量
- [ ] 无实现细节（语言、框架、API）
- [ ] 聚焦用户价值和业务需求
- [ ] 面向非技术利益相关者

## 需求完整性
- [ ] 无 [NEEDS CLARIFICATION] 标记残留
- [ ] 需求可测试且无歧义
- [ ] 成功标准可衡量

... 等等
```

### 9. 完成报告

向用户汇报：

- 功能目录路径
- 规格文件路径
- 检查清单验证结果
- 下一步：可进入 `/speckit.clarify`（澄清问题）或 `/speckit.plan`（技术设计）

## 核心原则

- 聚焦用户需要什么（WHAT）和为什么（WHY）— 不要写如何实现（HOW）
- 面向业务人员，而非开发人员
- 不要在规格文档中内嵌检查清单（单独文件）
- 未指定细节使用合理推断，并记录假设
- 成功标准必须可衡量、技术无关

## 参考资料

完整 speckit.specify 代理提示：`.github/agents/speckit.specify.agent.md`
规格模板：`.specify/templates/spec-template.md`
宪法：`.specify/memory/constitution.md`

## 完成标志

- [ ] `specs/<dir>/spec.md` 已创建并通过质量检查清单验证
- [ ] `specs/<dir>/checklists/requirements.md` 已创建
- [ ] 已向用户汇报功能目录、规格路径及就绪状态
