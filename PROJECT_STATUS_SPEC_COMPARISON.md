# Zephyr ERP 当前状态与 Spec 对照报告

> 快照日期：2026-09-10  
> 目的：给下一位 Agent（包括 GPT-6）提供重构前的事实基线。  
> 结论先行：项目已经具备一个可运行的 FastAPI + Vue ERP 骨架和多条后端业务链路，但不能按“所有 spec 都已完成”处理。主 ERP 早期任务清单过于乐观；价格管理、售后档案、移动端、产品框二维码扩展和真实浏览器验收仍有明显缺口。

## 1. 总体判断

### 已经形成的能力

- 后端：FastAPI、SQLAlchemy async、Pydantic、PostgreSQL/asyncpg、Alembic、JWT 登录、角色权限、Redis 配置、审计模型和多领域 API 已建立。
- 桌面前端：Vue 3 + TypeScript + Vite + Element Plus，已有登录、零件、模具、生产计划、报价、客户、材料、质量、包装、喷涂、价格、售后和发货订单等页面。
- 移动 H5：Vue 3 + Vant，已有登录、查询、生产状态、库存/包装/发货查询和扫码入口。
- 数据库：已有较多历史迁移，包含报价、零件、客户别名、TWP/模具、生产、材料、质量、包装、价格、售后、发货订单等表结构。
- 测试：后端约 34 个测试文件，根目录约 5 个 Python 测试文件，已有发货、售后、零件编辑、TWP、权限和服务层测试；另有 Playwright 脚本和历史验收报告。

### 不能视为已完成的部分

- 真实数据库迁移和完整端到端环境没有在当前工作区重新证明；已有记录明确提到 PostgreSQL `WinError 5` 连接权限阻塞。
- 真实浏览器验收不是全绿。发货订单的多角色、正式订单组合、完整清理场景仍未全部验收。
- 价格管理的代码和页面已经存在，但 `specs/003-price-management-system/tasks.md` 的 85 项任务仍全部未勾选，且代码实现没有达到规格要求的证据闭环。
- Gaibo 售后后端部分接口已存在，但前端编辑工作台、权限矩阵测试、迁移验证和浏览器验收大部分未完成。
- 二维码规格已经扩展到产品框二维码池、拆框、B/C 转换和工艺流转，但实际代码主要仍覆盖原材料、机台和工艺流转卡二维码；没有发现完整的产品二维码池/产品框/转换域实现。
- 桌面导航仍有多个入口明确标记为 disabled，若干页面保留 `TODO: API` 或占位提示。
- 若干 spec 仍有 `NEEDS CLARIFICATION`，不能在重构时自行猜测业务规则。

## 2. 规范与任务清单统计

任务清单统计来自各特性的 `tasks.md`；“已勾选”不等于真实验收通过。

| 特性 | Spec 状态/范围 | tasks.md 勾选 | 实际判断 |
|---|---|---:|---|
| `001-erp-system-architecture` | 主 ERP，10 个用户故事，FR-001~FR-085 | 137 / 137 | 基础后端和多条 API 链路已建成；前端和真实验收仍有缺口，任务状态偏乐观 |
| `002-material-qr-traceability` | 原材料 + 产品框全链路二维码 | 30 / 30（任务表） | 原材料 QR、分卷、机台、工艺流转卡已实现；产品框 QR 池、拆框、B/C 转换未见完整实现 |
| `003-price-management-system` | 客户材料/工序价格历史、调价审批、字典 | 0 / 85 | 有模型、迁移、API 和部分页面，但没有按 spec 完成测试、迁移验证、权限、性能和生产准备 |
| `005-gaibo-after-sales` | 客户组织的单件/安装包售后档案 | 16 / 45 | 后端基础、查询接口和部分 UI 已有；编辑、文档/工艺、历史和验收缺口大 |
| `006-mobile-companion` | 移动端只读工作台和扫码入口 | 无标准任务清单 | foundation 已有；二维码摄像头、生产会话和现场报工明确延期 |
| `007-shipping-order-flow` | 正式/样件订单、标签、取消、分批发货、物流、历史 | 47 / 49 | 业务代码基本形成；T044 多角色验收、T048 完整 Playwright 验收未完成 |

补充：`specs/002-material-qr-traceability/tasks.md` 的任务表显示 30/30，但该 spec 自身写明“原材料二维码能力已实现，产品框流转为本次扩展”，因此不能只依据任务勾选判断产品框扩展完成度。

## 3. 已完成或基本完成的能力

### 3.1 基础工程与平台能力

代码证据：`backend/app/main.py`、`backend/app/core/config.py`、`backend/app/database.py`、`backend/app/core/security.py`、`backend/app/api/deps.py`、`frontend/src/router/index.ts`。

- FastAPI 应用、CORS/中间件、异常处理和 `/api/v1` 路由注册已经建立。
- PostgreSQL async SQLAlchemy 会话和环境变量配置已经建立。
- JWT 生成/验证、密码哈希、当前用户依赖和角色等级字段已经建立。
- 报价、生产、仓库、质量、包装、喷涂、价格、售后、发货订单和二维码路由已经在 `main.py` 注册。
- Vue 路由守卫、登录跳转、权限等级元数据和 Pinia 用户/权限 store 已存在。
- Alembic 迁移数量较多，当前根目录 `alembic/versions` 约 65 个版本文件；同时仓库中还存在 `backend/alembic` 和多组历史脚本，需要后续统一。

### 3.2 主 ERP 业务骨架

主 spec 的早期任务覆盖以下模块，代码中均能找到对应模型、服务或 API：

- 报价与审批：`quote.py`、`quote_service.py`、`quotes.py`，包含技术审核、老板审批、定点、样件/量产路径、价格快照和撤销定点接口。
- 打样：`sampling.py`、`sampling_service.py`、`sampling_tasks.py`，包含任务、老板审核、评审、加急和看板接口。
- 模具与维修：`tooling.py`、`tooling_service.py`、`toolings.py`、`machines.py`，包含模具台账、机台扫码和维修池接口。
- 生产计划与报工：`production.py`、`production_service.py`、`session_service.py`、`process_flow_service.py`，包含计划、机台分配、材料匹配、连续模会话、报工和工艺流转卡。
- 原材料与仓库：`warehouse.py`、`material_batch_service.py`、`warehouse.py` API，包含批次、IQC、分卷、消耗、报废和追溯。
- 质量：`quality.py`、`quality_service.py`、`quality.py` API，包含首件、OQC、特赦和巡检模型/接口。
- 包装：`packaging.py`、`packaging_service.py`、`packaging.py` API，包含扫码、全检和库存接口。
- 喷涂：`coating.py`、`coating_service.py`、`coating.py` API，包含配方和喷涂记录接口。
- 超级管理员视角切换：`admin.py`、`admin_service.py`、`admin.py` API，以及前端权限 store/路由守卫。

### 3.3 原材料/机台/工艺流转二维码

代码证据：`backend/app/services/qr_service.py`、`backend/app/api/qr.py`、`backend/app/api/warehouse.py`、`backend/app/api/production.py`。

- 原材料批次自动生成 QR、扫码查询、分卷生成子卷 QR、父子追溯和扫码日志已经存在。
- 机台 QR、工艺流转卡 QR、反向追溯、补打 QR 接口已经存在。
- 移动端扫码页面已经调用 `/qr/lookup`，并保留手动输入兜底。

### 3.4 发货订单业务

代码证据：`backend/app/models/shipping_order.py`、`backend/app/services/shipping_order_service.py`、`backend/app/api/shipping_orders.py`、`frontend/src/views/shipping-orders/index.vue`、`frontend/src/views/shipping-orders/detail.vue`。

已实现的范围包括：

- 正式订单/样件订单、草稿创建更新删除、客户件号搜索和名称快照。
- 重复客户 + PO 警告、未建档客户件号警告和显式继续提交。
- 提交锁定、标签确认、未标签撤回/取消、标签后双人取消确认。
- 按明细或整单分批发货、数量剩余计算、多个物流行、物流修改历史。
- 订单详情、发货历史、操作历史、草稿清理脚本和审计记录。

未完成的验收不是业务代码不存在，而是证据不足：`specs/007-shipping-order-flow/tasks.md` 中 T044、T048 仍未勾选，`docs/shipping-order-acceptance.md` 也明确记录了真实浏览器组合尚未全部复验。

## 4. 按 Spec 仍未完成或仅部分完成

### 4.1 `003-price-management-system`：代码存在，但不能标记为完成

已看到：

- `backend/app/models/price.py` 有 `TreatmentDict`、`CustomerMaterialPrice`、`CustomerTreatmentPrice`、`PriceAdjustment` 等模型。
- `alembic/versions/feb2532a66b9_add_price_management_tables.py` 和 `backend/scripts/migrations/001~007` 有建表/迁移脚本。
- `backend/app/api/customer_prices.py`、`price_adjustments.py`、`treatments.py` 已注册并有 CRUD/查询接口。
- 前端有 `price-management/index.vue`、`CustomerPricesQuery.vue`、`PriceAdjustments.vue`、`TreatmentDict.vue`。

仍需 GPT-6 优先确认/修复：

- 规格要求的 85 个任务全部未勾选，缺少 API、迁移、权限、并发、性能和 E2E 验证闭环。
- spec 要求老板审批通过后更新 `price_accounts.current_price`；当前审批 API 主要新增客户价格历史，需核对并补齐价格台账的原子更新。
- spec 要求 `role_level >= 2/3/4` 的权限边界；当前价格 API 文件中需要逐一核验是否真正使用角色依赖，不能只依赖前端按钮。
- 材料/工序历史默认最近 3 条、无历史返回默认参考价、Decimal 精度、不可删除审计历史等要求，需要补测试并统一响应契约。
- 旧表迁移、冲突记录、回滚脚本、旧表引用扫描和生产迁移检查清单未形成可证明的完成链路。
- 前端价格管理页面存在英文文案、直接输入 ID 和未统一的接口错误处理，适合在领域重构时一起整理。

结论：价格管理是“已有实现雏形 + 未完成验收和一致性收口”，不是空白模块，也不是完成模块。

### 4.2 `005-gaibo-after-sales`：后端基础完成，编辑工作台未完成

已完成任务 16 项，主要是迁移、模型、schema、服务基础、权限映射、查询 API 和部分全局查询 UI。

仍未完成的 29 项集中在：

- 客户工作区完整列表/详情 UI和可复用查询表格。
- 单件主档案、客户需求的完整 CRUD 服务、编辑器和客户隔离测试。
- 安装包编辑器、组成行编辑、状态控制、未保存保护和字段可编辑性验证。
- 图纸版本、工艺路线/步骤、当前版本事务规则、资料状态编辑。
- 全量变更日志写入、历史 API、不可变历史测试。
- 权限矩阵、前端 type-check/build、迁移对比、桌面/移动视口浏览器验收。

实际页面只有 `frontend/src/views/after-sales/index.vue` 和 `kits.vue`；spec 计划中的 `customer.vue`、`single-parts.vue`、`package-detail.vue`、`RecordDossier.vue`、`ProcessRouteEditor.vue` 等完整编辑结构没有全部出现。

### 4.3 `002-material-qr-traceability`：原材料链已做，产品框扩展缺失

已完成/存在：

- 原料入厂赋码、母卷/子卷、IQC、分卷、扫码历史、机台 QR、工艺流转卡 QR、反向追溯、补打 QR。

未完成或未发现完整实现：

- 产品二维码池批量生成和打印。
- `ProductQrPoolItem`、`ProductBox`、产品框工艺事件、父子框关系等核心实体。
- 一框一订单绑定、已绑定不可改绑、拆框和父子框追溯。
- 卷料规格异常通知/确认流程。
- B/C 全量/部分转换，部分转换强制拆框及操作工确认。
- 产品框数量覆盖写入、生产完成后的主管更正和全链路审计。

Spec 中仍有 3 个 `[NEEDS CLARIFICATION]`：状态名称/通知方式、订单量与备货量分配、B/C 实际完成数量转换规则。GPT-6 必须先让用户确认，不能自行定案。

### 4.4 `006-mobile-companion`：foundation 已有，现场能力延期

已经存在：

- 登录和统一 API client。
- 价格/零件查询。
- 生产计划只读工作台。
- 库存、包装、发货查询。
- 扫码页面和手动输入兜底。

明确未完成：

- 浏览器摄像头真实扫码接入。
- 生产会话关联后的现场报工提交。
- 扫码结果的角色动作闭环。
- 离线只读缓存和弱网重试。
- 生产部署到 `/m` 或独立静态站点以及反向代理验收。

`mobile-h5/src/views/Report.vue` 中仍有扫码获取机台/零件的 TODO；`/report` 路由按 quickstart 约定暂不暴露。

### 4.5 `001-erp-system-architecture`：后端宽度完成，前端完成度不可信

主任务清单 137 项全部勾选，但当前代码仍能看到大量未收口点：

- `frontend/src/views/layout/index.vue` 中“工艺查询、机台执行、工艺流转、材料、外协、仓库、全检与包装、后处理、价格查询、报价、客户、权限分配”等入口仍 disabled 或没有对应路由。
- 模具、采样、材料、包装、喷涂页面中存在 `TODO: API` 或“接口尚未接入”的明确提示。
- `frontend/src/views/warehouse/index.vue` 明确写着库存作业与余额接口尚未接入。
- `frontend/src/views/after-sales/index.vue` 的图纸区域目前只保留位置和版本接口，不上传文件。
- 若干成功标准（响应时间、权限 100%、看板刷新、预警时延、生产按期率）没有当前基准测试或监控证据。
- 主 spec 仍保留样件评审批准人权限的 `NEEDS CLARIFICATION`。

结论：主 ERP 的“领域骨架/API覆盖”较广，但不能把所有用户可见流程称为已完成。

## 5. 交叉工程风险

### 5.1 规范与事实状态不同步

- `001` 的任务清单全勾选，但代码中仍有大量前端 TODO 和 disabled 入口。
- `003` 的任务清单全未勾选，但代码、迁移和页面已经部分存在。
- `005`、`007` 的勾选状态相对可信，但浏览器验收和数据库实证仍需单独看报告。
- 需要把任务清单改成“实现状态”和“验收状态”两列，不能只用一个 checkbox。

### 5.2 数据库迁移路径混杂

仓库同时出现根目录 `alembic/`、`backend/alembic/`、`backend/scripts/migrations/` 和历史迁移脚本。重构前必须确定唯一权威迁移链、唯一 `alembic.ini` 和唯一数据库 head；禁止继续新增平行迁移目录。

### 5.3 业务领域边界重叠

- 价格模型同时存在旧价格字段、客户价格历史、价格台账和调价审批概念。
- 售后旧模型 `after_sales.py` 与 Gaibo 新模型 `gaibo.py` 并存，前端仍保留旧 `kits.vue`。
- 原材料 QR、工艺流转卡 QR 和未来产品框 QR 的身份模型尚未统一。
- 发货订单已经保留库存/生产批次占位，但库存分配、QR 拣货和逆向流程按 spec 有意延期，需要明确接口边界。

### 5.4 验收与测试证据不足

- 当前测试数量不少，但部分是静态 SQL/契约测试，不等于真实 PostgreSQL 集成测试。
- 价格管理缺专门测试文件；Gaibo 计划中的多组测试文件尚未建立。
- 前端页面的 type-check/build 不能替代浏览器验收。
- 当前工作区存在大量未提交改动和删除/新增混合状态，不能用 Git diff 直接推断功能完成度。

## 6. 重构前建议的优先级

### P0：先建立可信基线

1. 复制数据库到隔离测试库，确认当前 Alembic 唯一 head、迁移可重复执行、现有数据可读。
2. 运行后端静态检查、单元/契约测试和前端 type-check/build，记录失败清单。
3. 启动后端和前端，使用实际浏览器验收登录、零件、报价、生产计划、价格、售后、发货订单和移动 H5。
4. 把每个 spec 的状态拆成：代码存在、API 可用、UI 可用、集成测试、浏览器验收、生产准备。
5. 处理所有仍未澄清的业务问题，再开始大规模重构。

### P1：统一架构，不改变业务数据

1. 选定唯一迁移链和数据库模型注册入口。
2. 统一 API 前缀、错误响应、分页格式、权限依赖、审计写入和软删除规则。
3. 划定领域边界：身份/客户零件、报价价格、生产工艺、材料仓库、质量包装、售后档案、发货订单、移动只读。
4. 为所有跨领域写操作定义服务层事务边界，禁止路由直接拼接复杂数据库写入。
5. 先保留兼容路由和旧数据映射，再逐步替换前端，避免一次性破坏现有数据。

### P2：按业务价值逐块收口

推荐顺序：

1. 客户/零件/别名与报价主链路。
2. 价格管理：先迁移和历史查询，再调价审批，再前端和性能验收。
3. 生产计划、材料匹配、报工会话、质量放行和包装库存。
4. 原材料 QR 和工艺流转卡 QR 的统一身份模型。
5. 发货订单与库存/包装的正式集成。
6. Gaibo 售后编辑、图纸/工艺版本和历史追溯。
7. 产品框 QR 池、拆框、B/C 转换等未实现扩展。
8. 移动端摄像头扫码和现场报工。

## 7. 给 GPT-6 的工作约束

- 不要从“重写整个 ERP”开始；先读取本文件、`AGENTS.md`、相关 feature 的 `spec.md/plan.md/tasks.md`、当前迁移 head 和验收报告。
- 不要删除现有迁移、旧 API 或业务数据，除非先建立兼容迁移、回滚方案和备份。
- 对每一项功能同时记录“实现结果”和“验收结果”；没有真实数据库/浏览器证据时只能标记为部分完成或待验收。
- 前端修改必须启动实际应用并完成浏览器验收；代码编译通过不能代替验收。
- 不要输出或提交 `.env`、令牌、数据库密码、测试账号和其他秘密。
- 对 spec 中 `[NEEDS CLARIFICATION]` 的内容先向用户提问，不要凭经验替用户决定。
- 每次重构保持小步提交，优先增加测试和兼容层，再移动领域代码。

## 8. 建议 GPT-6 新对话第一条消息

```text
你是 Zephyr ERP 的重构 Agent。请先阅读项目根目录的 AGENTS.md 和 PROJECT_STATUS_SPEC_COMPARISON.md，然后按本报告列出的 P0 顺序工作。不要先重写代码。

第一阶段只做只读基线：
1. 对照 specs/001、002、003、005、006、007 的 spec.md、plan.md、tasks.md；
2. 检查唯一 Alembic head、数据库连接和当前工作区状态；
3. 运行可安全运行的后端测试、前端 type-check/build；
4. 启动后端和前端，完成真实浏览器登录和核心页面验收；
5. 输出“实现状态/验收状态/阻塞项/风险”四列表格。

没有我的确认，不要删除迁移、合并旧模型、改数据库结构、恢复或清理生产数据，也不要自行决定 spec 中的 NEEDS CLARIFICATION 业务规则。
```

## 9. 结论

这个仓库适合“保留数据和 API 契约、分领域渐进重构”，不适合直接按全新项目重写。现有系统最有价值的资产是：主 ERP 的业务模型和路由宽度、原材料 QR 追溯、发货订单服务、已有数据库迁移、Excel/业务数据和历史验收资料。最需要优先修复的是：事实状态与 spec 不同步、迁移链混杂、前端大量未接 API、价格/售后功能未收口、产品框 QR 扩展缺失，以及真实数据库/浏览器验收证据不足。

## 10. 2026-09-09 本轮复核证据

本节记录本次继续核对和兼容层修复的可复现结果，不把历史报告中的“计划完成”改写成“验收完成”。

### 10.1 工程检查结果

| 检查 | 结果 | 解释 |
|---|---|---|
| `python -m compileall -q backend/app backend/tests` | 通过 | Python 源码可编译，不代表业务测试通过 |
| `frontend: npm run type-check` | 通过 | TypeScript/Vue 类型检查通过，不代表浏览器流程通过 |
| `mobile-h5: npm run build` | 通过 | 移动 H5 生产构建通过；摄像头/现场报工仍是 spec 的后续阶段 |
| 发货订单核心测试 | 11 passed | 服务、状态、清理测试通过 |
| 售后/Gaibo 相关测试 | 39 passed | 服务、契约、文档事件、导入、历史测试通过 |
| 后端全量 `python -m pytest -q tests`（从 `backend/`） | 325 passed, 23 failed, 23 errors, 1 skipped | 不能宣称全量测试通过；本轮统一 TWP 小数精度错误消息后，较上一轮多通过 1 项 |
| 根目录 `python -m pytest -q backend/tests` | 启动失败 | 根目录运行时没有把 `backend` 加入 `PYTHONPATH`，报 `ModuleNotFoundError: No module named 'app'` |
| 根目录/`backend/` `alembic heads` | 都显示 `20260822_shipping_orders` | 两个配置入口最终指向 root `alembic/versions`；图中有两个 base、多个 branchpoint，仍需隔离数据库升级/回滚验证 |
| Alembic revision graph | 65 revisions、1 head、2 bases、无缺失父引用 | `001_initial` 与 `a1b2c3d4e5f6` 在 `20260730_explicit_part_grouping` 汇合；这不是线性链，也不证明空库可部署 |
| `alembic upgrade head --sql` | 静态 SQL 生成通过 | 在 `PYTHONIOENCODING=utf-8` 环境下完整 65 个 revision 生成成功；本轮已修复价格、QR、parts、权限迁移中的 offline 结果集读取。尚未在真实数据库执行 upgrade/downgrade |

全量测试当前最直接的失败证据包括：发货合同测试读取 FastAPI/Starlette 新版本的 `_IncludedRouter.path`；多个 Part/显示分组测试向当前 `Part` 模型传入不存在的字段；部分编辑器测试的异步 mock 形状与实现不一致；TWP 精度错误消息与测试断言不一致。这些属于当前代码/测试基线问题，不能被中断归因掩盖。

### 10.2 Spec 任务与文件证据复核

- `001`：任务清单 `137/137`，但导航仍有多个 disabled 入口，材料、采样、包装、喷涂、仓库等页面仍有 `TODO/API 尚未接入`。
- `002`：任务清单 `30/30`，但产品框二维码实体和流程关键字在 `backend`、`frontend`、`mobile-h5` 中没有实现证据；只能确认原材料/机台/工艺流转卡链路。
- `003`：任务清单 `0/85`；计划中的服务层和专门 API/E2E/迁移测试文件仍不存在。现有模型、API、页面属于部分实现。
- `005`：任务清单 `16/45`；客户工作区、单件/安装包完整编辑器、图纸/工艺编辑、统一历史 API 和浏览器验收仍未完成。
- `006`：Spec 明确为 foundation 已实现、二维码摄像头和生产会话阶段待后续；`Report.vue` 仍留有机台/零件扫码 TODO。
- `007`：任务清单 `47/49`；T044 多角色隔离验收和 T048 完整 Playwright 验收仍未完成，验收文档还记录数据库 `WinError 5` 阻塞。

### 10.3 中断造成的状态判断

仓库没有一个可靠的“中断次数”审计字段，Git 工作区又有大量既有未提交、删除和新增文件，因此不能从 `git status` 精确计算中断次数。能够确认的是：不同特性的 tasks、spec、代码和验收报告存在多次不同步，表现为任务全勾选但 UI 仍占位、任务全未勾选但代码已有雏形，以及验收记录明确保留未完成项。对交接而言，应按“多次中断后留下的半成品/待验收状态”处理，而不是按一次完整交付处理。

### 10.4 当前最终判定

项目**没有全部完成**。可交接的准确标签是：

1. 平台骨架、主 ERP 后端宽度、原材料 QR、发货订单核心服务和部分售后查询能力已形成。
2. 价格管理、Gaibo 售后编辑、产品框二维码扩展、移动现场能力和多个桌面前端入口仍是部分完成或未完成。
3. 全量后端测试失败，真实数据库迁移和完整浏览器验收没有证据闭环。
4. GPT-6 重构必须先修复测试/环境基线、明确唯一迁移入口、补齐产品框业务澄清，并将“实现状态”和“验收状态”拆开管理。

### 10.5 已执行的首批基线修复（2026-09-08）

- 迁移 API 默认不再挂载；legacy endpoint 即使显式挂载也要求显式配置和 LV4，新增 `test_migration_api_security.py`。
- 价格历史、调价和工序字典接口已补齐最小角色校验：价格读写 LV2、审批 LV3、工序字典读 LV1/写 LV4。
- 价格 schema 已去除重复的 `PriceAdjustmentCreate/Response` 定义，客户调价审批与旧价格台账嵌套路由使用显式分离的契约；驳回原因校验、审批行锁和审批/客户价格历史单事务写入已加入。
- `app/config.py` 已改为兼容转发，QR 服务和主应用统一读取 `app.core.config`。
- 生产启动新增安全配置校验，拒绝默认或过短 `SECRET_KEY`，并禁止生产环境开启 legacy migration API。
- 普通 API 认证依赖现在拒绝 `type=refresh` 的 JWT，refresh token 只能用于刷新接口。
- 本批验收：Python compileall 通过；迁移安全、运行时配置、价格 schema、token 类型和 LV1-LV4 权限测试共 25 项通过。

本次继续执行又补了一层不改表的价格兼容修复：

- `PriceAccount` 旧 API 路径继续映射 canonical `prices` 表，旧字段名映射到 `material_name/net_weight/gross_weight/remark`。
- 年度价格写入/读取改用 canonical `price_years`，不再访问不存在的 `annual_records` 表关系。
- 旧价格台账接口不再查询不存在的 `is_deleted`、旧 adjustment 关系或旧 Part 编号字段；调价历史统一由 `/price-adjustments` 审批域提供。
- `PriceYear` 已纳入模型导出，相关模型导入、编译和价格安全/契约回归测试通过。

这些改动只处理 ORM/API 兼容边界，没有执行数据库改名、删除或数据迁移。`prices/price_accounts` 的最终 canonical 选择、现有库数据映射和 Alembic 图验证仍未完成。

### 10.6 2026-09-09 迁移离线渲染复核

- 已将 `v18_prices`、`v19_prices_add_cost_fields`、`v20_prices_add_surface_cost` 的表/列探测改为 PostgreSQL 幂等 DDL；没有执行重命名、删除表或数据迁移。
- 已为 QR、parts/quotes、销售报价和 LV1-LV4 权限迁移补充 offline-safe 分支，避免在静态 SQL 模式读取 `fetchone()/fetchall()` 结果；在线模式仍保留真实数据库检查或等价幂等语义。
- 验证命令：`PYTHONIOENCODING=utf-8 alembic upgrade head --sql`（Windows PowerShell 对应 `$env:PYTHONIOENCODING='utf-8'; ...`），完整 65 个 revision 到 `20260822_shipping_orders` 生成成功，exit code 0。
- 该结果只证明 Alembic 静态 SQL 可以渲染；当前没有连接真实 PostgreSQL 执行 `upgrade`、`downgrade`、schema diff 或现有数据校验。两个 base、多个 branchpoint 和旧 `backend/alembic/versions` 仍是部署前风险。
- 本轮后端回归：价格/安全/配置相关 10 项通过；全量为 `325 passed, 23 failed, 23 errors, 1 skipped`。
- 本轮还统一了 TWP 小数精度错误消息，相关单测通过；剩余失败仍集中在 Part 旧字段、display groups、异步 mock、shipping contract 和 TWP 多工具行为。

## 11. 架构复核新增的 P0/P1 改进项

本节是对本轮状态盘点的架构安全复核。它们优先级高于继续补页面，因为其中几项会直接影响数据安全、权限边界和迁移可重复性。

### P0：进入重构前必须先处理

1. **完成运行时迁移接口的最终下线。**

   初始复核发现 `backend/app/api/migrations.py` 的 `POST /migrations/run-all` 可以执行 DDL、数据写入和提交，且原先没有认证。首批修复已让该 router 默认不挂载；显式开启时也要求 LV4，`status` 同样受保护。生产仍应彻底移除这条 legacy API，只通过受控 Alembic CLI/部署任务迁移。

2. **完成价格域 canonical schema 的数据库收口。**

   当前历史迁移仍同时出现 `prices` 与 `price_accounts` 契约，运行时 migration API 和 `backend/scripts/migrations` 也使用不同字段、主键和日期语义。本轮已让旧 `price_accounts` 路径在 ORM 层兼容 `prices/price_years`，但这不是最终迁移。仍应决定唯一表模型、ID 类型、历史表、调价表和字段命名，再做可回滚兼容迁移；在空库和现有库上分别验证 ORM、CRUD 和迁移结果。

3. **继续收口价格审批的 schema、权限和原子事务。**

   首批修复已拆分 schema、补驳回原因校验、行锁和单事务写入；本轮兼容层也避免旧台账接口再写错误字段。仍需在真实数据库上验证审批成功/失败回滚、价格台账更新、历史和审计的一致性，并补充并发回归测试。

4. **补齐价格数据读取的认证和数据范围。**

   首批修复已为材料/工序价格历史、调价列表/详情和工序字典补充登录及最小角色校验，但客户/部门数据范围仍没有统一策略。价格和调价原因属于业务敏感数据，应继续补充“认证 + 最小角色 + 客户/部门范围”的矩阵测试，覆盖未登录、LV1、LV2、LV3、LV4。

### P1：重构第一阶段统一

- **确认唯一 Alembic 迁移链。** 当前命令行 `alembic heads` 可显示一个可加载 head，但 `alembic branches`、静态扫描和 `backend/alembic/versions` 仍显示多个分支点、独立历史文件和旧目录版本；这不能证明空库与现有库都能沿同一条完整链升级。必须生成 revision graph，在隔离数据库执行空库 `upgrade head`、现有库校验、关键 `downgrade` 和 schema diff，证明唯一可部署链后再归档旧路径。
- **继续完善 Settings 运行校验。** Settings 已统一到 `backend/app/core/config.py`，旧 `app/config.py` 仅保留兼容转发，QR 服务也已切换。生产默认或过短 `SECRET_KEY`、legacy migration API 已加入启动保护；数据库配置和 CORS allow-list 仍应纳入同一套生产校验。
- **统一认证令牌生命周期。** 当前依赖主要验证 JWT 可解码，未明确区分 access/refresh；logout 只清理客户端 token。重构时增加 token 类型校验、短期 access token、refresh 轮换和撤销策略。
- **统一事务边界。** 数据库会话和多个 service/route 都可能主动 commit。路由应只负责输入和响应，跨表写入交给 application service，在一个事务中完成并有失败回滚测试。
- **明确旧售后与 Gaibo 的兼容边界。** 旧 `after_sales` 模型/API 与 Gaibo 新模型/API 并存时，要定义唯一写入口、映射层、双读观察期和下线条件，避免双写和两套数据继续漂移。
- **把发货角色改成 capability policy。** 当前 actor 身份通过部门/职位字符串猜测，未知用户可能落入默认业务角色。标签确认、发货确认和双人取消应使用显式能力权限，并补充角色矩阵和并发发货测试。

### 重构组织建议

按身份/客户、报价/价格、生产/工艺、材料/仓库、质量/包装、售后、发货、移动只读划分领域。每个领域固定 `api -> application service -> repository/model` 边界，禁止路由直接完成跨领域多表写入。统一主键、时间字段、软删除、分页、错误码和审计格式；二维码则抽象成统一身份解析和追溯协议，再由原材料、工艺卡和产品框实现各自绑定规则。

## 12. 2026-09-10 实际验收更新

本轮重新启动服务并完成了只读/页面验收，未执行数据库迁移、删除、业务写入或凭据输入。

### 12.1 工程检查

- `backend`: `python -m compileall -q app` 通过。
- 全量后端测试：`325 passed, 23 failed, 23 errors, 1 skipped`。失败簇仍为 Part 旧字段、display groups、TWP 多工具 fixture/mock、shipping contract 路由字段和两个编辑器 mock 行为，不能标记为全量通过。
- `frontend`: `npm run type-check` 和 `npm run build` 通过；仅有 Sass/依赖注释和大 chunk 警告。
- `mobile-h5`: `npm run build` 通过。
- `$env:PYTHONIOENCODING='utf-8'; alembic upgrade head --sql` 通过；`alembic heads` 仍为 `20260822_shipping_orders`。这只是静态 SQL 渲染，未证明真实 PostgreSQL upgrade/downgrade。
- `/health`、桌面前端 `5173`、移动 H5 `8080` 和 OpenAPI 均返回 HTTP 200。

### 12.2 真实浏览器验收（2026-09-10，未登录基线）

使用 Codex In-app Browser（用户未指定外部浏览器）：

- 桌面 `/parts`：页面真实渲染，导航、筛选、表格和分页可见，显示约 4,979 条记录。
- 桌面 `/production`：页面真实渲染，显示 3 条计划；新建计划、刷新、资材确认队列和状态摘要可见。
- 桌面 `/shipping-orders`：页面真实渲染，列表、订单类型/状态筛选、历史订单和查看入口可见。
- 桌面 `/after-sales`：页面真实渲染，档案入口、搜索、类型/资料状态筛选、视图设置和空结果状态可见；当前数据显示 0 条。
- 移动 `http://127.0.0.1:8080/login`：登录表单真实渲染；直接访问受保护的 `/query` 被重定向回 `/login`。
- 该节只保留为未登录基线；2026-09-11 已在用户明确授权后完成登录态复核，结果见 12.4。

### 12.3 验收结论

项目可运行、核心页面可打开，但仍不是“全部完成”或“全量验收通过”。后续应以本节数字、全量测试失败簇和本报告的 P0/P1 清单为重构基线。

### 12.4 2026-09-11 登录态浏览器验收更新

本轮先按项目启动脚本恢复后端 `8000` 和桌面前端 `5173`，再单独启动移动 H5 `8080`。未执行数据库迁移、删除、发货、审批或其他业务写入；只使用用户明确提供的测试账号完成登录验证。

由于 Codex 内置浏览器控制插件返回 `unsupported Codex auth method: apikey`，本轮改用本机 Playwright 驱动的真实 Chromium 页面进行验收。该限制不影响页面请求和渲染验证，但不应把本轮称为 Codex In-app Browser 验收。

#### 桌面端

- 登录页接受测试账号并跳转到 `/parts`，页面出现“登录成功”。
- `/parts`：真实渲染零件列表、筛选/重置、新建入口、分页，当前显示 4,990 条记录。
- `/production`：真实渲染生产计划、资材确认队列和状态摘要，当前显示 3 条计划。
- `/shipping-orders`：真实渲染订单类型/状态筛选、历史订单列表和查看入口。
- `/after-sales`：真实渲染档案入口、客户/类型/状态筛选和档案列表，当前显示 178 条。

#### 移动 H5

- `/login` 接受同一测试账号并跳转到 `/query`，页面出现“登录成功”。
- `/query`：查询、客户选择、件号/名称输入和查询价格入口可见。
- `/production`：生产状态、刷新、全部/待备料/可排产筛选和 3 条计划可见。
- `/delivery`：交付、库存、包装/发货入口可见，当前提示暂无库存记录。
- `/scan`：扫码入口和“点击扫码”按钮可见；本轮未触发摄像头或提交扫描结果。

#### 浏览器运行信号

- Playwright 页面控制台错误：0；HTTP 4xx/5xx 响应：0。
- 发现 2 个页面切换时被框架主动取消的请求（`ERR_ABORTED`），未形成用户可见错误，也未产生失败响应。
- 登录态路由、页面标题和关键可见文本均符合预期；以上只证明当前运行实例的页面验收，不代表全量测试或生产部署完成。
- 追加 390×844 移动视口检查：`/query`、`/production`、`/delivery`、`/scan` 的 `scrollWidth` 均为 390，与视口宽度一致；关键按钮可见，控制台错误仍为 0。

### 12.5 更新后的验收结论

登录态桌面端和移动 H5 的核心只读页面已完成真实浏览器验收；项目仍不是“全部完成”或“全量验收通过”。未完成项仍包括全量后端失败簇、真实 PostgreSQL upgrade/downgrade、未接入 API 的页面、产品框二维码扩展、移动扫码/现场写入流程和 Spec 003/005/007 的剩余任务。

### 12.6 2026-09-11 全量复验与测试隔离风险

本轮再次执行完整工程和浏览器验收，结果如下：

- 服务：后端 `/health`、OpenAPI、桌面登录页、H5 登录页均返回 HTTP 200。
- 后端：`python -m compileall -q app` 通过；全量测试仍为 `325 passed, 23 failed, 23 errors, 1 skipped`，与前次基线一致。
- 桌面前端：`npm run type-check`、`npm run build` 通过；构建仍有 Sass 旧 API 和大 chunk 警告。
- 移动 H5：`npm run build` 通过。
- 登录态浏览器：桌面四个核心路由和 H5 四个核心路由均正常跳转并渲染；控制台错误 0、非主动取消的请求失败 0、HTTP 4xx/5xx 为 0；390×844 下 H5 无横向溢出。

复验发现新的 P0 风险：`backend/tests/conftest.py` 的 `db` fixture 直接使用应用 `settings.DATABASE_URL`，没有强制测试数据库名称、环境哨兵或统一事务回滚。该文件注释也明确写明当前只是 placeholder，真实测试应使用独立数据库。执行全量测试后，桌面 `/parts` 从 4,990 条变为 5,012 条，说明测试很可能向当前应用数据库提交并遗留了数据。由于无法在不核对业务归属的情况下安全判断哪些记录可删除，本轮未做清理。

在继续运行数据库型测试前，必须先完成：独立 `TEST_DATABASE_URL`、拒绝非测试库的启动哨兵、每用例事务回滚或临时 schema/database、以及残留数据审计。此前 12.4 的 4,990 条是测试前快照；当前浏览器快照为 5,012 条。

### 12.7 2026-09-11 测试零件清理结果

经用户明确确认，已按审计过的名称模式清理历史测试残留。操作在单个数据库事务内完成，并先建立数据库内恢复快照：

- `cleanup_backup_test_parts_20260911`：203 条原始零件完整行。
- `cleanup_backup_test_part_audits_20260911`：434 条审计关联原始行（JSONB 快照）。
- 删除 `parts` 测试零件 203 条、`part_identity_migration_issues` 217 条、`part_legacy_identifier_archive` 217 条。
- 删除后相同测试名称候选为 0，两张审计表对 `parts` 的孤儿引用均为 0。
- 数据库当前有效零件口径为 5,350 条；桌面 `/parts` 按页面展示/分组过滤口径显示 4,890 条，首屏不再出现 `Test Part`，浏览器控制台错误为 0。

备份表当前保留，可用于恢复。本次只清理已经核实的测试命名范围，没有触及其他零件或业务关联表。测试隔离缺陷仍未修复，在独立 `TEST_DATABASE_URL` 和回滚保护完成前，不得再次对当前数据库运行全量数据库测试。
