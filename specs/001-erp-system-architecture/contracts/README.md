# Contracts: Zephyr_test_ERP

**Feature**: 001-erp-system-architecture
**Date**: 2026-06-12

本目录记录系统对外暴露的接口契约。

---

## 1. Public API Contracts

### 1.1 Authentication

#### POST /api/auth/login

**Request**:
```json
{
  "username": "string",
  "password": "string"
}
```

**Response** (200):
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "string",
    "real_name": "string",
    "role_level": 5,
    "department": {
      "id": 1,
      "name": "string"
    }
  }
}
```

**Errors**:
- `401`: Invalid credentials

---

### 1.2 Part Name Dictionary (零件名称字典)

#### GET /api/v1/part-names

**Auth**: role >= 1

**Query Parameters**:
- `search` (optional): 搜索关键词（匹配一级、二级、三级分类）
- `primary_category` (optional): 按一级分类过滤
- `secondary_category` (optional): 按二级分类过滤
- `is_active` (optional): 按启用状态过滤
- `skip` (optional, default: 0): 分页偏移
- `limit` (optional, default: 100): 每页数量

**Response** (200):
```json
[
  {
    "id": 1,
    "primary_category": "支架",
    "secondary_category": "A型",
    "customer_part_name": "前门支架",
    "remark": "适用于XX车型",
    "usage_count": 15,
    "is_active": true,
    "sort_order": 0,
    "created_at": "2026-06-22T10:00:00Z",
    "updated_at": "2026-06-22T10:00:00Z"
  }
]
```

#### POST /api/v1/part-names

**Auth**: role >= 4

**Request**:
```json
{
  "primary_category": "支架",
  "secondary_category": "A型",
  "customer_part_name": "前门支架",
  "remark": "适用于XX车型"
}
```

**Response** (201):
```json
{
  "id": 1,
  "primary_category": "支架",
  "secondary_category": "A型",
  "customer_part_name": "前门支架",
  "remark": "适用于XX车型",
  "usage_count": 0,
  "is_active": true,
  "sort_order": 0,
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:00:00Z"
}
```

**Errors**:
- `400`: 相同的零件名称组合已存在 (UNIQUE constraint on primary_category + secondary_category + customer_part_name)

#### PATCH /api/v1/part-names/{id}

**Auth**: role >= 4

**Request**:
```json
{
  "primary_category": "支架",
  "secondary_category": "B型",
  "customer_part_name": "后门支架",
  "remark": "更新备注",
  "is_active": false
}
```

**Response** (200): Same as POST response

**Errors**:
- `404`: 零件名称不存在
- `400`: 相同的零件名称组合已存在

#### DELETE /api/v1/part-names/{id}

**Auth**: role >= 4

**Response** (204): No content

**Errors**:
- `404`: 零件名称不存在
- `400`: 该零件名称正在被 N 条记录使用，无法删除 (usage_count > 0)

---

### 1.3 Quotes

#### POST /api/quotes

**Auth**: role >= 5

**Request**:
```json
{
  "customer_name": "string",
  "items": [{
    "part_name": "string",
    "customer_part_no": "string (optional)",
    "annual_volume": 10000
  }]
}
```

**Response** (201):
```json
{
  "id": 1,
  "quote_number": "Q-20260612-001",
  "customer": { "id": 1, "name": "string" },
  "status": "waiting_tech_review",
  "items": [...],
  "created_at": "2026-06-12T10:00:00Z"
}
```

#### PUT /api/quotes/{id}/tech-review

**Auth**: role >= 4

**Request**:
```json
{
  "t_parameter": 2.5,
  "w_parameter": 100.0,
  "p_parameter": 50,
  "cavity_count": 4,
  "press_tonnage": 200,
  "tooling_fee": 50000,
  "tooling_fee_mode": "direct",
  "tooling_fee_discount": 0.0
}
```

#### PUT /api/quotes/{id}/boss-approve

**Auth**: role >= 9

**Response** (200):
```json
{
  "id": 1,
  "status": "boss_approved",
  "quote_snapshot": {
    "stamping_fee": 15.0,
    "profit": 5.0,
    "surface_treatment_fee": 3.0,
    "tooling_fee": 50000,
    "material_unit_price": 8.5
  },
  "boss_approved_at": "2026-06-12T10:30:00Z"
}
```

#### POST /api/quotes/{id}/fix

**Auth**: role >= 5

**Request**:
```json
{
  "fix_path": "mass_production | sampling",
  "tooling_number": "T-001",
  "ppap_number": "PPAP-001",
  "customer_part_no": "CUST-PN-001"
}
```

---

### 1.4 Production

#### POST /api/production/sessions/start

**Auth**: role >= 1

**Request**:
```json
{
  "plan_id": 1,
  "machine_id": 1,
  "material_batch_id": 1
}
```

**Response** (201):
```json
{
  "session_id": 1,
  "status": "active",
  "started_at": "2026-06-12T11:00:00Z",
  "validation": {
    "material_tooling_match": true,
    "can_force_start": false
  }
}
```

#### POST /api/production/reports

**Auth**: role >= 1

**Request**:
```json
{
  "session_id": 1,
  "strokes": 100
}
```

**Response** (201):
```json
{
  "id": 1,
  "report_number": "PR-20260612-001",
  "strokes": 100,
  "output_quantity": 400,
  "qualified_quantity": 398,
  "process_flow_card_id": 1,
  "card_number": "PFC-20260612-001",
  "created_at": "2026-06-12T11:05:00Z"
}
```

---

### 1.5 Warehouse

#### POST /api/warehouse/material-batches

**Auth**: role >= 3

**Request**:
```json
{
  "material_brand": "DC01",
  "material_type": "冷轧钢卷",
  "weight": 1000,
  "width": 1250,
  "supplier_name": "供应商A"
}
```

**Response** (201):
```json
{
  "id": 1,
  "batch_number": "MAT-20260612-001",
  "qr_code_path": "/static/qr/material/MAT-20260612-001.png",
  "status": "available",
  "created_at": "2026-06-12T09:00:00Z"
}
```

#### POST /api/warehouse/material-batches/{id}/split

**Auth**: role >= 3

**Request**:
```json
{
  "split_count": 3,
  "split_weights": [300, 350, 300],
  "split_widths": [400, 400, 400]
}
```

---

### 1.6 QR Code Response Contract

#### GET /api/qr/lookup?code={qr_code}

**Auth**: role >= 1

**Response** (200) — 原料批次:
```json
{
  "type": "material",
  "batch_number": "MAT-20260612-001",
  "info": {
    "material_brand": "DC01",
    "weight": 1000,
    "status": "in_use",
    "supplier": "供应商A",
    "created_at": "2026-06-12T09:00:00Z"
  },
  "trace": [
    { "action": "iqc_pass", "at": "2026-06-12T09:30:00Z" },
    { "action": "split", "children": ["MAT-20260612-002", "MAT-20260612-003"] },
    { "action": "fed_to_machine", "machine": "MCN-M001", "at": "2026-06-12T11:00:00Z" }
  ]
}
```

#### GET /api/qr/lookup?code=PFC-20260612-001

**Response** (200) — 工艺流转单:
```json
{
  "type": "process_flow",
  "card_number": "PFC-20260612-001",
  "info": {
    "part_name": "支架-001",
    "quantity": 400,
    "operator": "张三",
    "machine": "MCN-M001",
    "production_time": "2026-06-12T11:05:00Z",
    "status": "produced"
  },
  "trace": {
    "supplier": "供应商A",
    "material_batch": "MAT-20260612-001",
    "child_batch": "MAT-20260612-002",
    "machine": "MCN-M001",
    "operator": "张三",
    "production_time": "2026-06-12T11:05:00Z"
  }
}
```

---

## 2. Internal Event Contracts

### 2.1 State Change Events

系统内部通过事件总线广播状态变更：

```python
class QuoteStatusChanged(Event):
    quote_id: int
    old_status: QuoteStatus
    new_status: QuoteStatus
    changed_by: int
    changed_at: datetime

class PartStatusChanged(Event):
    part_id: int
    old_status: PartStatus
    new_status: PartStatus
    reason: str | None
    changed_by: int
    changed_at: datetime

class ProductionSessionClosed(Event):
    session_id: int
    plan_id: int
    total_output: int
    total_qualified: int
    process_flow_card_id: int
    closed_at: datetime
```

---

*Contracts documented. See [quickstart.md](../quickstart.md) for runnable validation scenarios.*
