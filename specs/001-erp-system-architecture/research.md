# Research: ERP System Architecture

**Feature**: 001-erp-system-architecture
**Date**: 2026-06-12
**Phase**: Phase 0 — Research & Clarification

---

## 1. Technology Stack Decisions

### 1.1 Language & Framework

**Decision**: Python 3.11 + FastAPI（后端 API）+ Vue 3（前端管理后台）+ 微信小程序（车间终端扫码）

**Rationale**:
- **FastAPI**: 高性能 async 框架，适合 ERP 的并发请求场景；自动 OpenAPI 文档降低前后端沟通成本；Python 在国内工厂信息化系统中有大量成熟案例（如 Odoo 生态）
- **Vue 3**: 管理后台（业务部/老板/组长）使用浏览器，Vue 3 + Element Plus 有丰富的企业级 UI 组件
- **微信小程序**: 车间操作工扫码终端主方案，利用微信原生扫码能力，支持扫码枪输入（H5 页面也可兼容）

**扫码终端策略**:
- 主方案：**微信小程序**，利用 `wx.scanCode` 原生扫码 API，支持扫码枪键盘输入模式
- 兼容方案：**H5 响应式页面**，扫码枪映射为键盘输入，通过 URL scheme 或 URL param 传递扫码内容

**Alternatives considered**:
- **C# / .NET + WPF**: 国内工厂桌面 ERP 传统方案，但 Web 化改造成本高，不适合互联网化协作
- **PHP / Laravel**: 适合中小型系统，但并发性能不如 FastAPI
- **Java / Spring Boot**: 成熟稳重，但开发效率低于 FastAPI，启动成本高

### 1.2 Database

**Decision**: PostgreSQL 15

**Rationale**:
- 支持 JSONB，可存储灵活的配置字段（如报价单的多道表面处理计价）
- 支持数组类型，适合多角色权限存储（`role_level[]`）
- 完整 ACID 事务，财务数据（报价审批、价格快照）安全可靠
- 支持行级安全策略（RLS），便于多租户/部门数据隔离
- PostGIS 支持未来工厂地理信息扩展

**Alternatives considered**:
- **MySQL 8**: 广泛使用但 JSON 支持较弱，JSON 查询性能差于 PostgreSQL
- **SQLite**: 仅适合单机/边缘设备，不适合多用户 ERP
- **SQL Server**: 商业许可成本高，Linux 支持不如 PostgreSQL

### 1.3 Authentication & Session

**Decision**: JWT + Redis Session

**Rationale**:
- FR-082 要求 Session Cookie 包含用户角色信息，JWT payload 可承载 `role_level`、`department` 等字段
- Redis 存储会话状态，支持分布式部署和会话失效管理
- 超级管理员视角切换（FR-079）可通过 JWT 刷新 token 实现

**Alternatives considered**:
- 纯 Session Cookie：不适合分布式，不够灵活
- 纯 JWT（无状态）：无法实现服务端会话失效（无法踢人）

### 1.4 QR Code Generation & Scanning

**Decision**: `qrcode` (Python) + `python-qrcode` 生成，`zxing` 或前端 JS 解码

**Rationale**:
- 原料批次、机台、工艺流转单均需生成 QR Code
- 扫码枪映射为键盘输入，无需原生扫码 SDK
- 前端 Vue 页面通过 `qrcode-reader` 库支持移动端扫码

**Alternatives considered**:
- `qrcode` + 后端实时生成：每次扫码查询均需网络，性能差
- **预生成 + 打印**：QR 码内容固定（批次号/机台编号），生成一次永久使用，更适合工厂环境

### 1.5 Project Structure

**Decision**: Monorepo 分层架构

```
backend/          # FastAPI 后端
├── app/
│   ├── models/   # SQLAlchemy ORM models
│   ├── schemas/  # Pydantic request/response schemas
│   ├── services/ # 业务逻辑层
│   ├── api/      # API 路由
│   └── core/     # 认证、权限、配置
frontend/         # Vue 3 管理后台
miniprogram/      # 微信小程序扫码终端
```

---

## 2. Architecture Decisions

### 2.1 API Architecture

**Decision**: RESTful API + BFF（Backend for Frontend）

**Rationale**:
- 管理后台（Vue 3）与车间终端（小程序）共用同一套后端，通过不同 BFF 层适配
- FastAPI 的 `APIRouter` 按领域拆分：quotes、parts、machines、production、quality 等

### 2.2 State Management

**Decision**: 状态机 + 事件溯源

**Rationale**:
- 报价单（FR-003）、零件（Draft→Sampling→MassProduction→Obsolete）、打样任务、机台状态均有明确的状态流转
- 使用 `python-statemachine` 或自定义状态机实现
- 关键状态变更写入审计日志（event sourcing 轻量实现）

### 2.3 File Storage

**Decision**: 云端 OSS（对象存储）+ 本地文件系统（缓存）

**Rationale**:
- 图纸文件（FR-006/FR-079）：业务部/开发部上传图片/PDF
- 定点后图纸自动归档（FR-079）：按「零件名+上传日期」命名，存入 OSS `drawings/{customer}/{part_name}/`
- 微信小程序直传 OSS，绕过后端中转，减少服务器带宽压力
- 轻量级云服务器推荐：阿里云 OSS / 腾讯云 COS / 华为云 OBS（均有免费额度）
- QR 码图片预生成后存 OSS，CDN 分发加速扫码识别

---

## 3. Open Questions (NEEDS CLARIFICATION)

### Q1: 样件评审通过权限

**Spec 原文**: "样件评审通过后零件切换为 MassProduction"
**Question**: 样件评审通过需要什么权限的人批准？老板还是品管部？
**Status**: RESOLVED — 默认品管部或业务经理代为传达客户评审意见（见 spec FR-022 原文），无需老板再次审批

### Q2: 技术栈最终确认

**Question**: 是否有公司现有技术栈偏好？（如已有 Java/.NET 基础设施）
**Impact**: 若有现有 .NET 栈，应选择 C# + ASP.NET Core 以复用基础设施
**Status**: RESOLVED — **无现有技术栈偏好，采用 Python 3.11 + FastAPI + Vue 3 + 微信小程序**

### Q3: 部署环境

**Question**: 部署在内网服务器还是云端？是否有 Docker/K8s 环境？
**Impact**: 决定数据库选型（SQL Server 许可）、文件存储方案、网络配置
**Status**: RESOLVED — **云端部署（轻量级云服务器），推荐 Docker 单容器部署**

---

## 4. Compliance Check

| Constitution Principle | Status | Notes |
|------------------------|--------|-------|
| 项目宪法文件存在但为空模板 | N/A | `.specify/memory/constitution.md` 为占位符，无实质约束 |
| 软删除（FR-085） | ✓ PLANNED | 所有 DELETE 操作使用 `is_deleted` 标记 |
| 权限验证 100%（FR-080/082） | ✓ PLANNED | JWT + Redis Session + 每次请求 role_level 验证 |
| 审计日志（FR-052/084） | ✓ PLANNED | 所有状态变更写入 `audit_logs` 表 |
| 图纸路径安全（FR-083） | ✓ PLANNED | 统一 `FileService.generate_path()` 函数，禁止硬编码 |

---

## 5. Recommended Implementation Priority

基于 spec 中 P1/P2/P3 优先级，建议分以下迭代实施：

| 迭代 | 范围 | 核心价值 |
|------|------|---------|
| **MVP (Iter 1)** | 报价与审批 + 价格台账 + 基础权限 | 系统最核心入口可用 |
| **Iter 2** | 打样管理 + 模具管理 | 样件和新模具流程打通 |
| **Iter 3** | 生产计划与报工 + 原材料 | 车间执行层数字化 |
| **Iter 4** | 质量管控 + 包装 | 质检闭环 |
| **Iter 5** | 喷涂 + 发货 + 超级管理员视角切换 | 完整业务闭环 |

---

*Research completed. All NEEDS CLARIFICATION items resolved or deferred to implementation phase.*
