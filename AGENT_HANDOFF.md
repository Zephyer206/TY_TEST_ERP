# 用户—Agent 交接记录

## 交接目标

用户要把 Zephyr ERP 整个项目带到另一台电脑继续修改。交接包应可解压后重建开发环境，并保留当前源码、迁移、业务数据、文档和本机配置。

## 已完成

- 生成根目录部署说明：`DEPLOYMENT_ENVIRONMENT.md`。
- 生成跨电脑说明：`TRANSFER_README.md`。
- 生成可重复打包脚本：`scripts/create_transfer_archive.ps1`。
- 生成新对话启动提示词：`NEW_CHAT_START_PROMPT.md`。
- 生成当前代码与 Spec 对照报告：`PROJECT_STATUS_SPEC_COMPARISON.md`。
- 压缩包位置：项目上级目录的 `Zephyr_test_Erp_transfer_20260826.zip`。
- 压缩包保留 `.env`、`backend/.env`、`.mcp.json`、`.auth_token*`、`shipping_test_accounts.local.txt` 以及 `.git`，但不在聊天中打印其内容。

## 交接包排除项

`node_modules`、`backend/.venv`、`backend/.runtime312`、Python/pytest 缓存、运行日志、Playwright 日志，以及 Windows 设备名文件。它们不可可靠跨电脑复用或不属于开发源文件；新电脑按 `DEPLOYMENT_ENVIRONMENT.md` 重建。

## 新 Agent 首要动作

1. 先阅读 `AGENTS.md`、本文件和 `DEPLOYMENT_ENVIRONMENT.md`。
2. 不要在回复、日志、提交或截图中输出 `.env`、`.mcp.json`、令牌或测试账号的值。
3. 修改前检查 `git status`，保留用户已有改动；不要执行破坏性重置。
4. 若修改前端，必须启动实际前端并完成浏览器验收；代码编译不能替代验收。
5. 数据库变更使用 Alembic，先备份并记录迁移结果。

## GPT-6 重构前新增 P0

- 核验 `backend/app/api/migrations.py` 的 `POST /api/v1/migrations/run-all` 已保持默认关闭。当前代码已加入显式配置和 LV4 保护；生产仍应移除 HTTP 迁移入口，只保留受控 Alembic CLI。
- 当前已确认 root 与 backend 兼容入口都加载根 `alembic/versions`：65 个 revision、1 个 head `20260822_shipping_orders`，但有两个 base（`001_initial`、`a1b2c3d4e5f6`）和多个 branchpoint。仍必须在隔离数据库验证空库升级、现有数据库校验和回滚路径；不能把“单 head”当成“可部署”。
- 价格域存在 `prices`、历史 `price_accounts` 迁移和 migration API 三套冲突契约。本轮已将旧 `price_accounts` API 的 ORM 兼容层收敛到 `prices/price_years`，但尚未执行真实数据库兼容迁移；下一步仍要确定最终 canonical schema、主键类型、字段名、历史表和调价表，再做可回滚迁移和 API 契约测试。
- 价格审批需要统一 schema，补齐 LV2/LV3/LV4 权限、行锁/版本并发控制，以及审批、价格更新、历史、审计的单事务提交。
- 统一 `backend/app/core/config.py` 与 `backend/app/config.py` 的配置来源，生产启动拒绝默认 `SECRET_KEY`。

首批基线修复已执行：迁移 API 默认已关闭并增加 LV4/配置保护；价格历史、调价和工序字典已补充 LV1-LV4 最小角色校验；重复价格 adjustment schema 已拆分，审批请求校验、行锁和单事务写入已加入；普通 API 已拒绝 refresh token；旧 `app.config` 已转发到 canonical Settings；生产启动安全校验和对应回归测试已加入。本轮又修复了旧价格台账接口读取不存在字段的问题，并将年度价格读写接到 `price_years`。价格表最终结构和 `prices/price_accounts` 数据兼容迁移仍需在隔离数据库中处理。

## 2026-09-09 最新验收基线

- `python -m pytest tests -q`（从 `backend/`）：`325 passed, 23 failed, 23 errors, 1 skipped`。
- 失败/错误主体与上一轮已知基线一致，主要仍集中在 Part 旧字段、display groups、TWP mock/断言和 shipping contract；本轮通过数增加 1 项。
- `python -m compileall -q app`：通过。
- `alembic heads`：`20260822_shipping_orders`；revision graph 有两个 base。`$env:PYTHONIOENCODING='utf-8'; alembic upgrade head --sql > $null` 已完整生成 65 个 revision 的静态 SQL（exit 0）。这只证明 offline SQL 可渲染；尚未在真实数据库执行 upgrade/downgrade，不能视为数据库迁移已验收。
- 本轮未运行浏览器验收；没有前端行为改动。
- 本轮统一了 TWP 小数精度错误消息，相关回归通过；全量较上一轮多通过 1 项。迁移 offline-safe 修复未执行真实 PostgreSQL upgrade/downgrade。

## 当前工作区提示

当前工作区存在大量既有未提交改动和新增文件，不能据此推断哪些是本次交接新增。交接包以打包时磁盘内容为准；新 Agent 应以实际文件和 `git status` 为证据继续工作。

## 安全与部署责任

包内凭据仅为用户明确要求的迁移便利而保留。迁移完成后由用户/部署者轮换数据库密码、令牌和 `SECRET_KEY`，并删除不再使用的测试账号。

## 2026-09-10 实际验收更新（未登录基线）

本轮重新启动服务并完成了只读/页面验收，未执行数据库迁移、删除、业务写入或凭据输入。

实现与工程验收：

- `backend`: `python -m compileall -q app` 通过。
- 全量后端测试：`325 passed, 23 failed, 23 errors, 1 skipped`；失败簇仍为 Part 旧字段、display groups、TWP 多工具 fixture/mock、shipping contract 路由字段和两个编辑器 mock 行为，不能标记为全量通过。
- `frontend`: `npm run type-check` 通过，`npm run build` 通过；仅有 Sass/依赖注释和大 chunk 警告。
- `mobile-h5`: `npm run build` 通过。
- `$env:PYTHONIOENCODING='utf-8'; alembic upgrade head --sql` 通过；`alembic heads` 仍为 `20260822_shipping_orders`。这仍只是静态 SQL 渲染，未证明真实 PostgreSQL upgrade/downgrade。
- `/health`、桌面前端 `5173`、移动 H5 `8080` 和 OpenAPI 均返回 HTTP 200。

真实浏览器验收（Codex In-app Browser，未指定外部浏览器）：

- 桌面 `/parts`：页面真实渲染，导航、筛选、表格和分页可见，显示约 4,979 条记录。
- 桌面 `/production`：页面真实渲染，显示 3 条计划；新建计划、刷新、资材确认队列和状态摘要可见。
- 桌面 `/shipping-orders`：页面真实渲染，列表、订单类型/状态筛选、历史订单和查看入口可见。
- 桌面 `/after-sales`：页面真实渲染，档案入口、搜索、类型/资料状态筛选、视图设置和空结果状态可见；当前数据显示 0 条。
- 移动 `http://127.0.0.1:8080/login`：登录表单真实渲染；直接访问受保护的 `/query` 被重定向回 `/login`。
- 本轮没有在浏览器内输入测试账号密码，因此没有把“真实登录后的 H5 查询/生产/交付/扫码流程”宣称为通过。按 `AGENTS.md`，需要用户明确授权后才能输入测试凭据。

当前验收结论：项目可运行、核心页面可打开，但仍不是“全部完成”或“全量验收通过”。2026-09-11 登录态结果见下节；下一位 Agent 应以最新节数字和 `PROJECT_STATUS_SPEC_COMPARISON.md` 的 P0/P1 清单为基线。

## 2026-09-11 登录态浏览器验收更新

服务恢复方式：项目启动脚本启动后端 `8000` 和桌面前端 `5173`，移动 H5 以 Vite 启动在 `8080`。本轮未运行迁移、删除、发货、审批或其他业务写操作；仅使用用户明确授权的测试账号进行登录验证。

内置浏览器控制插件返回 `unsupported Codex auth method: apikey`，因此本轮使用本机 Playwright 驱动的真实 Chromium 页面完成验收。该运行时限制应在新对话中保留，不能将本轮结果描述为 Codex In-app Browser 验收。

桌面端登录后结果：

- `/parts` 正常显示零件列表、筛选/重置、新建入口和分页，4,990 条记录。
- `/production` 正常显示生产计划和资材确认队列，3 条计划。
- `/shipping-orders` 正常显示筛选、历史订单和查看入口。
- `/after-sales` 正常显示档案、筛选和列表，178 条记录。

移动 H5 登录后结果：

- 登录后进入 `/query`，查询控件可见。
- `/production` 正常显示生产状态和 3 条计划。
- `/delivery` 正常显示交付/库存/包装发货入口和暂无库存状态。
- `/scan` 正常显示扫码入口；未触发摄像头或提交扫描结果。

浏览器信号：控制台错误 0、4xx/5xx 响应 0；有 2 个路由切换期间被框架取消的 `ERR_ABORTED` 请求，无用户可见错误。追加 390×844 移动视口检查时，四个 H5 路由 `scrollWidth` 均等于 390，未见横向溢出。

最新判定：登录态核心只读页面已完成真实浏览器验收；项目仍未全部完成。全量后端测试失败簇、真实 PostgreSQL upgrade/downgrade、未接 API 页面、产品框二维码扩展、移动扫码/现场写入和 Spec 003/005/007 剩余任务仍由接手 Agent 处理。

## 2026-09-11 全量复验新增阻断项

再次复验确认：服务与页面均可访问，后端 compileall、桌面类型检查/构建、H5 构建通过；全量后端测试仍为 `325 passed, 23 failed, 23 errors, 1 skipped`。登录后桌面和 H5 各四个核心路由均正常渲染，控制台错误、HTTP 4xx/5xx 和非主动取消的请求失败均为 0；390×844 H5 无横向溢出。

必须优先修复测试数据库隔离：`backend/tests/conftest.py` 当前直接连接 `settings.DATABASE_URL`，没有测试库哨兵或统一回滚。全量测试后 `/parts` 记录数从 4,990 增至 5,012，疑似产生了 22 条测试残留。本轮没有删除记录，因为尚未确认每条记录的业务归属。新 Agent 在建立独立 `TEST_DATABASE_URL` 和回滚机制前，不应再次对当前配置运行数据库型全量测试；先审计这 22 条增量，再由用户确认清理范围。

后续清理已在用户明确确认后完成：共识别并删除 203 条历史测试零件，同时删除对应的 217 条 identity issue 和 217 条 legacy archive 记录。删除前已在同一事务内建立 `cleanup_backup_test_parts_20260911`（203 条）和 `cleanup_backup_test_part_audits_20260911`（434 条）恢复快照。删除后测试命名候选为 0、审计孤儿引用为 0；桌面 `/parts` 显示 4,890 条且首屏不再出现 `Test Part`。不要删除这两张恢复表，除非用户另行确认；测试数据库隔离仍是未解决的 P0。
