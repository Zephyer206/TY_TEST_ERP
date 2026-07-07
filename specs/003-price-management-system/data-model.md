# Data Model: Price Management System

**Feature**: 003-price-management-system  
**Date**: 2026-07-08  
**Status**: Final Design

## Overview

价格管理系统的数据模型包含4张新表和2张扩展表，实现客户价格历史追踪、工序字典管理和价格调整审批流程。

## Entity Relationship Diagram

```
┌─────────────────┐         ┌──────────────────────────┐
│   customers     │────1:N──│ customer_material_prices │
│  (existing)     │         │      (new)               │
└─────────────────┘         └──────────────────────────┘
                                        │
                                        │ N:1
                                        ▼
                            ┌─────────────────┐
                            │  material_dict  │
                            │   (existing)    │
                            └─────────────────┘

┌─────────────────┐         ┌───────────────────────────┐
│   customers     │────1:N──│ customer_treatment_prices │
│  (existing)     │         │       (new)               │
└─────────────────┘         └───────────────────────────┘
                                        │
                                        │ N:1
                                        ▼
                            ┌─────────────────┐
                            │ treatment_dict  │
                            │     (new)       │
                            └─────────────────┘

┌─────────────────┐         ┌────────────────────┐
│ price_accounts  │────1:N──│ price_adjustments  │
│  (existing)     │         │      (new)         │
└─────────────────┘         └────────────────────┘

┌─────────────────┐
│     quotes      │────1:N──┐
│  (existing)     │         │
└─────────────────┘         │ (optional reference)
                            │
                ┌───────────┴──────────┐
                ▼                      ▼
 ┌──────────────────────────┐   ┌───────────────────────────┐
 │ customer_material_prices │   │ customer_treatment_prices │
 └──────────────────────────┘   └───────────────────────────┘
```

## Tables

### 1. treatment_dict (NEW)

**Purpose**: 全局表面处理工序参考字典，提供默认费率和计价方式

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | 工序ID（自增整数） |
| name | VARCHAR(100) | UNIQUE, NOT NULL | 工序名称（如"电镀锌"） |
| calc_mode | VARCHAR(20) | NOT NULL, DEFAULT 'manual' | 计价方式：manual(按件) / net_weight(按重量) |
| default_rate | DECIMAL(10,4) | NOT NULL, DEFAULT 0 | 默认费率（兜底值） |
| unit | VARCHAR(20) | NOT NULL, DEFAULT '元/件' | 单位：元/件 或 元/kg |
| is_active | BOOLEAN | DEFAULT TRUE | 是否激活（停用后不出现在下拉列表） |
| sort_order | INTEGER | DEFAULT 0 | 排序顺序（用于前端展示） |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

**Indexes**:
- `idx_treatment_dict_active` ON (is_active)

**Validation Rules**:
- name 必须唯一
- calc_mode 只能是 'manual' 或 'net_weight'
- default_rate >= 0

**Seed Data**:
```sql
INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active) VALUES
('热处理', 'manual', 1.50, '元/件', TRUE),
('电镀锌', 'manual', 2.00, '元/件', TRUE),
('发黑', 'manual', 1.20, '元/件', TRUE),
('喷涂', 'manual', 2.50, '元/件', TRUE),
('贴胶', 'manual', 0.80, '元/件', TRUE),
('阳极氧化', 'manual', 3.00, '元/件', TRUE),
('磷化', 'manual', 1.80, '元/件', TRUE),
('压铸镀层', 'net_weight', 15.00, '元/kg', TRUE),
('电镀镍', 'manual', 3.50, '元/件', TRUE),
('达克罗涂装', 'manual', 4.00, '元/件', TRUE);
```

---

### 2. customer_material_prices (NEW)

**Purpose**: 客户材料价格历史，记录每个客户每次报价中使用的材料单价

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | 记录ID |
| customer_id | UUID | NOT NULL, FK → customers(id) | 客户ID |
| material_id | INTEGER | NOT NULL, FK → material_dict(id) | 材质ID |
| unit_price | DECIMAL(10,4) | NOT NULL | 该客户该材质的成交单价（元/kg） |
| scrap_price | DECIMAL(10,4) | NULL | 该客户该材质的废料回收价 |
| quote_id | UUID | NULL, FK → quotes(id) | 关联报价单（可追溯定价来源） |
| quoted_at | TIMESTAMP | DEFAULT NOW() | 报价/记录时间 |
| created_by | UUID | NULL, FK → users(id) | 创建人 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

**Indexes**:
- `idx_cmp_customer_material` ON (customer_id, material_id, quoted_at DESC) - 主查询索引
- `idx_cmp_quote` ON (quote_id) WHERE quote_id IS NOT NULL - 报价单反查

**Validation Rules**:
- unit_price > 0
- scrap_price >= 0 (if not null)
- customer_id 必须存在于 customers 表
- material_id 必须存在于 material_dict 表

**Business Rules**:
- 只允许 INSERT 和 SELECT，禁止 UPDATE/DELETE（审计要求）
- 查询时默认按 quoted_at DESC 排序，返回最近3条
- 如无历史记录，兜底使用 material_dict.default_price

**Example Query** (最近3次价格):
```sql
SELECT unit_price, scrap_price, quoted_at, quote_id
FROM customer_material_prices
WHERE customer_id = :customer_id AND material_id = :material_id
ORDER BY quoted_at DESC
LIMIT 3;
```

---

### 3. customer_treatment_prices (NEW)

**Purpose**: 客户工序价格历史，记录每个客户每次报价中使用的工序费用

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | 记录ID |
| customer_id | UUID | NOT NULL, FK → customers(id) | 客户ID |
| treatment_id | INTEGER | NOT NULL, FK → treatment_dict(id) | 工序ID |
| unit_price | DECIMAL(10,4) | NOT NULL | 该客户该工序的成交价 |
| calc_mode_snapshot | VARCHAR(20) | NULL | 快照当时计价方式 |
| unit_snapshot | VARCHAR(20) | NULL | 快照当时单位 |
| quote_id | UUID | NULL, FK → quotes(id) | 关联报价单 |
| quoted_at | TIMESTAMP | DEFAULT NOW() | 报价/记录时间 |
| created_by | UUID | NULL, FK → users(id) | 创建人 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

**Indexes**:
- `idx_ctp_customer_treatment` ON (customer_id, treatment_id, quoted_at DESC)
- `idx_ctp_quote` ON (quote_id) WHERE quote_id IS NOT NULL

**Validation Rules**:
- unit_price > 0
- customer_id 必须存在于 customers 表
- treatment_id 必须存在于 treatment_dict 表

**Business Rules**:
- 只允许 INSERT 和 SELECT，禁止 UPDATE/DELETE
- calc_mode_snapshot 和 unit_snapshot 快照当时 treatment_dict 的值，防止字典变更影响历史解读
- 查询时默认按 quoted_at DESC 排序，返回最近3条
- 如无历史记录，兜底使用 treatment_dict.default_rate

**Example Query** (最近3次价格):
```sql
SELECT unit_price, calc_mode_snapshot, unit_snapshot, quoted_at, quote_id
FROM customer_treatment_prices
WHERE customer_id = :customer_id AND treatment_id = :treatment_id
ORDER BY quoted_at DESC
LIMIT 3;
```

---

### 4. price_adjustments (NEW)

**Purpose**: 价格调整审批记录，实现调价申请 → 审批流程

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | 审批记录ID |
| price_account_id | INTEGER | NOT NULL, FK → price_accounts(id) | 价格台账ID（被调价的零件） |
| old_price | DECIMAL(10,4) | NOT NULL | 旧价格 |
| new_price | DECIMAL(10,4) | NOT NULL | 新价格 |
| adjustment_type | VARCHAR(20) | NOT NULL | 调价类型：increase(上涨) / decrease(下降) |
| reason | TEXT | NOT NULL | 调价原因 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | 审批状态：pending / approved / rejected |
| created_by | UUID | NOT NULL, FK → users(id) | 申请人（业务经理） |
| created_at | TIMESTAMP | DEFAULT NOW() | 申请时间 |
| approved_by | UUID | NULL, FK → users(id) | 审批人（老板） |
| approved_at | TIMESTAMP | NULL | 审批时间 |
| rejection_reason | TEXT | NULL | 驳回原因 |

**Indexes**:
- `idx_pa_status_created` ON (status, created_at DESC) - 待审批列表查询
- `idx_pa_price_account` ON (price_account_id) - 某零件的调价历史

**Validation Rules**:
- old_price != new_price
- adjustment_type = 'increase' when new_price > old_price
- adjustment_type = 'decrease' when new_price < old_price
- status 只能是 'pending', 'approved', 'rejected'
- approved_by 和 approved_at 在 status = 'approved' 或 'rejected' 时必填

**State Machine**:
```
pending (初始状态)
   ├─> approved (审批通过) → 触发 price_accounts.current_price 更新
   └─> rejected (审批驳回) → 不更新价格，记录 rejection_reason
```

**Business Rules**:
- 申请人 role_level >= 5（业务经理）
- 审批人 role_level >= 9（老板）
- 审批通过时，在同一事务中更新 price_accounts.current_price
- 审批后不可撤回或修改（审计要求）

**Example Query** (待审批列表):
```sql
SELECT pa.*, u1.full_name as creator_name, u2.full_name as approver_name
FROM price_adjustments pa
LEFT JOIN users u1 ON pa.created_by = u1.id
LEFT JOIN users u2 ON pa.approved_by = u2.id
WHERE pa.status = 'pending'
ORDER BY pa.created_at DESC;
```

---

### 5. price_accounts (EXISTING - Extended)

**Purpose**: 零件价格台账（已存在），扩展批量查询筛选功能

**New Query Parameters**:
- `customer_id`: 按客户筛选
- `material`: 按材质名称筛选
- `min_price`, `max_price`: 价格区间筛选
- `page`, `page_size`: 分页

**New Indexes** (if not exists):
- `idx_price_accounts_customer` ON (customer_id)
- `idx_price_accounts_material` ON (material)
- `idx_price_accounts_current_price` ON (current_price)

**No Schema Changes** - 只扩展 API 查询功能

---

### 6. material_dict (EXISTING - No Changes)

**Purpose**: 全局材料字典（已存在），作为客户材料价格历史的外键目标

**Role in this feature**:
- customer_material_prices.material_id 引用此表
- 提供 default_price 作为兜底值（当客户无历史记录时）
- 接收 material_base_prices 的数据迁移

**No Schema Changes**

---

## Data Migration Plan

### Step 1-4: Create New Tables
按顺序创建4张新表：treatment_dict → customer_material_prices → customer_treatment_prices → price_adjustments

### Step 5: Migrate material_base_prices → material_dict

**Source**: material_base_prices (14 rows)  
**Target**: material_dict (existing)  
**Strategy**: 按 material_name 匹配，只插入 material_dict 中不存在的材质

```sql
INSERT INTO material_dict (code, name, density, default_price, scrap_price, is_active, created_at)
SELECT
    mbp.material_name,          -- code 暂用 material_name
    mbp.material_name,          -- name
    mbp.default_density,
    mbp.default_price,
    mbp.scrap_price,
    TRUE,
    mbp.updated_at
FROM material_base_prices mbp
WHERE NOT EXISTS (
    SELECT 1 FROM material_dict md WHERE md.name = mbp.material_name
);
```

**Conflict Handling**: 如已存在同名材质，保留 material_dict 现有数据，记录冲突到迁移日志

---

### Step 6: Migrate treatment_dicts → treatment_dict

**Source**: treatment_dicts (28 rows，其中18行是测试脏数据)  
**Target**: treatment_dict (new)  
**Strategy**: 白名单机制，只迁移10条真实工序

```sql
INSERT INTO treatment_dict (name, calc_mode, default_rate, unit, is_active)
SELECT name, calc_mode, rate, unit, TRUE
FROM treatment_dicts
WHERE name IN (
    '热处理','电镀锌','发黑','喷涂','贴胶',
    '阳极氧化','磷化','压铸镀层','电镀镍','达克罗涂装'
);
```

**Data Cleaning**: 丢弃包含 "Test"、"test_"、"API" 等测试标识的18行脏数据

---

### Step 7: Drop Legacy Tables

```sql
DROP TABLE IF EXISTS material_base_prices;
DROP TABLE IF EXISTS material_cost_history;
DROP TABLE IF EXISTS treatment_dicts;
DROP TABLE IF EXISTS treatment_cost_history;
```

**Pre-Check**: 迁移前全局搜索代码库，确认无引用这些旧表名

---

## Validation Rules Summary

| Entity | Rule | Enforcement |
|--------|------|-------------|
| treatment_dict | name 唯一 | DB UNIQUE constraint |
| treatment_dict | calc_mode IN ('manual', 'net_weight') | Pydantic validator |
| treatment_dict | default_rate >= 0 | Pydantic validator |
| customer_material_prices | unit_price > 0 | Pydantic validator |
| customer_material_prices | 只允许 INSERT/SELECT | API 层不暴露 UPDATE/DELETE |
| customer_treatment_prices | unit_price > 0 | Pydantic validator |
| customer_treatment_prices | 只允许 INSERT/SELECT | API 层不暴露 UPDATE/DELETE |
| price_adjustments | old_price != new_price | Pydantic validator |
| price_adjustments | adjustment_type 与价格变化方向一致 | Service 层验证 |
| price_adjustments | 状态转换遵循状态机 | Service 层验证 |
| price_adjustments | 审批人 role_level >= 9 | @require_role(9) decorator |

---

## State Machines

### Price Adjustment Approval Flow

```
┌─────────┐
│ pending │ (初始状态：待审批)
└────┬────┘
     │
     ├─── approve(approver_id, approved_at) ──> ┌──────────┐
     │                                           │ approved │
     │                                           └──────────┘
     │                                                 │
     │                                                 └──> 触发更新 price_accounts.current_price
     │
     └─── reject(approver_id, rejection_reason) ──> ┌──────────┐
                                                     │ rejected │
                                                     └──────────┘
```

**Transitions**:
- `pending → approved`: 老板审批通过，自动更新价格台账
- `pending → rejected`: 老板驳回，价格不变，记录驳回原因
- **不允许**从 approved 或 rejected 转换到其他状态（终态）

---

## Performance Considerations

### Query Optimization

1. **价格历史查询**:
   - 索引 `(customer_id, material_id, quoted_at DESC)` 支持快速定位 + 排序
   - 默认 LIMIT 3，避免全表扫描
   - 响应时间目标 < 2s (P95)

2. **待审批列表查询**:
   - 索引 `(status, created_at DESC)` 支持 WHERE status = 'pending' + 排序
   - 预期待审批数量 < 100，性能无瓶颈

3. **批量价格台账查询**:
   - 组合筛选条件（customer_id + material + price_range）
   - 分页查询，默认 20 条/页

### Data Volume Estimates (Year 1)

| Table | Estimated Rows | Growth Rate |
|-------|----------------|-------------|
| treatment_dict | 10-20 | Low (稳定) |
| customer_material_prices | 1,000-5,000 | 每次报价记录材料价格 |
| customer_treatment_prices | 2,000-10,000 | 每次报价可能多个工序 |
| price_adjustments | 120-600 | 每月10-50条审批 |

### Storage Estimates

- customer_material_prices: ~200 bytes/row × 5,000 = ~1 MB
- customer_treatment_prices: ~250 bytes/row × 10,000 = ~2.5 MB
- price_adjustments: ~300 bytes/row × 600 = ~180 KB

**Total**: < 5 MB (Year 1) - 存储压力极低

---

## References

- [material-treatment-price-history-final.md](../001-erp-system-architecture/database-analysis/material-treatment-price-history-final.md) - 数据库表结构定稿文档
- [research.md](./research.md) - 技术决策文档
- [Existing models](../../backend/app/models/) - 现有数据模型
