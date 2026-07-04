# Implementation Plan: Zephyr_test_ERP

**Branch**: `001-erp-system-architecture` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-erp-system-architecture/spec.md`

---

## Summary

Zephyr_test_ERP 是一套面向冲压制造企业的综合性企业资源管理系统，基于 Python 3.11 + FastAPI + Vue 3 + 微信小程序技术栈构建，部署于云端（轻量级云服务器 + Docker），采用分层架构处理从报价接单、模具开发、原料采购、生产执行、质量管控到包装出货的完整业务闭环。

---

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**:
- FastAPI 0.109+（API 框架）
- SQLAlchemy 2.0 + asyncpg（ORM + 异步数据库驱动）
- Pydantic v2（数据校验）
- python-jose + passlib（JWT 认证）
- python-statemachine（状态机）
- qrcode + Pillow（QR 码生成）
- Redis（会话存储，aioredis）
- Vue 3 + Element Plus + Vite（前端管理后台）

**Storage**: PostgreSQL 15（核心业务数据）+ Redis（会话）+ 云端 OSS（图纸/QR码，腾讯云COS或阿里云OSS）

**Testing**: pytest + pytest-asyncio + pytest-cov（后端）；Vitest（前端）

**Target Platform**: 云端（轻量级云服务器 + Docker 部署），浏览器访问（Chrome/Edge）+ 微信小程序

**Project Type**: Web Service（前后端分离）+ 微信小程序（扫码终端）

**Performance Goals**: API p95 响应时间 < 200ms；报工数据提交到看板可见延迟 ≤ 30 秒

**Constraints**: 云端部署（轻量级云服务器）；操作工使用扫码枪（键盘输入模式）；超级管理员视角切换无权限泄露；微信小程序为主，H5 为兼容方案

**Scale/Scope**: 初期支持单工厂 ~100 并发用户，~10 万零件档案，~1000 机台

---

## Constitution Check

*GATE: 项目宪法已生效 v1.0.0（2026-06-20），包含8条核心原则。*

| Gate | Status | Notes |
|------|--------|-------|
| 软删除策略（FR-085） | ✓ PASS | 所有实体含 `is_deleted` 字段，DELETE → UPDATE |
| 权限验证 100%（FR-080） | ✓ PASS | JWT 每次请求验证 role_level（1-4级权限体系） |
| 审计日志（FR-052/084） | ✓ PASS | `audit_logs` 表记录所有关键操作 |
| 图纸路径安全（FR-083） | ✓ PASS | `FileService.generate_path()` 统一生成，禁止硬编码 |
| 超级管理员视角隔离（FR-079） | ✓ PASS | 视角切换隐藏 role_level >= 3 按钮 |
| 报价单数据权限隔离 | ✓ PASS | 基于 role_level + department 的字段级权限控制 |

---

## Project Structure

### Documentation (this feature)

```
specs/001-erp-system-architecture/
├── spec.md              # 功能规格说明书
├── plan.md              # 本文件
├── research.md          # 技术选型研究
├── data-model.md        # 数据模型设计
├── quickstart.md        # 快速入门验证指南
├── contracts/           # 接口契约
│   └── README.md
└── tasks.md             # 任务清单 (/speckit.tasks 输出)
```

### Source Code (repository root)

```
backend/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py             # 配置管理
│   ├── database.py          # 数据库连接
│   ├── models/              # SQLAlchemy ORM Models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── quote.py
│   │   ├── part.py
│   │   ├── tooling.py       # 模具
│   │   ├── machine.py       # 机台
│   │   ├── production.py    # 生产计划/报工
│   │   ├── quality.py       # 质检
│   │   ├── warehouse.py     # 仓库/原材料
│   │   ├── coating.py       # 喷涂
│   │   └── audit.py         # 审计日志
│   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── quote.py
│   │   ├── part.py
│   │   └── ...
│   ├── services/            # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── quote_service.py
│   │   ├── part_service.py
│   │   ├── tooling_service.py
│   │   ├── production_service.py
│   │   └── ...
│   ├── api/                 # API 路由
│   │   ├── __init__.py
│   │   ├── deps.py          # 依赖注入（当前用户、权限）
│   │   ├── auth.py
│   │   ├── quotes.py
│   │   ├── parts.py
│   │   ├── toolings.py
│   │   ├── machines.py
│   │   ├── production.py
│   │   ├── quality.py
│   │   ├── warehouse.py
│   │   ├── coating.py
│   │   └── admin.py
│   ├── core/                # 核心安全/工具
│   │   ├── security.py      # JWT、密码哈希
│   │   ├── permissions.py  # 权限装饰器
│   │   ├── events.py       # 审计日志写入
│   │   └── file_service.py # 图纸路径生成
│   └── state_machines/     # 状态机定义
│       ├── quote_states.py
│       ├── part_states.py
│       └── tooling_states.py
├── tests/
│   ├── conftest.py
│   ├── api/
│   ├── services/
│   └── factories/          # pytest factories
├── alembic/                 # 数据库迁移
└── requirements.txt

frontend/                    # Vue 3 管理后台
├── src/
│   ├── api/               # axios 封装
│   ├── stores/            # Pinia 状态管理
│   ├── views/             # 页面视图
│   │   ├── quotes/        # 报价管理
│   │   ├── parts/         # 零件管理
│   │   ├── production/     # 生产计划
│   │   └── ...
│   └── router/
├── package.json
└── vite.config.ts

miniprogram/                  # 微信小程序扫码终端（主方案）
├── pages/
│   ├── index/              # 首页（扫码入口）
│   ├── scan/               # 扫码页面
│   ├── production/          # 报工页面
│   ├── material/            # 原材料扫码
│   └── quality/             # 质检页面
├── components/
│   └── ...
├── services/
│   └── api.js              # 小程序 API 封装
└── project.config.json

mobile-h5/                    # H5 扫码终端（兼容方案）
├── index.html
├── src/
│   ├── pages/
│   └── ...
└── package.json
```

**Structure Decision**: Monorepo 分层架构，后端 FastAPI 前后端分离，前端 Vue 3 管理后台 + 轻量扫码终端小程序。统一 Python 测试（pytest）和前端测试（Vitest）。

---

## Complexity Tracking

> 无 Constitution 违规项。所有架构决策均符合项目宪法（当前宪法为空模板，视为无约束）。

---

## Key Technical Decisions

### 1. 状态机实现

每个核心实体使用 `python-statemachine` 定义状态流转：

- **QuoteStateMachine**: 等待技术审核 ↔ 技术通过/驳回 ↔ 草稿 ↔ 待老板审批 ↔ 已审批
- **PartStateMachine**: Draft → Sampling → MassProduction → Obsolete
- **SamplingTaskStateMachine**: 待审核 → 待生产 → 打样中 → 待评审 → 已通过/未通过/已取消
- **MachineStateMachine**: idle ↔ running ↔ fault → pending_check → repairing → offline

### 2. 权限系统

基于 `role_level` 的 RBAC（4级权限体系）：
- **role_level = 1**（普通员工）：操作工、仓库管理员、质检员、喷涂工、设备维护员
- **role_level = 2**（管理人员及业务）：班组长、技术人员、业务人员、部门主管、会计、人事、设备主管
- **role_level = 3**（老板）：最终审批、全局数据查看
- **role_level = 4**（超级管理员）：系统管理、视角切换

每个 API endpoint 装饰 `@require_role(min_level=N)`
- JWT payload 包含 `role_level`、`department`、`user_id`
- 超级管理员切换视角：生成临时受限 token（原始 role_level 存入 Redis）

**数据权限隔离**（以报价单为例）：
- 业务部 + 老板 + 超管：完整查看所有报价单
- 开发部：仅通过"待审核队列"查看，能看模具费和技术参数，不能看其他价格
- 会计部：仅查看已定点报价单，能看总价/模具费/模摊费用，不能看技术参数
- 生产相关部门（生产部/原料仓库/品管部/喷涂部/设备部）：仅查看已定点报价单，能看技术参数，不能看价格

### 3. QR 码策略

- **预生成 + OSS 存储**：原料批次号、机台编号在创建时生成 QR 码图片，上传至云端 OSS（腾讯云COS/阿里云OSS），CDN 分发加速扫码识别
- **工艺流转单 QR**：在机台报工结账时动态生成，存入 OSS
- QR 内容格式：`{type}-{id}`，如 `MAT-batch_001`、`MCN-machine_001`、`PFC-flow_001`
- 微信小程序通过 `wx.scanCode` 扫码，解析内容后调用后端 API 查询详情

### 4. 报价单价格快照

老板审批通过时，将以下字段的当前值写入 `quote_snapshot` JSONB 字段：
- 材料单价、表面处理费、冲压费、模具费、利润
- 定点后不可修改，作为历史记录保留

### 5. 图纸存储

```
uploads/
├── drawings/
│   ├── {customer_name}/
│   │   ├── {part_name}_{upload_date}.pdf
│   │   └── ...
│   └── temp/               # 未分配客户的图纸暂存
└── qrcodes/
    ├── material/          # 原料批次 QR
    ├── machine/           # 机台 QR
    └── process_flow/      # 工艺流转单 QR
```

---

## Deferred Items

| Item | Reason | Deferred To |
|------|--------|-------------|
| 微信小程序为主，H5 为兼容方案 | 已确认：微信小程序为主 | Iter 1 |
| 技术栈替换为 .NET/Java | 已确认：无现有技术栈 | Iter 1 |
| 喷涂配方管理（FR-068~072） | P3 优先级低 | Iter 5 |

---

*Plan completed. Ready for `/speckit.tasks`.*
