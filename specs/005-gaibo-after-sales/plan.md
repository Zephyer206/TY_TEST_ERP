# Implementation Plan: gaibo 售后统一档案

**Branch**: `005-gaibo-after-sales` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-gaibo-after-sales/spec.md`

## Summary

2026-09-23 已确认售后单件直接使用统一 `parts`，安装包保留为独立售后实体。映射证据、迁移顺序和不可自动匹配规则见 [unified-parts-transition.md](./unified-parts-transition.md)。本文早期“独立单件主档案”描述以统一 `parts` 为准；当前数据/API 切换尚未完成。

把当前 FMG 专用安装包档案升级为客户可配置的 `gaibo` 售后模块。售后单件直接引用统一 `parts`，售后表保存客户要求、客户工作区、独立安装包/组成、图纸版本、客户专属工艺、资料状态和修改历史；先做只读映射预演，再逐步切换 API，不复制或自动合并有歧义的数据。前端采用一套客户工作区页面，同时支持售后查询、客户内零件/安装包筛选和档案详情，不为每个客户复制页面。

## Technical Context

**Language/Version**: Python 3.11+（本地后端保留项目现有 bundled Python 3.12 runtime）；TypeScript 5.9；Vue 3

**Primary Dependencies**: FastAPI 0.109、SQLAlchemy 2.0 async、asyncpg、Pydantic v2、Alembic、pytest/pytest-asyncio、Vue Router、Pinia、Element Plus、Vite

**Storage**: PostgreSQL 15；文件由现有 file service 保存对象键，业务表只保存引用和版本元数据

**Testing**: pytest + pytest-asyncio 后端单元/集成测试；Vue type-check/build；Codex 实际浏览器验收

**Target Platform**: Linux/Docker 后端和桌面浏览器工作台；第一阶段不覆盖移动端和客户门户

**Project Type**: FastAPI REST web service + Vue 3 web application

**Performance Goals**: 全局售后查询 P95 < 2 秒；客户列表/详情在目标数据量下分页返回；详情打开不重复请求同一资源

**Constraints**: 固定核心字段不可为空；客户可改显示标签但不可改规范键；工艺按客户需求隔离且只有一个当前版本；历史只追加不删除；所有写接口走 RBAC；迁移期间保留旧表和旧数据，不清理无关工作区改动

**Scale/Scope**: 当前已上传数据批次仅覆盖 ZF 墨西哥；系统须通过显式客户工作区支持后续多个客户，不将当前导入批次误作单客户系统约束。预计数千安装包、数万组成/单件需求；第一阶段实现桌面端查询、详情、编辑、版本和审计，不实现生产执行和外部门户

## Constitution / AGENTS Check

项目没有可用的 `specs/constitution.md`；本计划以根目录 `AGENTS.md` 为治理依据。

| AGENTS 要求 | 计划符合性 | 验证方式 |
|---|---|---|
| 先拆分阶段再改状态 | 通过 | 本计划按迁移、后端、前端、测试和验收分阶段 |
| 每阶段有独立验收证据 | 通过 | `quickstart.md` 为每阶段列出数据库、API、UI 验收项 |
| 保留无关历史改动 | 通过 | 新增/定向修改 gaibo 文件；不 reset、checkout 或清理工作区 |
| 不暴露凭据和秘密 | 通过 | 文档和测试不输出 DATABASE_URL、密钥或登录密码 |
| UI 必须真实浏览器验收 | 通过 | 最终阶段使用 Codex 浏览器测试并单独报告结果 |

**Gate result**: PASS。无需要以复杂度表豁免的治理冲突。

## Project Structure

### Documentation

```text
specs/005-gaibo-after-sales/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── contracts/after-sales.md
```

### Backend

```text
backend/app/models/after_sales.py       # 新 gaibo 模型，旧模型在迁移观察期保留
backend/app/schemas/after_sales.py      # 请求/响应 schema
backend/app/api/after_sales.py           # 统一售后路由（逐步替换 FMG 专用路由）
backend/app/services/after_sales_service.py
backend/app/services/after_sales_migration_service.py
backend/tests/test_after_sales_*.py
alembic/versions/*_gaibo_after_sales.py
backend/scripts/import_after_sales_gaibo.py
backend/scripts/verify_after_sales_gaibo.py
```

### Frontend

```text
frontend/src/views/after-sales/index.vue       # 售后查询/客户工作区入口
frontend/src/views/after-sales/customer.vue    # 通用客户页，单件/安装包筛选
frontend/src/views/after-sales/single-parts.vue
frontend/src/views/after-sales/package-detail.vue
frontend/src/components/after-sales/RecordSearch.vue
frontend/src/components/after-sales/RecordDossier.vue
frontend/src/components/after-sales/ProcessRouteEditor.vue
frontend/src/components/after-sales/ChangeHistory.vue
frontend/src/router/index.ts
frontend/src/views/layout/index.vue
frontend/src/tests/after-sales/*.spec.ts
```

**Structure Decision**: 复用现有 `backend/app`、`frontend/src` 和 Alembic 目录；以服务层隔离迁移与业务查询，以通用 Vue 组件复用客户页面，避免 FMG 专属页面分叉。具体文件名可在任务拆解时根据现有模块命名微调，但不改变数据边界和 API 契约。

## Implementation Stages

### Stage 0: 基线与迁移映射

**Deliverables**: 当前 revision、旧表统计、Excel 字段映射表、异常清单、备份记录。

**Acceptance**: 能逐行解释旧表到新实体的映射；不确定的 `d_code/tianyue_pn` 等含义进入人工复核，不猜测。

### Stage 1: 数据库和导入

**Deliverables**: 新表及约束/索引；FMG 工作区和数据导入脚本；旧数据到新数据的对照报告；可逆迁移。

**Acceptance**: 迁移后核心字段、组成、资料状态、价格、备注、历史完整率 100%；固定字段空值被阻止；旧表仍可读。

### Stage 2: 后端模型、服务和 API

**Deliverables**: gaibo SQLAlchemy/Pydantic 模型；工作区、全局查询、单件、客户需求、安装包、组成、图纸、工艺、资料状态、历史 API；RBAC 和冲突校验。

**Acceptance**: 契约测试通过；同一单件的客户 A/B 工艺隔离；版本切换原子；写操作产生历史；搜索和分页满足性能目标。

### Stage 3: 前端工作台

**Deliverables**: 售后查询入口、客户优先导航、客户通用列表、单件库查询、安装包详情、工艺/资料编辑和历史面板；保留已确认的导航层级。

**Acceptance**: 不新增未讨论的业务入口；客户页可筛选单件/安装包；全局搜索可跨客户；详情显示当前客户图纸和工艺；编辑和取消行为符合历史规则。

### Stage 4: 双读切换与清理决策

**Deliverables**: 新旧 API 对照脚本、运行日志、观察期报告、下线建议。

**Acceptance**: 关键查询新旧结果一致；浏览器验收通过；只有在用户确认且无残留引用后，另行制定旧表/旧路由下线任务。本阶段不自动删除旧表。

## Migration Strategy

```text
旧 FMG 表/Excel
      │ 复制 + 映射 + 原始值保留
      ▼
gaibo 新表族 ── 对照报告/人工复核 ── 新 API 只读
      │                                  │
      └──────── 观察期双读 ──────────────┘
                                         ▼
                              用户确认后再规划旧表下线
```

迁移必须支持重跑但不得重复创建业务记录；每条导入记录带来源文件、工作表、行号和批次。无法确认的客户字段、状态结论和组成关联保留原文并标记待复核。

## Test and Acceptance Strategy

- **数据库**：Alembic upgrade/downgrade、约束、索引、迁移幂等和对照报告。
- **服务**：固定字段校验、工艺当前版本唯一性、客户隔离、未关联组成、状态解析、审计写入。
- **API**：全局搜索/客户分页、CRUD、RBAC、400/403/404/409 错误契约。
- **前端**：TypeScript/build、组件交互、客户筛选、详情编辑和历史展示。
- **浏览器**：在实际运行的本地应用中验证登录后导航、全局搜索、客户页、单件详情、安装包详情、编辑保存/取消、窄屏可用性。浏览器结果与代码结果分开记录。

## Post-design Constitution Check

| 项目 | 结果 |
|---|---|
| 技术栈与现有项目一致 | PASS |
| 权限、审计、数据安全约束覆盖 | PASS |
| 迁移可验证且不删除无关/旧数据 | PASS |
| 前端变更有真实浏览器验收 | PASS |
| 未决业务问题 | 无；无法从历史数据确定的字段进入实现阶段人工复核，不自动猜测 |

## Complexity Tracking

无需要豁免的复杂度项。新表族数量较多是为了隔离客户工艺、支持版本和审计，直接扩展 FMG 表无法满足已确认需求。

## Next Step

使用 `speckit-tasks` 将本计划拆解为可独立验收的任务；任务生成后再开始数据库迁移和代码实现。当前阶段不创建 `tasks.md`，也不启动服务或修改前端。
