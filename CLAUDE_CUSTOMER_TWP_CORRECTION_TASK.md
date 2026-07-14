# 客户筛选与 T/W/P 数据纠正任务

## 模型与约束

- 默认使用 `claude-sonnet-5`；只有同一具体问题连续多次失败才切换 `claude-fable-5`。
- 完整阅读 `CLAUDE.md`、`specs/001-erp-system-architecture/data-model.md` 和现有前端验收报告。
- 本任务允许修复代码，并允许按下述严格规则执行可逆数据库纠正。
- 正式数据库操作前必须创建带时间戳的备份，并记录影响行；禁止清表、重导全部数据库、覆盖非空技术参数或删除客户。
- 工作树已有大量改动，不回退无关文件，不提交 Git。

## 已确认事实

1. `customers.id=54, name='大陆集团', customer_code='BB'` 是实际客户，关联约 105 个有效零件。
2. `customers.id=105, name='B-B 大陆集团'` 是空重复记录，零件、模具关联均为 0。
3. `customers.id=90, name='60T 连续模'` 不是客户，零件、模具关联均为 0。
4. 零件页面只请求 `/customers` 默认 50 条，导致用户看到空重复记录、看不到真正的大陆集团。
5. 6,953 个有效零件中只有 924 个有 T/W/P 或 `spec_twph`。
6. 新导入 Excel 原始规格包含 `0.6*25*53`、`1.2*65*20(1出3)`、`1.0*9.0(±0.05)*27...` 等，但当前解析器只读取独立 T/W/P 列，没有解析组合规格列。

## 一、客户数据与下拉筛选

### 数据库纠正

执行前备份以下两行到带时间戳的审计/备份文件或表：

- customers.id = 90
- customers.id = 105

再次只读确认两者 `part_customer_aliases`、`tooling_customer_links`、quotes/价格等相关业务引用均为 0 后，只允许将 `is_active=false`，不得 DELETE。

不得修改 `customers.id=54`。

### API

改进 `GET /api/v1/customers`：

- 默认只返回 `is_active=true`。
- 增加可选参数 `has_parts`；为 true 时用 `EXISTS part_customer_aliases`（只计 `is_active=true` 的别名）筛选。
- `CustomerResponse` 返回 `customer_code`，可选返回 `part_count`。
- 搜索至少支持客户名称和客户代码。
- 避免 join 导致重复或错误计数。

### 前端

- 零件管理客户筛选请求 `/customers?limit=200&has_parts=true`。
- 客户价格查询也只显示有效且有零件关系的客户。
- 客户标签显示 `customer_code + name`，但不得把名称里的旧前缀冒充代码。
- 下拉中不得出现 `60T 连续模`、ID 105 的空重复大陆集团。
- 必须能选择 ID 54 的大陆集团并返回其所有关联零件；页面数量与 SQL `COUNT(DISTINCT part_id)` 一致。

## 二、T/W/P 解析与安全回填

### 解析器

扩展 `backend/scripts/import_excel_authoritative.py`：

- 组合规格字段解析成 thickness / width / pitch。
- 支持 `*`、`×`、`x`、`X` 分隔。
- 支持数值旁的公差括号，例如 `1.0*9.0(±0.05)*27`。
- 支持尾部说明、`1出N`、`一出N`，但不得把穴数或公差数字误当 T/W/P。
- 优先使用明确的独立 T/W/P 列；只有独立字段为空时才使用组合规格。
- 无法可靠解析的格式保持为空并进入报告，不猜测。
- 添加覆盖真实格式和反例的测试/断言。

### Dry-run 与回填规则

创建专用脚本，例如 `backend/scripts/backfill_twp_from_excel.py`，默认必须是 dry-run。它应重新读取原始 Excel/暂存来源，不能假设所有 sheet 的规格都固定在 `raw_data[10]`。

按 `excel_import_rows.resolved_part_id` 汇总：

- 仅处理 IMPORTED 且 resolved_part_id 非空的来源行。
- 仅当目标 `parts.thickness/width/pitch` 当前全部为空时考虑自动回填。
- 同一 part_id 的所有可解析来源必须得到唯一且完全一致的 `(T,W,P)`。
- 任一 part_id 出现多个规格，标记 CONFLICT，不更新。
- 已有任一非空 T/W/P 与新解析结果不同，标记 CONFLICT，不覆盖。
- 执行模式先备份受影响 `parts` 和 `excel_import_rows` 行，再在单一事务中更新。
- 同步更新 staging 的 `parsed_thickness/width/pitch`；如项目仍使用 `spec_twph` 展示，可保存规范化显示字符串，但不得用它替代数值字段。
- 输出 JSON/Markdown 报告：扫描行、可解析行、唯一零件、冲突零件、安全回填零件、未解析示例、更新前后非空统计。

在确认 dry-run 结果满足规则后执行安全回填；不得处理冲突项。

## 三、前端显示

- 默认零件列表 TWP 列必须读取 API 的 `thickness/width/pitch`，有值时清楚显示 `T… × W… × P…`。
- 对未回填或冲突零件显示 `-`，不能伪造。
- 详情页同步显示相同数值。
- 默认排序页面应真实展示数据库当前记录；不得为了截图伪造前端示例数据或隐藏空值。

## 四、强制验收

必须使用 PostgreSQL MCP/只读 SQL 与 Playwright 浏览器 MCP：

1. SQL 确认 ID 90、105 已停用且业务引用仍为 0；ID 54 保持有效且关联数量正确。
2. 浏览器从菜单打开零件管理，客户下拉确认没有 `60T 连续模` 和空重复 `B-B 大陆集团`。
3. 选择实际大陆集团，搜索结果必须非空，页面数量/抽样 ID 与 SQL 一致。
4. 清空筛选，检查默认第一页；至少抽样 5 个有 T/W/P 的真实零件，与 staging 原始规格和 parts 数值逐项一致。
5. 用内部名称搜索至少一个回填后的零件，详情页 T/W/P 与列表、SQL一致。
6. 检查相关网络请求全部 200，控制台本功能相关错误为 0。
7. 截图保存到 `screenshots/customer-twp-correction/`，必须是真 PNG，并检查文件签名和大小。

## 报告

生成 `CUSTOMER_TWP_CORRECTION_RESULT.md`，必须包含：

- 根因与修改文件
- 两个停用客户的备份位置和引用检查
- T/W/P dry-run 与正式回填统计
- 冲突数量及示例（不自动处理）
- 大陆集团数据库/页面零件数对照
- 5 个 T/W/P 抽样对照
- Playwright 操作、网络、控制台、截图路径
- 测试和构建真实结果
- 未完成项和风险，不得把未通过项写成完成
