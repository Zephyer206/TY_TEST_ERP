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

查询公司及其客户入口。顶层按“天越 / 盖博”分组，客户工作区显式包含 `company_id`/`company_name`；天越客户不返回安装包能力，盖博客户可返回安装包能力。支持 `search`、`is_active`、分页。

响应项至少包含：`id`、已核实的 `company_id`/`company_name`、公司内 `customer_id`/`customer_name`、`slug`、`display_name`、`is_active`、`capabilities`、`record_counts`。不能通过同名候选或当前仅有一个售后客户而自动认定身份映射。

### `POST /after-sales/workspaces`

创建客户工作区。

请求：`company_id`、该公司内 `customer_id`、`slug`、`display_name`、可选 `field_labels`、`extra_field_definitions`。公司和客户关系必须通过显式映射校验。

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

公司区分的售后单件视图。天越和盖博客户在物理身份经确认后可引用同一 `parts.id`；公司/客户件号以独立作用域的别名保存，响应返回公司、客户和身份来源。盖博只有在显式确认物理零件共享后才能引用天越零件，禁止按件号相似度自动关联或覆盖天越别名。

禁止新增绕过归属规则的通用单件创建接口。新增天越物理零件走天越 `parts` API；盖博售后新身份留在盖博域。若盖博确认复用既有物理零件，只创建盖博客户要求和公司作用域别名，不改写天越客户数据。

### `POST /after-sales/workspaces/{workspace_id}/parts/{part_id}/requirements`

为指定公司客户对经确认的物理零件创建售后要求。客户件号/修订通过公司和客户作用域的别名管理；IBI、价格、币种、扩展字段和售后备注写入该客户要求。允许同一 `part_id` 有多家公司/客户要求，但不允许字段互相覆盖；歧义身份返回 `409`。

## 安装包

### `GET /after-sales/workspaces/{workspace_id}/packages`

仅查询盖博公司客户的安装包，支持 `q`、资料状态、价格状态和分页。天越工作区调用时拒绝或不提供该路由。每条记录明确返回所属公司、工作区及客户。

### `POST /after-sales/workspaces/{workspace_id}/packages`

创建安装包，至少需要 `package_number`，客户由路由中的已绑定工作区确定；不接受与工作区客户冲突的另一个客户值。若安装包本身承载核心字段，仍需校验 IBI、天越内部组成和价格的业务要求。

### `GET /after-sales/packages/{package_id}`

返回安装包主信息、组成、资料状态、备注和修改历史。

### `POST /after-sales/packages/{package_id}/items`

添加已关联统一零件或暂存组成。客户上下文继承自所属安装包/工作区，写入和匹配时不得跨客户。请求以 `component_part_id` 或 `unlinked_customer_part_number` 标识组成，不要求创建虚假的售后单件记录；客户专属 IBI、天越内部组成、数量、顺序继续保留在安装包行。若 Excel 已提供天越内部组成但 IBI 尚未提供，允许 `ibi=null`、`match_state=missing_ibi`，不得猜测 IBI。当前 `requirement_id` 是迁移兼容字段，不能作为最终零件身份。

### 导入客户边界

每个导入任务必须显式指定目标客户工作区，并校验来源文件/批次的客户范围。当前来源批次据业务说明只包含 ZF 墨西哥数据，因此只能导入经确认对应此客户的工作区；现存售后客户记录名为 FMG 墨西哥，ZF 与 FMG 是否为同一客户尚待业务确认，不得由名称或唯一批次推断。这不限制系统未来支持其他客户。客户不明或混有其他客户的数据必须拒绝导入或隔离复核，不得落入默认客户。

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
