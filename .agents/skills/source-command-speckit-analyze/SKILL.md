---
name: "source-command-speckit-analyze"
description: "对 spec.md、plan.md 和 tasks.md 进行跨文档一致性和质量分析。 当用户说 \"/speckit.analyze\"、想验证规格/计划/任务的一致性、想在实施前检查缺口时使用。"
---

# source-command-speckit-analyze

Use this skill when the user asks to run the migrated source command `speckit.analyze`.

## Command Template

# Speckit Analyze — 跨文档分析

对三个核心文档进行非破坏性的一致性和质量分析。

## 前置条件

- `specs/<feature>/spec.md`
- `specs/<feature>/plan.md`
- `specs/<feature>/tasks.md`（必须存在，需先运行 `/speckit.tasks`）

## 运行约束

**严格只读**：不修改任何文件。只输出结构化分析报告。

## 工作流程

### 1. 加载文档

从仓库根目录运行 `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks`。

读取各文档的关键章节：

**spec.md**：概述、功能需求、成功标准、用户故事、边界情况

**plan.md**：架构/技术栈选择、数据模型引用、阶段、技术约束

**tasks.md**：任务 ID、描述、阶段分组、并行标记 [P]、文件路径

**宪法**：`.specify/memory/constitution.md` 用于原则验证

### 2. 构建语义模型

创建内部表示：

- **需求清单**：FR-### 和 SC-### 标识符 + 命令式短语别名
- **用户故事清单**：带验收标准的离散动作
- **任务覆盖映射**：将每个任务映射到需求或故事
- **宪法规则集**：MUST/SHOULD 规范声明

### 3. 检测遍历

结果限制 50 条。执行以下分析：

**A. 重复检测**
- 相近重复的需求 → 标记低质量表述以便合并

**B. 歧义检测**
- 缺少可衡量标准的模糊形容词（快、可扩展、安全、直观）
- 未解决的占位符（TODO、???、`<placeholder>`）

**C. 规格不足**
- 有动词但缺少宾语或可衡量结果的需求
- 引用未定义文件/组件的任务

**D. 宪法一致性**
- 任何与 MUST 原则冲突的需求 → CRITICAL

**E. 覆盖缺口**
- 无关联任务的需求
- 无映射需求的任务

**F. 不一致性**
- 跨文档的术语漂移
- 计划中有但规格中无的数据实体
- 任务顺序矛盾

### 4. 严重性分配

| 严重性 | 条件 |
|--------|------|
| CRITICAL | 违反宪法 MUST、缺少核心文档、阻塞基线功能的缺口 |
| HIGH | 重复/冲突需求、不可测试的验收标准 |
| MEDIUM | 术语漂移、缺少非功能性任务覆盖 |
| LOW | 样式改进、不影响执行顺序的轻微冗余 |

### 5. 生成分析报告

输出 Markdown 格式报告：

```markdown
## 规格分析报告

| ID | 分类 | 严重性 | 位置 | 摘要 | 建议 |
|----|------|--------|------|------|------|
| A1 | 重复 | HIGH | spec.md:L120-134 | 两个相近的需求... | 合并表述 |

**覆盖度摘要表：**

| 需求标识 | 有任务？ | 任务ID | 备注 |
|---|---|---|---|
| FR-001 | 是 | T001, T002 | |

**宪法一致性问题：**（如有）

**未映射任务：**（如有）

**指标：**
- 需求总数：N
- 任务总数：N
- 覆盖率：N%
- 关键问题数：N
```

### 6. 下一步行动

- 存在 CRITICAL 问题：建议在 `/speckit.implement` 前解决
- 仅 LOW/MEDIUM：用户可继续，提供改进建议
- 提供修复建议："是否需要我为前 N 个问题提出具体修复建议？"

## 参考资料

完整 speckit.analyze 代理提示：`.github/agents/speckit.analyze.agent.md`

## 完成标志

- [ ] 已生成含所有发现的分析报告
- [ ] 严格只读 — 未修改文件
- [ ] 已提供含命令建议的下一步行动
