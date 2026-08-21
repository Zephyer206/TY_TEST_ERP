# gaibo 售后 API 契约

所有路径以 `/api/v1` 为前缀。响应使用现有 FastAPI/Pydantic JSON 风格，分页统一返回 `items`、`total`、`page`、`page_size`。所有写接口必须经过现有 RBAC。

## 权限

| 能力 | 最低级别 | 说明 |
|---|---:|---|
| 查看和查询 | 1 | 客户页、全局搜索、详情、历史 |
| 编辑客户需求/安装包 | 2 | 固定字段、扩展字段、组成和备注 |
| 编辑图纸和工艺 | 3 | 版本、生效状态和步骤 |
| 管理客户配置 | 4 | 客户入口、显示名称、扩展字段定义 |
| 停用/恢复和迁移复核 | 5 | 仅保留审计，不物理删除 |

## 客户工作区

### `GET /after-sales/workspaces`

查询售后客户入口。支持 `search`、`is_active`、分页。

响应项至少包含：`id`、`customer_id`、`slug`、`display_name`、`is_active`、`record_counts`。

### `POST /after-sales/workspaces`

创建客户工作区。

请求：`customer_id`、`slug`、`display_name`、可选 `field_labels`、`extra_field_definitions`。

### `PATCH /after-sales/workspaces/{workspace_id}`

修改显示名称、状态和字段配置；不允许改变规范键含义。

## 全局查询

### `GET /after-sales/search`

查询参数：`q`、`workspace_id`、`record_type`（`single_part|installation_package`）、`status`、`page`、`page_size`。

响应项统一包含：`record_type`、`record_id`、`workspace_id`、`workspace_name`、`customer_part_number`、`ibi`、`tianyue_internal_composition`、`price`、`display_name`、`updated_at`。

搜索必须覆盖客户件号、IBI、天越内部组成、安装包号、单件名称和备注；SQL 分页，不返回已停用记录，除非传 `include_inactive=true` 且调用者具备权限。

## 客户页和单件库

### `GET /after-sales/workspaces/{workspace_id}/records`

查询客户下的单件需求和安装包。支持 `record_type`、`q`、`status`、分页和排序。

### `GET /after-sales/single-parts`

独立单件查询入口。支持 `q`、`workspace_id`、`has_customer_requirement` 和分页；返回主档案及客户数量，不复制客户数据。

### `POST /after-sales/single-parts`

创建单件主档案，可选 `part_id`、`tianyue_internal_part_no`、`name`、`drawing_reference`。

### `POST /after-sales/single-parts/{single_part_id}/requirements`

创建客户需求。四个固定字段 `customer_part_number`、`ibi`、`tianyue_internal_composition`、`price` 必填；扩展字段写入 `extra_data`。

## 安装包

### `GET /after-sales/workspaces/{workspace_id}/packages`

查询客户安装包，支持 `q`、资料状态、价格状态和分页。

### `POST /after-sales/workspaces/{workspace_id}/packages`

创建安装包，至少需要 `package_number`；若安装包本身承载核心字段，仍需校验 IBI、天越内部组成和价格的业务要求。

### `GET /after-sales/packages/{package_id}`

返回安装包主信息、组成、资料状态、备注和修改历史。

### `POST /after-sales/packages/{package_id}/items`

添加已关联客户需求或暂存组成。通常请求满足：`requirement_id` 与 `unlinked_customer_part_number` 至少一个，且 IBI、天越内部组成、数量、顺序齐全。若 Excel 已提供天越内部组成但 IBI 尚未提供，允许 `ibi=null`、`match_state=missing_ibi`，保留内部组成并在详情显示“待补 IBI”，不得猜测 IBI。

### `PATCH /after-sales/packages/{package_id}/items/{item_id}`

修改数量、顺序、状态和备注；已关联项不能无审计地替换为另一客户需求。

## 图纸、工艺和资料状态

### `GET/POST /after-sales/requirements/{requirement_id}/drawings`

当前阶段只维护客户图纸版本元数据，不启用 PDF 文件上传。每次新版本必须说明 `version`、`file_key`、`status`；仅一条版本可以标记当前生效。详情接口会同时预留单件主档案的天越图纸引用 `drawing_reference`。

正式启用文件上传后，增加 `POST /after-sales/requirements/{requirement_id}/drawings/file` 和 `POST /after-sales/single-parts/{single_part_id}/drawings/file` multipart 接口；响应增加 `preview_url`，由后端生成 PDF 首页缩略图，详情页据此显示缩略图。文件存储、版本、权限和备份规则见 [pdf-storage-plan.md](../pdf-storage-plan.md)。

### `GET/POST /after-sales/requirements/{requirement_id}/process-routes`

创建或查询客户专属工艺路线。路线写入步骤数组，每个步骤至少包含顺序、工序名称、机台/模具（可空）、关键参数、质量检查点和备注。

### `PATCH /after-sales/process-routes/{route_id}/current`

原子切换当前生效路线，并将同一需求旧路线置为历史。

### `GET/POST /after-sales/requirements/{requirement_id}/documents`

维护图纸、样件、PPAP 和客户扩展资料状态，日期字段独立返回。`submitted_at` 不得自动转换为 `ok`。

## 修改历史

### `GET /after-sales/history`

按 `workspace_id`、`entity_type`、`entity_id`、时间范围和分页查询。响应包含 `action`、`changed_fields`、旧值、新值、操作人和时间。

历史只读，任何成功的 PATCH/POST 都必须追加记录。

## 错误契约

- `400`: 固定字段缺失、扩展字段不符合客户定义、状态转换非法。
- `404`: 工作区、单件、需求、安装包或版本不存在。
- `409`: 同一客户需求已有当前工艺、版本号重复、组成顺序冲突或并发更新冲突。
- `403`: 当前用户无对应能力。
