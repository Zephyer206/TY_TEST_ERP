---
name: "source-command-speckit-implement"
description: "根据 tasks.md 执行任务，实现代码。当用户说 \"/speckit.implement\"、想按任务清单实现功能时使用。"
---

# source-command-speckit-implement

Use this skill when the user asks to run the migrated source command `speckit.implement`.

## Command Template

# Speckit Implement — 任务执行

根据 `tasks.md` 清单执行任务，实现代码。

## 前置条件

- `specs/<feature>/tasks.md`（包含 `- [ ]` 复选框任务列表）
- `specs/<feature>/plan.md`（技术栈、文件结构）
- `specs/<feature>/spec.md`（功能需求）

## 工作流程

### 1. 解析任务范围

解析用户指定的范围：
- `Phase N`：执行第 N 阶段所有任务
- `TXXX-TYYY`：执行从 TXXX 到 TYYY 的所有任务
- `USX`：执行标签为 USX 的所有任务
- 无参数：执行所有未完成的任务

### 2. 读取设计文档

从 FEATURE_DIR 读取：
- `tasks.md`（任务清单）
- `plan.md`（技术栈、文件结构）
- `spec.md`（功能需求）

### 3. 执行任务

按顺序执行任务，遵循：
- `[P]` 标记的任务可并行执行
- 无标记的任务必须按顺序执行
- 每个任务完成后，更新 `tasks.md` 复选框为 `- [x]`

### 4. 实现规范

每个任务的实现必须：

1. **创建/修改指定文件**
2. **遵循现有代码风格**（从 Phase 1/2 已实现的代码中学习）
3. **添加必要的导入和类型标注**
4. **包含完整的错误处理**
5. **符合 plan.md 中的技术决策**

### 5. 验证

任务完成后：
- 检查语法错误
- 确保文件路径正确
- 更新 `tasks.md` 复选框

## 任务格式

```
- [x] T022 [P] [US1] 在 backend/src/models/quote.py 中创建报价单模型
```

## 完成报告

汇报：
- 已完成任务 ID 列表
- 创建/修改的文件列表
- 遇到的任何问题

## 参考资料

任务清单：`.specify/templates/tasks-template.md`
实现模板：参考 Phase 1/2 已实现的代码

## 完成标志

- [ ] 所有指定任务已完成
- [ ] `tasks.md` 复选框已更新
- [ ] 已向用户汇报完成情况
