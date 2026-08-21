# 售后 PDF 图纸存储规划

## 当前阶段

当前只在单件详情中预留“客户图纸”和“天越图纸”的展示位置，不启用文件上传、PDF 预览或下载。详情页已经预留固定比例的 PDF 缩略图框；后续接口返回 `preview_url`（PDF 首页 PNG/JPEG 缩略图）后即可显示。已有图纸版本接口继续作为元数据接口使用，不能把服务器路径直接暴露给前端。

- 客户图纸：归属于客户需求 `gaibo_customer_requirements`，用于保存客户侧版本、状态和日期。
- 天越图纸：归属于单件主档案 `gaibo_single_parts`，现阶段通过 `drawing_reference` 预留引用位置，避免同一内部图纸被多个客户重复保存。

## 初期存储位置

项目当前使用腾讯云轻量服务器作为部署节点，第一阶段 PDF 存储在服务器挂载卷中：

```text
uploads/
└─ after-sales/
   └─ drawings/
      ├─ customer/{workspace_id}/{requirement_id}/{uuid}.pdf
      └─ tianyue/{single_part_id}/{uuid}.pdf
```

文件不放在 `frontend/dist`、`static` 或数据库中，也不使用客户名、零件名作为真实路径。数据库只保存文件元数据和相对文件键，文件由后端权限接口读取。

## 预留接口

当前已存在的元数据接口：

- `GET /api/v1/after-sales/gaibo/requirements/{requirement_id}`：返回客户图纸版本。
- `POST /api/v1/after-sales/gaibo/requirements/{requirement_id}/drawings`：创建客户图纸版本元数据。
- `PATCH /api/v1/after-sales/gaibo/drawings/{drawing_id}`：修改客户图纸版本元数据。
- `PATCH /api/v1/after-sales/gaibo/single-parts/{single_part_id}`：维护天越图纸的引用字段。

后续启用上传时，再增加 multipart 文件接口，不改变上述详情接口的基本结构：

- `POST /api/v1/after-sales/gaibo/requirements/{requirement_id}/drawings/file`
- `POST /api/v1/after-sales/gaibo/single-parts/{single_part_id}/drawings/file`

上传响应应包含版本、来源、对象键、原始文件名、文件类型、文件大小、SHA-256、`preview_url`（缩略图）和受权限控制的预览/下载地址。缩略图由后端在上传后生成，不由前端直接解析 PDF。

## 迁移与安全要求

1. 上传只允许 PDF，校验文件头、MIME 类型和大小；文件按版本追加，不覆盖历史文件。
2. 详情页只显示版本、状态、日期和文件名；真实文件路径由后端处理。
3. 服务器磁盘必须定期备份到腾讯云 COS、另一台服务器或离线介质，不能只保留单份。
4. 文件数量或容量增长后，将存储实现切换到 COS 私有桶；数据库中的相对文件键和业务接口保持不变。
