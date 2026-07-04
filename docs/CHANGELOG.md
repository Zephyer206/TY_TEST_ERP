# 变更日志

## V7.3（2026-05-27）图纸分类 + 临时目录 + 自动归位 + 报价页 UI 改造

### 功能变更

- 新增报价单编辑页面 `/sales/quotes/{quote_id}/edit`（`templates/sales/quote_edit.html`）
  - 路由：`sales.py` `@router.get("/quotes/{quote_id}/edit")`，权限 `role_level >= 4`
  - 数据源：`get_quote_detail_for_edit(quote_id)`，内部自动序列化 datetime/Decimal
  - **UI 改造**：
    - 报价状态"TECH_APPROVED"显示为"开发已填写"
    - 隐藏报价模式行
    - 材料牌号增删改（+新建/-删除按钮，调用 `sales.materials_quick_add` 和 `sales.material_delete`）
    - 核算面板新增"废料单价"行（`dispScrapPrice`）
    - 吨位/机型改为只读，自动带入技术部填写的 `quotes.machine_type`
    - 年用量拆分为"年均用量"（`quotes.annual_avg`）和"生命周期"（`quotes.lifecycle_years`）

- 图纸分类存放重构
  - 旧路径：`static/uploads/drawings/{uuid}.pdf`（平铺）、`static/uploads/sdr/{uuid}.pdf`
  - 新路径：`static/uploads/drawings/{客户名}/{零件名}/{零件号}/drawings/`
  - 无客户时：`static/uploads/drawings/_unassigned/{part_id}/drawings/`
  - SDR 文件前缀：`SDR_{uuid}.pdf`

- 无客户临时存放 + 自动归位
  - 上传时无客户 → 存入 `_unassigned` 临时目录
  - `update_quote(..., customer_id=...)` 发现 `customer_id` 从 null → 有值 → 自动调用 `migrate_drawings_for_quote(quote_id)` 迁移图纸到标准路径，同步更新数据库 URL

- `QuoteUpdateBody` 新增 `customer_id`、`annual_avg`、`lifecycle_years` 字段

### 数据库变更

- `quotes` 表新增 `annual_avg NUMERIC(12,2)`、`lifecycle_years NUMERIC(5,2)`（通过 SQL 直接添加，`alembic` 多分支故不使用迁移）

### 修改文件

| 文件 | 变更 |
|---|---|
| `app/api/sales.py` | `quote_edit_page` 路由、`_get_drawing_subdir()`、`_save_drawing_file()`、`api_drawing_upload()`（支持 part_id）、`QuoteUpdateBody` 加字段 |
| `app/api/tech_api.py` | `_get_drawing_subdir_by_quote()`、`api_sdr_upload()` 重构为分类路径 |
| `app/services/db_service.py` | `migrate_drawings_for_quote()`、`update_quote()` 加参数、`get_quote_detail_for_edit()` 序列化 |
| `templates/sales/quote_edit.html` | 完整重构 |
| `templates/sales/part_pricing.html` | 面包屑 |
| `scripts/migrate_drawings.py` | 一次性迁移脚本 |
| `static/js/api_config.js` | 新增 `sales.material_delete` |

### 已迁移文件

```
drawings/test/弹簧片/15/drawings/
  8e467c1bd5f44686acc79536516be41b.pdf       ← 业务图纸
  SDR_9dd4f6589fd0435cb3f0bc63fb0f3910.pdf  ← SDR 图纸
```
