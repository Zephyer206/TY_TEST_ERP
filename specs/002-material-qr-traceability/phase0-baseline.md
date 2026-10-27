# Phase 0：二维码基线盘点与验收报告

**日期**：2026-10-12（Asia/Hong_Kong）
**关联计划**：[plan.md](./plan.md)
**实现结果**：已形成可重复的只读盘点脚本、接口库存、数据库证据、业务決策草案和回归映射。
**盘点验收结果**：通过；**整个 Phase 0 结果**：INCOMPLETE，业务决定等待确认。

**2026-10-13 业务进度更新**：D-P001～D-P003 状态/站内通知、数量分配和实际完成数量转换已确认并回填规格，规格澄清标记为 0；其他 P0 契约仍待冻结。下列接口/数据库结果保留 2026-10-12 的实际盘点快照，不代表本轮重新执行了数据库或 UI 验收。

**2026-10-13 工程更新**：D-P007 的幂等/时间/重试/错误合同已确定；D-P005 编码/批量/A4 通用打印出口已确定、授权待角色决定。打印队列只读清单可见 PDF 及富士施乐/佳能重定向队列，未发出打印作业或验证物理设备。详见 [打印合同](./contracts/qr-printing.md)，这些结果不改变下面的 2026-10-12 数据库证据快照。

## 1. 执行阶段与边界

1. 核对 002 的规格、计划、模型、契约、旧任务和现有代码。完成；旧 `tasks.md` 为 2026-06 原材料/工艺卡任务，不能作为本次产品框扩展验收。
2. 盘点接口、共享 registry、权限、迁移图谱与实际数据库。完成；数据库强制只读事务，业务写入为 0。
3. 执行 QR 辅助函数与无效输入 API 检查，形成后续完整回归映射。完成；测试边界列在第 5 节。
4. 取得业务回答、回填规格/模型/契约、复核 Gate。尚未完成；状态见 [业务决策记录](./phase0-decisions.md) 和 [验收清单](./checklists/phase0.md)。

本轮没有执行生产迁移、创建测试业务记录、发送外部通知或修改前端。没有启动本地后台服务：最初对 `127.0.0.1:8000/health` 和 OpenAPI 的检查均无法连接；后续 API 检查在真实 FastAPI 路由的进程内 ASGI 测试中完成。

## 2. 可重复证据

脚本：[scripts/verification/inspect_qr_phase0.py](../../scripts/verification/inspect_qr_phase0.py)。输出：[phase0-evidence.json](./phase0-evidence.json)。

```powershell
python scripts/verification/inspect_qr_phase0.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_api_usage.ps1
```

脚本仅读取配置好的连接用于授权数据库检查，不输出连接 URL、密码、令牌或个人身份。输出只包含目录位置、路由、源码哈希、迁移标识、表结构和聚合数量。异常只记录类型；不打印原始异常。数据库使用 `SET TRANSACTION READ ONLY`，证据中 `transaction_read_only=on`。

## 3. 数据库与代码事实

| 项目 | 观察结果 | 含义 |
|---|---|---|
| 代码迁移头 | `20261009_qg_pricing_costs` | 当前唯一 head；迁移图共 72 个 revision、2 个历史 base |
| 实际数据库版本 | `20261009_qg_pricing_costs` | 版本一致；版本一致不保证每个约束与旧任务宣称一致 |
| 原材料批次/旧子卷/流转/扫码日志 | 各 0 条 | 不能用现有数据证明入库、分卷、审计和反查端到端结果 |
| 机台 | 53 条 | 已有设备主表 |
| 生产计划/机台分配 | 3 / 4 条 | 已有 `ProductionPlan` 和 `PlanMachineAssignment`，是否作为产品框订单需业务定案 |
| 生产会话/工艺流转卡 | 各 0 条 | 反向追溯需要后续独立测试库场景 |
| 产品框六表及通知 outbox | 7 张表均未创建 | 符合当前仍处于扩展规划阶段的事实 |
| 原材料 QR 字段 | `qr_code` 可空，实际无唯一索引/约束 | 与旧 T001 的“唯一非空”完成描述不同；必须补做兼容评估和测试 |
| 原材料身份 | `qr_uid` 非空且唯一 | 新子卷创建必须提供有效 `qr_uid` |
| 当前认证设置 | `AUTH_DISABLED=true` | 当前配置将用户代入 LV4；不能用此模式证明 LV1/LV2 权限验收 |

已有追溯数据链：`ProductionSession.plan_id/assignment_id/machine_id/material_batch_id/operator_id` → `ProcessFlowCard.session_id`。产品框事件需要明确关联这条来源链；只保存可编辑批次号不能替代可靠的原材料身份引用。

实际部门/等级账户聚合包含 `admin/LV4`、`engineering/LV2`、`prod/LV1/LV2`、`sales/LV2`、`warehouse/LV1` 和测试组。未发现专用质量部门组；生产计划没有专用订单业务负责人字段。不能仅靠 `require_role(min_level=2)` 将所有 LV2 当作生产主管或订单负责人。

## 4. 基线缺口与处理顺序

| 优先级 | 发现 | 证据和后续处理 |
|---|---|---|
| 前置 | 业务未冻结 | 2026-10-12 盘点时 FR-031～033 共 3 个澄清项；2026-10-13 三项全部关闭，订单/路线、打印、角色/收件人与可靠性契约继续评审 |
| 前置 | 双套母子卷结构不一致 | `MaterialBatch.children` 指向旧 `MaterialBatchChild`；新分卷使用同表 `parent_batch_id`；子卷查询引用的 `MaterialBatch.parent_batch` 未定义。先明确兼容范围，再补关系与回归 |
| 前置 | 新子卷缺少必填身份 | `split_batch()` 创建 `MaterialBatch` 时没有填 `qr_uid`，实际字段非空。应在独立测试库复现并修复，保证失败不扣母卷重量 |
| 前置 | 重复分卷编号冲突风险 | 每次分卷从 `CH01` 重编号，`batch_no` 实际唯一；同秒入库编号也依赖时间。后续做重复/并发用例及数据库序列方案 |
| 前置 | 持久化 QR 与扫码图片可能不同 | 扫码台账调用按当天日期生成的 `generate_material_batch_qr_base64()`；补打接口则使用已存 QR。跨天查询必须验证图片 payload 与已存身份一致 |
| 前置 | 部分返回字段存在类型风险 | 原材料补打对字符串 `lifecycle_status` 访问 `.value`；缺真实批次时该分支未运行。后续用字符串/空值夹具回归 |
| 前置 | 原材料 QR 约束漂移 | 实际 `qr_code` 可空且无唯一约束；不能只读 `alembic_version` 就认为旧二维码约束已生效 |
| 接口整合 | 31 个库存路由未登记 | 第 7 节逐路由列出；调用前补共享 registry、领域 wrapper、类型和合同，不删除仍有调用者的接口 |
| UI 整合 | 原材料追溯页面使用模拟数据 | `frontend/src/views/materials/trace.vue` 的 `handleScan()` 没有实际 API 调用；前端修复后必须做真实浏览器验收 |
| 产品框设计 | 契约缺口 | 元数据编辑、后续工艺推进、部分转换的子 QR/版本、机台扫码上下文、分配/负责人/通知重试契约仍需补齐 |
| 上线前 | 权限验收环境 | 使用独立测试配置和真实角色认证验证；禁止依赖默认代入 LV4 的验收模式证明权限通过 |

这些条目是盘点发现，尚未实施修复；本轮 Phase 0 授权范围为澄清与基线盘点。后续正式实施须以本表为回归前置，不沿用旧完成声明。

## 5. 已执行检查与验收限制

| 检查 | 实际结果 | 可以证明的范围 |
|---|---|---|
| MAT payload 生成与解析 | PASS | 虚拟实体 ID 的格式往返 |
| MCN payload 生成与解析 | PASS | 虚拟机台 payload 往返 |
| PFC payload 生成与解析 | PASS | 虚拟工艺卡 payload 往返 |
| 无效格式/未知前缀辅助函数 | PASS | 格式与类型基础拒绝分支 |
| QR PNG 生成 | PASS | 合法 PNG、300×300、base64 数据 URI；不代表打印机或实物扫码验收 |
| `/qr/lookup` 无效格式 | PASS，HTTP 200、`found=false` | 真实 ASGI 路由的无效输入分支 |
| `/qr/lookup` 未知前缀 | PASS，HTTP 200、`found=false` | 真实 ASGI 路由的未知类型分支 |
| 手工检索缺少 type | PASS，HTTP 200、`found=false` | 真实 ASGI 路由的必填业务参数分支 |
| 源码路由与 OpenAPI 比对 | PASS，32 个均存在 | 后端路由被应用挂载，不代表各数据库操作运行成功 |
| 数据库只读结构盘点 | PASS | 实际版本、表/列/约束/索引和数量 |
| API 使用扫描 | PASS，0 违规 | 当前扫描所覆盖的活跃源码规则；不是未登记路由数量检查 |

ASGI 检查使用合成操作工替换认证依赖、空数据库依赖，仅执行无需数据库的拒绝分支，不运行 lifespan。认证、生产服务生命周期、真实来料/分卷/工艺卡查询、纸质打印、扫码响应性能、并发和浏览器验收均 **NOT_RUN**。这些检查不能替代端到端验收，也不能认定旧基线全部通过。

## 6. 原材料及设备回归案例映射

| 案例 | 映射端点/能力 | 独立夹具与预期 | 状态 |
|---|---|---|---|
| R-MAT-01 | 登记、IQC、批次查询 | 独立测试物料/供应商；QR 非空且唯一，重量/状态正确、无身份漂移 | 未运行 |
| R-MAT-02 | 分卷、母卷/子卷扫码、子卷列表 | 100 kg 母卷拆 30+20，余 50；子卷有独立身份，母/子/同胞关系正确 | 未运行 |
| R-MAT-03 | 重复、并发及无效分卷 | 第二次分卷不重号；超量/零量/负数/状态错误拒绝，失败后母子数据不变 | 未运行 |
| R-MAT-04 | 扫码图像与补打 | 对旧日期 QR 查询并解码图片；身份不变，补打不建新批次，有操作者审计 | 未运行 |
| R-MAT-05 | 消耗、报废、流转查询 | 记录来源、变动前后重量与操作者，验证 LV1/LV2/LV3 边界 | 未运行 |
| R-MCN-01 | 生成机台 QR、机台扫码 | 本机状态/信息正确，写入 MCN 查询日志；缺机台返回 404 | 未运行 |
| R-MCN-02 | 既有设备扫描状态机 | 明确与新“再扫机台完成订单”的语义区分，不复用故障/维修扫描作为生产完成 | 未运行 |
| R-PFC-01 | 投料校验、开工、关会话、生成流转卡 | 会话→机台/计划/原材料/操作工→工艺卡链完整，回滚不留半提交 | 未运行 |
| R-PFC-02 | 工艺卡扫码、反向追溯 | 原材料/机台/模具/零件/操作工正确，沿稳定存储身份查询 | 未运行 |
| R-PFC-03 | 入库与工艺卡补打 | 记录入库确认，补打身份保持，状态与审计完整 | 未运行 |
| R-QR-01 | 通用 QR lookup/手工查询 | 已验证 3 个无 DB 拒绝分支；有效实体/越权/伪造 payload 仍需测试 | 部分通过 |
| R-QR-02 | 通用 QR 生成 | 在测试环境替换外部上传器，校验 prefix/图片；本轮未调用云上传 | 未运行 |
| R-LOG-01 | 扫码日志创建/查询 | 当前登录账号留痕，类型/动作和时间正确，不能伪造操作者 | 未运行 |

建议分别落地到 `backend/tests/test_material_qr_baseline.py`、`backend/tests/test_machine_qr_baseline.py`、`backend/tests/test_process_flow_qr_baseline.py`、`backend/tests/test_qr_baseline_permissions.py` 和真实浏览器用例；上述测试文件目前为后续交付目标，尚未创建。当前 `backend/tests/conftest.py` 默认使用应用数据库并可能提交用户，不能直接用作写入基线夹具；应先引入受保护的独立测试数据库配置及隔离事务。

旧 `quickstart.md` 的 US2 是“大卷分条”，新规格 US2 是“产品二维码池”，其 SC 标号也属旧版；后续更新操作手册时必须使用本轮 R-* 映射，不把旧编号套到新故事。

## 7. 现有 API 库存

下表的路径相对于 `/api/v1`，源码行号为本轮盘点位置。`最低等级` 仅指检测到的显式 `require_role` 调用，`登录` 表示没有发现更高等级 guard；不代表部门/订单范围权限已被验证。所有端点暂保留；未登记项在有新活跃调用之前必须登记。

| ID | 方法 | 路径 | 最低等级 | Registry | 源码 |
|---|---|---|---|---|---|
| B001 | POST | `/warehouse/material-batches` | LV2 | 未登记 | `backend/app/api/warehouse.py:699` |
| B002 | GET | `/warehouse/material-batches` | 登录 | 未登记 | `backend/app/api/warehouse.py:734` |
| B003 | GET | `/warehouse/material-batches/{batch_id}` | 登录 | 未登记 | `backend/app/api/warehouse.py:754` |
| B004 | GET | `/warehouse/material-batches/by-no/{batch_no}` | 登录 | 未登记 | `backend/app/api/warehouse.py:767` |
| B005 | PUT | `/warehouse/material-batches/{batch_id}/iqc` | LV2 | 未登记 | `backend/app/api/warehouse.py:780` |
| B006 | POST | `/warehouse/material-batches/{batch_id}/split` | LV2 | 未登记 | `backend/app/api/warehouse.py:804` |
| B007 | POST | `/warehouse/material-batches/{batch_id}/consume` | LV1 | 未登记 | `backend/app/api/warehouse.py:869` |
| B008 | POST | `/warehouse/material-batches/{batch_id}/scrap` | LV3 | 未登记 | `backend/app/api/warehouse.py:898` |
| B009 | GET | `/warehouse/material-batches/{batch_id}/trace` | 登录 | 未登记 | `backend/app/api/warehouse.py:922` |
| B010 | GET | `/warehouse/material-batches/scan/{batch_id}` | 登录 | 未登记 | `backend/app/api/warehouse.py:958` |
| B011 | GET | `/warehouse/material-batches/scan/child/{child_id}` | 登录 | 未登记 | `backend/app/api/warehouse.py:1011` |
| B012 | GET | `/warehouse/material-batches/{batch_id}/children` | 登录 | 未登记 | `backend/app/api/warehouse.py:1120` |
| B013 | POST | `/warehouse/scans` | 登录 | 未登记 | `backend/app/api/warehouse.py:1315` |
| B014 | GET | `/warehouse/scans/{entity_type}/{entity_id}` | 登录 | 未登记 | `backend/app/api/warehouse.py:1343` |
| B015 | POST | `/warehouse/material-batches/{batch_id}/reprint-qr` | 登录 | 未登记 | `backend/app/api/warehouse.py:1377` |
| B016 | POST | `/machines/{machine_id}/scan` | LV2 | 未登记 | `backend/app/api/machines.py:184` |
| B017 | POST | `/machines/{machine_id}/generate-qr` | 登录 | 未登记 | `backend/app/api/machines.py:333` |
| B018 | GET | `/machines/scan/{machine_id}` | 登录 | 未登记 | `backend/app/api/machines.py:351` |
| B019 | POST | `/production/sessions/verify-material` | 登录 | 未登记 | `backend/app/api/production.py:1078` |
| B020 | POST | `/production/sessions/start` | LV1 | 未登记 | `backend/app/api/production.py:1093` |
| B021 | POST | `/production/sessions/{session_id}/close` | LV1 | 未登记 | `backend/app/api/production.py:1268` |
| B022 | GET | `/production/process-flow-cards` | 登录 | 未登记 | `backend/app/api/production.py:1307` |
| B023 | GET | `/production/process-flow-cards/scan/{card_id}` | 登录 | 未登记 | `backend/app/api/production.py:1402` |
| B024 | GET | `/production/process-flow-cards/{card_id}/reverse-trace` | 登录 | 未登记 | `backend/app/api/production.py:1455` |
| B025 | PUT | `/production/process-flow-cards/{card_id}/inbound` | 登录 | 未登记 | `backend/app/api/production.py:1503` |
| B026 | POST | `/production/process-flow-cards/{card_id}/reprint-qr` | 登录 | 未登记 | `backend/app/api/production.py:1571` |
| B027 | GET | `/qr/lookup` | 登录 | qr.lookup | `backend/app/api/qr.py:272` |
| B028 | POST | `/qr/generate` | 登录 | 未登记 | `backend/app/api/qr.py:347` |
| B029 | GET | `/qr/material/{batch_id}` | 登录 | 未登记 | `backend/app/api/qr.py:376` |
| B030 | GET | `/qr/machine/{machine_id}` | 登录 | 未登记 | `backend/app/api/qr.py:400` |
| B031 | GET | `/qr/process-flow/{card_id}` | 登录 | 未登记 | `backend/app/api/qr.py:425` |
| B032 | GET | `/qr/part/{part_id}` | 登录 | 未登记 | `backend/app/api/qr.py:450` |

## 8. 迁移与回滚方案

1. 业务 Gate 通过后，新增产品框独立表的增量迁移，目标 `down_revision` 基于再次确认的当时 head；本轮基准为 `20261009_qg_pricing_costs`，不能使用旧 quickstart 的 `qr002_material_traceability` 当作当前迁移目标。
2. 先在独立测试库重放迁移图、检查实际约束差异，并准备数据库备份/恢复演练。现有两个历史 base 要保留，不重写或重新盖章已有版本。
3. 先验证 upgrade，再验证空测试数据下 downgrade 回本轮基准、再 upgrade；记录新表/索引/外键/枚举与旧原材料表不变的结果。
4. 产品框已产生正式扫码/绑定/拆框/转换事件后，不用 drop 表回滚；先停止新增写入，回退兼容应用版本，保留 QR 身份和审计，按审批后的备份恢复方案处理数据。
5. 本轮没有执行任何上述升降级、备份导出或生产恢复；这些是可执行顺序和进入条件，不是已完成证据。

## 9. Phase 0 Gate 结论

基线盘点已通过限定范围内的验收。2026-10-13 正式状态、站内通知、数量分配和实际完成数量转换已确认并同步设计文档，`requirements.md` 无澄清残留检查通过；可靠性与编码/通用打印工程基准已确定。订单/路线、角色/收件人及打印授权仍见 [phase0-decisions.md](./phase0-decisions.md)，当前 **Phase 0 INCOMPLETE**，不进入生产迁移或上线实现。


## 10. 2026-10-22 只读刷新与收尾

代码迁移头和业务库版本均为20261020_ppap，product_qr_pool_items/product_boxes存在数为0；扫码列分别使用scantype/scanoperation PostgreSQL枚举，旧关联主键均integer。此次仅查询catalog及alembic_version，未执行业务DDL/DML。Phase 0当前结论见phase0-closeout.md；本报告此前的INCOMPLETE及20261009基线保留为历史证据，不用于当前迁移父版本。
