# Implementation Plan: Price Management System Backend

**Branch**: `003-price-management-system` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-price-management-system/spec.md`

## Summary

实现完整的价格管理系统后端，包括客户材料价格历史、客户工序价格历史、工序字典管理和价格调整审批流程。核心技术方案：
- 新建4张表：customer_material_prices、customer_treatment_prices、treatment_dict、price_adjustments（带审批状态）
- 迁移并废弃旧表：material_base_prices → material_dict，treatment_dicts → treatment_dict，删除空表 material_cost_history 和 treatment_cost_history
- 实现完整 CRUD API，遵循项目现有风格（asyncpg + FastAPI + Pydantic v2）
- 实现价格调整审批工作流（业务经理申请 → 老板审批 → 自动更新价格台账）
- 添加后端单元测试和集成测试

参考设计文档：`specs/001-erp-system-architecture/database-analysis/material-treatment-price-history-final.md`

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: 
- FastAPI 0.104+ (Web framework)
- SQLAlchemy 2.0+ with asyncpg (Async ORM + PostgreSQL driver)
- Pydantic v2 (Schema validation)
- Alembic (Database migrations)
- pytest + pytest-asyncio (Testing)

**Storage**: PostgreSQL 15

**Testing**: pytest with async support, coverage target 80%+

**Target Platform**: Linux server (Docker containerized)

**Project Type**: Web service (RESTful API)

**Performance Goals**: 
- 价格历史查询 < 2s (P95)
- 审批操作 < 1s (P95)
- 支持50并发查询请求

**Constraints**: 
- 必须使用 asyncpg（宪法 II）
- 所有统计必须在 SQL 中完成，禁止 Python 循环累加（宪法 III）
- 权限检查必须使用 @require_role 装饰器（宪法 IV）
- 所有价格字段使用 DECIMAL(10,4)
- 历史记录不允许删除，只允许查询和新增（审计要求）

**Scale/Scope**: 
- 预期第一年各1000-5000条价格历史记录
- price_adjustments 预期每月10-50条审批记录
- treatment_dict 预计10-20条工序

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 宪法符合性验证

| 原则 | 要求 | 本计划符合性 | 说明 |
|------|------|-------------|------|
| I. 中文优先 | MUST | ✅ 通过 | 代码注释、提交信息、文档均使用中文 |
| II. 技术栈锁定 | MUST | ✅ 通过 | 使用 FastAPI + asyncpg + PostgreSQL + Pydantic v2 + Alembic |
| III. 算力下推 | MUST | ✅ 通过 | 价格历史查询使用 SQL ORDER BY + LIMIT，审批统计使用 SQL 聚合 |
| IV. RBAC 权限 | MUST | ✅ 通过 | 使用 @require_role 装饰器，业务经理 >= 5，老板 >= 9，管理员 >= 10 |
| V. 报价状态机 | MUST | N/A | 本功能不涉及报价状态变更 |
| VI. 定点原子性 | MUST | N/A | 本功能不涉及定点写入 |
| VII. 数据安全 | MUST | ✅ 通过 | 敏感字段使用 Decimal，历史记录不支持删除（审计要求） |
| VIII. 服务稳定性 | MUST | ✅ 通过 | 不涉及端口变更，迁移脚本可回滚 |

**结论**: ✅ 无宪法冲突，通过门控检查

## Project Structure

### Documentation (this feature)

```text
specs/003-price-management-system/
├── plan.md              # This file
├── research.md          # Phase 0: 技术选型和设计决策
├── data-model.md        # Phase 1: 数据库表结构设计
├── quickstart.md        # Phase 1: 端到端验证场景
├── contracts/           # Phase 1: API 契约定义
│   ├── customer-material-prices.md
│   ├── customer-treatment-prices.md
│   ├── treatment-dict.md
│   └── price-adjustments.md
└── tasks.md             # Phase 2: 任务分解（由 /speckit.tasks 生成）
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── customer_prices.py          # 新增：客户材料/工序价格历史 API
│   │   ├── treatments.py                # 新增：工序字典 CRUD API
│   │   ├── price_adjustments.py         # 新增：价格调整审批 API
│   │   └── price_accounts.py            # 已存在：扩展批量查询筛选
│   ├── models/
│   │   ├── price.py                     # 扩展：新增 CustomerMaterialPrice、CustomerTreatmentPrice、TreatmentDict、PriceAdjustment 模型
│   │   └── __init__.py                  # 更新：导出新模型
│   ├── schemas/
│   │   ├── price.py                     # 扩展：新增对应 Pydantic schemas
│   │   └── treatment.py                 # 新增：工序相关 schemas
│   ├── services/
│   │   ├── customer_price_service.py    # 新增：客户价格历史业务逻辑
│   │   ├── treatment_service.py         # 新增：工序字典业务逻辑
│   │   └── price_adjustment_service.py  # 新增：审批工作流逻辑
│   └── core/
│       └── permissions.py               # 已存在：复用 @require_role
├── scripts/
│   └── migrations/
│       ├── 001_create_treatment_dict.py                 # 新增：创建工序字典表
│       ├── 002_create_customer_material_prices.py       # 新增：创建客户材料价格历史表
│       ├── 003_create_customer_treatment_prices.py      # 新增：创建客户工序价格历史表
│       ├── 004_create_price_adjustments.py              # 新增：创建价格调整审批表
│       ├── 005_migrate_material_base_prices.py          # 新增：迁移 material_base_prices → material_dict
│       ├── 006_migrate_treatment_dicts.py               # 新增：清理并迁移 treatment_dicts → treatment_dict
│       └── 007_drop_legacy_tables.py                    # 新增：删除废弃表
└── tests/
    ├── test_api_customer_prices.py                      # 新增：客户价格历史 API 测试
    ├── test_api_treatments.py                           # 新增：工序字典 API 测试
    ├── test_api_price_adjustments.py                    # 新增：价格调整审批 API 测试
    └── test_migrations_price_system.py                  # 新增：数据迁移测试
```

**Structure Decision**: 遵循现有后端项目结构（backend/app/），API 路由按功能模块分文件（customer_prices.py、treatments.py、price_adjustments.py），models 和 schemas 扩展现有 price.py 文件，新增 treatment.py schema 文件。数据迁移脚本放在 backend/scripts/migrations/ 目录，按顺序编号确保执行顺序。

## Complexity Tracking

**无宪法违规项**，本功能完全符合项目技术栈和设计原则。

## Phase 0: Research & Decisions

### 研究任务清单

| 任务 | 状态 | 输出文件 |
|------|------|----------|
| R1: 数据库表结构设计（参考已定案设计文档） | ✅ 已完成 | research.md + data-model.md |
| R2: 审批工作流状态机设计 | ✅ 已完成 | research.md |
| R3: 数据迁移策略和回滚方案 | ✅ 已完成 | research.md |
| R4: API 路由命名和权限分配 | ✅ 已完成 | contracts/ |

**说明**: 数据库表结构已在 `specs/001-erp-system-architecture/database-analysis/material-treatment-price-history-final.md` 中定稿（2026-07-06），本计划直接采用该设计。

## Phase 1: Design & Contracts

### 1.1 数据模型

**输出**: `data-model.md`

核心实体：
- **customer_material_prices**: 客户材料价格历史（UUID 主键，关联 customers + material_dict）
- **customer_treatment_prices**: 客户工序价格历史（UUID 主键，关联 customers + treatment_dict，快照 calc_mode/unit）
- **treatment_dict**: 工序字典（INTEGER 主键，全局参考数据）
- **price_adjustments**: 价格调整审批（UUID 主键，关联 price_accounts，状态机：pending → approved/rejected）

关键设计：
- 价格历史表只允许 INSERT 和 SELECT，禁止 UPDATE/DELETE（审计要求）
- 工序价格历史快照当时的计价方式和单位，避免字典变更影响历史真实性
- 审批状态：pending（待审批）、approved（已通过）、rejected（已驳回）

### 1.2 API 契约

**输出**: `contracts/` 目录

| API | 路由 | 方法 | 权限 | 契约文件 |
|-----|------|------|------|----------|
| 查询客户材料价格历史 | /api/customer-prices/materials | GET | role_level >= 5 | customer-material-prices.md |
| 新增客户材料价格记录 | /api/customer-prices/materials | POST | role_level >= 5 | customer-material-prices.md |
| 查询客户工序价格历史 | /api/customer-prices/treatments | GET | role_level >= 5 | customer-treatment-prices.md |
| 新增客户工序价格记录 | /api/customer-prices/treatments | POST | role_level >= 5 | customer-treatment-prices.md |
| 查询工序字典列表 | /api/treatments | GET | role_level >= 1 | treatment-dict.md |
| 新增工序 | /api/treatments | POST | role_level >= 10 | treatment-dict.md |
| 更新工序 | /api/treatments/{id} | PUT | role_level >= 10 | treatment-dict.md |
| 停用工序 | /api/treatments/{id} | PATCH | role_level >= 10 | treatment-dict.md |
| 提交调价申请 | /api/price-adjustments | POST | role_level >= 5 | price-adjustments.md |
| 查询待审批列表 | /api/price-adjustments/pending | GET | role_level >= 9 | price-adjustments.md |
| 审批调价申请 | /api/price-adjustments/{id}/approve | POST | role_level >= 9 | price-adjustments.md |
| 驳回调价申请 | /api/price-adjustments/{id}/reject | POST | role_level >= 9 | price-adjustments.md |

### 1.3 快速入门指南

**输出**: `quickstart.md`

端到端验证场景：
1. 运行数据迁移脚本，验证旧表数据正确迁移
2. 创建测试客户和材质数据
3. 新增客户材料价格历史记录
4. 查询最近3次价格，验证排序和限制
5. 业务经理提交调价申请
6. 老板审批通过，验证价格台账自动更新
7. 查询审批历史，验证审计轨迹完整

## Phase 2: Task Breakdown

**输出**: 由 `/speckit.tasks` 命令生成 `tasks.md`

任务分组预览（详细任务由 tasks 命令生成）：

**Stage 1: 数据库层（可并行）**
- 创建 Alembic 迁移脚本（7个脚本，按顺序执行）
- 编写迁移测试（验证数据完整性和回滚）

**Stage 2: 模型和 Schema 层（依赖 Stage 1）**
- 定义 SQLAlchemy 模型（4个新模型）
- 定义 Pydantic schemas（Request/Response schemas）

**Stage 3: 服务层（依赖 Stage 2）**
- 实现客户价格历史服务
- 实现工序字典服务
- 实现价格调整审批服务

**Stage 4: API 层（依赖 Stage 3）**
- 实现客户价格历史 API
- 实现工序字典 API
- 实现价格调整审批 API
- 扩展 price_accounts API（批量查询筛选）

**Stage 5: 测试（可并行开发）**
- 单元测试（服务层）
- 集成测试（API 层）
- 端到端测试（完整业务流程）

**Stage 6: 文档和收尾**
- 更新 API 文档
- 执行生产环境迁移（需人工监督）
- 更新 Agent 上下文

## Testing Strategy

### 单元测试（pytest）

- **服务层测试**: 使用 mock 数据库，测试业务逻辑
  - customer_price_service: 价格历史查询、兜底逻辑、排序限制
  - treatment_service: 工序 CRUD、停用逻辑
  - price_adjustment_service: 审批状态机、价格更新原子性

### 集成测试（pytest + 测试数据库）

- **API 测试**: 真实数据库，测试完整请求响应
  - 客户价格历史 API: CRUD + 权限验证 + 边界情况（空历史、重复记录）
  - 工序字典 API: CRUD + 权限验证 + 停用后的查询行为
  - 价格调整审批 API: 完整审批流程 + 权限验证 + 并发审批

### 端到端测试

- **完整业务流程**: 从数据迁移到审批通过
  - 场景1: 旧数据迁移 → 新API查询 → 验证数据一致性
  - 场景2: 业务经理报价 → 记录价格历史 → 查询历史参考
  - 场景3: 提交调价 → 老板审批 → 验证价格更新 → 查询审计日志

### 性能测试

- 客户价格历史查询性能（目标 < 2s P95）
- 审批操作响应时间（目标 < 1s P95）
- 并发查询压力测试（50并发请求）

## Migration Strategy

### 数据迁移顺序

```
1. 创建 treatment_dict 表（空表）
2. 创建 customer_material_prices 表（空表）
3. 创建 customer_treatment_prices 表（空表）
4. 创建 price_adjustments 表（空表）
5. 迁移 material_base_prices → material_dict（14行数据，按 material_name 匹配，只插入缺失材质）
6. 迁移 treatment_dicts → treatment_dict（只迁移10条真实工序，丢弃18条测试脏数据）
7. 删除旧表（material_base_prices、material_cost_history、treatment_dicts、treatment_cost_history）
```

### 回滚方案

- 每个迁移脚本包含 `down()` 函数，可逆向回滚
- 关键数据迁移前备份（material_base_prices、treatment_dicts）
- 如迁移失败，恢复备份表，回滚到步骤4之前
- 新表删除不影响现有功能（旧API继续使用 material_dict）

### 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| material_dict 已存在同名材质，price 不同 | 数据冲突 | 不覆盖现有数据，只插入缺失材质，记录冲突到日志 |
| treatment_dicts 脏数据过多，误删真实数据 | 数据丢失 | 白名单机制，只迁移明确的10条真实工序名称 |
| 删除旧表后，遗留代码引用旧表名 | 运行时错误 | 迁移前全局搜索旧表名引用（material_base_prices、treatment_dicts），确认无引用后再删除 |
| 迁移期间服务中断 | 用户体验 | 迁移脚本设计为可在运行时执行，无需停机，旧API不受影响 |

## Implementation Phases

### Phase 0: Research (Complete)

- ✅ 数据库表结构设计已定案（参考 material-treatment-price-history-final.md）
- ✅ 审批工作流状态机已明确（pending/approved/rejected）
- ✅ 数据迁移策略已制定（7步迁移 + 回滚方案）

### Phase 1: Database Schema & Migration

**Duration**: 2-3 days

**Deliverables**:
- 7个 Alembic 迁移脚本
- 迁移测试脚本
- 数据备份和回滚脚本

### Phase 2: Models & Schemas

**Duration**: 1-2 days

**Deliverables**:
- 4个 SQLAlchemy 模型
- 对应 Pydantic schemas（Create/Update/Response）

### Phase 3: Services & Business Logic

**Duration**: 3-4 days

**Deliverables**:
- customer_price_service.py（价格历史查询、兜底逻辑）
- treatment_service.py（工序 CRUD）
- price_adjustment_service.py（审批工作流、价格更新原子性）

### Phase 4: API Endpoints

**Duration**: 3-4 days

**Deliverables**:
- customer_prices.py（材料/工序价格历史 API）
- treatments.py（工序字典 API）
- price_adjustments.py（审批 API）
- 扩展 price_accounts.py（批量查询筛选）

### Phase 5: Testing

**Duration**: 2-3 days

**Deliverables**:
- 单元测试（80%+ 覆盖率）
- 集成测试（API 完整流程）
- 端到端测试（业务场景验证）

### Phase 6: Documentation & Deployment

**Duration**: 1 day

**Deliverables**:
- 更新 API 文档
- 生产环境迁移执行
- 更新 Agent 上下文

**Total Duration**: 12-17 days

## Risk Assessment

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据迁移失败导致数据丢失 | 中 | 高 | 迁移前备份，测试库先验证，回滚脚本就绪 |
| 审批工作流并发冲突（多人同时审批同一申请） | 低 | 中 | 使用数据库行锁，乐观锁版本号机制 |
| 旧代码引用已删除的表导致运行时错误 | 中 | 高 | 迁移前全局搜索代码库，确认无引用后再删除 |
| 性能不达标（查询 > 2s） | 低 | 中 | 添加索引（customer_id, material_id, quoted_at DESC），查询限制默认3条 |
| 工序字典变更影响历史价格解读 | 低 | 低 | 已快照 calc_mode 和 unit，历史记录不受影响 |

## Success Metrics

- ✅ 所有数据迁移脚本通过测试，零数据丢失
- ✅ API 单元测试覆盖率 >= 80%
- ✅ 价格历史查询响应时间 < 2s (P95)
- ✅ 审批操作响应时间 < 1s (P95)
- ✅ 端到端测试场景全部通过
- ✅ 生产环境迁移成功，无回滚

## Next Steps

1. 运行 `/speckit.tasks` 生成详细任务分解
2. 创建 Git 分支 `003-price-management-system`
3. 执行 Phase 1: 数据库迁移脚本开发
4. 在测试环境验证迁移脚本
5. 按阶段顺序实施开发和测试
