# Quickstart: Price Management System Backend

**Feature**: 003-price-management-system  
**Date**: 2026-07-08  
**Purpose**: 端到端验证场景，证明功能正常工作

## Prerequisites

- Python 3.11 环境
- PostgreSQL 15 数据库运行中
- 后端服务已启动（`uvicorn app.main:app --port 8000`）
- 测试数据库已初始化（包含测试用户、客户、材质）

## Test Data Setup

### 1. 创建测试用户

```bash
# 业务经理（role_level = 2）
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "sales_manager",
    "password": "test123",
    "full_name": "张经理",
    "role_level": 2
  }'

# 老板（role_level = 3）
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "boss",
    "password": "test123",
    "full_name": "李老板",
    "role_level": 3
  }'

# 保存返回的 token 用于后续请求
SALES_TOKEN="<业务经理的JWT token>"
BOSS_TOKEN="<老板的JWT token>"
```

### 2. 准备测试数据（客户、材质、零件）

```sql
-- 插入测试客户
INSERT INTO customers (id, name, customer_code) VALUES
(101, '比亚迪', 'BYD001');

-- 确认材质存在（SUS304应该已在 material_dict 中）
SELECT id, name, default_price FROM material_dict WHERE name = 'SUS304';
-- 假设返回 id = 1, default_price = 18.00

-- 插入内部零件；parts 不直接归属于单一客户
INSERT INTO parts (id, internal_name) VALUES
(1001, '测试零件A');

-- 建立客户件号映射；同一内部零件可映射多个客户
INSERT INTO part_customer_aliases
  (id, part_id, customer_id, customer_part_no, revision)
VALUES
  (3001, 1001, 101, 'BYD-TEST-001', '');

INSERT INTO price_accounts (id, part_id, customer_id, current_price) VALUES
(2001, 1001, 101, 50.00);
```

---

## Scenario 1: 数据迁移验证

### Step 1: 运行迁移脚本

```bash
cd backend/scripts/migrations

# 按顺序执行迁移脚本
python 001_create_treatment_dict.py
python 002_create_customer_material_prices.py
python 003_create_customer_treatment_prices.py
python 004_create_price_adjustments.py
python 005_migrate_material_base_prices.py
python 006_migrate_treatment_dicts.py
python 007_drop_legacy_tables.py
```

**Expected Output**:
```
✓ 001: treatment_dict 表创建成功
✓ 002: customer_material_prices 表创建成功
✓ 003: customer_treatment_prices 表创建成功
✓ 004: price_adjustments 表创建成功
✓ 005: 迁移 material_base_prices → material_dict，插入 X 条新材质，跳过 Y 条冲突
✓ 006: 迁移 treatment_dicts → treatment_dict，插入 10 条真实工序，丢弃 18 条测试数据
✓ 007: 删除旧表成功
```

### Step 2: 验证迁移结果

```sql
-- 检查工序字典
SELECT COUNT(*) FROM treatment_dict;  -- 应返回 10

-- 检查材质字典（应包含迁移的材质）
SELECT name, default_price FROM material_dict WHERE name IN ('SUS304', 'Q235');

-- 确认旧表已删除
SELECT COUNT(*) FROM material_base_prices;  -- 应报错：表不存在
```

**Expected**: 
- treatment_dict 有10条记录
- material_dict 包含所有迁移的材质
- 旧表查询失败（表不存在）

---

## Scenario 2: 客户材料价格历史记录

### Step 1: 查询无历史记录的客户材料价格（兜底逻辑）

```bash
curl -X GET "http://localhost:8000/api/customer-prices/materials?customer_id=101&material_id=1" \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "history": [],
  "suggested_price": 18.00,
  "message": "无历史记录，建议使用材料字典默认价格"
}
```

### Step 2: 新增客户材料价格记录

```bash
curl -X POST http://localhost:8000/api/customer-prices/materials \
  -H "Authorization: Bearer $SALES_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 101,
    "material_id": 1,
    "unit_price": 18.50,
    "scrap_price": 3.50,
    "quote_id": null
  }'
```

**Expected Response**:
```json
{
  "id": 3001,
  "customer_id": 101,
  "material_id": 1,
  "unit_price": 18.50,
  "scrap_price": 3.50,
  "quote_id": null,
  "quoted_at": "2026-07-08T10:30:00Z",
  "created_at": "2026-07-08T10:30:00Z"
}
```

### Step 3: 再次查询，验证历史记录

```bash
curl -X GET "http://localhost:8000/api/customer-prices/materials?customer_id=101&material_id=1&limit=3" \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "history": [
    {
      "id": 3001,
      "unit_price": 18.50,
      "scrap_price": 3.50,
      "quoted_at": "2026-07-08T10:30:00Z",
      "quote_id": null
    }
  ],
  "suggested_price": null,
  "message": null
}
```

### Step 4: 添加多条历史记录，验证最近3条限制

```bash
# 添加第2条记录（价格不同）
curl -X POST http://localhost:8000/api/customer-prices/materials \
  -H "Authorization: Bearer $SALES_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 101,
    "material_id": 1,
    "unit_price": 19.00,
    "scrap_price": 3.60
  }'

# 添加第3条记录
curl -X POST http://localhost:8000/api/customer-prices/materials \
  -H "Authorization: Bearer $SALES_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 101,
    "material_id": 1,
    "unit_price": 19.50,
    "scrap_price": 3.70
  }'

# 添加第4条记录
curl -X POST http://localhost:8000/api/customer-prices/materials \
  -H "Authorization: Bearer $SALES_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 101,
    "material_id": 1,
    "unit_price": 20.00,
    "scrap_price": 3.80
  }'

# 查询，应只返回最近3条
curl -X GET "http://localhost:8000/api/customer-prices/materials?customer_id=101&material_id=1&limit=3" \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "history": [
    {"unit_price": 20.00, "scrap_price": 3.80, "quoted_at": "2026-07-08T10:33:00Z"},
    {"unit_price": 19.50, "scrap_price": 3.70, "quoted_at": "2026-07-08T10:32:00Z"},
    {"unit_price": 19.00, "scrap_price": 3.60, "quoted_at": "2026-07-08T10:31:00Z"}
  ],
  "suggested_price": null,
  "message": null
}
```

**Verification**: 
- ✓ 返回3条记录，按时间降序排列
- ✓ 第1条记录（18.50）未出现（被排除在最近3条之外）
- ✓ 数据库中仍保留全部4条记录（验证：直接查询数据库）

---

## Scenario 3: 客户工序价格历史记录

### Step 1: 查询工序字典

```bash
curl -X GET http://localhost:8000/api/treatments \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
[
  {
    "id": 1,
    "name": "热处理",
    "calc_mode": "manual",
    "default_rate": 1.50,
    "unit": "元/件",
    "is_active": true
  },
  {
    "id": 2,
    "name": "电镀锌",
    "calc_mode": "manual",
    "default_rate": 2.00,
    "unit": "元/件",
    "is_active": true
  },
  ...
]
```

### Step 2: 新增客户工序价格记录（快照计价方式）

```bash
curl -X POST http://localhost:8000/api/customer-prices/treatments \
  -H "Authorization: Bearer $SALES_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 101,
    "treatment_id": 2,
    "unit_price": 2.20,
    "calc_mode_snapshot": "manual",
    "unit_snapshot": "元/件",
    "quote_id": null
  }'
```

**Expected Response**:
```json
{
  "id": 4001,
  "customer_id": 101,
  "treatment_id": 2,
  "unit_price": 2.20,
  "calc_mode_snapshot": "manual",
  "unit_snapshot": "元/件",
  "quote_id": null,
  "quoted_at": "2026-07-08T10:40:00Z"
}
```

### Step 3: 修改工序字典，验证历史记录不受影响

```bash
# 修改工序字典：将电镀锌的计价方式从 manual 改为 net_weight
curl -X PUT http://localhost:8000/api/treatments/2 \
  -H "Authorization: Bearer $BOSS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "calc_mode": "net_weight",
    "default_rate": 15.00,
    "unit": "元/kg"
  }'

# 查询工序历史，验证快照值仍是 manual
curl -X GET "http://localhost:8000/api/customer-prices/treatments?customer_id=101&treatment_id=2" \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "history": [
    {
      "id": 4001,
      "unit_price": 2.20,
      "calc_mode_snapshot": "manual",  // ← 仍是旧值，未受字典变更影响
      "unit_snapshot": "元/件",
      "quoted_at": "2026-07-08T10:40:00Z"
    }
  ],
  "suggested_price": null
}
```

**Verification**: 
- ✓ 历史记录的 calc_mode_snapshot 仍是 "manual"
- ✓ 工序字典已变更为 "net_weight"
- ✓ 快照机制保护历史真实性

---

## Scenario 4: 价格调整审批流程

### Step 1: 业务经理提交调价申请

```bash
curl -X POST http://localhost:8000/api/price-adjustments \
  -H "Authorization: Bearer $SALES_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price_account_id": 2001,
    "old_price": 50.00,
    "new_price": 55.00,
    "adjustment_type": "increase",
    "reason": "材料涨价10%，需要同步调整零件价格"
  }'
```

**Expected Response**:
```json
{
  "id": 5001,
  "price_account_id": 2001,
  "old_price": 50.00,
  "new_price": 55.00,
  "adjustment_type": "increase",
  "reason": "材料涨价10%，需要同步调整零件价格",
  "status": "pending",
  "created_by": "<sales_manager_user_id>",
  "created_at": "2026-07-08T11:00:00Z",
  "approved_by": null,
  "approved_at": null
}
```

### Step 2: 验证价格台账未变化（待审批状态）

```bash
curl -X GET http://localhost:8000/api/price-accounts/2001 \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "id": 2001,
  "current_price": 50.00,  // ← 仍是旧价格，未变化
  ...
}
```

### Step 3: 老板查看待审批列表

```bash
curl -X GET http://localhost:8000/api/price-adjustments/pending \
  -H "Authorization: Bearer $BOSS_TOKEN"
```

**Expected Response**:
```json
[
  {
    "id": 5001,
    "price_account_id": 2001,
    "part_name": "测试零件A",
    "customer_name": "比亚迪",
    "old_price": 50.00,
    "new_price": 55.00,
    "adjustment_type": "increase",
    "reason": "材料涨价10%，需要同步调整零件价格",
    "status": "pending",
    "creator_name": "张经理",
    "created_at": "2026-07-08T11:00:00Z"
  }
]
```

### Step 4: 老板审批通过

```bash
curl -X POST http://localhost:8000/api/price-adjustments/<adjustment_id>/approve \
  -H "Authorization: Bearer $BOSS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response**:
```json
{
  "id": 5001,
  "status": "approved",
  "approved_by": "<boss_user_id>",
  "approved_at": "2026-07-08T11:05:00Z",
  "message": "审批通过，价格已更新"
}
```

### Step 5: 验证价格台账已自动更新

```bash
curl -X GET http://localhost:8000/api/price-accounts/2001 \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "id": 2001,
  "current_price": 55.00,  // ← 已更新为新价格
  "updated_at": "2026-07-08T11:05:00Z",
  ...
}
```

### Step 6: 验证审批历史可追溯

```bash
curl -X GET "http://localhost:8000/api/price-adjustments?price_account_id=2001" \
  -H "Authorization: Bearer $BOSS_TOKEN"
```

**Expected Response**:
```json
[
  {
    "id": 5001,
    "old_price": 50.00,
    "new_price": 55.00,
    "status": "approved",
    "creator_name": "张经理",
    "approver_name": "李老板",
    "created_at": "2026-07-08T11:00:00Z",
    "approved_at": "2026-07-08T11:05:00Z"
  }
]
```

**Verification**: 
- ✓ 审批通过后，price_accounts.current_price 自动更新
- ✓ 审批记录包含完整审计轨迹（申请人、审批人、时间）
- ✓ 审批历史可按零件查询

---

## Scenario 5: 审批驳回流程

### Step 1: 业务经理提交新的调价申请

```bash
curl -X POST http://localhost:8000/api/price-adjustments \
  -H "Authorization: Bearer $SALES_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price_account_id": 2001,
    "old_price": 55.00,
    "new_price": 65.00,
    "adjustment_type": "increase",
    "reason": "客户要求紧急涨价"
  }'
```

### Step 2: 老板驳回申请

```bash
curl -X POST http://localhost:8000/api/price-adjustments/<adjustment_id>/reject \
  -H "Authorization: Bearer $BOSS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rejection_reason": "涨幅过大，需重新与客户协商"
  }'
```

**Expected Response**:
```json
{
  "id": 5002,
  "status": "rejected",
  "approved_by": "<boss_user_id>",
  "approved_at": "2026-07-08T11:15:00Z",
  "rejection_reason": "涨幅过大，需重新与客户协商",
  "message": "审批已驳回"
}
```

### Step 3: 验证价格台账未变化

```bash
curl -X GET http://localhost:8000/api/price-accounts/2001 \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "id": 2001,
  "current_price": 55.00,  // ← 仍是旧价格，未变化
  ...
}
```

**Verification**: 
- ✓ 驳回后，价格台账不变
- ✓ 驳回原因已记录
- ✓ 审批记录状态为 "rejected"

---

## Scenario 6: 权限验证

### Step 1: 普通操作工尝试提交调价申请（应失败）

```bash
# 创建普通操作工用户（role_level = 1）
WORKER_TOKEN="<操作工的JWT token>"

curl -X POST http://localhost:8000/api/price-adjustments \
  -H "Authorization: Bearer $WORKER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price_account_id": 2001,
    "old_price": 55.00,
    "new_price": 60.00,
    "adjustment_type": "increase",
    "reason": "测试权限"
  }'
```

**Expected Response**:
```json
{
  "detail": "权限不足：需要 role_level >= 2"
}
```
**Status Code**: 403 Forbidden

### Step 2: 业务经理尝试审批申请（应失败）

```bash
curl -X POST http://localhost:8000/api/price-adjustments/<adjustment_id>/approve \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected Response**:
```json
{
  "detail": "权限不足：需要 role_level >= 3"
}
```
**Status Code**: 403 Forbidden

**Verification**: 
- ✓ 权限检查正常工作
- ✓ @require_role 装饰器生效

---

## Performance Verification

### Test 1: 价格历史查询性能

```bash
# 批量插入100条历史记录
for i in {1..100}; do
  curl -X POST http://localhost:8000/api/customer-prices/materials \
    -H "Authorization: Bearer $SALES_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"customer_id\": 101,
      \"material_id\": 1,
      \"unit_price\": $((18 + i * 0.1)),
      \"scrap_price\": 3.50
    }"
done

# 测量查询响应时间
time curl -X GET "http://localhost:8000/api/customer-prices/materials?customer_id=101&material_id=1&limit=3" \
  -H "Authorization: Bearer $SALES_TOKEN"
```

**Expected**: 
- 响应时间 < 2s (P95)
- 返回最近3条记录

### Test 2: 并发查询压力测试

```bash
# 使用 Apache Bench 测试50并发请求
ab -n 500 -c 50 -H "Authorization: Bearer $SALES_TOKEN" \
  "http://localhost:8000/api/customer-prices/materials?customer_id=101&material_id=1&limit=3"
```

**Expected**: 
- 无请求失败
- 平均响应时间 < 2s

---

## Success Criteria

验证完成后，确认以下所有场景通过：

- ✅ 数据迁移成功，旧表数据正确迁移到新表
- ✅ 客户材料价格历史查询和新增正常
- ✅ 最近3条限制生效，历史记录完整保留
- ✅ 客户工序价格历史查询和新增正常
- ✅ 工序计价方式快照机制正常（字典变更不影响历史）
- ✅ 价格调整审批流程完整（申请 → 审批通过 → 价格更新）
- ✅ 审批驳回流程正常（价格不变，驳回原因记录）
- ✅ 权限验证正常（role_level 检查生效）
- ✅ 审批历史可追溯
- ✅ 性能指标达标（查询 < 2s，并发50无问题）

---

## Rollback Plan

如功能验证失败，执行回滚：

```bash
# 运行回滚脚本（按逆序执行）
cd backend/scripts/migrations
python 007_drop_legacy_tables.py --rollback
python 006_migrate_treatment_dicts.py --rollback
python 005_migrate_material_base_prices.py --rollback
python 004_create_price_adjustments.py --rollback
python 003_create_customer_treatment_prices.py --rollback
python 002_create_customer_material_prices.py --rollback
python 001_create_treatment_dict.py --rollback
```

**Expected**: 
- 所有新表删除
- 旧表恢复（从备份）
- 系统恢复到迁移前状态

---

## Next Steps

验证通过后：

1. 执行生产环境迁移（需人工监督）
2. 更新 API 文档
3. 通知前端团队对接新 API
4. 更新 Agent 上下文（`/speckit.agent-context.update`）
