# 🌐 Zephyr ERP API 接口文档

**技术栈**: FastAPI + SQLAlchemy 2.0 + PostgreSQL  
**API 版本**: v1  
**基础路径**: `/api/v1`  
**文档地址**: `/docs` (开发模式)

---

## 📖 API 概览

Zephyr ERP 系统使用 **FastAPI** 构建 RESTful API，提供完整的冲压工厂管理功能。

### 核心特性

- ✅ **异步架构** - 基于 FastAPI 的高性能异步 API
- ✅ **自动文档** - Swagger UI (/docs) 和 ReDoc (/redoc)
- ✅ **类型安全** - Pydantic 模型验证
- ✅ **JWT 认证** - Bearer Token 认证机制
- ✅ **CORS 支持** - 跨域资源共享
- ✅ **异常处理** - 统一的错误响应格式

---

## 🔐 认证方式

所有 API 端点（除 `/auth/login` 外）都需要 JWT 认证。

### 获取 Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**响应**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "real_name": "管理员",
    "role_level": 4,
    "dept": "admin"
  }
}
```

### 使用 Token

```http
GET /api/v1/parts
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

---

## 📁 API 模块分类

### 1. 认证与用户管理

#### 🔑 Auth (auth.py)
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/logout` - 用户登出
- `GET /api/v1/auth/me` - 获取当前用户信息
- `POST /api/v1/auth/refresh` - 刷新 Token

#### 👤 Admin (admin.py)
- `GET /api/v1/users` - 获取用户列表
- `POST /api/v1/users` - 创建用户
- `PUT /api/v1/users/{id}` - 更新用户
- `DELETE /api/v1/users/{id}` - 删除用户
- `POST /api/v1/users/{id}/reset-password` - 重置密码

**权限要求**: role_level >= 4 (超级管理员)

---

### 2. 核心业务模块

#### 📋 Quotes (quotes.py)
**报价管理 - 系统核心入口**

- `GET /api/v1/quotes` - 获取报价单列表
- `GET /api/v1/quotes/{id}` - 获取报价单详情
- `POST /api/v1/quotes` - 创建报价单
- `PUT /api/v1/quotes/{id}` - 更新报价单
- `DELETE /api/v1/quotes/{id}` - 删除报价单（软删除）
- `POST /api/v1/quotes/{id}/submit` - 提交老板审批
- `POST /api/v1/quotes/{id}/approve` - 老板审批通过
- `POST /api/v1/quotes/{id}/reject` - 老板审批驳回
- `POST /api/v1/quotes/{id}/nominate` - 定点确认
- `GET /api/v1/quotes/pending-boss` - 待老板审批列表

**数据流程**: 
```
创建报价 → 技术审核 → 填写价格 → 提交老板审批 → 审批通过 → 定点确认
```

---

#### 🔧 Parts (parts.py)
**零件管理**

- `GET /api/v1/parts` - 获取零件列表
- `GET /api/v1/parts/{id}` - 获取零件详情
- `POST /api/v1/parts` - 创建零件
- `PUT /api/v1/parts/{id}` - 更新零件
- `DELETE /api/v1/parts/{id}` - 删除零件
- `GET /api/v1/parts/{id}/aliases` - 获取零件客户别名
- `POST /api/v1/parts/{id}/aliases` - 添加客户别名

**零件状态流转**:
```
draft → sampling → mass_production → obsolete
```

---

#### 💰 Price Accounts (price_accounts.py)
**价格台账管理**

- `GET /api/v1/price-accounts` - 获取价格台账列表
- `GET /api/v1/price-accounts/{id}` - 获取价格台账详情
- `POST /api/v1/price-accounts` - 创建价格台账
- `PUT /api/v1/price-accounts/{id}` - 更新价格台账
- `POST /api/v1/price-accounts/{id}/annual-records` - 添加年降记录
- `GET /api/v1/price-accounts/{id}/current-price` - 获取当前价格
- `POST /api/v1/price-accounts/{id}/adjust` - 手动调价

**价格计算**: 支持年降自动计算和手动调价

---

#### 👥 Customers (customers.py)
**客户管理**

- `GET /api/v1/customers` - 获取客户列表
- `GET /api/v1/customers/{id}` - 获取客户详情
- `POST /api/v1/customers` - 创建客户
- `PUT /api/v1/customers/{id}` - 更新客户
- `DELETE /api/v1/customers/{id}` - 删除客户

---

### 3. 生产管理模块

#### 🏭 Production (production.py)
**生产计划与报工**

- `GET /api/v1/production/plans` - 获取生产计划列表
- `POST /api/v1/production/plans` - 创建生产计划
- `PUT /api/v1/production/plans/{id}` - 更新生产计划
- `POST /api/v1/production/plans/{id}/assign-machine` - 分配机台
- `POST /api/v1/production/reports` - 提交报工记录
- `GET /api/v1/production/reports` - 获取报工记录
- `POST /api/v1/production/sessions` - 开启报工会话（连续模）
- `PUT /api/v1/production/sessions/{id}/close` - 关闭报工会话

**报工模式**:
- **简易模**: 单次报工
- **连续模**: 会话模式，多次提交冲次

---

#### 🔨 Toolings (toolings.py)
**模具管理**

- `GET /api/v1/toolings` - 获取模具列表
- `GET /api/v1/toolings/{id}` - 获取模具详情
- `POST /api/v1/toolings` - 创建模具
- `PUT /api/v1/toolings/{id}` - 更新模具
- `POST /api/v1/toolings/{id}/maintenance` - 记录维修
- `GET /api/v1/toolings/{id}/maintenance-logs` - 获取维修历史

**模具状态**: available / in_use / maintenance / converted / scrapped

---

#### 🖥️ Machines (machines.py)
**机台管理**

- `GET /api/v1/machines` - 获取机台列表
- `GET /api/v1/machines/{id}` - 获取机台详情
- `POST /api/v1/machines` - 创建机台
- `PUT /api/v1/machines/{id}` - 更新机台
- `POST /api/v1/machines/{id}/status` - 更新机台状态
- `GET /api/v1/machines/{id}/status-logs` - 获取状态变更历史

**机台状态**: idle / running / fault / pending_check / repairing / offline

---

#### 🎨 Sampling Tasks (sampling_tasks.py)
**打样任务管理**

- `GET /api/v1/sampling-tasks` - 获取打样任务列表
- `POST /api/v1/sampling-tasks` - 创建打样任务
- `PUT /api/v1/sampling-tasks/{id}` - 更新打样任务
- `POST /api/v1/sampling-tasks/{id}/approve` - 老板审批打样
- `POST /api/v1/sampling-tasks/{id}/start` - 开始打样
- `POST /api/v1/sampling-tasks/{id}/submit-review` - 提交评审
- `POST /api/v1/sampling-tasks/{id}/review` - 评审结果

---

### 4. 质量管理模块

#### ✅ Quality (quality.py)
**质量检验**

- `POST /api/v1/quality/first-piece` - 首件检验
- `POST /api/v1/quality/oqc` - OQC 出货检验
- `POST /api/v1/quality/patrol` - 巡检记录
- `POST /api/v1/quality/exemption` - 强行特赦
- `GET /api/v1/quality/inspections` - 获取检验记录

**检验流程**:
```
首件检验 → 批量生产 → 巡检 → OQC 出货检验 → 放行
```

---

### 5. 仓库与物流模块

#### 📦 Warehouse (warehouse.py)
**原材料与仓库管理**

- `GET /api/v1/warehouse/materials` - 获取原材料批次
- `POST /api/v1/warehouse/materials` - 创建材料批次
- `PUT /api/v1/warehouse/materials/{id}` - 更新批次
- `POST /api/v1/warehouse/materials/{id}/iqc` - IQC 检验
- `POST /api/v1/warehouse/materials/{id}/split` - 分条操作
- `GET /api/v1/warehouse/suppliers` - 获取供应商列表

---

#### 📦 Packaging (packaging.py)
**包装管理**

- `POST /api/v1/packaging/scan` - 包装扫码
- `POST /api/v1/packaging/warehouse` - 全检入库
- `GET /api/v1/packaging/records` - 获取包装记录

---

### 6. 表面处理模块

#### 🎨 Coating (coating.py)
**喷涂管理**

- `GET /api/v1/coating/recipes` - 获取喷涂配方
- `POST /api/v1/coating/recipes` - 创建喷涂配方
- `POST /api/v1/coating/records` - 喷涂报工
- `GET /api/v1/coating/records` - 获取喷涂记录

---

### 7. 二维码与追溯

#### 📱 QR Code (qr.py)
**二维码扫码与追溯**

- `POST /api/v1/qr/scan` - 扫码操作
- `GET /api/v1/qr/material/{batch_number}` - 查询原材料批次
- `GET /api/v1/qr/machine/{machine_number}` - 查询机台信息
- `GET /api/v1/qr/process-flow/{card_number}` - 查询工艺流转单
- `GET /api/v1/qr/logs` - 扫码日志

---

### 8. 字典管理模块

#### 📖 Part Names (part_names.py + part_names_extra.py)
**零件名称字典 - 三级分类系统**

**主接口** (part_names.py):
- `GET /api/v1/part-names` - 获取零件名称列表
- `POST /api/v1/part-names` - 创建零件名称
- `PUT /api/v1/part-names/{id}` - 更新零件名称
- `DELETE /api/v1/part-names/{id}` - 删除零件名称

**扩展接口** (part_names_extra.py):
- `GET /api/v1/part-names/categories/primary` - 获取一级分类
- `GET /api/v1/part-names/categories/secondary?primary_category=X` - 获取二级分类
- `GET /api/v1/part-names/tree` - 获取完整三级树形结构

**三级分类结构**:
```
一级分类 (primary_category) - 零件主名称
  └─ 二级分类 (secondary_category) - 细分类别
      └─ 三级分类 (customer_part_name) - 客户零件名称
```

---

#### 🧪 Materials (materials.py)
**材料字典**

- `GET /api/v1/materials` - 获取材料列表
- `POST /api/v1/materials` - 创建材料
- `PUT /api/v1/materials/{id}` - 更新材料

---

#### ⚙️ Machine Tonnages (machine_tonnages.py)
**机台吨位字典**

- `GET /api/v1/machine-tonnages` - 获取吨位列表
- `POST /api/v1/machine-tonnages` - 创建吨位

---

#### 🔧 Mold Types (mold_types.py)
**模具类型字典**

- `GET /api/v1/mold-types` - 获取模具类型列表
- `POST /api/v1/mold-types` - 创建模具类型

---

## 🔒 权限控制

### 角色级别 (role_level)

| 级别 | 角色 | 说明 |
|------|------|------|
| 1 | 普通员工 | 操作工、仓库管理员、质检员 |
| 2 | 管理人员及业务 | 班组长、技术人员、业务人员 |
| 3 | 老板 | 最终审批、全局数据查看 |
| 4 | 超级管理员 | 系统管理、用户管理 |

### 权限装饰器

```python
from app.api.deps import require_role

@router.post("/admin-only")
async def admin_endpoint(current_user: CurrentUser = Depends(require_role(4))):
    # 仅超级管理员可访问
    pass
```

---

## 📊 数据模型

### 通用响应格式

**成功响应**:
```json
{
  "id": 1,
  "name": "零件A",
  "status": "mass_production",
  "created_at": "2026-07-04T10:00:00Z"
}
```

**错误响应**:
```json
{
  "detail": "错误描述",
  "errors": ["字段 -> 错误信息"]
}
```

### HTTP 状态码

- `200 OK` - 请求成功
- `201 Created` - 资源创建成功
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 未认证
- `403 Forbidden` - 无权限
- `404 Not Found` - 资源不存在
- `422 Unprocessable Entity` - 验证错误
- `500 Internal Server Error` - 服务器错误

---

## 🌐 CORS 配置

允许的源:
- `http://localhost:3000` (前端开发)
- `http://localhost:5173` (Vite 开发服务器)
- 其他配置的源

---

## 📝 API 使用示例

### 示例 1: 创建报价单

```bash
curl -X POST "http://localhost:8000/api/v1/quotes" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "part_id": 1,
    "customer_id": 1,
    "annual_volume": 100000,
    "thickness": 1.5,
    "width": 50.0,
    "press_stroke": 10.0,
    "cavity_count": 2
  }'
```

### 示例 2: 提交生产报工

```bash
curl -X POST "http://localhost:8000/api/v1/production/reports" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": 1,
    "machine_id": 1,
    "strokes": 1000,
    "qualified_quantity": 1950
  }'
```

### 示例 3: 查询零件名称树

```bash
curl -X GET "http://localhost:8000/api/v1/part-names/tree" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📚 更多信息

- **Swagger 文档**: `http://localhost:8000/docs`
- **ReDoc 文档**: `http://localhost:8000/redoc`
- **健康检查**: `http://localhost:8000/health`
- **API 版本**: `http://localhost:8000/` (根路径)

---

## 🛠️ 开发信息

**框架版本**:
- FastAPI: ^0.100.0
- SQLAlchemy: ^2.0.0
- Pydantic: ^2.0.0
- PostgreSQL: 14+

**代码位置**:
- API 路由: `backend/app/api/`
- 数据模型: `backend/app/models/`
- Pydantic Schema: `backend/app/schemas/`
- 业务逻辑: `backend/app/services/`

---

**最后更新**: 2026-07-04  
**文档版本**: v1.0
