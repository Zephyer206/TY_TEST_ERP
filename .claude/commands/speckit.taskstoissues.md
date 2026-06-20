---
name: speckit.taskstoissues
description: >
  将 tasks.md 中的任务转换为 GitHub Issues。
  当用户说 "/speckit.taskstoissues" 且想从任务列表创建 GitHub Issues 时使用。
---

# Speckit Tasks to Issues — 任务转 Issue

将 `tasks.md` 中的任务转换为 GitHub Issues。

## 前置条件

- `specs/<feature>/tasks.md` 必须存在
- Git remote 必须为 GitHub URL

## 工作流程

### 1. 初始化

从仓库根目录运行 `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks` 获取 FEATURE_DIR 和 TASKS 路径。

### 2. 验证 GitHub Remote

获取 Git remote：

```bash
git config --get remote.origin.url
```

**仅在 remote 为 GitHub URL 时继续。**

非 GitHub：中止并报告 remote URL。

### 3. 加载任务

读取 `tasks.md` 并提取：
- 任务 ID（T001、T002...）
- 任务描述
- 阶段分组
- 文件路径
- 用户故事标签

### 4. 创建 GitHub Issues

通过 GitHub MCP 服务器（`github/github-mcp-server/issue_write`）为每个任务创建 GitHub Issue：

**Issue 标题**：`T001: [任务描述]`

**Issue 正文**包含：
- 任务 ID 和阶段
- 描述
- 文件路径引用
- 用户故事标签（如适用）
- 阶段上下文

**标签**：`feature/<功能名>`、`phase/<阶段号>`

### 5. 安全检查

**关键**：仅在与 remote URL 匹配的仓库中创建 Issue。

仓库不匹配时报错中止。

## 完成报告

汇报：
- 创建的 Issue 数量
- Issue 链接
- 阶段分布

## 参考资料

完整 speckit.taskstoissues 代理提示：`.github/agents/speckit.taskstoissues.agent.md`

## 完成标志

- [ ] 已为所有任务创建 GitHub Issues
- [ ] 仅在匹配的仓库中创建
- [ ] 已向用户汇报 Issue 数量和链接
