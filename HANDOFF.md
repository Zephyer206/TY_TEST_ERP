# Zephyr ERP 当前交接

更新时间：2026-09-23
工作目录：C:\Users\WIT_User\Desktop\Zephyr_test_Erp
当前分支：003-price-management-system

## 新对话先读

1. AGENTS.md：项目执行、浏览器验收和 API 架构硬约束。
2. 本文件：本轮最新实现与验收状态。
3. AGENT_HANDOFF.md：更早的历史交接记录和未解决的全局技术债。

不要执行 git reset --hard、git checkout -- 或批量删除。当前工作区有大量用户既有改动和未提交文件，开始任何修改前先运行 git status --short --branch。

## 本轮目标与结果

### 1. 零件详情 500

根因已经确认：数据库中的 ToolingBriefInfo.mold_type 可以为空，但详情响应 schema 曾按非空字段校验；另外运行中的 uvicorn 进程仍加载旧 schema，源码修改未重载时仍会返回 500。

已完成：

- backend/app/schemas/part_editor_relationships.py：mold_type 和详情兼容字段 status 允许为空。
- backend/app/api/part_editor_relationships.py：详情响应显式返回 status=None。
- 关系批量保存接口先执行乐观锁校验，再查询关系表，冲突场景可稳定返回 409。

## API 注册表迁移

桌面端和移动端共用后端接口以及共享注册表，不保留旧页面兼容调用层。

- 共享注册表：shared/api/registry.js
- 桌面类型桥接：frontend/src/api/registry.ts
- 桌面统一请求分发：frontend/src/api/client.ts
- 桌面领域模块：frontend/src/api/ 下的 auth、admin、parts、customers、dictionary、quotes、production、packaging、pricing、afterSales、shippingOrders 等模块。
- 移动端领域模块和请求客户端：mobile-h5/src/api/。
- /api/v1 只在底层请求客户端配置。页面和业务组件不应直接写后端路径、导入 axios 或调用原生 fetch。
- frontend/src/api/index.ts 已不再导出旧 axios/sendApiRequest 兼容客户端。
- frontend/src/utils/request.ts 仅保留底层 axios 实例；旧 get/post/put/patch/del 快捷导出已删除。
- 未使用的 frontend/src/utils/api-helper.ts（原生 fetch）已删除。
- 不存在的 warehouse.lowStock 和 sampling /upload 注册/调用已移除；sampling 附件目前只保留本地选择，后端正式 multipart 合同建立后再注册。

当前注册表验收：

- 111 个唯一 key。
- 重复 key：0。
- registry 字段无效项：0。
- 与实时 GET /openapi.json 的已注册 method/path 对比：0 个 miss。

## 已迁移的主要页面

零件列表、零件详情/编辑、客户、材料、字典、仪表盘、登录、包装、报价、客户价格、生产、排产、价格调整、售后、发货订单和权限 store 均已迁移到领域 API 模块。移动端查询、生产、交付、扫码、报工等页面使用 mobile-h5/src/api/。

## 已执行的验证

### 代码和接口

- PowerShell：7.6.5，分支确认：003-price-management-system。
- API 使用扫描：scripts/check_api_usage.ps1 -FailOnViolation -> 0 violation(s) found。
- 桌面端 npm run type-check -> 通过。
- 桌面端 npm run build -> 通过；仅有既有 Sass/Rollup 警告。
- 移动端 npm run check:api -> 0 violation(s) found。
- 移动端 npm run build -> 通过。
- PYTHONPATH=backend; python -m pytest backend/tests/test_part_editor_relationships.py -q -> 26 passed。
- 实际后端 API：登录 200，零件分组列表 200，详情和 include_tooling_catalog=true 均 200；前 20 个零件详情 20/20 通过。

### Playwright 页面验收

Codex 原生浏览器控制通道因 Codex auth token is unavailable 不可用；没有把它冒充为浏览器通过。使用本机 Playwright Chromium 完成实际页面验收。

- 桌面 http://127.0.0.1:5173/parts：显示 4890 条记录，首行详情抽屉可打开，编辑模式显示 26 个表单控件和“保存”按钮，页面错误 0。
- 移动端 390x844：登录后查询页显示零件数据，/api/v1/parts 返回 200；生产页显示“生产情况”，/api/v1/production/plans/workbench 返回 200，页面错误 0。

## 当前服务状态

交接前最后一次 PowerShell 检查：

- 后端 8000：已停止。
- 桌面前端 5173：已停止。
- 移动端临时开发服务 8080：已停止。

如需继续验收，按项目脚本/现有启动方式启动服务，并重新验证端口，不要假设服务仍在运行。

## 尚未解决或需要注意

- 工作区仍是脏的，很多文件是用户或此前任务留下的 staged/unstaged/untracked 变更；不要据此做清理或回滚。
- 没有把后端全量 pytest 宣称为通过。旧交接记录中仍有全量测试失败簇和测试数据库隔离 P0；继续跑数据库型全量测试前，先建立独立测试库/回滚机制。
- 这轮只保证注册表中的 111 个接口与实时 OpenAPI 契约一致，不代表后端全部 200+ 路由都已经被前端使用或全部纳入业务模块。
- sampling 页面仍是部分 TODO 页面；附件只暂存本地文件列表，没有虚构一个后端上传接口。
- 任何前端可见改动都必须重新做真实 Playwright 验收；类型检查、构建或 API 探针不能替代页面验收。

## 推荐接续顺序

1. 阅读 AGENTS.md、本文件和 AGENT_HANDOFF.md。
2. 运行 git status --short --branch，确认当前变更边界。
3. 如继续 API 工作，先检查 shared/api/registry.js、对应领域 wrapper、后端 route 和测试是否同步。
4. 如继续后端测试，先解决测试数据库隔离，不要直接对当前业务数据库运行会写入数据的全量测试。
5. 如继续前端工作，启动服务后使用 Playwright 验收目标页面，并分别报告实现结果和验收结果。

## 敏感信息规则

不要在新对话、命令输出、日志、截图、提交信息或报告中输出 .env、DATABASE_URL 密码、SECRET_KEY、令牌或测试账号密码。

## 2026-09-23 续接复核

本次续接未修改业务代码，仅重新执行了验证。实际 PowerShell 为 7.6.5，当前分支仍为 003-price-management-system。

### 实现与接口复核

- scripts/check_api_usage.ps1 -FailOnViolation：0 violation(s) found。
- 桌面端 npm --prefix frontend run type-check：通过。
- 桌面端 npm --prefix frontend run build：通过；仅有既有 Sass/Rollup 大 chunk 警告。
- 移动端 npm --prefix mobile-h5 run check:api：0 violation(s) found。
- 移动端 npm --prefix mobile-h5 run build：通过。
- PYTHONPATH=backend; python -m pytest backend/tests/test_part_editor_relationships.py -q：26 passed。
- 共享注册表静态校验：111 项、重复 key/path 0、字段错误 0；桌面和移动 wrapper 120 个调用点均有注册；与实时 OpenAPI 的 265 条路由比对，已注册接口缺失 0。
- /health 和 /openapi.json：HTTP 200。

### 浏览器复核

- Codex 原生浏览器通道仍因 unsupported Codex auth method: apikey 不可用，未将其冒充为通过。
- 使用本机 Playwright Chromium 实际验收：桌面 /parts 稳定显示 4890 条记录，首行详情和编辑模式可用；详情、历史请求均 HTTP 200，页面/控制台错误 0。
- 使用 390x844 Playwright Chromium 验收移动 /query?tab=parts 和 /production：零件详情弹层、3 条生产计划均可见，相关接口 HTTP 200，无页面错误和横向溢出。
- 首次导航中偶发的 ERR_ABORTED 是路由切换取消，后续相同请求返回 200，不是服务端 5xx。

### 续接后服务状态

- 后端 8000：仍在监听（PID 9808）。
- 桌面前端 5173：仍在监听（PID 10920）。
- 移动端临时 8080：已停止。
