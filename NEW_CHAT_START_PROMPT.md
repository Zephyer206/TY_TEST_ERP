# 新对话启动提示词（直接复制）

你是 Zephyr ERP 项目的接手 Agent。请先不要修改代码，也不要输出任何密钥、令牌、数据库密码或测试账号内容。

请按以下顺序阅读并完成接手检查：

1. 阅读项目根目录 `AGENTS.md`，遵守其中的执行、验收和安全规则。
2. 阅读 `AGENT_HANDOFF.md`，了解用户目标、已完成事项和交接包排除项。
3. 阅读 `PROJECT_STATUS_SPEC_COMPARISON.md`，先了解各 Spec 的完成度、缺口、风险和建议重构顺序。
4. 阅读 `DEPLOYMENT_ENVIRONMENT.md`，确认新电脑需要安装的软件、端口、环境变量和启动方式。
5. 阅读 `TRANSFER_README.md` 和 `README.md`，了解迁移说明与项目概览。
6. 执行只读检查：`git status --short --branch`，确认 Python/Node/npm/PostgreSQL/Redis 版本，并检查后端和前端目录结构。
7. 如果依赖尚未安装，按 `DEPLOYMENT_ENVIRONMENT.md` 创建 Python 虚拟环境并执行 `pip install -r backend/requirements.txt`、`npm install`（frontend 和 mobile-h5）。
8. 在不打印配置值的前提下检查 `.env`、`backend/.env`、`.mcp.json` 是否指向当前电脑可访问的服务；不要把这些文件提交到公开仓库。
9. 确认 PostgreSQL 数据库后再执行 Alembic 迁移；如果需要恢复业务数据，先让用户确认要使用哪个 `backups/` SQL 备份。
10. 启动后端和前端，完成真实浏览器验收；前端改动不能只用编译结果代替浏览器验收。
11. 首次回复用户时，先报告环境检查结果、当前 Git 工作区状态、阻塞项和建议的下一步，等待用户指定要修改的功能。

重构前的 P0 顺序：

1. 核验 `POST /api/v1/migrations/run-all` 默认未挂载；它当前不是 Alembic 受控流程，生产应最终移除。
2. 生成 Alembic revision graph。当前已知结果是 65 个 revision、1 个 head `20260822_shipping_orders`，但有两个 base 和多个 branchpoint；必须在隔离数据库验证空库升级、现有库校验和回滚路径，不能把单 head 当成可部署证明。
3. 对价格域完成 canonical schema 收口。旧 `price_accounts` API 已有一层映射到 `prices/price_years`，但真实数据库兼容迁移、主键/字段最终选择和审批表校验仍未完成；先补契约测试，再改迁移。
4. 继续验证价格审批的 LV2/LV3/LV4 权限、并发锁和单事务原子性；首批重复 schema、驳回原因和基础行锁修复已经完成。
5. 统一 `backend/app/core/config.py` 与 `backend/app/config.py` 的 Settings 来源，生产启动时拒绝默认 `SECRET_KEY`。

在以上基线问题处理前，不要开始大规模前端重写或删除旧迁移。每项工作分别记录“实现状态”和“验收状态”。

当前首批基线修复已经完成：legacy migration API 默认关闭并受 LV4/配置保护；价格相关接口已补最小角色校验；重复价格 adjustment schema 已拆分，审批请求校验、行锁和单事务写入已加入；普通 API 已拒绝 refresh token；Settings 已统一到 `app.core.config`；生产密钥校验和回归测试已加入。最新一轮还修复了旧价格台账 API 对不存在字段的读取，并将年度价格接到 `price_years`。接手后应从真实数据库兼容迁移、Alembic 可执行性和全量测试失败继续，不要重复修改已完成的安全基线。

当前可复现后端基线（2026-09-10）：从 `backend/` 运行 `python -m pytest tests -q` 得到 `325 passed, 23 failed, 23 errors, 1 skipped`；`python -m compileall -q app` 通过。`frontend` 的 `npm run type-check` 与 `npm run build`、`mobile-h5` 的 `npm run build` 均通过。使用 `PYTHONIOENCODING=utf-8` 运行 `alembic upgrade head --sql` 已完整生成 65 个 revision 的静态 SQL，`alembic heads` 为 `20260822_shipping_orders`，但尚未在真实 PostgreSQL 执行迁移或回滚。

2026-09-11 登录态浏览器验收已完成：先恢复后端 `8000`、桌面前端 `5173` 和移动 H5 `8080`，再用用户明确提供的测试账号登录。桌面 `/parts`（4,990 条记录）、`/production`（3 条计划）、`/shipping-orders`（订单列表/查看入口）、`/after-sales`（178 条档案）均真实渲染；移动 H5 `/query`、`/production`、`/delivery`、`/scan` 登录后均真实渲染。Playwright Chromium 页面控制台错误为 0，4xx/5xx 响应为 0；有 2 个路由切换期间被框架取消的请求（`ERR_ABORTED`），未形成可见错误。390×844 移动视口下四个 H5 路由均无横向溢出。Codex 内置浏览器控制插件因 `unsupported Codex auth method: apikey` 不可用，因此本轮不能称为 In-app Browser 验收。扫码摄像头和任何业务写入未触发。

重要新增阻断项：不要直接运行数据库型全量测试。`backend/tests/conftest.py` 当前直接使用应用 `settings.DATABASE_URL`，没有独立测试库哨兵或统一事务回滚；2026-09-11 再次运行全量测试后，`/parts` 从 4,990 条增至 5,012 条，疑似遗留 22 条测试数据。当前未清理，因为业务归属尚未核对。接手后先建立独立 `TEST_DATABASE_URL`、拒绝非测试库的保护和每用例回滚，再审计增量并让用户确认清理范围。最新浏览器快照的零件数是 5,012，不应继续引用 4,990 作为当前值。

上述测试残留后来已经用户确认并完成清理：实际累计识别 203 条测试零件，连同 434 条对应迁移审计记录删除；数据库内恢复快照为 `cleanup_backup_test_parts_20260911`（203 条）和 `cleanup_backup_test_part_audits_20260911`（434 条）。清理后测试候选为 0、审计孤儿引用为 0，桌面 `/parts` 显示 4,890 条且不再出现 `Test Part`。不要重复清理或删除恢复表。测试隔离本身仍未修复，因此在建立独立测试库前不要再次运行数据库型全量测试。

交接背景：用户要在另一台电脑继续修改整个 Zephyr ERP 项目。压缩包保留了源码、迁移、文档、业务数据、`.git`、环境配置、令牌和测试账号；这些敏感值只能用于本地配置，绝不能出现在回复、日志、截图或提交中。虚拟环境、node_modules、缓存和运行日志没有随包带走，需要在新电脑重建。最新浏览器验收结果以本段和 `AGENT_HANDOFF.md` 的 2026-09-11 节为准。
