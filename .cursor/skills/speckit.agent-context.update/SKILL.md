---
name: speckit.agent-context.update
description: >
  刷新编码 Agent 上下文文件中的 Spec Kit 管理区域。
  当用户说 "/speckit.agent-context.update" 或想将最新计划路径同步到 Agent 上下文文件时使用。
---

# Speckit Agent Context Update — 同步 Agent 上下文

刷新编码 Agent 上下文文件中的 Spec Kit 管理区域。

## 概述

Agent 上下文文件是为编码 Agent 提供指令的文件。
管理区域由 `<!-- SPECKIT START -->` 和 `<!-- SPECKIT END -->` 标记界定。
本命令将该区域更新为指向最新计划。

## 上下文文件发现

读取 `.specify/extensions/agent-context/agent-context-config.yml` 查找：

- `context_file` — 要管理的编码 Agent 上下文文件路径
- `context_markers.start` / `.end` — 定界符（默认：`<!-- SPECKIT START -->` / `<!-- SPECKIT END -->`）

## 上下文文件位置（按 Agent）

| Agent | 上下文文件 |
|-------|-----------|
| Claude.ai | `CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cursor Agent | `.cursorrules` 或工作区指令 |

本项目的上下文文件为 `.github/copilot-instructions.md`。

## 工作流程

### 1. 检测最新计划

查找最近修改的 `specs/*/plan.md`：

```powershell
Get-ChildItem -Path specs -Recurse -Filter plan.md | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

或使用脚本：

```powershell
. .specify/extensions/agent-context/scripts/powershell/update-agent-context.ps1
```

### 2. 更新管理区域

读取上下文文件。将 `<!-- SPECKIT START -->` 和 `<!-- SPECKIT END -->` 之间的内容替换为最新计划引用：

```markdown
<!-- SPECKIT START -->
最新功能计划：specs/<feature>/plan.md
<!-- SPECKIT END -->
```

### 3. 保存

写入更新的上下文文件。

## 完成报告

汇报：
- 更新的上下文文件
- 引用的计划路径
- 修改的文件

## 参考资料

完整 speckit.agent-context.update 代理提示：`.github/agents/speckit.agent-context.update.agent.md`
Agent 上下文扩展配置：`.specify/extensions/agent-context/agent-context-config.yml`

## 完成标志

- [ ] 上下文文件的管理区域已更新为指向最新计划路径
- [ ] 已向用户汇报修改的文件
