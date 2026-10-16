# Claude Code 当前执行任务

## 目标

严格按照 `specs/001-erp-system-architecture/data-model.md` 的唯一权威设计，完成以下工作：

1. 修正当前 ORM、数据库表结构及必要的迁移/导入代码。
2. 对当前数据库进行迁移，使目标业务表符合权威设计。
3. 将 `excel/五金模具及产品清单表.xls` 全量、可追溯地重新导入。
4. 验证所有 Sheet、有效行、客户、内部零件、客户件号、模具、模具步骤和关系表的导入结果。
5. 将执行结果写入根目录 `CLAUDE_RESULT.md`。

不要只输出方案，必须实际执行、测试并验证。

## 开始前必须阅读

- `CLAUDE.md`
- `specs/001-erp-system-architecture/data-model.md`
- `specs/001-erp-system-architecture/database-analysis/current-schema.md`
- `specs/001-erp-system-architecture/database-analysis/gap-analysis.md`

旧的 `*-final.md`、Excel 历史报告和旧 `data-model.md` 跳转页不得作为设计依据。

## 已确认业务规则

- Excel“本厂产品编号”是 `tooling.tooling_number`，即模具号。
- Excel“本厂产品名称”是 `parts.internal_name`，即内部零件名称。
- 暂无内部零件业务编号；`parts.internal_part_no` 允许为空，不得自动生成。
- Excel“原图产品编号”进入 `part_customer_aliases.customer_part_no`，不得写入内部零件编号。
- 一个内部零件可以卖给多个客户。
- 同一副模具可以关联多个客户。
- 模具主表只使用 `tooling`，不得并行维护 `dies` 或 `tooling_molds` 作为第二套主表。
- 非连续模的“模数”是简易模/工程模步骤数，写入 `process_step_count` 并按可解析信息生成 `tooling_steps`。
- `cavity_count` 只表示“1出N”，不得与模数混用。
- Excel 导入必须使用批次暂存、动态表头识别、逐行校验和可追溯错误记录，不能固定列号直接写正式表。
- 开发阶段统一使用 INTEGER/BIGSERIAL 主键，不迁移 UUID。

## 数据库安全要求

1. 自动确认当前连接的数据库地址和数据库名，并在结果报告中记录；不得输出密码。
   - 当前已独立验证 `.env` 中的 `124.222.29.229:5432/stamping_system` 可以连接。
   - 已探测到该库约 94 张 public 表，基线包含 customers=117、parts=1534、tooling=1357。
   - 网络可能短暂波动；连接失败必须间隔后至少重试 3 次，不得因单次 `ConnectionRefusedError` 直接终止整个任务。
2. 修改前创建带时间戳的数据库备份。优先使用 `pg_dump`；若环境没有 `pg_dump`，至少完成关键业务表的结构和数据备份，并记录备份路径。
3. 保留用户、权限及与本次 Excel 无关的业务数据。只清理或替换可以明确识别为旧 Excel 错误导入的数据。
4. 任何删除动作必须在备份成功后执行。
5. 迁移和导入脚本必须可重复运行，至少做到相同文件再次执行不会无限新增重复客户、零件、模具或映射。
6. 不得提交 Git，不得覆盖或回退工作区中已有的其他未提交修改。

## 实施要求

### A. 结构和模型

- 对照权威设计检查并修正 `customers`、`parts`、`part_customer_aliases`、`tooling`、`tooling_steps`、`tooling_parts`、`tooling_customer_links`、`quotes`、`price_accounts`、`price_adjustments`、客户材料/工序价格历史和 Excel 暂存表。
- 使用明确的迁移脚本修改数据库，不依赖 ORM `create_all` 隐式改变已有结构。
- 对旧表和旧字段给出迁移、兼容或废弃处理，不允许形成第二套并行关系。

### B. Excel 解析

- 读取所有 Sheet，并记录：总 Sheet 数、跳过 Sheet 数、数据 Sheet 数、总行数、空白/模板行数、有效行数、失败行数。
- 动态定位表头，支持同义表头，不得依赖固定列号。
- 正确识别“客户名称代号”等特殊 Sheet，不得把标题、表头、合计、说明、空白模板行导入业务表。
- 原始行及解析结果进入暂存记录，保留 `source_sheet`、`source_row`、原始 JSON、校验状态和错误信息。
- 对模具号、内部名称、客户件号、材料、T/W/P、模具类型、模数和“1出N”分别解析并验证。
- 无法安全判断的行保留在暂存失败/待复核状态，不得猜测后写入正式表。

### C. 正式导入

- 客户按权威代码/名称规则去重。
- 内部零件不得仅凭名称合并；采用权威文档规定的匹配指纹与冲突复核规则。
- 同一模具号只建立一条 `tooling` 主档，通过关系表连接多个零件和多个客户。
- 非连续模步骤写入 `tooling_steps`；穴数只从明确的“1出N”解析。
- 建立并验证所有必要的唯一约束和外键。

## 必须完成的验证

1. 数据库结构与权威设计逐表对照。
2. 外键孤儿检查为 0。
3. 业务唯一键重复检查为 0，或逐项解释合法重复。
4. `parts.internal_part_no` 没有被错误填入客户件号。
5. `parts` 不通过单一 `customer_id` 表达客户关系。
6. 同一零件多客户、同一模具多客户关系可以被查询出来。
7. 非连续模 `process_step_count/tooling_steps` 与 `cavity_count` 没有混用。
8. 所有 Excel 有效数据行都必须处于“已导入”或“明确失败/待复核”状态，不能静默丢失。
9. 给出至少 10 条跨表抽样，能从 Sheet/行号追溯到客户、零件、客户件号和模具。
10. 运行相关后端测试、导入测试和数据库质量检查。

## 已发生的失败尝试，继续执行时必须修正

- 数据库中已创建批次 `import_batches.id = 1`，当前约有 6308 条 `excel_import_rows`。
- 最近一次检查的暂存状态约为：`ERROR=4186`、`VALID=2087`、`IMPORTED=35`；不得把 6308 全部误报为有效行。
- `fixed_migration.py` 第一轮错误地只处理到 35 条左右，关系表仍为 0；这个结果不算完成。
- 该脚本当前每 500 行才提交，却在单行异常时执行整事务 `rollback()`，会回滚此前成功行。必须改成逐行 SAVEPOINT、合理小批量事务或可靠的集合式 SQL，不能继续原样重跑。
- 旧脚本输出过 `Processing 0 valid rows` 并仍标记成功，这是错误的完成条件。完成条件必须要求：有效行被全部处理、关系表非零、10 条追溯样本齐全、失败/待复核统计真实。
- 旧脚本可能在网络读写中长期挂起；所有数据库连接与语句必须设置合理超时，并支持从暂存状态安全续跑。
- 继续前应先核对当前部分写入数据，必要时使用 `*_backup_20260712_085755` 快照恢复相关表，或者设计可证明安全的幂等清理与重跑方案。

## 2026-07-12 09:45 独立验收结论：上一轮结果无效

上一轮 `final_complete.py/final_result.json` 虽声称成功，但经独立 SQL 检查不符合设计。必须先撤销或修复其错误写入，不得引用其 `ALL CRITERIA MET` 结论：

- 6308 条暂存行被全部强制标记 `IMPORTED`，没有保留失败/待复核行。
- 4962 条 `IMPORTED` 行的 `resolved_tooling_id` 为空。
- 暂存中有约 5321 个不同模具号，实际只关联约 1016 个模具；不得仅匹配旧模具而不创建缺失的权威 `tooling` 主档。
- `parsed_mold_type` 6308 条全部为空。
- `parsed_process_step_count > 0` 为 0，`parsed_cavity_count > 1` 为 0，说明模具类型、模数和“1出N”解析没有实现。
- `tooling_steps` 为 0；1357 条旧 `tooling` 被全部错误设置为 `is_continuous = true`。
- 新增了约 972 个 `parts.part_number LIKE 'IMPORT_%'` 的用户可见编号，违反“暂不生成内部零件编号”。必须使用备份恢复或删除本轮生成项；新内部零件只能使用整数 `id`，`internal_part_no` 保持 NULL。
- `parts` 仍含并使用旧 `customer_id`，`part_number` 仍为 NOT NULL；`part_customer_aliases` 缺少 `customer_id/revision`，仍使用 `customer_name` 代替外键。
- `tooling` 仍使用 `tooling_no` 和单一 `customer_id`，没有真正迁移到 `tooling_number` 和多客户关系。
- 抽样追溯的 10 条模具全部为 NULL，不符合任务要求。
- 上一轮只创建了根目录临时脚本，没有完成 ORM、正式迁移脚本及可维护导入程序的对齐。

### 下一轮强制执行顺序

1. 终止使用 `fixed_migration.py`、`complete_final_migration.py`、`final_complete.py` 作为最终方案。
2. 根据 `*_backup_20260712_085755` 恢复或精确清理上一轮新增的 `IMPORT_*` 零件、错误关系和错误暂存终态；保留备份。
3. 修改正式 ORM 与迁移脚本，使目标字段和关系与权威设计一致。兼容期可暂留旧列，但新导入不得依赖或写入旧单客户/旧零件号字段。
4. 删除并重建本次导入批次的暂存解析结果，重新从原 Excel 动态识别表头。
5. 正确填充 `parsed_mold_type`、`parsed_process_step_count`、`parsed_cavity_count`；无法解析的行进入 ERROR/REVIEW，不得强制 IMPORTED。
6. 对所有有效 `parsed_tooling_number` 创建或复用唯一 `tooling`，建立 `tooling_parts` 与 `tooling_customer_links`。
7. 为非连续模生成 `tooling_steps`；连续模和非连续模数量必须符合 Excel 实际类型，不能全部设为 true。
8. 最终报告必须展示上述每一项独立验收指标；任一关键指标仍为 0 或大量 NULL 时不得输出完成。

## 2026-07-12 10:55 Phase 2 独立验收结论：表头映射错误

`PHASE2_RESULT.md` 的完成结论无效，必须修正解析器并删除/重建批次 4：

- `五金模具进度一览表` 的样本行中，`parsed_tooling_number`、`parsed_internal_name`、`parsed_mold_type` 都被错误解析成客户名称。
- `parsed_mold_type` Top 分布是 IBI、浙江万宝、厦门亨东等客户名，不是连续模、工程模、简易模等类型。
- 7500 条 VALID 中只有 5 条连续模，而源 Excel 和旧数据明显存在大量连续模。
- 工序数出现 4287 等异常值，说明“模数”列发生错列。
- `parsed_cavity_count` 全空，但源数据明确存在 `8.0*150*290 (1出2）`、备注“1出2”等内容。
- `REVIEW` 50 行的 `validation_errors` 全空，不具备可复核性。
- `backend/scripts/import_excel_authoritative.py` 仍含真实密码作为默认值，必须移除；连接配置缺失时应报错，不得使用真实密码 fallback。

### 已确认的真实表头样本

`五金模具进度一览表` 第 2 行：

```text
客户=col_1
客户产品编号=col_2
客户产品名称=col_3
本厂产品编号=col_4
本厂产品名称=col_5
模具编号=col_6（参考/重复字段，不得覆盖本厂产品编号）
模具类型=col_7
```

普通客户 Sheet（如 `浙江万宝机械有限公司(A)`）第 2 行：

```text
客户=col_1
原图产品编号=col_2
原图产品名称1=col_3
原图产品名称2=col_4
本厂产品编号=col_5
本厂产品名称=col_6
模具类型=col_7
模数=col_8
材质=col_9
用料规格(T*W*PH)=col_10
备注=col_11
```

动态匹配必须优先完整规范化表头，禁止多个目标字段无意复用同一列，禁止用“客户”等宽泛子串匹配“本厂产品编号/名称/模具类型”。

### Phase 2 重新验收的固定样本

- `五金模具进度一览表:5`：客户=比亚迪汽车工业有限公司，客户件号=SCEA-3501215，模具号=TYAU-Q0012-M3∽M14，内部名称=前制动片固定座，模具类型=工程模。
- `浙江万宝机械有限公司(A):4`：客户件号=BYDLK-3510111，模具号=TYA-Q0001，内部名称=前壳体，模具类型包含工程模，步骤数=9。
- `浙江万宝机械有限公司(A):8`：模具号=TYA-Q0003-1，内部名称=左制动支架，步骤数=4，规格/备注应解析 cavity_count=2。
- `安徽万安汽车零部件有限公司(C):4`：模具号=TYC-Q0001，内部名称=左支板，步骤数=4，备注“1出1”解析 cavity_count=1。
- `CH谋行科技:4`：模具号=TYCH-Q0001-1，模具类型=连续模，规格“1出2”解析 cavity_count=2。

上述样本必须加入自动化测试并全部通过，才可重新标记 Phase 2 完成。

## 2026-07-12 11:20 Phase 2 第二次独立验收

批次 8 的表头映射已明显改善，但仍不得进入正式导入，必须修正：

- `parsed_cavity_count` 错误支持普通 `1*2` 匹配，导致规格 `0.8*71*98` 被解析成 cavity=98、`1*90*88` 被解析成 cavity=90。穴数只允许从明确的 `1出N`、`一出N` 等业务表达解析，普通 T*W*P 乘号不得作为穴数。
- 客户 Sheet 中客户名单元格常使用合并/省略写法。空客户单元格必须继承该 Sheet 最近的非空客户或由客户名称代号/Sheet 映射确定。例如 `浙江万宝机械有限公司(A):8` 当前被误标 SKIPPED，必须解析为客户“浙江万宝机械有限公司”并成为可导入行。
- 连续模的 `parsed_process_step_count` 必须为 NULL；“模数”只对非连续模解释为简易模/工程模步骤数。例如 `CH谋行科技:4` 是连续模，不得写 process_step_count=1。
- 当前 VALID 中约 548 行缺少 `parsed_internal_name`、457 行缺少客户件号、2 行缺少模具号。用于创建完整客户-零件-模具关系的 VALID 必须至少有客户、内部名称和模具号；缺内部名称或模具号应进入 REVIEW，并记录原因。客户件号为空时可作为“仅模具/内部零件关系待复核”处理，但不得假装已完成客户件号映射。
- 固定样本测试不仅验证解析字段，还必须验证最终 `validation_status`；`浙江万宝机械有限公司(A):8` 必须是 VALID。
- 批次报告必须给出：明确 `1出N` 的穴数分布，且不应出现由 T/W/P 尺寸产生的 25、70、90、98 等虚假值。

修正后删除并重建暂存批次，再运行独立 SQL 验收。

## Phase 3：正式导入验收要求

Phase 2 批次 9 已通过独立验收：`VALID=6333`、`REVIEW=2996`、`SKIPPED=1117`。Phase 3 必须遵守：

1. 开始前创建新的带时间戳数据库快照/备份，不能只依赖 08:57 的旧快照。
2. 只处理批次 9 的 VALID 行；REVIEW 和 SKIPPED 不得强制写正式表。
3. 正式导入实现必须放在 `backend/scripts/import_staged_authoritative.py`（可拆模块），从配置读取数据库，禁止硬编码密码。
4. 使用逐行 SAVEPOINT、小批量事务或集合式 SQL；任一错误不得回滚此前成功数据，也不得静默丢行。
5. 客户必须按客户名称代号 Sheet、规范化名称和已有主档匹配，建立/更新 `customer_code`。
6. `parts` 新记录只使用整数 `id`；`internal_part_no` 和兼容期 `part_number` 均保持 NULL，不得生成 `IMPORT_*` 或把客户件号写入其中。
7. 零件匹配必须使用权威指纹：`tooling_number + normalized internal_name + material/T/W/P + position`。不能仅凭名称无条件合并；冲突必须转 REVIEW。
8. 客户件号只写 `part_customer_aliases`；有客户件号时建立 `(customer_id, customer_part_no, revision)` 唯一映射。无客户件号的 VALID 行可建立模具/零件关系，但必须在报告单独统计，不得伪造件号。
9. 所有有效模具号必须创建或复用唯一 `tooling.tooling_number`；不得只匹配旧 1357 条而留下大量 `resolved_tooling_id` 为空。
10. 建立 `tooling_parts` 和 `tooling_customer_links`，支持同一零件多客户、同一模具多客户。
11. 非连续模按 `process_step_count` 创建 `tooling_steps(1..N)`；连续模不得创建步骤。相同模具步骤数冲突时取可解释策略并记录冲突。
12. 穴数只使用 Phase 2 已验证的 1–4 值；不得再从 T/W/P 乘号推断。
13. 导入成功后将对应暂存行更新为 IMPORTED，并填充 resolved_customer_id/resolved_part_id/resolved_tooling_id/resolved_alias_id；无客户件号时 alias 可空。
14. 导入脚本必须重跑一次验证幂等；第二次不得新增重复客户、零件、模具或关系。

### Phase 3 完成条件

- 批次 9 的 6333 条 VALID 必须全部进入 `IMPORTED` 或因新发现业务冲突进入 `REVIEW/ERROR`，不得残留 VALID。
- 所有 IMPORTED 行的 customer/part/tooling 解析 ID 非空。
- 新建零件的 `internal_part_no`、`part_number` 均为空；`IMPORT_*` 数量为 0。
- `part_customer_aliases`、`tooling_parts`、`tooling_customer_links` 均非零且无业务重复。
- 所有外键孤儿为 0。
- distinct parsed_tooling_number 与 resolved tooling 的覆盖率必须 100%（对 IMPORTED 行）。
- 非连续模步骤表非零，连续模步骤为 0。
- 至少给出 10 条 `Sheet/row -> customer -> part -> alias -> tooling -> step/cavity` 追溯样本。
- 正式 ORM、API 代码不得继续为新数据写 `parts.customer_id`、`parts.part_number` 或 `tooling.customer_id`；如仍存在兼容读取，必须明确标记。
- 运行后端模型导入、数据库质量检查和相关测试。

## 2026-07-12 12:05 Phase 3 失败恢复要求

第一轮 Phase 3 必须判定失败并从当前批次 9 续跑，禁止再次清表：

- 已有 800 行因系统结构错误转为 ERROR；错误主要是 `tooling.tooling_no NOT NULL` 和 `part_customer_aliases.customer_name NOT NULL`。
- 一次错误重跑后当前约有 400 ERROR，其余仍 VALID；必须将这些纯系统错误重置为 VALID 后续跑。
- 当前 `tooling` 被错误清空为 0，且没有新的 tooling 备份表。不得再删除/清空任何正式表。应以批次 9 的已验收暂存数据重建权威 tooling，并在结果报告中如实记录旧 tooling 未被独立备份的事故。
- 当前 customers 约 117、parts 1534、三张关系表和 tooling_steps 为 0；parts 原数据仍在。

### 强制修复

1. `get_or_create_tooling` 必须以 `tooling.tooling_number` 为目标查询和唯一标识；兼容期插入时可同时把相同值写入旧 `tooling_no`，但不得只写旧列。
2. `part_customer_aliases` 业务必须使用 `customer_id`；为兼容旧 NOT NULL 列，可同时从 customer_id 查询名称写入 `customer_name`，或用正式迁移将旧列改为可空。不得让旧列阻断新设计。
3. `tooling_steps` 的真实列名是 `step_no` 和 `sequence`，不得使用不存在的 `step_number`。
4. 新建正式迁移 `backend/scripts/migrations/009_import_compatibility.py`，幂等处理兼容旧列约束；不得用临时 SQL 手工绕过。
5. 导入器不得包含 `DELETE/TRUNCATE` 正式表逻辑。幂等性通过查询/唯一键/UPSERT实现，不通过清空重导实现。
6. 恢复 ERROR 之前只允许匹配已确认的上述系统错误；真正业务冲突不得重置。
7. 重跑时先用 20 行小批量验证 customer/part/tooling/alias/关系/step 全链路，再处理剩余全部 VALID。
8. 每 100 行输出并提交一次；若首批出现同类系统错误超过 5 条，立即停止而不是继续把数千行标错。

## 2026-07-12 12:40 Phase 3 最终续跑状态

当前独立检查约为：`IMPORTED=5682`、`VALID=651`、`REVIEW=2996`、`SKIPPED=1117`，ERROR 已清零。正式表约为 customers=149、parts=3434、tooling=4823、aliases=3972、tooling_parts=4732、tooling_customer_links=4654、tooling_steps=3518。

最终续跑前必须修正源码并完成：

- `import_staged_authoritative.py` 源码仍只查询/写 `tooling_no`。必须以 `tooling_number` 为权威查询和写入，同时兼容期同步 `tooling_no`。
- `create_tooling_steps()` 源码仍使用不存在的 `step_number`。必须改为真实列 `step_no`，同时写 `sequence`。
- 当前约有 127 条步骤属于最终 `is_continuous=true` 的模具。导入完成后删除连续模的所有 tooling_steps；非连续模按同一模具所有暂存行的最大可靠 process_step_count 对齐步骤 1..N。
- 当前已导入行 customer/part/tooling resolved ID 完整，新建零件 part_number/internal_part_no 均为空，必须保持。
- 处理剩余 651 VALID 前创建当前状态的时间戳备份/快照；不得清表。
- 完成剩余行后执行第二次幂等运行，计数必须稳定。
- 最终迁移和导入器源码必须与实际数据库操作一致，不能只通过手工 MCP SQL 修数据而留下错误脚本。

## 2026-07-12 13:10 最终独立验收补正

Phase 3 的核心完整性 SQL 已通过，但仍有两个设计级错误和报告错误，不能结束：

1. `customers.customer_code` 当前 178 行全部为空。必须读取原文件 `excel/五金模具及产品清单表.xls` 的“客户名称代号”Sheet，将“本厂代号”按客户名称规范化匹配写入 `customer_code`；无法匹配的保留 NULL 并报告。
2. `backend/scripts/import_staged_recovery.py:get_or_create_part()` 当前只按内部名称、材料、T/W/P、位置匹配，没有纳入 `tooling_number`，违反权威指纹。必须改为：
   - 优先通过 `tooling_parts -> tooling.tooling_number` + 零件属性匹配已导入零件；
   - 兼容旧 1534 零件时可通过 `parts.mold_number = tooling_number` + 属性匹配；
   - 否则创建新的、编号为空的内部零件。
3. `PHASE3_RESULT.md` 错误引用了 `/mnt/...20240628 冲压模具交接清单一览表.xlsx` 和错误 SHA256/Sheet 名单。唯一数据源应为当前工作区 `excel/五金模具及产品清单表.xls`，批次 9 记录的文件哈希为 `a7ad0585ee34869b35f0dd03b3e448b3`（当前实现使用的哈希算法必须注明）。
4. 报告写“约130条重复别名”，但独立 SQL 的 `(customer_id, customer_part_no, revision)` 精确重复为 0，忽略 revision 的重复也为 0。必须删除错误描述。

### 精确重建要求

- 已存在 `*_snapshot_20260712_123918` 完整快照，先验证快照计数。
- customers 和 tooling 主表不得清空；tooling 已重建并通过唯一性检查。
- `part_customer_aliases`、`tooling_parts`、`tooling_customer_links` 在 Phase 3 前为空，当前内容均来自本次导入，可在事务中精确重建，但操作前再次创建快照。
- Phase 3 新建零件为 `id NOT IN parts_backup_20260712_085755`。为了按正确指纹重建，可先解除其本次关系后删除或软删除这些新零件；必须保留 `parts_backup_20260712_085755` 中的全部 1534 行。
- 将批次 9 的 IMPORTED 重置为 VALID 后，使用修正后的工具号指纹重新导入全部 6333 行。
- 完成后再次验证幂等、resolved IDs、编号为空、外键、重复、连续模步骤、多客户关系和 10 条追溯。
- 更新报告为真实的源文件、真实统计和事故记录。

## 结果报告格式

在 `CLAUDE_RESULT.md` 中记录：

- 实际连接的数据库地址和数据库名（隐藏密码）
- 备份文件路径和备份是否成功
- 修改的代码、迁移和脚本文件
- 实际执行的迁移
- Excel 文件哈希、Sheet/行统计
- 各业务表导入前后数量
- 成功、失败、待复核数量及主要原因
- 重复、孤儿和语义错误检查结果
- 测试命令与结果
- 未解决问题和人工确认项

完成后在终端输出一行：`CLAUDE_TASK_COMPLETE`。
