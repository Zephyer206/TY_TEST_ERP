# gaibo 售后统一档案研究结论

## 研究范围

本阶段只为售后模块制定可实施的架构和迁移方案，不修改业务代码。研究输入包括：

- GitHub 上已完成且持续维护的 ERP/售后项目：ERPNext、Odoo、Dolibarr。
- 当前 Zephyr ERP 的 FMG 安装包实现、Alembic 迁移和 Vue 页面。
- 已确认的业务规则：客户优先组织、全局售后查询、单件主库、客户专属工艺、安装包引用单件、固定核心字段和修改历史。

## 参考项目结论

### ERPNext

**Decision**: 采用“客户上下文 + 独立业务档案 + 可追溯状态对象”的思想。

**Rationale**: ERPNext 将 Issue、SLA、Warranty Claim 等对象分开维护，同时以客户和关联对象串起查询。这适合本项目把单件主档案、客户需求、安装包、资料状态和历史拆成独立实体，而不是把所有字段继续堆在 FMG 安装包表中。

**Alternatives considered**: 直接把现有安装包表扩展为客户通用表。该方式短期改动小，但无法表达同一单件在不同客户下不同的图纸和工艺，也不能可靠支持单件全局查询。

### Odoo

**Decision**: 采用模块化菜单、列表优先和档案详情模式。

**Rationale**: Odoo 的模块和记录详情边界清楚，列表、筛选、详情和权限可以复用。售后导航使用一个通用客户工作区页面，不为每个客户复制 Vue 页面。

**Alternatives considered**: 为 FMG 墨西哥、客户1、客户2分别建立前端页面。该方式会造成页面分叉，新增客户需要发版，不符合客户可配置目标。

### Dolibarr

**Decision**: 采用跨客户全局搜索入口，并在结果中明确客户、记录类型和核心识别字段。

**Rationale**: 售后人员经常从客户件号、IBI 或内部组成反查档案，搜索入口应是独立工作流，而非藏在某个客户页面中。

**Alternatives considered**: 只提供客户内搜索。该方式不能满足单件库和跨客户定位需求，且相同内部单件被多个客户使用时容易漏查。

### OpenFSM

**Decision**: 仅参考“客户到工作任务”的关联思路，不作为主架构。

**Rationale**: 项目规模和维护活跃度不足，不适合承担本 ERP 的档案、权限、资料版本和迁移设计。

## 当前代码和数据库发现

- 后端模型位于 `backend/app/models/after_sales.py`，当前核心表为 `after_sales_installation_kits`、`after_sales_kit_components`、`after_sales_kit_component_annotations`、`after_sales_kit_change_logs`。
- 当前安装包主表含 `fmg_code`、`d_code`、`tianyue_pn`、`ibi_spec`、`internal_kit_spec`、图纸/样件/PPAP 状态、价格和原始 Excel JSON，字段命名和唯一约束均 FMG 专用。
- 当前 API 仅提供 `/api/v1/after-sales/installation-kits` 列表、详情和组成标注，不能按客户查询，也没有单件、客户需求、图纸版本或工艺路线资源。
- 当前前端页面为 `frontend/src/views/after-sales/kits.vue`，路由为 `after-sales/kits`，导航只显示 FMG 墨西哥。
- 现有安装包数据迁移于 `alembic/versions/20260814_after_sales_kits.py`，后续迁移必须先做行数、核心字段、组成和状态对照，再考虑停用旧 API。

## 关键设计决策

1. **客户优先但不复制页面**：数据库用客户工作区关联客户，前端用一套客户列表/详情组件；新增客户只需配置数据。
2. **单件主档案与客户需求分离**：单件主档案只保存跨客户稳定的身份和可选产品关联；客户件号、IBI、天越内部组成、价格、图纸、工艺和扩展字段存于客户需求。
3. **安装包只保存组合关系**：已建单件通过外键引用，未建档组成用暂存字段保存并明确 `unlinked` 状态，禁止复制单件主档案。
4. **固定字段采用规范键**：数据库固定保存 `customer_part_number`、`ibi`、`tianyue_internal_composition`、`price`；客户可改显示名称，但不能改查询语义。
5. **资料和工艺版本化**：图纸、工艺路线和资料状态均有版本/生效状态；同一客户需求只允许一个当前生效工艺。
6. **审计不可破坏**：成功编辑追加修改历史，历史记录不提供业务删除；客户停用采用软停用。
7. **迁移分阶段**：先创建新表并导入旧 FMG 数据，运行双读/对照报告；验收通过后切换 API 和前端，旧表至少保留一个观察周期。
8. **第一阶段桌面端**：不在本计划中加入移动端、外部门户、生产执行或客户自助审批。

## 需要在实现中遵守的约束

- 所有数据库访问使用现有 FastAPI + SQLAlchemy async + asyncpg 模式。
- 所有写 API 使用现有 `CurrentUser` 和 `require_role` 权限检查。
- 所有统计、分页和全局搜索在 SQL 中完成，并为客户、核心字段、状态和更新时间建立索引。
- 价格使用 `NUMERIC(14,4)`；文件只保存现有文件服务可引用的路径/对象键，不把二进制塞入业务表。
- 不删除或覆盖工作区中与本功能无关的历史改动。

