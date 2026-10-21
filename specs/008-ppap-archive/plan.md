# PPAP implementation plan

## Stages and independent acceptance

1. 需求与环境：spec/checklist/contracts/data-model 完整；检查数据库版本、服务和预览运行时。
2. 服务端：新增 PPAP 表、独立私有文件目录、质量权限、公司隔离、乐观版本检查和快照；真实数据库/API 验收。
3. 界面：零件→PPAP，台账/详情/目录/预览/关联/提交历史；统一 API registry/client；构建及 API 使用扫描。
4. 浏览器：运行中应用完成建档、嵌套目录、上传与预览、新版本、旧快照、公司切换、只读权限、手机布局；记录证据。

## Architecture

- 复用 FastAPI/SQLAlchemy/PostgreSQL、Vue/Element Plus、公司 store。
- 新增独立 ppap domain API，所有端点注册到 shared registry，由 frontend/src/api/registry.ts typed bridge 暴露。
- 档案/目录/文件/文件版本/提交轮次/操作日志分表，工作资料可维护，提交快照保存当次不可变的 ID 和名称。
- 关联对象使用受服务端验证的结构化快照，绑定天越 parts 或盖博 requirements/packages。
- 私有文件位于公开 uploads 之外；读取走鉴权接口；UUID 存储名，用户文件名仅作元数据。
- Excel 在本机 LibreOffice 独立进程/profile 中转换为 PDF，限制超时，保留原件；前端通过统一 client 获取 blob 预览，提供工作表清单。
- PDF 使用本地 PDF.js 页面查看器，提供翻页、缩放和可读文字；Excel 转换为包含各工作表、图片和合并布局的 PDF，工作表可切换。样本质量单独验证。
- 不接入在线编辑、外发通知、生产放行自动联动。

## Existing work

工作区已有其他任务的未提交修改。只在必要的 main/models/router/layout/registry 位置追加 PPAP 集成，保留其他修改，不重置工作区。
