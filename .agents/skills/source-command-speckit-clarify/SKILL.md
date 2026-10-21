---
name: "source-command-speckit-clarify"
description: "识别当前功能规格中的模糊区域，通过定向提问将回答编码回规格文件。 当用户说 \"/speckit.clarify\" 或想在计划前消除歧义时使用。"
---

# source-command-speckit-clarify

Use this skill when the user asks to run the migrated source command `speckit.clarify`.

## Command Template

# Speckit Clarify — 需求澄清

通过定向提问识别并解决当前功能规格中的模糊区域。

## 前置条件

- `specs/<feature>/spec.md` 必须存在

## 工作流程

### 1. 初始化

从仓库根目录运行 `.specify/scripts/powershell/check-prerequisites.ps1 -Json -PathsOnly` 获取 FEATURE_DIR 和 FEATURE_SPEC。

### 2. 加载宪法

读取 `.specify/memory/constitution.md`（如存在），获取项目原则。

### 3. 歧义扫描

按以下分类扫描规格（每项标记：Clear / Partial / Missing）：

- **功能范围**：核心目标、明确排除范围、用户角色区分
- **领域与数据**：实体、属性、关联、状态转换、规模假设
- **交互与体验**：关键旅程、错误/空值/加载状态、无障碍
- **非功能性**：性能、可扩展性、可靠性、可观测性、安全
- **集成**：外部服务、数据格式、协议假设
- **边界情况**：负向场景、限流、冲突解决
- **约束**：技术限制、权衡、拒绝的替代方案
- **术语**：术语表、术语一致性

### 4. 问题生成

从 Partial/Missing 分类中生成最多 5 个优先排序的问题。
每个问题必须能以以下方式回答：
- 简短多选题（2-5 个互斥选项），或
- 简短回答（≤5 个词）

**每个问题**：
1. 分析所有选项，确定最佳推荐
2. 优先展示推荐选项：`**推荐：** 选项 [X] - <理由>`
3. 以表格呈现所有选项
4. 等待用户回答（"A"、"是的"、"推荐"或自定义回答）
5. 记录回答，进入下一题

**停止规则**：
- 所有关键歧义已提前解决
- 用户表示完成（"够了"、"可以"、"停止"）
- 已问了 5 个问题

### 5. 整合答案

每接受一个回答后：
1. 确保规格中存在 `## Clarifications` 章节
2. 如为本会话首个回答，添加 `### Session YYYY-MM-DD` 小节
3. 追加：`- Q: <问题> → A: <回答>`
4. 将澄清内容应用到最合适的规格章节
5. **立即保存**规格文件（原子覆盖）

### 6. 重新验证需求检查清单

如 `FEATURE_DIR/checklists/requirements.md` 存在：
- 对照更新后的规格重新评估每个复选框
- 仅在实际状态变化时切换 `[ ]` / `[x]`
- 汇报前后通过数

## 完成报告

汇报：
- 提问与回答的数量
- 更新后的规格路径
- 涉及的章节
- 需求检查清单状态（前后对比）
- 覆盖度摘要（每项分类：Resolved / Deferred / Clear / Outstanding）
- 下一步建议

## 核心原则

- 最多 5 个问题
- 不要提前透露后续问题
- 用户表示完成时停止
- 无关键歧义：汇报并建议继续

## 参考资料

完整 speckit.clarify 代理提示：`.github/agents/speckit.clarify.agent.md`

## 完成标志

- [ ] 所有 [NEEDS CLARIFICATION] 标记已解决或减至最多 3 个
- [ ] 规格已更新包含澄清内容
- [ ] 需求检查清单已重新验证
- [ ] 已向用户汇报覆盖度摘要
