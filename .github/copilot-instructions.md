<!-- SPECKIT START -->
**Current Active Feature**: `001-erp-system-architecture`
**Plan**: `specs/001-erp-system-architecture/plan.md`
**Data Model**: `specs/001-erp-system-architecture/data-model.md`
**Quickstart**: `specs/001-erp-system-architecture/quickstart.md`

**Tech Stack**: Python 3.11 + FastAPI (backend), Vue 3 + Element Plus (frontend), 微信小程序 (扫码终端主方案), PostgreSQL 15, Redis, 云端OSS
**Architecture**: Monorepo, RESTful API, JWT auth, role-based permissions (role_level 1-10)
**Key Patterns**: State machines for quote/part/tooling states, event sourcing for audit logs, QR code pre-generation + OSS storage + CDN
**Deployment**: Cloud (轻量级云服务器 + Docker), 微信小程序主方案

Read the plan before implementing any code. All backend code under `backend/`, frontend under `frontend/`, miniprogram under `miniprogram/`.
<!-- SPECKIT END -->
