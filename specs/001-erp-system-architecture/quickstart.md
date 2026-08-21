# Quickstart: Zephyr_test_ERP

**Feature**: 001-erp-system-architecture
**Date**: 2026-06-12

本文档提供系统端到端可运行的验证场景，用于验证核心功能链路是否正常工作。**不包含完整实现代码**，实现细节详见 `tasks.md`。

---

## 1. Environment Setup

### 1.1 Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | 后端运行环境 |
| PostgreSQL | 15+ | 数据库（云端 RDS 或自建） |
| Redis | 6+ | 会话存储（云端 Redis 或自建） |
| Node.js | 18+ | 前端构建 |
| Docker | 24+ | 容器化部署（轻量级云服务器） |
| 微信开发者工具 | 最新版 | 小程序开发调试 |
| Git | any | 版本控制 |

### 1.2 云端部署方案（Docker 单容器）

```bash
# 1. 云服务器准备（推荐 2核4G Ubuntu 22.04）
ssh root@your-server

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 3. 克隆项目
git clone https://your-repo/Cloud-Stamping.git
cd Cloud-Stamping

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，配置：
# - DATABASE_URL（PostgreSQL 连接串，云厂商提供）
# - REDIS_URL（Redis 连接串，或使用云 Redis）
# - OSS_SECRET_KEY（腾讯云COS或阿里云OSS）
# - SECRET_KEY（JWT签名密钥）

# 5. 拉取并启动
docker-compose up -d

# 6. 初始化数据库
docker exec cloud-stamping-backend-1 alembic upgrade head

# 7. 创建初始管理员
docker exec -it cloud-stamping-backend-1 python scripts/init_admin.py
```

### 1.3 本地开发环境

```bash
# 1. 克隆并进入后端目录
cd backend

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库和 Redis 连接信息

# 5. 数据库迁移
alembic upgrade head

# 6. 创建初始超级管理员
python -c "from app.core.security import hash_password; \
from app.models.user import User; \
from app.database import SessionLocal; \
db = SessionLocal(); \
db.add(User(username='admin', password_hash=hash_password('admin123'), \
           real_name='系统管理员', role_level=4)); \
db.commit()"

# 7. 启动后端
uvicorn app.main:app --reload --port 8000

# 8. 启动前端（新终端）
cd frontend && npm install && npm run dev

# 9. 导入小程序项目（微信开发者工具）
# 打开 miniprogram/ 目录，填入后端 API 地址
```

### 1.3 Default Test Accounts

| Username | Password | Role |
|----------|---------|------|
| admin | admin123 | 超级管理员 (role_level=4) |
| boss | boss123 | 老板 (role_level=3) |
| sales_mgr | sales123 | 业务经理 (role_level=2) |
| engineer | eng123 | 设计工程师 (role_level=2) |
|组长 | leader123 | 生产组长 (role_level=2) |
| operator | op123 | 操作工 (role_level=1) |

---

## 2. Run Scenarios

### Scenario 1: 报价与审批完整链路

**Purpose**: 验证报价单从创建到定点确认的完整审批流

**Steps**:

```bash
# 1. 业务经理登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "sales_mgr", "password": "sales123"}'
# Response: {"access_token": "xxx", "user": {"role_level": 2, ...}}

# 2. 创建报价单（带 JWT token）
curl -X POST http://localhost:8000/api/quotes \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "客户A",
    "items": [{
      "part_name": "支架-001",
      "annual_volume": 10000
    }]
  }'
# Response: {"id": 1, "quote_number": "Q-20260612-001", "status": "waiting_tech_review"}

# 3. 设计工程师登录并填写技术参数
curl -X PUT http://localhost:8000/api/quotes/<quote_id>/tech-review \
  -H "Authorization: Bearer <engineer_token>" \
  -d '{
    "t_parameter": 2.5,
    "w_parameter": 100.0,
    "p_parameter": 50,
    "cavity_count": 4,
    "press_tonnage": 200,
    "tooling_fee": 50000,
    "tooling_fee_mode": "direct"
  }'

# 4. 业务经理填写价格并提交老板审批
curl -X PUT http://localhost:8000/api/quotes/<quote_id>/submit-boss \
  -H "Authorization: Bearer <sales_token>" \
  -d '{"stamping_fee": 15.0, "profit": 5.0}'

# 5. 老板审批通过
curl -X PUT http://localhost:8000/api/quotes/<quote_id>/boss-approve \
  -H "Authorization: Bearer <boss_token>"

# 6. 定点确认（选择直接量产）
curl -X POST http://localhost:8000/api/quotes/<quote_id>/fix \
  -H "Authorization: Bearer <sales_token>" \
  -d '{"fix_path": "mass_production", "tooling_number": "T-001"}'

# Expected: 报价单状态 = "boss_approved", 零件状态 = "mass_production"
```

**Success Criteria**: 零件从 Draft → MassProduction，零件模具信息同步更新

---

### Scenario 2: 打样管理链路

**Purpose**: 验证样件路径从创建到评审通过的流程

**Prerequisites**: Scenario 1 定点时选择 `fix_path: "sampling"`

```bash
# 1. 组长或业务经理创建打样任务
curl -X POST http://localhost:8000/api/sampling-tasks \
  -H "Authorization: Bearer <sales_token>" \
  -d '{
    "part_id": 1,
    "customer_id": 1,
    "planned_finish_date": "2026-06-20",
    "sample_quantity": 5
  }'

# 2. 老板审核确认
curl -X PUT http://localhost:8000/api/sampling-tasks/<task_id>/boss-approve \
  -H "Authorization: Bearer <boss_token>"

# 3. 组长安排打样（分配机台）
curl -X PUT http://localhost:8000/api/sampling-tasks/<task_id>/start \
  -H "Authorization: Bearer <leader_token>" \
  -d '{"machine_id": 1}'

# 4. 打样完成，提交评审
curl -X PUT http://localhost:8000/api/sampling-tasks/<task_id>/submit-review \
  -H "Authorization: Bearer <leader_token>"

# 5. 评审通过
curl -X PUT http://localhost:8000/api/sampling-tasks/<task_id>/review \
  -H "Authorization: Bearer <qa_token>" \
  -d '{"result": "passed", "notes": "尺寸合格"}'
```

**Success Criteria**: 零件状态从 Sampling → MassProduction，打样任务状态 = "passed"

---

### Scenario 3: 生产报工链路

**Purpose**: 验证扫码报工全流程

```bash
# 1. 创建生产计划
curl -X POST http://localhost:8000/api/production/plans \
  -H "Authorization: Bearer <leader_token>" \
  -d '{
    "part_id": 1,
    "total_quantity": 1000,
    "deadline": "2026-06-15",
    "urgency": "normal"
  }'

# 2. 分配机台
curl -X POST http://localhost:8000/api/production/plans/<plan_id>/assign-machine \
  -H "Authorization: Bearer <leader_token>" \
  -d '{"machine_id": 1}'

# 3. 操作工扫码（模拟：先扫原材料，再扫机台）
curl -X POST http://localhost:8000/api/production/sessions/start \
  -H "Authorization: Bearer <operator_token>" \
  -d '{
    "plan_id": 1,
    "machine_id": 1,
    "material_batch_id": 1
  }'

# 4. 多次报工
curl -X POST http://localhost:8000/api/production/reports \
  -H "Authorization: Bearer <operator_token>" \
  -d '{
    "session_id": 1,
    "strokes": 100
  }'

# 5. 结账会话
curl -X POST http://localhost:8000/api/production/sessions/<session_id>/close \
  -H "Authorization: Bearer <operator_token>"
```

**Success Criteria**: 报工记录生成，工艺流转单自动创建，生产计划完成量更新

---

### Scenario 4: 原材料分条与追溯

**Purpose**: 验证大卷料拆分小卷料的 QR 追溯链路

```bash
# 1. 登记原材料（大卷）
curl -X POST http://localhost:8000/api/warehouse/material-batches \
  -H "Authorization: Bearer <warehouse_token>" \
  -d '{
    "material_brand": "DC01",
    "material_type": "冷轧钢卷",
    "weight": 1000,
    "width": 1250
  }'

# 2. 执行分条
curl -X POST http://localhost:8000/api/warehouse/material-batches/<batch_id>/split \
  -H "Authorization: Bearer <warehouse_token>" \
  -d '{
    "split_count": 3,
    "split_widths": [400, 400, 400]
  }'
# Expected: 生成3个子卷批次，QR码关联原始大卷

# 3. 扫码子卷 QR，验证追溯链
curl -X GET http://localhost:8000/api/warehouse/material-batches/<child_batch_id>/trace \
  -H "Authorization: Bearer <any_token>"
# Expected: 展示父卷 → 子卷 → 分条时间 → 当前状态
```

---

### Scenario 5: 超级管理员视角切换

**Purpose**: 验证 admin 切换部门视角时无老板权限泄露

```bash
# 1. 超级管理员切换到业务视角
curl -POST http://localhost:8000/api/admin/switch-context \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"department_id": "<sales_dept_id>"}'

# 2. 尝试访问老板审批 API（应被拒绝）
curl -X PUT http://localhost:8000/api/quotes/<quote_id>/boss-approve \
  -H "Authorization: Bearer <switched_token>"
# Expected: 403 Forbidden

# 3. 切换回 admin
curl -POST http://localhost:8000/api/admin/switch-back \
  -H "Authorization: Bearer <switched_token>"
# Expected: 恢复全部权限
```

**Success Criteria**: 切换视角后 role_level >= 3 的 API 全部返回 403

---

## 3. API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/login` | POST | None | 用户登录 |
| `/api/auth/me` | GET | JWT | 获取当前用户 |
| `/api/quotes` | POST | role >= 2 | 创建报价单 |
| `/api/quotes/{id}` | GET | role >= 1 | 获取报价单详情 |
| `/api/quotes/{id}/tech-review` | PUT | role >= 4 | 技术审核 |
| `/api/quotes/{id}/submit-boss` | PUT | role >= 2 | 提交老板审批 |
| `/api/quotes/{id}/boss-approve` | PUT | role >= 3 | 老板审批 |
| `/api/quotes/{id}/fix` | POST | role >= 2 | 定点确认 |
| `/api/sampling-tasks` | POST | role >= 3 | 创建打样任务 |
| `/api/sampling-tasks/{id}/boss-approve` | PUT | role >= 3 | 老板审核打样 |
| `/api/sampling-tasks/{id}/review` | PUT | role >= 3 | 评审打样 |
| `/api/production/plans` | POST | role >= 3 | 创建生产计划 |
| `/api/production/plans/{id}/assign-machine` | POST | role >= 3 | 分配机台 |
| `/api/production/sessions/start` | POST | role >= 1 | 开启报工会话 |
| `/api/production/reports` | POST | role >= 1 | 提交报工 |
| `/api/warehouse/material-batches` | POST | role >= 3 | 登记原材料 |
| `/api/warehouse/material-batches/{id}/split` | POST | role >= 3 | 分条操作 |
| `/api/admin/switch-context` | POST | role >= 4 | 切换视角 |
| `/api/admin/switch-back` | POST | role >= 4 | 恢复视角 |

---

## 4. QR Code Format

| Type | Prefix | Example |
|------|--------|---------|
| 原料批次 | `MAT-` | `MAT-20260612-001` |
| 机台 | `MCN-` | `MCN-M001` |
| 工艺流转单 | `PFC-` | `PFC-20260612-001` |

---

*Quickstart completed. See [data-model.md](./data-model.md) for entity details and [tasks.md](./tasks.md) for implementation tasks.*
