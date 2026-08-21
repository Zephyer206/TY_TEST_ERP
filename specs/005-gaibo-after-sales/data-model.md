# gaibo 售后数据模型

## 设计原则

数据模型把“跨客户稳定身份”和“客户具体要求”分开。安装包是客户交付组合，不复制单件资料。所有业务对象使用软停用或版本状态，历史记录保留。

## 实体与字段

### `gaibo_customer_workspaces`

客户售后工作区，复用 `customers` 的客户身份，但保存售后模块自己的入口和字段显示配置。

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

### `gaibo_single_parts`

独立单件主档案，是单件查询入口的数据集合，不按客户复制。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `part_id` | integer nullable | 可选 FK 现有 `parts.id` |
| `tianyue_internal_part_no` | varchar(100) nullable | 天越内部查询号；不用于替代客户件号 |
| `name` | varchar(300) nullable | 单件名称 |
| `drawing_reference` | varchar(500) nullable | 全局图纸引用，可被客户图纸覆盖 |
| `is_active` | boolean | 软停用 |
| `created_at/updated_at` | timestamp | 审计时间 |

### `gaibo_customer_requirements`

某客户对某单件的一条独立要求，保存四个固定核心字段和客户特有内容。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `workspace_id` | integer | FK 工作区 |
| `single_part_id` | integer | FK 单件主档案 |
| `customer_part_number` | varchar(200) | NOT NULL |
| `ibi` | text | NOT NULL |
| `tianyue_internal_composition` | text | NOT NULL |
| `price` | numeric(14,4) | NOT NULL |
| `currency` | char(3) | 默认 USD |
| `extra_data` | JSONB | 客户扩展信息 |
| `remark` | text nullable | 业务备注 |
| `is_active` | boolean | 软停用 |
| `created_at/updated_at` | timestamp | 审计时间 |

唯一性建议为 `(workspace_id, single_part_id, customer_part_number)`，同时允许同一单件在不同客户下拥有不同要求。

### `gaibo_installation_packages`

客户安装包档案。名称不写死 FMG，FMG 墨西哥只是一个工作区下的记录。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `workspace_id` | integer | FK 工作区 |
| `package_number` | varchar(200) | 客户侧安装包号，工作区内唯一 |
| `name` | varchar(300) nullable | 安装包名称 |
| `price` | numeric(14,4) nullable | 若安装包有独立价格则保存 |
| `currency` | char(3) | 默认 USD |
| `remark` | text nullable | 业务备注 |
| `source_data` | JSONB | Excel 原始映射和导入元数据 |
| `is_active` | boolean | 软停用 |
| `created_at/updated_at` | timestamp | 审计时间 |

### `gaibo_package_items`

安装包组成，既支持已建单件，也支持暂未建档的组成。

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

约束：已关联项使用 `requirement_id`，普通未建档项使用 `unlinked_customer_part_number`；当 Excel 已提供内部组成但未提供 IBI 时，允许两者均为空且 `ibi IS NULL`，状态为 `missing_ibi`。不得猜测或生成 IBI；天越内部组成始终保留。

### `gaibo_drawings`

客户专属图纸版本。作用域为客户需求，不覆盖全局单件或其他客户。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | integer | PK |
| `requirement_id` | integer | FK 客户需求 |
| `version` | varchar(50) | 需求内唯一 |
| `file_key` | varchar(500) | 文件服务对象键 |
| `status` | varchar(30) | `not_started` / `in_progress` / `ok` / `not_ok` / `not_applicable` |
| `effective_from/effective_to` | timestamp nullable | 生效窗口 |
| `submitted_at/approved_at` | timestamp nullable | 资料时间 |
| `remark` | text nullable | 资料备注 |

### `gaibo_process_routes` 与 `gaibo_process_steps`

客户和单件作用域内的工艺路线及步骤。

路线字段：`id`、`requirement_id`、`version`、`status`、`is_current`、`effective_from`、`effective_to`、`remark`、时间字段。

步骤字段：`id`、`route_id`、`sequence`、`operation_name`、`machine_id nullable`、`tooling_id nullable`、`key_parameters JSONB`、`quality_checkpoints JSONB`、`remark`。

约束：同一 `requirement_id` 只能有一条 `is_current=true` 的路线；步骤顺序在路线内唯一；生产执行记录不在第一阶段写入这些表。

### `gaibo_document_statuses`

统一保存图纸、样件、PPAP 和客户扩展资料的状态及时间，不再把日期混进无法查询的自由文本。

字段：`id`、`requirement_id` 或 `package_id`（二选一）、`document_type`、`status`、`submitted_at`、`concluded_at`、`remark`、`source_data`、时间字段。

状态枚举：`not_started`、`in_progress`、`ok`、`not_ok`、`not_applicable`。提交日期不等于通过，只有明确结论才允许显示为 OK。

### `gaibo_change_logs`

统一修改历史，覆盖客户配置、单件需求、安装包、组成、图纸、工艺和资料状态。

字段：`id`、`workspace_id`、`entity_type`、`entity_id`、`action`、`changed_fields JSONB`、`summary`、`actor_user_id`、`created_at`。

成功写操作必须追加一条记录；历史 API 只读，禁止业务删除。

## 关系图

```text
customers
  └─ gaibo_customer_workspaces
       ├─ gaibo_customer_requirements ── gaibo_single_parts
       │      ├─ gaibo_drawings
       │      ├─ gaibo_process_routes ── gaibo_process_steps
       │      └─ gaibo_document_statuses
       ├─ gaibo_installation_packages
       │      └─ gaibo_package_items ──(optional) gaibo_customer_requirements
       └─ gaibo_change_logs
```

## 迁移映射

| 旧表/字段 | 新对象 | 规则 |
|---|---|---|
| `after_sales_installation_kits.fmg_code` | `gaibo_installation_packages.package_number` | 创建 FMG 墨西哥工作区后逐行映射 |
| `d_code` / `tianyue_pn` | `gaibo_customer_requirements.customer_part_number` 或扩展字段 | 由导入映射配置确认，不能静默猜测 |
| `ibi_spec` | requirement/package item `ibi` | 保留原始值，空值进入人工复核 |
| `internal_kit_spec` | requirement/package item `tianyue_internal_composition` | 保留原始值，空值禁止新记录通过 |
| `price` / `currency` | requirement 或 package `price` | 数值精度保持，价格来源差异写入 remark/source_data |
| `drawing_status`、`sample_status`、`ppap_status` | `gaibo_document_statuses` | 解析状态与日期；提交日期不能自动判定 OK |
| `after_sales_kit_components` | `gaibo_package_items` | 一一对应项优先关联单件，无法确认则 `unlinked` |
| `after_sales_kit_change_logs` | `gaibo_change_logs` | 保留 action、summary、changed_fields 和时间 |
