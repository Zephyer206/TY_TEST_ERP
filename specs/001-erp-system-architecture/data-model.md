# Data Model: Zephyr_test_ERP

**Feature**: 001-erp-system-architecture
**Date**: 2026-06-12

---

## 1. Core Entities Overview

```
User ─────┬──── Department
          │
          └──── Quote ──── QuoteItem ──── Part
                              │
Part ─────┬─── PartCustomerAlias
          ├── Tooling (模具)
          ├── ToolingPart (模具-零件关联)
          ├── MaterialBatch (原料批次，单表自引用)
          │       └── MaterialBatch.parent_batch_id → MaterialBatch (子卷)
          └── ProductionPlan ─── ProductionReport (报工)

Part ───────── ProductionPlan
      └──────── ProductionReport
                    └──────── ProcessFlowCard (工艺流转单)

Machine ──┬── Tooling (当前模具)
          └── MachineStatusLog

SamplingTask ─── Part (样件)

QualityInspection ─── Part (质检)
  ├── FirstPieceInspection (首件检验)
  ├── OQCInspection (OQC出货检验)
  └── QAExemption (强行特赦)

CoatingRecord ─── Part (喷涂)

AuditLog (审计日志)
```

---

## 2. Entity Definitions

### 2.1 User & Auth

```
Table: users
├── id                      UUID PRIMARY KEY
├── username                VARCHAR(50) UNIQUE NOT NULL
├── password_hash           VARCHAR(255) NOT NULL
├── real_name               VARCHAR(100) NOT NULL
├── role_level              INTEGER NOT NULL DEFAULT 1  -- 1=普通员工, 2=管理人员及业务, 3=老板, 4=超级管理员
├── department_id           UUID REFERENCES departments(id)
├── special_permissions     JSONB NULL  -- 特殊权限代码数组，引用 special_permissions_dict.permission_code
├── is_active               BOOLEAN DEFAULT TRUE  -- 账户是否启用
├── last_login_at           TIMESTAMP NULL  -- 最后登录时间
├── is_deleted              BOOLEAN DEFAULT FALSE
├── created_at              TIMESTAMP DEFAULT NOW()
└── updated_at              TIMESTAMP DEFAULT NOW()

Table: special_permissions_dict  -- 特殊权限字典
├── id                      UUID PRIMARY KEY
├── permission_code         VARCHAR(50) UNIQUE NOT NULL  -- 权限代码（如 'quote_review'）
├── permission_name         VARCHAR(100) NOT NULL        -- 权限名称（如 '报价技术审核权限'）
├── description             TEXT NULL                    -- 权限说明
├── required_role_level     INTEGER NULL                 -- 要求的最低 role_level
├── required_department     VARCHAR(50) NULL             -- 要求的部门
├── is_active               BOOLEAN DEFAULT TRUE
└── created_at              TIMESTAMP DEFAULT NOW()

Table: departments
├── id              UUID PRIMARY KEY
├── name            VARCHAR(50) NOT NULL  -- 业务部/生产部/开发部/原料仓库/品管部/全检部/喷涂部/会计部/人事部/设备部/admin
├── is_deleted      BOOLEAN DEFAULT FALSE
└── created_at      TIMESTAMP DEFAULT NOW()

Table: admin_context_switches
├── id              UUID PRIMARY KEY
├── admin_user_id   UUID REFERENCES users(id) NOT NULL
├── target_dept_id  UUID REFERENCES departments(id) NOT NULL
├── original_role   INTEGER NOT NULL
├── switched_at     TIMESTAMP DEFAULT NOW()
└── switched_back_at TIMESTAMP NULL
```

### 2.2 Quote (报价单)

```
Table: quotes
├── id                        UUID PRIMARY KEY
├── quote_number              VARCHAR(20) UNIQUE NOT NULL  -- 报价单号 Q-YYYYMMDD-NNN
├── customer_id               UUID REFERENCES customers(id)
├── status                    VARCHAR(30) NOT NULL  -- waiting_tech_review/tech_approved/tech_rejected/draft/pending_boss/boss_approved/boss_rejected
├── submitted_by              UUID REFERENCES users(id)
├── submitted_at              TIMESTAMP NULL
├── boss_approved_by          UUID REFERENCES users(id) NULL
├── boss_approved_at          TIMESTAMP NULL
├── boss_reject_reason        TEXT NULL
├── is_fixed                  BOOLEAN DEFAULT FALSE  -- 定点确认
├── fix_path                  VARCHAR(20) NULL  -- mass_production / sampling
├── quote_snapshot            JSONB NULL  -- 老板审批时的价格快照
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: quote_items
├── id                        UUID PRIMARY KEY
├── quote_id                  UUID REFERENCES quotes(id) NOT NULL
├── part_id                   UUID REFERENCES parts(id) NULL  -- 可能新建零件
├── part_name                 VARCHAR(200) NOT NULL
├── customer_part_no          VARCHAR(100) NULL  -- 客户件号
├── annual_volume             DECIMAL(12,2) NULL  -- 年用量
├── t_parameter               DECIMAL(8,3) NULL  -- 厚度 T (mm)
├── w_parameter               DECIMAL(8,3) NULL  -- 宽度 W (mm)
├── p_parameter               DECIMAL(8,3) NULL  -- 冲次 P
├── cavity_count              INTEGER NULL  -- 穴数
├── press_tonnage             DECIMAL(10,2) NULL  -- 吨位
├── tooling_fee               DECIMAL(12,2) NULL  -- 模具费
├── tooling_fee_mode          VARCHAR(20) NULL  -- direct / amortized
├── tooling_fee_discount      DECIMAL(5,4) DEFAULT 0  -- 模具费折扣率 0.0~1.0
├── tooling_amortization_amount   DECIMAL(12,4) NULL  -- 单件模摊费用（模具费/模摊数量）
├── tooling_amortization_quantity INTEGER NULL  -- 模摊数量
├── stamping_fee              DECIMAL(12,2) NULL  -- 冲压费
├── total_price               DECIMAL(14,2) NULL  -- 总价
├── notes                     TEXT NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
└── created_at                TIMESTAMP DEFAULT NOW()

Table: surface_treatments  -- 多道表面处理
├── id                        UUID PRIMARY KEY
├── quote_item_id             UUID REFERENCES quote_items(id) NOT NULL
├── sequence                  INTEGER NOT NULL  -- 处理顺序
├── treatment_name            VARCHAR(100) NOT NULL
├── treatment_fee             DECIMAL(12,2) NOT NULL
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: quote_tech_reviews  -- 技术审核记录
├── id                        UUID PRIMARY KEY
├── quote_id                  UUID REFERENCES quotes(id) NOT NULL
├── reviewed_by               UUID REFERENCES users(id) NOT NULL
├── status                    VARCHAR(20) NOT NULL  -- approved / rejected
├── review_notes              TEXT NULL
├── reviewed_at               TIMESTAMP DEFAULT NOW()
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: customers
├── id                        UUID PRIMARY KEY
├── name                      VARCHAR(200) NOT NULL
├── contact_person            VARCHAR(100) NULL
├── contact_phone             VARCHAR(50) NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
└── created_at                TIMESTAMP DEFAULT NOW()
```

### 2.3 Part (零件)

```
Table: parts
├── id                        UUID PRIMARY KEY
├── part_number               VARCHAR(50) UNIQUE NOT NULL  -- 零件编号
├── part_name                 VARCHAR(200) NOT NULL
├── status                    VARCHAR(30) NOT NULL  -- draft / sampling / mass_production / obsolete
├── tooling_id                UUID REFERENCES toolings(id) NULL  -- 当前模具
├── ppap_number               VARCHAR(50) NULL
├── vehicle_model             VARCHAR(100) NULL  -- 车型
├── cavity_count              INTEGER NULL
├── press_tonnage             DECIMAL(10,2) NULL
├── material_type             VARCHAR(100) NULL
├── net_weight                DECIMAL(10,3) NULL  -- 净重 (kg)
├── gross_weight              DECIMAL(10,3) NULL  -- 毛重 (kg)
├── drawing_path              VARCHAR(500) NULL  -- 图纸路径
├── surface_treatment_type    VARCHAR(100) NULL  -- 表面处理类型
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: part_name_dict  -- 零件名称字典（三级分类系统）
├── id                        INTEGER PRIMARY KEY AUTOINCREMENT
├── primary_category          VARCHAR(100) NOT NULL  -- 一级分类（必填）- 零件主名称
├── secondary_category        VARCHAR(100) NULL  -- 二级分类（可选）
├── customer_part_name        VARCHAR(200) NULL  -- 三级分类（可选）- 客户零件名称
├── remark                    TEXT NULL  -- 备注说明
├── name                      VARCHAR(200) NULL  -- [已废弃] 零件名称
├── category                  VARCHAR(100) NULL  -- [已废弃] 旧分类字段
├── usage_count               INTEGER DEFAULT 0  -- 使用次数（统计用）
├── is_active                 BOOLEAN DEFAULT TRUE  -- 是否启用
├── sort_order                INTEGER DEFAULT 0  -- 排序
├── created_at                TIMESTAMP DEFAULT NOW()
├── updated_at                TIMESTAMP DEFAULT NOW()
└── created_by                INTEGER NULL REFERENCES users(id)

Table: part_customer_aliases
├── id                        UUID PRIMARY KEY
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── customer_id               UUID REFERENCES customers(id) NOT NULL
├── customer_part_no          VARCHAR(100) NOT NULL
├── price_account_id          UUID REFERENCES price_accounts(id) NULL
└── UNIQUE(part_id, customer_id, customer_part_no)

Table: price_accounts
├── id                        UUID PRIMARY KEY
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── customer_id               UUID REFERENCES customers(id) NOT NULL
├── is_active                 BOOLEAN DEFAULT TRUE
├── base_price                DECIMAL(14,4) NULL  -- 基准单价
├── material_unit_price        DECIMAL(14,4) NULL  -- 材料单价
├── waste_price               DECIMAL(14,4) NULL  -- 废料价
├── price_snapshot            JSONB NULL  -- 定点快照
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()
-- UNIQUE(part_id, customer_id) at DB level

Table: annual_price_records  -- 年降价格记录
├── id                        UUID PRIMARY KEY
├── price_account_id          UUID REFERENCES price_accounts(id) NOT NULL
├── year                      INTEGER NOT NULL
├── unit_price                DECIMAL(14,4) NOT NULL
├── annual_volume             DECIMAL(12,2) NULL
├── created_by                UUID REFERENCES users(id) NOT NULL
├── created_at                TIMESTAMP DEFAULT NOW()
└── UNIQUE(price_account_id, year)

Table: price_adjustments  -- 手动调价记录
├── id                        UUID PRIMARY KEY
├── price_account_id          UUID REFERENCES price_accounts(id) NOT NULL
├── old_price                 DECIMAL(14,4) NOT NULL
├── new_price                 DECIMAL(14,4) NOT NULL
├── adjustment_reason         TEXT NOT NULL
├── adjusted_by               UUID REFERENCES users(id) NOT NULL
├── adjusted_at               TIMESTAMP DEFAULT NOW()
└── is_deleted                BOOLEAN DEFAULT FALSE
```

### 2.4 Tooling (模具)

```
Table: toolings
├── id                        UUID PRIMARY KEY
├── tooling_number            VARCHAR(50) UNIQUE NULL  -- 定点确认后由人工分配
├── customer_product_no       VARCHAR(100) NULL  -- 客户产品号
├── cavity_count              INTEGER NULL
├── press_tonnage             DECIMAL(10,2) NULL
├── ppap_number               VARCHAR(50) NULL
├── vehicle_model             VARCHAR(100) NULL
├── status                    VARCHAR(30) NOT NULL  -- available / in_use / maintenance / converted / scrapped
├── current_machine_id        UUID REFERENCES machines(id) NULL
├── created_by                UUID REFERENCES users(id) NOT NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: tooling_parts  -- 模具-零件关联（多对多）
├── id                        UUID PRIMARY KEY
├── tooling_id                UUID REFERENCES toolings(id) NOT NULL
├── part_id                   UUID REFERENCES parts(id) NOT NULL
└── UNIQUE(tooling_id, part_id)

Table: tooling_maintenance_logs
├── id                        UUID PRIMARY KEY
├── tooling_id                UUID REFERENCES toolings(id) NOT NULL
├── fault_time                TIMESTAMP NOT NULL
├── fault_reason              TEXT NOT NULL
├── repair_solution           TEXT NULL
├── repair_completed_at       TIMESTAMP NULL
├── repaired_by               UUID REFERENCES users(id) NULL
└── is_deleted                BOOLEAN DEFAULT FALSE
```

### 2.5 Machine (机台)

```
Table: machines
├── id                        UUID PRIMARY KEY
├── machine_number            VARCHAR(50) UNIQUE NOT NULL
├── machine_name              VARCHAR(100) NOT NULL
├── model                     VARCHAR(100) NULL
├── status                    VARCHAR(20) NOT NULL  -- idle / running / fault / pending_check / repairing / offline
├── current_tooling_id        UUID REFERENCES toolings(id) NULL
├── current_plan_id           UUID REFERENCES production_plans(id) NULL
├── current_part_id           UUID REFERENCES parts(id) NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: machine_status_logs
├── id                        UUID PRIMARY KEY
├── machine_id                UUID REFERENCES machines(id) NOT NULL
├── from_status               VARCHAR(20) NOT NULL
├── to_status                 VARCHAR(20) NOT NULL
├── changed_by                UUID REFERENCES users(id) NOT NULL
├── changed_at                TIMESTAMP DEFAULT NOW()
└── reason                    TEXT NULL
```

### 2.6 Sampling Task (打样任务)

```
Table: sampling_tasks
├── id                        UUID PRIMARY KEY
├── task_number               VARCHAR(20) UNIQUE NOT NULL  -- SAM-YYYYMMDD-NNN
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── customer_id               UUID REFERENCES customers(id) NOT NULL
├── order_date                DATE NOT NULL  -- 下单时间
├── planned_finish_date        DATE NOT NULL  -- 计划完成时间
├── actual_finish_date        DATE NULL
├── sample_quantity           INTEGER NOT NULL  -- 样件数量
├── status                    VARCHAR(30) NOT NULL  -- pending_review / pending_production / sampling / pending_review / passed / failed / cancelled
├── is_urgent                 BOOLEAN DEFAULT FALSE
├── created_by                UUID REFERENCES users(id) NOT NULL
├── boss_approved_by          UUID REFERENCES users(id) NULL
├── boss_approved_at          TIMESTAMP NULL
├── started_at                TIMESTAMP NULL
├── submitted_review_by       UUID REFERENCES users(id) NULL
├── submitted_review_at       TIMESTAMP NULL
├── review_result             VARCHAR(20) NULL  -- passed / failed
├── review_notes              TEXT NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()
```

### 2.7 Production (生产)

```
Table: production_plans
├── id                        UUID PRIMARY KEY
├── plan_number               VARCHAR(20) UNIQUE NOT NULL  -- PP-YYYYMMDD-NNN
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── total_quantity            INTEGER NOT NULL
├── completed_quantity        INTEGER DEFAULT 0
├── deadline                   DATE NOT NULL
├── urgency                   VARCHAR(10) NOT NULL  -- normal / urgent / critical
├── status                    VARCHAR(20) NOT NULL  -- planned / in_progress / completed / cancelled / closed
├── assigned_by                UUID REFERENCES users(id) NOT NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: plan_machine_assignments  -- 计划-机台分配
├── id                        UUID PRIMARY KEY
├── plan_id                   UUID REFERENCES production_plans(id) NOT NULL
├── machine_id                UUID REFERENCES machines(id) NOT NULL
├── assigned_by                UUID REFERENCES users(id) NOT NULL
├── assigned_at                TIMESTAMP DEFAULT NOW()
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: production_reports  -- 报工记录
├── id                        UUID PRIMARY KEY
├── report_number              VARCHAR(20) UNIQUE NOT NULL  -- PR-YYYYMMDD-NNN
├── plan_id                   UUID REFERENCES production_plans(id) NOT NULL
├── machine_id                UUID REFERENCES machines(id) NOT NULL
├── material_batch_id         UUID REFERENCES material_batches(id) NOT NULL
├── operator_id               UUID REFERENCES users(id) NOT NULL
├── strokes                    INTEGER NOT NULL  -- 冲次
├── output_quantity           INTEGER NOT NULL  -- 产出数量 (strokes * cavity_count)
├── qualified_quantity         INTEGER NOT NULL  -- 良品数
├── report_time               TIMESTAMP NOT NULL
├── session_id                VARCHAR(50) NULL  -- 会话ID（连续模）
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: production_sessions  -- 连续模报工会话
├── id                        UUID PRIMARY KEY
├── session_id                VARCHAR(50) UNIQUE NOT NULL
├── plan_id                   UUID REFERENCES production_plans(id) NOT NULL
├── machine_id                UUID REFERENCES machines(id) NOT NULL
├── material_batch_id         UUID REFERENCES material_batches(id) NOT NULL
├── operator_id               UUID REFERENCES users(id) NOT NULL
├── cavity_count              INTEGER NOT NULL
├── started_at                TIMESTAMP NOT NULL
├── ended_at                  TIMESTAMP NULL
├── total_strokes             INTEGER DEFAULT 0
├── total_output              INTEGER DEFAULT 0
├── total_qualified           INTEGER DEFAULT 0
├── status                    VARCHAR(20) NOT NULL  -- active / closed
└── is_deleted                BOOLEAN DEFAULT FALSE
```

### 2.8 Process Flow Card (工艺流转单)

```
Table: process_flow_cards
├── id                        UUID PRIMARY KEY
├── card_number               VARCHAR(30) UNIQUE NOT NULL  -- PFC-YYYYMMDD-NNN
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── production_report_id      UUID REFERENCES production_reports(id) NOT NULL
├── material_batch_id         UUID REFERENCES material_batches(id) NOT NULL  -- 原料批次
├── machine_id                UUID REFERENCES machines(id) NOT NULL
├── operator_id               UUID REFERENCES users(id) NOT NULL
├── shift                      VARCHAR(20) NOT NULL  -- 早班/中班/晚班
├── output_quantity           INTEGER NOT NULL
├── production_time           TIMESTAMP NOT NULL  -- 生产时间
├── qr_code_path              VARCHAR(500) NULL
├── status                    VARCHAR(20) NOT NULL  -- produced / inspected / warehoused
├── warehouse_time            TIMESTAMP NULL
├── warehouse_operator_id     UUID REFERENCES users(id) NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()
```

### 2.9 Warehouse (仓库/原材料)

```
Table: material_batches
├── id                        UUID PRIMARY KEY
├── batch_number              VARCHAR(50) UNIQUE NOT NULL  -- 批次号 MAT-YYYYMMDD-NNN
├── qr_code_path              VARCHAR(500) NULL
├── material_brand            VARCHAR(100) NOT NULL  -- 牌号
├── material_type             VARCHAR(50) NOT NULL  -- 类型
├── supplier_id               UUID REFERENCES suppliers(id) NULL
├── weight                    DECIMAL(10,3) NOT NULL  -- 当前重量 (kg)
├── original_weight           DECIMAL(10,3) NOT NULL  -- 原始重量
├── width                     DECIMAL(8,2) NULL  -- 宽度 (mm)
├── status                    VARCHAR(20) NOT NULL  -- available / in_use / consumed / depleted / scrapped / split
├── parent_batch_id           UUID REFERENCES material_batches(id) NULL  -- 父批次（分条）
├── iqc_status                VARCHAR(20) NOT NULL  -- pending / qualified / unqualified
├── iqc_by                    UUID REFERENCES users(id) NULL
├── iqc_at                    TIMESTAMP NULL
├── is_whse_confirmed         BOOLEAN DEFAULT FALSE
├── confirmed_by              UUID REFERENCES users(id) NULL
├── confirmed_at               TIMESTAMP NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: material_batch_children  -- 子卷（分条后）
├── id                        UUID PRIMARY KEY
├── parent_batch_id           UUID REFERENCES material_batches(id) NOT NULL
├── child_batch_id            UUID REFERENCES material_batches(id) NOT NULL
├── split_width               DECIMAL(8,2) NULL
├── split_weight              DECIMAL(10,3) NOT NULL
├── split_at                  TIMESTAMP DEFAULT NOW()
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: suppliers
├── id                        UUID PRIMARY KEY
├── name                      VARCHAR(200) NOT NULL
├── contact_person            VARCHAR(100) NULL
├── contact_phone             VARCHAR(50) NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
└── created_at                TIMESTAMP DEFAULT NOW()
```

### 2.10 Quality (质量)

```
Table: first_piece_inspections
├── id                        UUID PRIMARY KEY
├── plan_id                   UUID REFERENCES production_plans(id) NOT NULL
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── inspected_by              UUID REFERENCES users(id) NOT NULL
├── inspected_at              TIMESTAMP DEFAULT NOW()
├── result                    VARCHAR(20) NOT NULL  -- passed / failed
├── approved_by               UUID REFERENCES users(id) NULL  -- 组长审批
├── approved_at               TIMESTAMP NULL
├── notes                     TEXT NULL
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: oqc_inspections
├── id                        UUID PRIMARY KEY
├── card_id                   UUID REFERENCES process_flow_cards(id) NOT NULL
├── inspected_by              UUID REFERENCES users(id) NOT NULL
├── inspected_at              TIMESTAMP DEFAULT NOW()
├── qty_inspected             INTEGER NOT NULL  -- 抽检数量
├── qty_passed                INTEGER NOT NULL  -- 合格数量
├── result                    VARCHAR(20) NOT NULL  -- passed / failed
├── notes                     TEXT NULL
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: qa_exemptions  -- 强行特赦
├── id                        UUID PRIMARY KEY
├── card_id                   UUID REFERENCES process_flow_cards(id) NOT NULL
├── exempted_by               UUID REFERENCES users(id) NOT NULL
├── exempted_at               TIMESTAMP DEFAULT NOW()
├── reason                    TEXT NOT NULL
├── exempt_type               VARCHAR(20) NOT NULL  -- first_piece / oqc
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: patrol_inspections  -- 巡检记录
├── id                        UUID PRIMARY KEY
├── machine_id                UUID REFERENCES machines(id) NOT NULL
├── inspected_by              UUID REFERENCES users(id) NOT NULL
├── inspected_at              TIMESTAMP DEFAULT NOW()
├── machine_status            VARCHAR(20) NOT NULL
├── abnormality_description    TEXT NULL
└── is_deleted                BOOLEAN DEFAULT FALSE
```

### 2.11 Packaging (包装)

```
Table: packaging_records
├── id                        UUID PRIMARY KEY
├── card_id                   UUID REFERENCES process_flow_cards(id) NOT NULL
├── packed_quantity           INTEGER NOT NULL
├── packager_id               UUID REFERENCES users(id) NOT NULL
├── packed_at                  TIMESTAMP DEFAULT NOW()
├── status                    VARCHAR(20) NOT NULL  -- wip / inspected
└── is_deleted                BOOLEAN DEFAULT FALSE
```

### 2.12 Coating (喷涂)

```
Table: coating_recipes
├── id                        UUID PRIMARY KEY
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── sand_material             VARCHAR(100) NOT NULL  -- 砂料
├── coating_material          VARCHAR(100) NOT NULL  -- 涂料
├── surface_type              VARCHAR(50) NOT NULL  -- 表面类型
├── version                   INTEGER DEFAULT 1
├── created_by                UUID REFERENCES users(id) NOT NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
└── created_at                TIMESTAMP DEFAULT NOW()

Table: coating_records
├── id                        UUID PRIMARY KEY
├── card_id                   UUID REFERENCES process_flow_cards(id) NOT NULL
├── recipe_id                 UUID REFERENCES coating_recipes(id) NOT NULL
├── coating_quantity          INTEGER NOT NULL
├── qualified_quantity         INTEGER NOT NULL
├── operator_id               UUID REFERENCES users(id) NOT NULL
├── coated_at                  TIMESTAMP DEFAULT NOW()
├── is_deleted                BOOLEAN DEFAULT FALSE
└── created_at                TIMESTAMP DEFAULT NOW()
```

### 2.13 Audit & Logging

```
Table: audit_logs
├── id                        UUID PRIMARY KEY
├── entity_type               VARCHAR(50) NOT NULL  -- quote / part / tooling / machine / etc.
├── entity_id                 UUID NOT NULL
├── action                    VARCHAR(50) NOT NULL  -- create / update / delete / status_change
├── operator_id               UUID REFERENCES users(id) NOT NULL
├── operated_at               TIMESTAMP DEFAULT NOW()
├── changes                    JSONB NULL  -- {"field": {"old": x, "new": y}}
├── notes                     TEXT NULL
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: qr_scan_logs  -- 二维码扫码日志
├── id                        UUID PRIMARY KEY
├── qr_type                   VARCHAR(20) NOT NULL  -- material / machine / process_flow
├── qr_content                VARCHAR(100) NOT NULL
├── operator_id               UUID REFERENCES users(id) NOT NULL
├── operation_type            VARCHAR(30) NOT NULL  -- query / feed_material / report / warehouse
├── scanned_at                TIMESTAMP DEFAULT NOW()
└── is_deleted                BOOLEAN DEFAULT FALSE
```

---

## 3. Indexes

Critical indexes for performance:

```sql
-- 用户查询
CREATE INDEX idx_users_department ON users(department_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_users_active ON users(is_active) WHERE is_deleted = FALSE;
CREATE INDEX idx_users_special_perms ON users USING GIN(special_permissions) WHERE special_permissions IS NOT NULL;

-- 特殊权限字典
CREATE INDEX idx_special_perms_code ON special_permissions_dict(permission_code) WHERE is_active = TRUE;
CREATE INDEX idx_special_perms_dept ON special_permissions_dict(required_department) WHERE required_department IS NOT NULL;

-- 报价单查询
CREATE INDEX idx_quotes_status ON quotes(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_quotes_submitted_by ON quotes(submitted_by);
CREATE INDEX idx_quotes_customer ON quotes(customer_id);

-- 零件查询
CREATE INDEX idx_parts_status ON parts(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_parts_number ON parts(part_number);
CREATE INDEX idx_parts_tooling ON parts(tooling_id) WHERE tooling_id IS NOT NULL;

-- 模具查询
CREATE INDEX idx_toolings_status ON toolings(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_toolings_machine ON toolings(current_machine_id) WHERE current_machine_id IS NOT NULL;

-- 机台查询
CREATE INDEX idx_machines_status ON machines(status) WHERE is_deleted = FALSE;

-- 生产计划
CREATE INDEX idx_plans_status ON production_plans(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_plans_deadline ON production_plans(deadline);

-- 工艺流转单
CREATE INDEX idx_pfc_status ON process_flow_cards(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_pfc_part ON process_flow_cards(part_id);
CREATE INDEX idx_pfc_qr ON process_flow_cards(card_number);

-- 原料批次
CREATE INDEX idx_batches_status ON material_batches(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_batches_supplier ON material_batches(supplier_id);
CREATE INDEX idx_batches_iqc ON material_batches(iqc_status);

-- 审计日志
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_operator ON audit_logs(operator_id);
CREATE INDEX idx_audit_time ON audit_logs(operated_at);

-- 价格档案
CREATE INDEX idx_price_part_customer ON price_accounts(part_id, customer_id) WHERE is_deleted = FALSE;

-- 零件名称字典
CREATE INDEX idx_part_name_dict_primary ON part_name_dict(primary_category) WHERE is_active = TRUE;
CREATE INDEX idx_part_name_dict_secondary ON part_name_dict(secondary_category) WHERE is_active = TRUE AND secondary_category IS NOT NULL;
CREATE INDEX idx_part_name_dict_active ON part_name_dict(is_active);
```

---

## 4. State Transitions

### Quote States

```
等待技术审核 → 技术通过 → 草稿 → 待老板审批 → 已审批(定点)
     ↓            ↓         ↓          ↓
  技术驳回 ← ─────┘    老板驳回 ←───┘
     ↓
 等待技术审核(重新提交)
```

### Part States

```
Draft → Sampling → MassProduction → Obsolete
```

### Machine States

```
idle ↔ running ↔ fault → pending_check → repairing → offline
                  ↑______________|        ↓
                  └───────────────────────┘
```

### Sampling Task States

```
pending_review → pending_production → sampling → pending_review
                    ↓                                    ↓
                cancelled                            passed / failed
```

---

## 6. Data Access Control (数据权限控制)

### 6.1 报价单数据权限隔离

**核心原则**：
- 业务部 + 老板 + 超管：完整查看所有报价单
- 开发部：仅通过"待审核队列"查看，能看模具费和技术参数，不能看其他价格
- 会计部：仅查看已定点报价单，能看总价/模具费/模摊费用，不能看技术参数和其他价格
- 生产相关部门：仅查看已定点报价单，能看技术参数，不能看任何价格

### 6.2 报价单字段权限矩阵

| 字段类型 | 业务部 | 开发部 | 会计部 | 生产部 | 原料仓库 | 品管部 | 喷涂部 | 设备部 | 老板 | 超管 |
|---------|-------|-------|-------|-------|---------|-------|-------|-------|------|------|
| **基础信息** |
| 报价单号、客户名称、零件名称 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 年用量 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **价格字段** |
| 总价 (total_price) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 模具费 (tooling_fee) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 模摊费用 (tooling_amortization_amount) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 模摊数量 (tooling_amortization_quantity) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 冲压费 (stamping_fee) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 表面处理费 (treatment_fee) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **技术参数** |
| T 厚度 (t_parameter) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| W 宽度 (w_parameter) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| P 冲次 (p_parameter) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 穴数 (cavity_count) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 吨位 (press_tonnage) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 材料类型 (material_type) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 模具编号 (tooling_number) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 表面处理类型 (surface_treatment_type) | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 6.3 数据查询范围

| 部门 | 报价单查询范围 | 过滤条件 |
|------|--------------|---------|
| 业务部 | 所有报价单 | 无过滤 |
| 开发部 | 待审核队列 | `status = 'waiting_tech_review'` |
| 会计部 | 仅已定点 | `is_fixed = true` |
| 生产部 | 仅已定点 | `is_fixed = true` |
| 原料仓库 | 仅已定点 | `is_fixed = true` |
| 品管部 | 仅已定点 | `is_fixed = true` |
| 全检部 | 仅已定点 | `is_fixed = true` |
| 喷涂部 | 仅已定点 | `is_fixed = true` |
| 设备部 | 仅已定点 | `is_fixed = true` |
| 人事部 | 不可访问 | - |
| 老板 | 所有报价单 | 无过滤 |
| 超级管理员 | 所有报价单 | 无过滤 |

### 6.4 权限实现方式

**实现层次**：代码层字段过滤（API 响应层）

**核心逻辑**：
1. 查询时根据 `role_level` + `department` 应用过滤条件
2. 响应时根据权限矩阵动态隐藏字段（设置为 `null` 或移除）
3. 开发部通过专用端点 `GET /api/quotes/pending-tech-review` 访问待审核队列

**权限判断示例**：
```python
def can_view_quote(user: User, quote: Quote) -> bool:
    # 老板、超管、业务部：查看所有
    if user.role_level >= 3 or user.department.name == "业务部":
        return True
    
    # 开发部：仅通过待审核队列访问（专用端点）
    if user.department.name == "开发部":
        return quote.status == "waiting_tech_review"
    
    # 会计部、生产相关部门：仅已定点
    if user.department.name in ["会计部", "生产部", "原料仓库", "品管部", "全检部", "喷涂部", "设备部"]:
        return quote.is_fixed == True
    
    # 其他部门：无权限
    return False
```

### 6.5 特殊权限系统

**设计原则**：基础角色（role_level + department）+ 特殊权限（special_permissions）双重验证

**典型场景**：报价技术审核权限
- 基础条件：role_level >= 2（管理人员及业务）且 department = '开发部'
- 特殊权限：拥有 'quote_review' 权限

**权限检查逻辑**：
```python
async def has_special_permission(
    db: AsyncSession,
    user: User,
    permission_code: str
) -> bool:
    """检查用户是否拥有特殊权限"""
    
    # 1. 查询权限定义
    perm_def = await db.execute(
        select(SpecialPermissionsDict).where(
            SpecialPermissionsDict.permission_code == permission_code,
            SpecialPermissionsDict.is_active == True
        )
    )
    perm = perm_def.scalar_one_or_none()
    if not perm:
        return False
    
    # 2. 检查基础条件
    if user.role_level < perm.required_role_level:
        return False
    if perm.required_department and user.department.name != perm.required_department:
        return False
    
    # 3. 检查特殊权限
    if not user.special_permissions:
        return False
    return permission_code in user.special_permissions
```

**初始权限定义**：
```sql
INSERT INTO special_permissions_dict (
    permission_code, 
    permission_name, 
    description, 
    required_role_level, 
    required_department
) VALUES (
    'quote_review',
    '报价技术审核权限',
    '审核报价单技术参数，填写 T/W/P/穴数/吨位/模具费',
    2,
    '开发部'
);
```

**超管授权/撤销 API**：
- `POST /api/admin/users/{user_id}/special-permissions` - 授予特殊权限
- `DELETE /api/admin/users/{user_id}/special-permissions/{permission_code}` - 撤销特殊权限

**授权验证规则**：
1. 用户必须满足权限的基础条件（required_role_level + required_department）
2. 权限代码必须在 special_permissions_dict 中存在且 is_active = true
3. 仅超级管理员（role_level = 4）可以授予/撤销特殊权限

---

## 7. Validation Rules

| Field | Rule |
|-------|------|
| `users.role_level` | 1 ≤ role_level ≤ 4 (1=普通员工, 2=管理人员及业务, 3=老板, 4=超级管理员) |
| `users.special_permissions` | JSONB 数组，每个元素必须是有效的 permission_code（存在于 special_permissions_dict 且 is_active=true） |
| `special_permissions_dict.permission_code` | 唯一且非空，最大 50 字符 |
| `special_permissions_dict.required_role_level` | 1 ≤ value ≤ 4（若设置） |
| `quote_items.t_parameter`, `w_parameter`, `p_parameter` | > 0 |
| `quote_items.tooling_fee_discount` | 0.0 ≤ value ≤ 1.0 |
| `production_reports.strokes` | ≥ 0 |
| `production_reports.qualified_quantity` | ≤ output_quantity |
| `material_batches.weight` | ≥ 0 |
| `price_accounts` | UNIQUE(part_id, customer_id) |
| `part_name_dict.primary_category` | NOT NULL, max 100 chars |
| `part_name_dict` | UNIQUE(primary_category, secondary_category, customer_part_name) |

---

*Data model completed. Ready for `/speckit.tasks`.*
