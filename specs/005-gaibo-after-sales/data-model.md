# gaibo 售后数据模型

## 设计原则

售后档案按“所属公司 → 公司客户 → 售后记录”隔离。`parts.id` 表示经确认的物理零件身份，不等于某一家公司的客户件号。当前主系统数据以天越为主；部分物理零件可经确认被天越和盖博共同引用，但各公司/客户件号、别名、价格、图纸和工艺必须独立保存。盖博不得未经确认把新的业务记录写入天越零件主档。盖博可管理独立安装包，天越公司不提供安装包功能。安装包组成只有在身份确认且符合公司/客户权限后才关联零件；未确认组成保留原始行。

## 实体与字段

### `gaibo_customer_workspaces`

客户售后工作区，显式绑定一个所属公司和该公司客户身份，并保存售后模块自己的入口与字段显示配置。天越工作区禁用安装包；盖博工作区可启用安装包。任何导入都必须先确定盖博目标工作区，禁止由文件名、客户件号或当前唯一数据客户推断客户。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `customer_id` | integer | FK `customers.id`，唯一 |
| `slug` | varchar(100) | 唯一，用于路由和稳定查询 |
| `display_name` | varchar(200) | 页面标题，可与客户主数据名称不同 |
| `is_active` | boolean | 软停用，默认 true |
| `field_labels` | JSONB | 固定规范键到客户显示名称的映射 |
| `extra_field_definitions` | JSONB | 客户扩展字段定义，不改变核心字段 |
| `created_at/updated_at` | timestamp | 审计时间 |

### 统一零件 `parts`（售后单件主档）

天越或盖博客户售后单件均可在“共享物理零件身份已确认”时引用同一 `parts.id`；公司/客户件号通过带公司和客户作用域的别名保存。盖博单件不得因名称、件号相似或页面共用而进入天越 `parts`；无可靠映射的旧行保持待复核，不创建猜测的 `parts` 记录。

### 公司/客户零件别名

`part_customer_aliases` 的业务唯一作用域必须至少包含 `company_id`、`customer_id`、`part_id`、客户件号和修订。相同 `part_id` 在天越和盖博可以有不同客户件号；同一客户下的件号重复、修订差异或处理差异仍需按业务规则复核。别名不能仅凭名称、件号相似或数据库 ID 自动跨公司建立。

### `gaibo_single_parts`（仅历史兼容）

历史兼容表保留旧主键、来源字段和到 `parts.id` 的映射，供对账、旧接口兼容和追溯。切换期间不删除该表；新业务不得新增记录。具体迁移字段须以实际数据库结构为准。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `part_id` | integer nullable | 可选 FK 现有 `parts.id` |
| `tianyue_internal_part_no` | varchar(100) nullable | 天越内部查询号；不用于替代客户件号 |
| `name` | varchar(300) nullable | 单件名称 |
| `drawing_reference` | varchar(500) nullable | 全局图纸引用，可被客户图纸覆盖 |
| `is_active` | boolean | 软停用 |
| `created_at/updated_at` | timestamp | 审计时间 |

### `gaibo_customer_requirements`（客户零件要求表）

某公司客户对一个物理零件的一条独立要求，保存公司、客户、客户件号以及客户专属核心字段和售后内容。只有确认共享物理身份后，天越和盖博要求才可引用同一 `parts.id`；各自的业务字段互不覆盖。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `workspace_id` | integer | FK 工作区 |
| `single_part_id` | integer | 现行 schema 的历史兼容 FK；目标改为直接 FK 统一 `parts.id`，字段切换由后续 Alembic 阶段执行 |
| `part_customer_alias_id` | integer | 目标 FK `part_customer_aliases.id`；客户件号和修订从统一别名读取，不在售后要求中复制维护 |
| `ibi` | text | NOT NULL |
| `tianyue_internal_composition` | text | NOT NULL |
| `price` | numeric(14,4) | NOT NULL |
| `currency` | char(3) | 默认 USD |
| `extra_data` | JSONB | 客户扩展信息 |
| `remark` | text nullable | 业务备注 |
| `is_active` | boolean | 软停用 |
| `created_at/updated_at` | timestamp | 审计时间 |

客户件号身份由统一零件别名管理。售后要求唯一性须结合客户、`part_id` 及业务需求维度确认；重复数据分类前不得直接添加唯一约束。IBI、价格、币种、扩展资料和售后备注属于客户要求，不写入全局零件字段。

### `gaibo_installation_packages`

独立的客户售后安装包档案，不是 `parts` 单件记录。每个包必须经 `workspace_id` 归属一个已显式绑定客户的客户工作区，因此包的客户身份是必填且可从包详情/列表明确返回的业务字段；不能只依赖前端当前筛选上下文。安装包可在身份和分类经确认后关联组合父零件；映射未确认前不得自动创建或绑定零件。导入批次必须指定客户/工作区并校验文件中的客户范围，跨客户或客户不明的行拒绝导入或隔离待复核。当前来源批次据业务说明只含 ZF 墨西哥数据；现有数据库的售后客户记录名为 FMG 墨西哥，二者是否同一客户必须由业务确认，不可由名称或本批唯一性推断。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `workspace_id` | integer | FK 工作区 |
| 公司/客户归属 | via workspace | 工作区必须有已确认的公司和客户身份；API 响应返回公司、客户及名称，写入时从工作区派生，不接受客户端另传不一致归属 |
| `package_number` | varchar(200) | 客户侧安装包号，工作区内唯一 |
| `name` | varchar(300) nullable | 安装包名称 |
| `price` | numeric(14,4) nullable | 若安装包有独立价格则保存 |
| `currency` | char(3) | 默认 USD |
| `remark` | text nullable | 业务备注 |
| `source_data` | JSONB | Excel 原始映射和导入元数据 |
| `is_active` | boolean | 软停用 |
| `created_at/updated_at` | timestamp | 审计时间 |

### `gaibo_package_items`（安装包组成及迁移兼容）

安装包组成保留售后业务行、客户上下文、状态和来源。确认身份的组成可关联 `parts.id`；未关联行继续原样保留。安装包独立于 `parts`，因此本阶段不要求把售后组成同步到需要零件父件的 `part_BOM`；只有以后明确需要生产 BOM 语义时另行设计，不以虚构父零件满足结构约束。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `package_id` | integer | FK 安装包 |
| `requirement_id` | integer nullable | FK 客户需求；已关联时使用 |
| `unlinked_customer_part_number` | varchar(200) nullable | 未建档时的暂存件号 |
| `ibi` | text nullable | Excel 未提供时为空，详情标记“待补 IBI”；不得用内部组成代填 |
| `tianyue_internal_composition` | text NOT NULL | 组成级固定字段 |
| `quantity` | numeric(12,3) | 默认 1 |
| `sequence` | integer | 包内顺序，唯一于 package |
| `match_state` | varchar(20) | `linked` / `unlinked` / `missing_ibi` / `non_part` |
| `status` | varchar(30) nullable | 外购/暂无模具/开发中等标注 |
| `remark` | text nullable | 组成备注 |

约束：已关联项保留历史 `requirement_id` 并记录确认后的 `component_part_id`；普通未建档项使用 `unlinked_customer_part_number`。当 Excel 已提供内部组成但未提供 IBI 时，允许标记 `missing_ibi`。不得猜测或生成 IBI；天越内部组成始终保留。

### `gaibo_drawings`

客户专属图纸版本。作用域为客户工作区和统一零件，不覆盖全局零件或其他客户。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `requirement_id` | integer | 现行 schema 的客户要求 FK；目标可以继续通过要求记录解析到 `workspace_id` + `parts.id`，不复制零件身份 |
| `version` | varchar(50) | 需求内唯一 |
| `file_key` | varchar(500) | 文件服务对象键 |
| `status` | varchar(30) | `not_started` / `in_progress` / `ok` / `not_ok` / `not_applicable` |
| `effective_from/effective_to` | timestamp nullable | 生效窗口 |
| `submitted_at/approved_at` | timestamp nullable | 资料时间 |
| `remark` | text nullable | 资料备注 |

### `gaibo_process_routes` 与 `gaibo_process_steps`

客户和单件作用域内的工艺路线及步骤。

路线字段（当前实现）：`id`、`requirement_id`、`version`、`status`、`is_current`、`effective_from`、`effective_to`、`remark`、时间字段。目标语义按所属要求解析到客户工作区和统一 `parts.id` 隔离，不要求复制零件字段。

步骤字段：`id`、`route_id`、`sequence`、`operation_name`、`machine_id nullable`、`tooling_id nullable`、`key_parameters JSONB`、`quality_checkpoints JSONB`、`remark`。

约束：同一 `requirement_id` 只能有一条 `is_current=true` 的路线；步骤顺序在路线内唯一；生产执行记录不在第一阶段写入这些表。

### `gaibo_document_statuses`

统一保存图纸、样件、PPAP 和客户扩展资料的状态及时间，不再把日期混进无法查询的自由文本。

字段（当前实现）：`id`、`requirement_id` 或 `package_id`（二选一）、`document_type`、`status`、`submitted_at`、`concluded_at`、`remark`、`source_data`、时间字段。单件资料通过要求关联的统一 `parts.id` 定位。

状态枚举：`not_started`、`in_progress`、`ok`、`not_ok`、`not_applicable`。提交日期不等于通过，只有明确结论才允许显示为 OK。

### `gaibo_change_logs`

统一修改历史，覆盖客户配置、单件需求、安装包、组成、图纸、工艺和资料状态。

字段：`id`、`workspace_id`、`entity_type`、`entity_id`、`action`、`changed_fields JSONB`、`summary`、`actor_user_id`、`created_at`。

成功写操作必须追加一条记录；历史 API 只读，禁止业务删除。

## 关系图

```text
customers
  └─ gaibo_customer_workspaces
        ├─ gaibo_customer_requirements ── parts (`part_id`)
       │      ├─ gaibo_drawings
       │      ├─ gaibo_process_routes ── gaibo_process_steps
       │      └─ gaibo_document_statuses
        ├─ gaibo_installation_packages（独立售后安装包）
        │      └─ gaibo_package_items ── parts（组成身份确认后可选关联）
       └─ gaibo_change_logs
```

## 迁移映射

| 旧表/字段 | 新对象 | 规则 |
|---|---|---|
| `gaibo_single_parts.part_id` | `parts.id` | 现存显式外键优先作为已有关联证据；空值只生成候选，不因名称相似自动写入。旧记录及历史引用保留，歧义记录待复核 |
| 售后客户件号 | `part_customer_aliases` + 售后要求 | 客户、件号、处理、修订和质量状态核对后关联；不得静默合并重复项 |
| 客户工作区 | `customers` + `gaibo_customer_workspaces` | 建立显式客户映射，不按名称候选或相同数字 ID 自动连接 |
| 安装包 | `gaibo_installation_packages` | 作为独立售后实体保留，不并入普通 `parts` |
| 安装包组成 | `gaibo_package_items` | 售后组成行是权威记录；身份确认后可关联 `parts.id`，本阶段不强制写入 `part_BOM` |
| `after_sales_installation_kits.fmg_code` | `gaibo_installation_packages.package_number` | 仅在确认来源批次客户与目标工作区一致后逐行映射；当前来源据业务说明为 ZF 墨西哥，现有售后客户名为 FMG 墨西哥，二者关系待业务确认 |
| `d_code` / `tianyue_pn` | `gaibo_customer_requirements.customer_part_number` 或扩展字段 | 由导入映射配置确认，不能静默猜测 |
| `ibi_spec` | requirement/package item `ibi` | 保留原始值，空值进入人工复核 |
| `internal_kit_spec` | requirement/package item `tianyue_internal_composition` | 保留原始值，空值禁止新记录通过 |
| `price` / `currency` | requirement 或 package `price` | 数值精度保持，价格来源差异写入 remark/source_data |
| `drawing_status`、`sample_status`、`ppap_status` | `gaibo_document_statuses` | 解析状态与日期；提交日期不能自动判定 OK |
| `after_sales_kit_components` | `gaibo_package_items` | 一一对应项优先关联单件，无法确认则 `unlinked` |
| `after_sales_kit_change_logs` | `gaibo_change_logs` | 保留 action、summary、changed_fields 和时间 |
