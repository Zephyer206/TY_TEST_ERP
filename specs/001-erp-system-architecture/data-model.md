# Data Model: Zephyr_test_ERP

**Feature**: 001-erp-system-architecture
**Date**: 2026-06-12
**Last Updated**: 2026-07-07 (数据库设计定稿)

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

**说明**：完整报价单结构包含材料快照、审批流程、定点管理和版本控制。详细设计见 [complete-database-design-summary.md](database-analysis/complete-database-design-summary.md)

```
Table: quotes
├── id                        INTEGER PRIMARY KEY  -- 实际数据库使用 INTEGER
├── quote_serial              VARCHAR(50) NULL  -- 报价单号
├── part_id                   INTEGER NOT NULL  -- 关联零件
├── customer_id               INTEGER NULL  -- 关联客户
├── customer_product_no       VARCHAR(100) NULL  -- 客户产品号
├── vehicle_model             VARCHAR(100) NULL  -- 车型
│
│-- 技术参数（TWP 估算值）
├── thickness                 NUMERIC NULL  -- T 厚度 (mm)
├── width                     NUMERIC NULL  -- W 宽度 (mm)
├── press_stroke              NUMERIC NULL  -- P 步距 (mm)
├── cavity_count              INTEGER NOT NULL DEFAULT 1  -- 穴数
├── gross_weight              NUMERIC NULL  -- 毛重估算
├── scrap_rate                NUMERIC NULL  -- 废料率
│
│-- 材料快照（报价时固化）
├── material_id               INTEGER NULL
├── snapshot_mat_name         VARCHAR(100) NULL
├── snapshot_mat_price        NUMERIC NOT NULL DEFAULT 0  -- 材料单价快照
├── snapshot_scrap_price      NUMERIC NULL  -- 废料价快照
├── snapshot_density          NUMERIC NULL  -- 密度快照
│
│-- 成本与价格
├── material_net_cost         NUMERIC NULL  -- 材料净成本
├── stamping_fee              NUMERIC NOT NULL DEFAULT 0  -- 冲压费
├── surface_fee               NUMERIC NOT NULL DEFAULT 0  -- 表面处理费
├── treatment_fee             NUMERIC NOT NULL DEFAULT 0  -- 其他工序费
├── inspection_fee            NUMERIC NOT NULL DEFAULT 0  -- 检验费
├── packaging_fee             NUMERIC NOT NULL DEFAULT 0  -- 包装费
├── mold_cost                 DECIMAL NOT NULL DEFAULT 0  -- 模具费
├── profit_margin             NUMERIC NOT NULL DEFAULT 0  -- 利润率
├── final_price               NUMERIC NULL  -- 最终单价
│
│-- 表面处理（JSONB）
├── treatment_items           JSONB NULL  -- [{treatment_id, treatment_name, unit_price, calc_mode}, ...]
│
│-- 手动覆盖
├── unit_price_override       NUMERIC NULL
├── material_cost_override    NUMERIC NULL
├── final_price_override      NUMERIC NULL
├── override_fields           JSONB DEFAULT '[]'  -- 记录哪些字段被手动修改
│
│-- 审批流程
├── approval_status           VARCHAR(20) NOT NULL DEFAULT 'DRAFT'  -- DRAFT/PENDING/APPROVED/REJECTED
├── submitted_by              INTEGER NULL
├── submitted_at              TIMESTAMP NULL
├── approved_by               INTEGER NULL
├── approved_at               TIMESTAMP NULL
├── rejection_reason          TEXT NULL
│
│-- 定点管理
├── nomination_status         VARCHAR(20) NULL  -- 定点状态
├── nomination_attachment     VARCHAR(500) NULL  -- 定点附件路径
├── nomination_confirmed_by   INTEGER NULL
├── nomination_confirmed_at   TIMESTAMP NULL
│
│-- 版本管理
├── parent_quote_id           INTEGER NULL  -- 父报价单ID（修改报价时创建新版本）
├── price_snapshot            JSONB NULL  -- 价格快照
│
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: quote_items  -- 暂时保留（待整合到 quotes）
├── id                        UUID PRIMARY KEY
├── quote_id                  UUID REFERENCES quotes(id) NOT NULL
├── part_id                   UUID REFERENCES parts(id) NULL
├── part_name                 VARCHAR(200) NOT NULL
├── customer_part_no          VARCHAR(100) NULL
├── annual_volume             DECIMAL(12,2) NULL
├── t_parameter               DECIMAL(8,3) NULL
├── w_parameter               DECIMAL(8,3) NULL
├── p_parameter               DECIMAL(8,3) NULL
├── cavity_count              INTEGER NULL
├── press_tonnage             DECIMAL(10,2) NULL
├── tooling_fee               DECIMAL(12,2) NULL
├── tooling_fee_mode          VARCHAR(20) NULL
├── tooling_fee_discount      DECIMAL(5,4) DEFAULT 0
├── tooling_amortization_amount   DECIMAL(12,4) NULL
├── tooling_amortization_quantity INTEGER NULL
├── stamping_fee              DECIMAL(12,2) NULL
├── total_price               DECIMAL(14,2) NULL
├── notes                     TEXT NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
└── created_at                TIMESTAMP DEFAULT NOW()

Table: surface_treatments  -- 多道表面处理
├── id                        UUID PRIMARY KEY
├── quote_item_id             UUID REFERENCES quote_items(id) NOT NULL
├── sequence                  INTEGER NOT NULL
├── treatment_name            VARCHAR(100) NOT NULL
├── treatment_fee             DECIMAL(12,2) NOT NULL
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: quote_tech_reviews  -- 技术审核记录
├── id                        UUID PRIMARY KEY
├── quote_id                  UUID REFERENCES quotes(id) NOT NULL
├── reviewed_by               UUID REFERENCES users(id) NOT NULL
├── status                    VARCHAR(20) NOT NULL
├── review_notes              TEXT NULL
├── reviewed_at               TIMESTAMP DEFAULT NOW()
└── is_deleted                BOOLEAN DEFAULT FALSE

Table: customers  -- 客户主表（从 tooling_customers 重命名）
├── id                        INTEGER PRIMARY KEY  -- 实际数据库使用 INTEGER（非 UUID）
├── name                      VARCHAR(200) UNIQUE NOT NULL
├── contact_person            VARCHAR(100) NULL
├── contact_phone             VARCHAR(50) NULL
├── contact_email             VARCHAR(100) NULL
├── address                   TEXT NULL
├── sheet_key                 VARCHAR(100) NULL  -- Google Sheets 关联键
├── is_active                 BOOLEAN DEFAULT TRUE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()
```

### 2.3 Part (零件)

**说明**：零件表包含 TWP（Thickness/Width/Pitch）技术参数，由技术部门维护。详细设计见 [part-entity-parts-table-final.md](database-analysis/part-entity-parts-table-final.md)

```
Table: parts
├── id                        UUID PRIMARY KEY
├── part_number               VARCHAR(50) UNIQUE NOT NULL
├── part_name                 VARCHAR(200) NOT NULL
├── status                    VARCHAR(30) NOT NULL  -- draft / sampling / mass_production / obsolete
│
│-- 技术参数（TWP - 最精确值，技术部门维护）
├── thickness                 DECIMAL(8,3) NULL  -- T 厚度 (mm)
├── width                     DECIMAL(8,3) NULL  -- W 宽度 (mm)
├── pitch                     DECIMAL(8,3) NULL  -- P 步距 (mm)，单个零件所需材料长度
│
│-- 材料和吨位
├── material_id               INTEGER REFERENCES material_dict(id) NULL
├── press_tonnage_id          INTEGER REFERENCES machine_tonnage_dict(id) NULL
│
│-- 模具关联
├── tooling_id                UUID REFERENCES tooling(id) NULL
├── cavity_position           INTEGER NULL  -- 穴位（一模多腔时标识左右件）
│
│-- 零件属性
├── ppap_number               VARCHAR(50) NULL
├── vehicle_model             VARCHAR(100) NULL
├── net_weight                DECIMAL(10,3) NULL  -- 净重 (kg)
├── gross_weight              DECIMAL(10,3) NULL  -- 毛重 (kg)
├── weight_source             VARCHAR(20) NULL  -- 重量来源标识
├── drawing_path              VARCHAR(500) NULL
├── sdr_drawing_path          VARCHAR(500) NULL
├── ppap_path                 VARCHAR(500) NULL
├── surface_treatment_type    VARCHAR(100) NULL
│
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: part_name_dict  -- 零件名称字典（三级分类系统）
├── id                        INTEGER PRIMARY KEY AUTOINCREMENT
├── primary_category          VARCHAR(100) NOT NULL  -- 一级分类（必填）
├── secondary_category        VARCHAR(100) NULL  -- 二级分类（可选）
├── customer_part_name        VARCHAR(200) NULL  -- 三级分类（可选）
├── remark                    TEXT NULL
├── name                      VARCHAR(200) NULL  -- [已废弃]
├── category                  VARCHAR(100) NULL  -- [已废弃]
├── usage_count               INTEGER DEFAULT 0
├── is_active                 BOOLEAN DEFAULT TRUE
├── sort_order                INTEGER DEFAULT 0
├── created_at                TIMESTAMP DEFAULT NOW()
├── updated_at                TIMESTAMP DEFAULT NOW()
└── created_by                INTEGER NULL REFERENCES users(id)

Table: part_customer_aliases  -- 客户件号映射（一卖多支持）
├── id                        UUID PRIMARY KEY
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── customer_id               INTEGER REFERENCES customers(id) NOT NULL
├── customer_part_no          VARCHAR(100) NOT NULL
├── is_primary                BOOLEAN DEFAULT FALSE  -- 是否主客户（动态计算）
├── price_account_id          UUID REFERENCES price_accounts(id) NULL
├── created_at                TIMESTAMP DEFAULT NOW()
└── UNIQUE(part_id, customer_id)

Table: price_accounts  -- 零件价格台账
├── id                        UUID PRIMARY KEY
├── part_id                   UUID REFERENCES parts(id) NOT NULL
├── customer_id               INTEGER REFERENCES customers(id) NOT NULL
├── is_active                 BOOLEAN DEFAULT TRUE
│
│-- 重量：估算值 vs 实测值
├── estimated_net_weight_kg   DECIMAL(10,3) NULL  -- 报价阶段估算重量
├── actual_net_weight_kg      DECIMAL(10,3) NULL  -- 首件检验实测重量
│
│-- 价格构成
├── base_price                DECIMAL(14,4) NULL  -- 基准单价
├── current_price             DECIMAL(14,4) NULL  -- 当前执行价（手动调整）
├── material_unit_price       DECIMAL(14,4) NULL  -- 材料单价
├── scrap_price               DECIMAL(14,4) NULL  -- 废料价
│
│-- 年降参考
├── reduction_pct             DECIMAL(5,2) NULL  -- 年降百分比
├── price_year                INTEGER NULL  -- 价格年份
│
│-- 成本偏离标记
├── cost_deviation_flag       BOOLEAN DEFAULT FALSE  -- 实测重量偏离>5%时自动标记
│
├── price_snapshot            JSONB NULL  -- 定点快照
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
├── updated_at                TIMESTAMP DEFAULT NOW()
└── CONSTRAINT uq_price_part_customer UNIQUE(part_id, customer_id)

Table: annual_price_records  -- 年降价格记录
├── id                        UUID PRIMARY KEY
├── price_account_id          UUID REFERENCES price_accounts(id) NOT NULL
├── year                      INTEGER NOT NULL
├── unit_price                DECIMAL(14,4) NOT NULL
├── annual_volume             DECIMAL(12,2) NULL
├── created_by                UUID REFERENCES users(id) NOT NULL
├── created_at                TIMESTAMP DEFAULT NOW()
└── UNIQUE(price_account_id, year)

Table: price_adjustments  -- 手动调价记录（老板审批）
├── id                        UUID PRIMARY KEY
├── price_account_id          UUID REFERENCES price_accounts(id) NOT NULL
├── old_price                 DECIMAL(14,4) NOT NULL
├── new_price                 DECIMAL(14,4) NOT NULL
├── adjustment_reason         TEXT NOT NULL
├── approval_status           VARCHAR(20) NOT NULL DEFAULT 'pending'  -- pending/approved/rejected
├── adjusted_by               UUID REFERENCES users(id) NOT NULL
├── adjusted_at               TIMESTAMP DEFAULT NOW()
├── approved_by               UUID REFERENCES users(id) NULL
├── approved_at               TIMESTAMP NULL
└── is_deleted                BOOLEAN DEFAULT FALSE
```

### 2.3.1 Material & Treatment (材料和工序)

**说明**：材料和工序字典表 + 客户特定价格历史。详细设计见 [material-treatment-price-history-final.md](database-analysis/material-treatment-price-history-final.md)

```
Table: material_dict  -- 材料字典（全局标准价格）
├── id                        SERIAL PRIMARY KEY
├── code                      VARCHAR(50) UNIQUE NOT NULL
├── name                      VARCHAR(100) NOT NULL
├── density                   DECIMAL(10,3) NOT NULL  -- 密度 (g/cm³)
├── default_price             DECIMAL(10,4) NULL  -- 标准材料单价 (元/kg)，兜底值
├── scrap_price               DECIMAL(10,4) NULL  -- 标准废料价格 (元/kg)
├── category                  VARCHAR(50) NULL
├── is_active                 BOOLEAN DEFAULT TRUE
└── created_at                TIMESTAMP DEFAULT NOW()

Table: treatment_dict  -- 工序字典（全局标准费率）
├── id                        SERIAL PRIMARY KEY
├── name                      VARCHAR(100) UNIQUE NOT NULL  -- 工序名称
├── calc_mode                 VARCHAR(20) NOT NULL DEFAULT 'manual'  -- manual(按件) / net_weight(按重量)
├── default_rate              DECIMAL(10,4) NOT NULL DEFAULT 0  -- 默认费率，兜底值
├── unit                      VARCHAR(20) NOT NULL DEFAULT '元/件'  -- 元/件 或 元/kg
├── is_active                 BOOLEAN DEFAULT TRUE
├── sort_order                INTEGER DEFAULT 0
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: machine_tonnage_dict  -- 机床吨位字典（固定规格）
├── id                        SERIAL PRIMARY KEY
├── tonnage                   VARCHAR(50) UNIQUE NOT NULL  -- 60吨/110吨/160吨/200吨/200吨双轴/250吨/400吨
├── tonnage_value             INTEGER NOT NULL
├── description               VARCHAR(200) NULL
├── is_active                 BOOLEAN DEFAULT TRUE
└── sort_order                INTEGER DEFAULT 0

Table: customer_material_prices  -- 客户材料价格历史
├── id                        UUID PRIMARY KEY DEFAULT gen_random_uuid()
├── customer_id               INTEGER REFERENCES customers(id) NOT NULL
├── material_id               INTEGER REFERENCES material_dict(id) NOT NULL
├── unit_price                DECIMAL(10,4) NOT NULL  -- 该客户该材质的成交单价 (元/kg)
├── scrap_price               DECIMAL(10,4) NULL  -- 该客户该材质的废料回收价
├── quote_id                  INTEGER REFERENCES quotes(id) NULL  -- 关联报价单，可追溯
├── quoted_at                 TIMESTAMP DEFAULT NOW()
├── created_by                UUID REFERENCES users(id) NULL
└── created_at                TIMESTAMP DEFAULT NOW()
-- 保留全部历史记录，查询时取最近3次

Table: customer_treatment_prices  -- 客户工序价格历史
├── id                        UUID PRIMARY KEY DEFAULT gen_random_uuid()
├── customer_id               INTEGER REFERENCES customers(id) NOT NULL
├── treatment_id              INTEGER REFERENCES treatment_dict(id) NOT NULL
├── unit_price                DECIMAL(10,4) NOT NULL  -- 该客户该工序的成交价
├── calc_mode_snapshot        VARCHAR(20) NULL  -- 快照当时计价方式
├── unit_snapshot             VARCHAR(20) NULL  -- 快照当时单位
├── quote_id                  INTEGER REFERENCES quotes(id) NULL
├── quoted_at                 TIMESTAMP DEFAULT NOW()
├── created_by                UUID REFERENCES users(id) NULL
└── created_at                TIMESTAMP DEFAULT NOW()
-- 保留全部历史记录，查询时取最近3次
```

### 2.4 Tooling (模具)

**说明**：模具资产管理，记录归属客户（用于审厂合规）。详细设计见 [customer-entity-group-final.md](database-analysis/customer-entity-group-final.md)

```
Table: tooling
├── id                        UUID PRIMARY KEY
├── tooling_number            VARCHAR(50) UNIQUE NOT NULL
├── name                      VARCHAR(200) NOT NULL
├── status                    VARCHAR(30) NOT NULL  -- available / in_use / maintenance / converted / scrapped
├── total_cavity_count        INTEGER NOT NULL DEFAULT 1
│
│-- 归属（客户审厂合规）
├── owner_customer_id         INTEGER REFERENCES customers(id) NULL  -- NULL = 公司自有模具
│
│-- 资产信息
├── tooling_cost              DECIMAL(14,2) NULL
├── supplier                  VARCHAR(200) NULL
├── purchase_date             DATE NULL
│
│-- 寿命管理
├── shot_count                INTEGER DEFAULT 0  -- 累计冲次
├── max_shot_count            INTEGER NULL  -- 设计寿命
├── last_maintenance_date     DATE NULL
├── maintenance_cycle_days    INTEGER NULL
│
├── current_machine_id        UUID REFERENCES machines(id) NULL
├── created_by                UUID REFERENCES users(id) NOT NULL
├── is_deleted                BOOLEAN DEFAULT FALSE
├── created_at                TIMESTAMP DEFAULT NOW()
└── updated_at                TIMESTAMP DEFAULT NOW()

Table: tooling_parts  -- 模具-零件关联（多对多）
├── id                        UUID PRIMARY KEY
├── tooling_id                UUID REFERENCES tooling(id) NOT NULL
├── part_id                   UUID REFERENCES parts(id) NOT NULL
└── UNIQUE(tooling_id, part_id)

Table: tooling_maintenance_logs
├── id                        UUID PRIMARY KEY
├── tooling_id                UUID REFERENCES tooling(id) NOT NULL
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
CREATE INDEX idx_quotes_approval_status ON quotes(approval_status) WHERE is_deleted = FALSE;
CREATE INDEX idx_quotes_submitted_by ON quotes(submitted_by);
CREATE INDEX idx_quotes_customer ON quotes(customer_id);

-- 零件查询
CREATE INDEX idx_parts_status ON parts(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_parts_number ON parts(part_number);
CREATE INDEX idx_parts_tooling ON parts(tooling_id) WHERE tooling_id IS NOT NULL;
CREATE INDEX idx_parts_material ON parts(material_id) WHERE material_id IS NOT NULL;

-- 零件别名（一卖多）
CREATE INDEX idx_part_aliases_part ON part_customer_aliases(part_id);
CREATE INDEX idx_part_aliases_customer ON part_customer_aliases(customer_id);

-- 模具查询
CREATE INDEX idx_tooling_status ON tooling(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_tooling_machine ON tooling(current_machine_id) WHERE current_machine_id IS NOT NULL;
CREATE INDEX idx_tooling_owner ON tooling(owner_customer_id) WHERE owner_customer_id IS NOT NULL;

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

-- 客户材料价格历史
CREATE INDEX idx_cmp_customer_material ON customer_material_prices(customer_id, material_id, quoted_at DESC);
CREATE INDEX idx_cmp_quote ON customer_material_prices(quote_id) WHERE quote_id IS NOT NULL;

-- 客户工序价格历史
CREATE INDEX idx_ctp_customer_treatment ON customer_treatment_prices(customer_id, treatment_id, quoted_at DESC);
CREATE INDEX idx_ctp_quote ON customer_treatment_prices(quote_id) WHERE quote_id IS NOT NULL;

-- 零件名称字典
CREATE INDEX idx_part_name_dict_primary ON part_name_dict(primary_category) WHERE is_active = TRUE;
CREATE INDEX idx_part_name_dict_secondary ON part_name_dict(secondary_category) WHERE is_active = TRUE AND secondary_category IS NOT NULL;
CREATE INDEX idx_part_name_dict_active ON part_name_dict(is_active);

-- 材料字典
CREATE INDEX idx_material_dict_active ON material_dict(is_active);
CREATE INDEX idx_material_dict_code ON material_dict(code);

-- 工序字典
CREATE INDEX idx_treatment_dict_active ON treatment_dict(is_active);
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

## 7. Validation Rules

| Field | Rule |
|-------|------|
| `users.role_level` | 1 ≤ role_level ≤ 4 (1=普通员工, 2=管理人员及业务, 3=老板, 4=超级管理员) |
| `users.special_permissions` | JSONB 数组，每个元素必须是有效的 permission_code（存在于 special_permissions_dict 且 is_active=true） |
| `special_permissions_dict.permission_code` | 唯一且非空，最大 50 字符 |
| `special_permissions_dict.required_role_level` | 1 ≤ value ≤ 4（若设置） |
| `parts.thickness`, `width`, `pitch` | > 0（TWP 参数） |
| `quotes.thickness`, `width`, `press_stroke` | > 0（报价时 TWP 估算） |
| `production_reports.strokes` | ≥ 0 |
| `production_reports.qualified_quantity` | ≤ output_quantity |
| `material_batches.weight` | ≥ 0 |
| `price_accounts` | UNIQUE(part_id, customer_id) |
| `part_customer_aliases` | UNIQUE(part_id, customer_id) |
| `part_name_dict.primary_category` | NOT NULL, max 100 chars |
| `material_dict.density` | > 0 (g/cm³) |
| `customer_material_prices.unit_price` | > 0 (元/kg) |
| `customer_treatment_prices.unit_price` | > 0 |
| `machine_tonnage_dict.tonnage_value` | > 0 |

---

## 8. Business Rules & Data Flow

### 8.1 材料成本计算公式

```
单件材料成本 = [T(mm) × W(mm) × P(mm) × 密度(g/cm³) × (材料单价 - 废料价格)(元/kg)] / (10^6 × 穴数)

取值优先级：
- TWP: parts 表（最精确）
- 密度: material_dict.density
- 材料单价: customer_material_prices（最近1次）或 material_dict.default_price
- 废料价格: customer_material_prices.scrap_price 或 material_dict.scrap_price
```

### 8.2 数据流转流程

```
① 报价阶段
   quotes: 填写估算 TWP (T/W/P)
   快照材料价格（snapshot_mat_price, snapshot_density）
   → 计算 material_net_cost
   → 老板审批（DRAFT → PENDING → APPROVED）

② 定点阶段
   quotes.nomination_status = confirmed
   → 创建/更新 parts: 从 quotes 拷贝 TWP（初始值）
   → 创建 price_accounts: estimated_net_weight
   → 写入 customer_material_prices: 本次成交价
   → 写入 customer_treatment_prices: 本次工序价

③ 开模阶段
   创建 tooling: 模具基本信息, owner_customer_id
   → 更新 parts.tooling_id: 关联零件到模具

④ 技术维护阶段
   更新 parts.TWP: 根据实际模具调整（最精确值）
   → 重新计算 net_weight

⑤ 首件检验阶段
   更新 price_accounts.actual_net_weight: 实测重量
   → 自动检测成本偏离（>5% 标记 cost_deviation_flag）

⑥ 调价流程
   创建 price_adjustments: pending_approval
   → 老板审批 → approved
   → 更新 price_accounts.current_price
```

### 8.3 特殊业务场景

**一卖多（一个零件卖给多个客户）**：
- parts 表：1条记录
- part_customer_aliases：N条记录（每个客户一条）
- price_accounts：N条记录（每个客户独立价格）

**一模多腔（一个模具生产多个零件）**：
- tooling 表：1条记录，total_cavity_count=N
- parts 表：N条记录，每个 parts.tooling_id 指向同一个 tooling
- 每个 part 有独立的 cavity_position 标识穴位

**跨客户使用（客户A的模具为客户B生产）**：
- tooling.owner_customer_id = 客户A（归属）
- production_plans.customer_id = 客户B（实际生产）
- 合规检查视图标记跨客户使用场景

---

## 9. Key Design Decisions

### 9.1 主键类型策略

| 表类型 | 主键类型 | 说明 |
|-------|---------|------|
| 字典表 | INTEGER/SERIAL | material_dict, treatment_dict, machine_tonnage_dict |
| 客户表 | INTEGER | customers（实际数据库，从 tooling_customers 重命名） |
| 报价表 | INTEGER | quotes（实际数据库） |
| 业务主表 | UUID | parts, tooling, users, production_plans 等 |

**建议**：短期保持现状兼容现有代码，长期可迁移到 UUID 以支持分布式扩展。

### 9.2 TWP 参数位置

**决策**：TWP（Thickness/Width/Pitch）存储在 parts 表，不存在 tooling 表。

**理由**：
- 零件的固有属性，技术部门维护最精确值
- 一模多腔时左右件的 TWP 可能不同
- parts.tooling_id 反向关联到模具

**数据流**：quotes 估算 → parts 初始值 → 技术部门维护 → 最精确值

### 9.3 价格体系分层

**全局字典表**（兜底参考价）：
- material_dict.default_price
- treatment_dict.default_rate

**客户特定历史价**（优先使用）：
- customer_material_prices（按客户+材质记录，保留全部历史，查询最近3次）
- customer_treatment_prices（按客户+工序记录，保留全部历史，查询最近3次）

**零件定案价**（最终生效价）：
- price_accounts.current_price（手动调整，非自动年降）

### 9.4 表命名规范更新

| 旧表名 | 新表名 | 状态 |
|-------|-------|------|
| `tooling_customers` | `customers` | ✅ 重命名 |
| `toolings` | `tooling` | 建议统一为单数形式 |
| `material_base_prices` | - | ⛔ 废弃，迁移到 material_dict |
| `treatment_dicts` | `treatment_dict` | ⛔ 废弃，清理后重建 |

---

## 10. Reference Documentation

完整的数据库设计文档位于 `specs/001-erp-system-architecture/database-analysis/`：

- **[complete-database-design-summary.md](database-analysis/complete-database-design-summary.md)** — 15张核心表完整设计总结
- **[customer-entity-group-final.md](database-analysis/customer-entity-group-final.md)** — Customer 实体组完整设计
- **[part-entity-parts-table-final.md](database-analysis/part-entity-parts-table-final.md)** — parts / part_name_dict
- **[part-entity-aliases-table-final.md](database-analysis/part-entity-aliases-table-final.md)** — part_customer_aliases
- **[part-entity-price-tables-final.md](database-analysis/part-entity-price-tables-final.md)** — price_accounts / price_adjustments
- **[material-treatment-price-history-final.md](database-analysis/material-treatment-price-history-final.md)** — 材料/工序字典和价格历史

---

*Data model updated with database design finalized on 2026-07-07. Ready for implementation.*
