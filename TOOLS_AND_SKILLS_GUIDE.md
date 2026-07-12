# Zephyr ERP - 工具和技能使用指南

**创建日期**: 2026-07-07  
**文档版本**: v1.0

本文档记录项目中可用的 MCP 服务器和 Skills，以及它们的使用方法。

---

## 📦 已安装的 MCP 服务器

### 1. PostgreSQL MCP Server

**配置**: `@modelcontextprotocol/server-postgres`

**功能**: 直接访问和操作云端 PostgreSQL 数据库

**连接信息**:
- 数据库地址: `124.222.29.229:5432`
- 数据库名称: `stamping_system`
- 数据库用户: `postgres`
- 当前连接的表: 90 张（完整列表见下文）

**主要用途**:
- 查询表结构（schema）
- 检查数据库现状
- 读取表数据
- 执行 SQL 查询

**使用示例**:

```python
# 通过 MCP 读取表结构
# 在 Claude Code 中，可以直接要求：
# "查询 tooling_customers 表的结构"
# "检查 parts 表有哪些字段"
# "读取 material_dict 表的数据"
```

### 2. Playwright MCP Server

**配置**: `@playwright/mcp` (使用 Microsoft Edge 浏览器)

**功能**: 自动化浏览器操作，用于测试和数据抓取

**支持的浏览器**: Microsoft Edge (msedge)

**主要用途**:
- 自动化前端 E2E 测试
- 网页截图和录制
- 填写表单和点击按钮
- 导航页面和等待元素
- 抓取网页数据
- 模拟用户交互

**使用示例**:

```javascript
// 通过 Playwright MCP 控制浏览器
// 在 Claude Code 中，可以直接要求：
// "打开浏览器访问 http://localhost:3000"
// "在登录页面输入用户名 admin 和密码 123456"
// "点击登录按钮"
// "截图保存当前页面"
// "检查页面是否显示'欢迎回来'"
// "填写报价单表单"
// "点击提交并等待响应"
```

**典型场景**:
- **前端 E2E 测试**: 自动化测试报价单创建流程
- **UI 回归测试**: 验证界面修改后功能是否正常
- **数据填充**: 批量创建测试数据
- **页面截图**: 生成文档或错误报告的截图
- **表单验证**: 测试表单验证逻辑
- **工作流测试**: 测试完整业务流程（报价→审批→定点）

**测试凭据**（参考 memory）:
- 用户名: `admin`
- 密码: `123456`

**Playwright 特性**:
- 支持多浏览器（当前配置为 Edge）
- 自动等待元素加载
- 网络请求拦截
- 视频录制和截图
- 移动端模拟
- 并发测试



**当前旧库实际表资源**（现状盘点，不是目标设计，90 张表）:

> 目标表结构只能以 [`specs/001-erp-system-architecture/data-model.md`](specs/001-erp-system-architecture/data-model.md) 为准。以下列表仅用于识别当前数据库中的历史表和待迁移对象。

**核心业务表**:
- `users` - 用户表
- `quotes` - 报价单
- `parts` - 零件主表
- `tooling_customers` - 客户表（需重命名为 customers）
- `part_customer_aliases` - 零件客户别名（一卖多）
- `machines` - 机台表
- `production_plans` - 生产计划
- `production_reports` - 报工记录
- `material_batches` - 原料批次
- `process_flow_cards` - 工艺流转单

**字典表**:
- `material_dict` - 材料字典
- `treatment_dicts` - 工序字典（待重建）
- `machine_tonnage_dict` - 机床吨位字典
- `part_name_dict` - 零件名称字典
- `system_dicts` - 系统字典

**价格相关表**:
- `material_base_prices` - 材料基础价格（待废弃）
- `prices` - 价格表
- `annual_reductions` - 年降记录
- `price_years` - 价格年份
- `price_adjustment_log` - 调价日志

**质量检验表**:
- `first_piece_inspections` - 首件检验
- `oqc_inspections` - OQC 检验
- `qa_exemptions` - 质量特赦
- `patrol_inspections` - 巡检记录
- `qc_logs` - 质检日志

**仓库物流表**:
- `material_batches` - 原料批次
- `material_batch_children` - 子卷
- `suppliers` - 供应商
- `finished_goods_inventory` - 成品库存
- `inventory_transactions` - 库存事务
- `delivery_notes` - 发货单
- `packaging_records` - 包装记录

**审计日志表**:
- `audit_logs` - 审计日志
- `qr_scan_logs` - 二维码扫描日志
- `machine_status_logs` - 机台状态日志

**其他表** (完整列表):
- `admin_context_switches`, `alembic_version`, `assignments`
- `batch_transactions`, `bom_routings`, `coating_recipes`, `coating_records`
- `defect_logs`, `delivery_items`, `die_parts`, `dies`, `equipments`
- `finished_inventory`, `inbound_orders`, `maintenance_logs`, `manual_adjustments`
- `material_cost_history`, `material_slitting_logs`, `material_transactions`
- `mold_offline_records`, `mold_type_dict`, `mold_types`
- `oqc_reports`, `packaging_logs`, `part_aliases`, `part_cost_snapshot`
- `part_customer_alias`, `pkg_error_logs`, `pkg_packaging_logs`, `pkg_shipping_logs`
- `plan_machine_assignments`, `plan_machines`, `production_logs`, `production_scrap`
- `production_sessions`, `qa_audit_logs`, `qc_inspection_logs`, `remnant_inventory`
- `routing_records`, `routing_tickets`, `sample_inventory`, `sample_tasks`
- `sf_production_logs`, `shipping_logs`, `spraying_logs`, `spraying_material_consumption`
- `spraying_recipes`, `tooling_maintenance_logs`, `tooling_molds`, `tooling_parts`
- `treatment_cost_history`, `work_orders`

---

## 🛠️ 可用的 Skills

> Skills 是预定义的命令，部分通过 `/skill-name` 语法调用，部分自动激活。

### 当前项目 Skills

**检查方式**:
```bash
# 查看项目中定义的 skills
ls .claude/skills/
```

#### 1. UI/UX Pro Max - 设计智能系统

**安装位置**: `.claude/skills/ui-ux-pro-max/`

**功能**: AI 驱动的 UI/UX 设计智能系统，包含完整的设计知识库

**核心能力**:
- **67 种 UI 样式** - Glassmorphism、Claymorphism、Minimalism、Brutalism、Neumorphism、Bento Grid、Dark Mode 等
- **161 个调色板** - 针对不同行业和产品类型的配色方案
- **57 个字体组合** - Google Fonts 字体配对，自动生成 CSS import
- **161 条行业规则** - 针对不同产品类型的设计系统生成规则
- **25 种图表类型** - 数据可视化推荐
- **22 个技术栈** - React、Next.js、Vue、Svelte、Astro、SwiftUI、React Native、Flutter、WPF、WinUI 3、UWP、Avalonia、Uno Platform 等
- **99 条 UX 指南** - 最佳实践、反模式和可访问性规则

**激活方式**: 自动激活（当你进行 UI/UX 相关任务时）

**使用示例**:

```javascript
// 自然语言使用（自动激活）
"为我的 SaaS 产品创建一个着陆页"
"设计一个医疗分析仪表板"
"创建一个深色模式的作品集网站"
"构建一个电商移动应用 UI"
"为金融银行应用设计深色主题"

// 高级命令：设计系统生成器
py .claude/skills/ui-ux-pro-max/scripts/search.py "SaaS dashboard" --design-system -p "MyApp"

// 领域特定搜索
py .claude/skills/ui-ux-pro-max/scripts/search.py "glassmorphism" --domain style
py .claude/skills/ui-ux-pro-max/scripts/search.py "elegant serif" --domain typography
py .claude/skills/ui-ux-pro-max/scripts/search.py "dashboard" --domain chart

// 技术栈特定指南
py .claude/skills/ui-ux-pro-max/scripts/search.py "form validation" --stack react
py .claude/skills/ui-ux-pro-max/scripts/search.py "responsive layout" --stack html-tailwind
```

**设计系统持久化**:

```bash
# 生成并保存设计系统到 design-system/MASTER.md
py .claude/skills/ui-ux-pro-max/scripts/search.py "SaaS dashboard" --design-system --persist -p "Zephyr ERP"

# 创建页面特定的覆盖文件
py .claude/skills/ui-ux-pro-max/scripts/search.py "dashboard" --design-system --persist -p "Zephyr ERP" --page "dashboard"
```

这将创建分层的设计系统结构：
```
design-system/
├── MASTER.md           # 全局设计规则（颜色、字体、间距、组件）
└── pages/
    └── dashboard.md    # 页面特定覆盖（仅记录与 Master 的差异）
```

**设计系统生成示例输出**:
```markdown
## Design System: Zephyr ERP

### Pattern
- Real-Time / Operations Landing
- 转化焦点: 运维/安全/物联网产品。演示或沙盒链接。信任信号。
- CTA 位置: 主 CTA 在导航 + 指标之后

### Style
- 名称: Glassmorphism
- 模式支持: Light ✓ Full | Dark ✓ Full
- 关键词: 磨砂玻璃、透明、模糊背景、分层、充满活力的背景

### Colors
- Primary: #0F172A
- Secondary: #1E293B
- Accent/CTA: #22C55E
- Background: #020617
- Foreground: #F8FAFC

### Typography
- 标题: Fira Code
- 正文: Fira Sans
- Google Fonts: https://fonts.googleapis.com/css2?family=Fira+Code...

### 预交付检查清单
- [ ] 无表情符号图标（使用 SVG: Heroicons/Lucide）
- [ ] 所有可点击元素添加 cursor-pointer
- [ ] 悬停状态使用平滑过渡（150-300ms）
- [ ] 亮色模式：文本对比度最低 4.5:1
- [ ] 响应式：375px, 768px, 1024px, 1440px
```

**适用场景**:
- ✅ 设计新页面（着陆页、仪表板、管理面板、SaaS、移动应用）
- ✅ 创建或重构 UI 组件（按钮、弹窗、表单、表格、图表）
- ✅ 选择配色方案、字体系统、间距规范或布局体系
- ✅ 审查 UI 代码的用户体验、可访问性或视觉一致性
- ✅ 实现导航结构、动效或响应式行为

**跳过场景**:
- ❌ 纯后端逻辑开发
- ❌ 仅涉及 API 或数据库设计
- ❌ 非视觉类脚本或自动化任务

**相关 Skills**（同时安装）:
- `banner-design` - 横幅设计
- `brand` - 品牌设计
- `design` - 通用设计
- `design-system` - 设计系统
- `slides` - 幻灯片设计
- `ui-styling` - UI 样式（shadcn/ui + Tailwind）

**CLI 工具**:
```bash
# 更新 skill
npm install -g ui-ux-pro-max-cli
uipro update

# 卸载
uipro uninstall
```

---

#### 2. BMS Speckit - 自动化开发工作流

**版本**: v6.12.0（2026-06-30）  
**安装位置**: `.claude/commands/bms-speckit-auto/`

**🚀 新功能：全自动开发管道**

使用 `/bms-speckit:bms-speckit-auto` 启动完整的 12 步自动化开发流程：

```bash
/bms-speckit:bms-speckit-auto "创建客户管理模块"
```

**12 步开发管道**：
1. **Brainstorm** - 探索需求和设计方案
2. **Research** - 最佳实践和技术调研
3. **Constitution** - 工程原则定义
4. **CLAUDE.md sync** - 同步项目配置
5. **Specify** - 功能规格说明
6. **Plan** - 实施计划
7. **Tasks** - 任务列表
8. **Analyze** - 一致性检查
9. **Implement with rolling QC** - 实现 + 滚动质量检查
10. **Final quality gate** - 最终质量关卡
11. **Merge to main** - 合并到主分支
12. **Done** - 完成

**自动化特性**：
- ✅ 完全自主运行，无需中途确认
- ✅ 自动解决不明确需求（记录假设）
- ✅ 每步自动提交并推送
- ✅ 内置 9 维度质量检查：
  - 代码错误
  - 安全性（含 SQL 参数化）
  - 依赖管理
  - UX/UI
  - 可访问性
  - 部署制品
  - 跨数据库兼容性
  - 真实数据库集成测试
  - 业务逻辑验证

**单独使用的 Speckit Skills**：
- `/speckit.constitution` - 创建/更新项目宪法和治理规则
- `/speckit.specify` - 编写需求规格说明
- `/speckit.plan` - 制定实施计划
- `/speckit.implement` - 执行实施
- `/speckit.analyze` - 分析代码或需求
- `/speckit.clarify` - 澄清需求细节
- `/speckit.tasks` - 任务管理

**使用建议**：
- 💡 大型功能开发：使用 `/bms-speckit:bms-speckit-auto` 完整工作流
- 💡 单个步骤：使用 `/speckit.*` 独立命令
- 💡 需求不明确时：让 BMS Speckit 自动推断并记录假设

**更新方法**：
```bash
npm install -g bms-speckit-plugin
cp -r "$(npm root -g)/bms-speckit-plugin/skills/"* .claude/commands/
```

---

#### 3. 其他内置 Skills

使用 `/help` 查看所有可用的内置命令

---

## 📝 常用操作示例

### 1. 查询数据库表结构

**方式A - 使用 MCP**:
```
"查询 tooling_customers 表的完整结构"
"显示 parts 表的所有列和类型"
```

**方式B - 使用 Python 脚本**:
```bash
cd backend
python scripts/tools/inspect_cloud_schema.py
```

### 2. 查询表数据

**通过 MCP**:
```
"查询 tooling_customers 表有多少行数据"
"显示 material_dict 表的前10条记录"
"检查 treatment_dicts 表的所有数据"
```

### 3. 执行数据库迁移

**使用 Alembic**:
```bash
cd backend

# 创建迁移脚本
alembic revision -m "add customer material prices table"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 4. 检查设计与实际的差异

**使用检查脚本**:
```bash
cd backend
python scripts/tools/inspect_cloud_schema.py
# 会生成 current-schema.md 并对比设计文档
```

---

## 🔍 数据库当前状态（2026-07-07）

### 统计信息
- **总表数**: 90 张
- **设计表数**: 38 张
- **已实现**: 27 张（共同表）
- **缺失**: 11 张（设计了但未创建）
- **多余**: 63 张（云端有但设计中没有）

### 缺失的核心表（需要创建）

1. **customers** - 客户主表（tooling_customers 需重命名）
2. **price_accounts** - 零件价格台账
3. **price_adjustments** - 调价记录（带审批）
4. **customer_material_prices** - 客户材料价格历史（新设计）
5. **customer_treatment_prices** - 客户工序价格历史（新设计）
6. **departments** - 部门表
7. **special_permissions_dict** - 特殊权限字典
8. **quote_items** - 报价明细（待整合）
9. **quote_tech_reviews** - 技术审核记录
10. **surface_treatments** - 表面处理明细
11. **sampling_tasks** - 打样任务（实际有 sample_tasks）

### 需要重构的表

| 现有表 | 操作 | 目标 |
|-------|------|------|
| `tooling_customers` | 重命名 | `customers` |
| `material_base_prices` | 迁移+废弃 | 数据迁移到 `material_dict` |
| `treatment_dicts` | 清理+重建 | 新建 `treatment_dict` |
| `material_cost_history` | 废弃 | 改为 `customer_material_prices` |
| `treatment_cost_history` | 废弃 | 改为 `customer_treatment_prices` |

---

## 📚 相关文档

### 数据库设计文档
- [data-model.md](specs/001-erp-system-architecture/data-model.md) - 唯一权威数据库与 Excel 导入设计
- [current-schema.md](backend/current-schema.md) - 云端数据库实际结构（自动生成）

### 维护指南
- [maintenance-guide.md](specs/001-erp-system-architecture/database-analysis/maintenance-guide.md)
- [gap-analysis.md](specs/001-erp-system-architecture/database-analysis/gap-analysis.md)

---

## 🚀 下一步操作

### 立即可做的
1. ✅ 使用 PostgreSQL MCP 查询任何表的结构和数据
2. ✅ 通过 MCP 执行 SQL 查询（只读）
3. ✅ 检查表数据内容，验证迁移策略

### 需要创建的
1. 📝 数据库迁移脚本（Alembic）
2. 📝 数据迁移脚本（material_base_prices → material_dict）
3. 📝 表重命名脚本（tooling_customers → customers）

### 注意事项
- ⚠️ PostgreSQL MCP 可以读取数据，但**写操作需要谨慎**
- ⚠️ 建议先在本地测试迁移脚本，再应用到云端
- ⚠️ 重要表操作前先备份数据

---

## 💡 使用提示

### 如何快速查询表信息
```
直接问: "tooling_customers 表有哪些字段？"
直接问: "material_dict 表有多少条数据？"
直接问: "查询 treatment_dicts 表的所有记录"
```

### 如何检查某个设计是否已实现
```
直接问: "检查云端数据库是否有 customer_material_prices 表"
直接问: "对比设计文档和实际数据库的差异"
```

### 如何生成迁移脚本
```
直接说: "创建数据库迁移脚本，添加 customer_material_prices 表"
直接说: "生成重命名 tooling_customers 为 customers 的迁移脚本"
```

---

**文档维护**: 当添加新的 MCP 服务器或 Skills 时，请更新此文档。
