# Current Database Schema

**Generated**: 2026-07-07 20:21:13
**Database**: PostgreSQL (stamping_system)
**Total Tables**: 90

---

## Overview

This document describes the ACTUAL database schema currently deployed in the cloud PostgreSQL instance.


## User & Auth


### Table: `users`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('users_id_seq'::regclass) |
| username | VARCHAR(50) | ✗ | - |
| password | VARCHAR(100) | ✗ | - |
| real_name | VARCHAR(50) | ✓ | - |
| dept | VARCHAR(20) | ✗ | 'prod'::character varying |
| role_level | INTEGER | ✓ | 1 |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| position | VARCHAR(50) | ✓ | '员工'::character varying |
| is_tech | BOOLEAN | ✗ | false |
| is_superadmin | BOOLEAN | ✓ | false |

**Indexes**:

- `users_username_key` (UNIQUE)

---

## Quote


### Table: `part_customer_alias`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('part_customer_alias_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| customer_id | INTEGER | ✗ | - |
| shipping_part_no | VARCHAR(100) | ✗ | - |
| remark | VARCHAR(500) | ✓ | ''::character varying |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| created_by | INTEGER | ✓ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |

**Foreign Keys**:

- `part_id` → `parts.id`
- `customer_id` → `tooling_customers.id`
- `created_by` → `users.id`

**Indexes**:

- `part_customer_alias_part_id_customer_id_key` (UNIQUE)
- `idx_alias_part`
- `idx_alias_customer`
- `idx_alias_part_customer` (UNIQUE)

---

### Table: `part_customer_aliases`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('part_customer_aliases_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| customer_name | VARCHAR(150) | ✗ | - |
| customer_part_no | VARCHAR(100) | ✗ | - |
| customer_part_name | VARCHAR(150) | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `uq_part_customer` (UNIQUE)
- `idx_pca_customer`
- `idx_pca_part`

---

### Table: `quotes`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('quotes_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| quote_serial | VARCHAR(50) | ✓ | - |
| annual_usage | INTEGER | ✗ | 0 |
| pricing_mode | VARCHAR(20) | ✗ | 'independent'::character varying |
| thickness | NUMERIC | ✓ | - |
| width | NUMERIC | ✓ | - |
| press_stroke | NUMERIC | ✓ | - |
| cavity_count | INTEGER | ✗ | 1 |
| scrap_rate | NUMERIC | ✗ | 0.1000 |
| gross_weight | NUMERIC | ✓ | - |
| snapshot_mat_price | NUMERIC | ✗ | 0 |
| snapshot_mat_name | VARCHAR(100) | ✓ | - |
| snapshot_density | NUMERIC | ✓ | - |
| snapshot_scrap_price | NUMERIC | ✓ | - |
| material_net_cost | NUMERIC | ✓ | - |
| stamping_fee | NUMERIC | ✗ | 0 |
| surface_fee | NUMERIC | ✗ | 0 |
| treatment_fee | NUMERIC | ✗ | 0 |
| profit_margin | NUMERIC | ✗ | 0 |
| final_price | NUMERIC | ✓ | - |
| unit_price_override | NUMERIC | ✓ | - |
| material_cost_override | NUMERIC | ✓ | - |
| final_price_override | NUMERIC | ✓ | - |
| override_fields | JSONB | ✓ | '[]'::jsonb |
| approval_status | VARCHAR(20) | ✗ | 'DRAFT'::character varying |
| rejection_reason | TEXT | ✓ | - |
| parent_quote_id | INTEGER | ✓ | - |
| submitted_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| submitted_by | INTEGER | ✓ | - |
| approved_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| approved_by | INTEGER | ✓ | - |
| nomination_status | VARCHAR(20) | ✓ | - |
| nomination_attachment | TEXT | ✓ | - |
| price_snapshot | JSONB | ✓ | - |
| nomination_confirmed_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| nomination_confirmed_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| mold_cost | NUMERIC | ✗ | 0.00 |
| machine_type | VARCHAR(50) | ✓ | - |
| is_deleted | BOOLEAN | ✗ | false |
| die_id | INTEGER | ✓ | - |
| customer_id | INTEGER | ✓ | - |
| customer_product_no | VARCHAR(100) | ✓ | - |
| vehicle_model | VARCHAR(100) | ✓ | - |
| inspection_fee | NUMERIC | ✓ | 0 |
| packaging_fee | NUMERIC | ✓ | 0 |
| sdr_drawing_path | VARCHAR(500) | ✓ | - |
| press_tonnage | INTEGER | ✓ | - |
| material_utilization | NUMERIC | ✓ | - |
| mold_life | INTEGER | ✓ | - |
| mold_type | VARCHAR(50) | ✓ | - |
| annual_avg | NUMERIC | ✓ | - |
| lifecycle_years | NUMERIC | ✓ | - |
| treatment_items | JSONB | ✓ | - |
| mold_discount_mode | VARCHAR(32) | ✓ | 'direct'::character varying |
| mold_discount_rate | NUMERIC | ✓ | 1.0 |
| material_id | INTEGER | ✓ | - |
| machine_tonnage_id | INTEGER | ✓ | - |
| mold_type_id | INTEGER | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `parent_quote_id` → `quotes.id`
- `submitted_by` → `users.id`
- `approved_by` → `users.id`
- `nomination_confirmed_by` → `users.id`
- `die_id` → `dies.id`
- `material_id` → `material_dict.id`
- `machine_tonnage_id` → `machine_tonnage_dict.id`
- `mold_type_id` → `mold_type_dict.id`

**Indexes**:

- `quotes_quote_serial_key` (UNIQUE)
- `idx_quotes_part_id`
- `idx_quotes_approval_status`
- `idx_quotes_parent`
- `idx_quotes_die_id`
- `idx_quotes_customer_id`
- `idx_quotes_material_id`
- `idx_quotes_machine_tonnage_id`
- `idx_quotes_mold_type_id`

---

### Table: `tooling_customers`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('tooling_customers_id_seq'::regclass) |
| name | VARCHAR(200) | ✗ | - |
| sheet_key | VARCHAR(50) | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |

**Indexes**:

- `tooling_customers_name_key` (UNIQUE)
- `tooling_customers_sheet_key_key` (UNIQUE)

---

## Part


### Table: `die_parts`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('die_parts_id_seq'::regclass) |
| die_id | INTEGER | ✓ | - |
| part_id | INTEGER | ✓ | - |
| product_number | VARCHAR(64) | ✓ | - |
| seq_order | INTEGER | ✓ | 0 |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `mold_parts_mold_id_part_id_key` (UNIQUE)
- `idx_die_parts_die_id`
- `idx_die_parts_part_id`

---

### Table: `part_aliases`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('part_aliases_id_seq'::regclass) |
| internal_part_id | INTEGER | ✗ | - |
| customer_id | INTEGER | ✗ | - |
| alias_part_number | VARCHAR(100) | ✗ | - |
| alias_name | VARCHAR(200) | ✓ | - |
| is_active | BOOLEAN | ✗ | true |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `internal_part_id` → `parts.id`
- `customer_id` → `tooling_customers.id`

**Indexes**:

- `uq_part_alias_part_customer` (UNIQUE)
- `uq_alias_part_number` (UNIQUE)
- `idx_part_alias_internal_part`
- `idx_part_alias_customer`

---

### Table: `part_cost_snapshot`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('part_cost_snapshot_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| material_name | VARCHAR(100) | ✓ | - |
| material_unit_price | NUMERIC | ✓ | - |
| material_cost_per_pc | NUMERIC | ✓ | - |
| treatment_snapshot | JSONB | ✓ | - |
| gross_weight_g | NUMERIC | ✓ | - |
| last_adjusted_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Indexes**:

- `part_cost_snapshot_part_id_key` (UNIQUE)

---

### Table: `parts`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('parts_id_seq'::regclass) |
| part_number | VARCHAR(50) | ✗ | - |
| internal_name | VARCHAR(100) | ✓ | - |
| drawing_url | TEXT | ✓ | - |
| spec_info | TEXT | ✓ | - |
| status | VARCHAR(20) | ✓ | '待开发'::character varying |
| is_urgent | BOOLEAN | ✓ | false |
| target_count | INTEGER | ✓ | 0 |
| spray_status | VARCHAR(30) | ✗ | 'pending'::character varying |
| spray_stamped_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| material_name | VARCHAR(100) | ✓ | - |
| nomination_status | VARCHAR(20) | ✓ | - |
| nomination_attachment | TEXT | ✓ | - |
| price_snapshot | JSON | ✓ | - |
| nomination_confirmed_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| nomination_confirmed_by | INTEGER | ✓ | - |
| customer_id | INTEGER | ✓ | - |
| sample_judgment_status | VARCHAR(30) | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| version | VARCHAR(20) | ✗ | 'V1.0'::character varying |
| part_status | VARCHAR(20) | ✗ | 'DRAFT'::character varying |
| stock_pcs | INTEGER | ✗ | 0 |
| remark | VARCHAR(200) | ✓ | ''::character varying |
| mold_number | VARCHAR(50) | ✓ | - |
| mold_type | VARCHAR(30) | ✓ | - |
| press_tonnage | VARCHAR(30) | ✓ | - |
| ppap_no | VARCHAR(50) | ✓ | - |
| customer_product_no | VARCHAR(100) | ✓ | - |
| vehicle_model | VARCHAR(100) | ✓ | - |
| part_name_id | INTEGER | ✓ | - |
| material_id | INTEGER | ✓ | - |
| machine_tonnage_id | INTEGER | ✓ | - |
| mold_type_id | INTEGER | ✓ | - |

**Foreign Keys**:

- `customer_id` → `tooling_customers.id`
- `part_name_id` → `part_name_dict.id`
- `material_id` → `material_dict.id`
- `machine_tonnage_id` → `machine_tonnage_dict.id`
- `mold_type_id` → `mold_type_dict.id`

**Indexes**:

- `uq_parts_remark` (UNIQUE)
- `idx_parts_part_name_id`
- `idx_parts_material_id`
- `idx_parts_machine_tonnage_id`
- `idx_parts_mold_type_id`

---

### Table: `tooling_parts`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('tooling_parts_id_seq'::regclass) |
| mold_id | INTEGER | ✓ | - |
| customer_product_no | VARCHAR(100) | ✓ | - |
| customer_product_name | VARCHAR(200) | ✓ | - |
| gross_weight_g | NUMERIC | ✓ | - |
| net_weight_g | NUMERIC | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |

**Foreign Keys**:

- `mold_id` → `tooling_molds.id`

---

## Tooling/Die


### Table: `dies`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('dies_id_seq'::regclass) |
| mold_number | VARCHAR(100) | ✗ | - |
| part_id | INTEGER | ✓ | - |
| mold_name | VARCHAR(200) | ✓ | - |
| mold_type | VARCHAR(50) | ✓ | - |
| cavity_count | INTEGER | ✗ | 1 |
| lifecycle_status | VARCHAR(20) | ✗ | 'AVAILABLE'::character varying |
| converted_to_mold_id | INTEGER | ✓ | - |
| current_location | VARCHAR(100) | ✓ | - |
| lifespan_strokes | BIGINT | ✓ | - |
| current_strokes | BIGINT | ✓ | 0 |
| supplier | VARCHAR(200) | ✓ | - |
| purchase_date | DATE | ✓ | - |
| remarks | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| mold_set_count | INTEGER | ✓ | 1 |
| press_tonnage | VARCHAR(50) | ✓ | - |
| current_equipment_id | INTEGER | ✓ | - |
| thickness_mm | NUMERIC | ✓ | NULL::numeric |
| width_mm | NUMERIC | ✓ | NULL::numeric |
| pitch_mm | NUMERIC | ✓ | NULL::numeric |
| die_type | VARCHAR(30) | ✗ | 'progressive'::character varying |

**Foreign Keys**:

- `part_id` → `parts.id`
- `converted_to_mold_id` → `dies.id`
- `current_equipment_id` → `equipments.id`

**Indexes**:

- `molds_mold_number_key` (UNIQUE)
- `idx_molds_status`
- `idx_molds_part_id`

---

### Table: `mold_offline_records`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('mold_offline_records_id_seq'::regclass) |
| machine_id | INTEGER | ✗ | - |
| mold_number | VARCHAR(100) | ✓ | - |
| mold_name | VARCHAR(200) | ✓ | - |
| fault_reason | TEXT | ✓ | - |
| offline_time | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| maintenance_status | VARCHAR(50) | ✗ | 'waiting_parts'::character varying |
| status_updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| status_updated_by | INTEGER | ✓ | - |
| assigned_tech_id | INTEGER | ✓ | - |
| remark | TEXT | ✓ | - |
| completed_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| repair_start_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| repair_end_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| current_part_number | VARCHAR(100) | ✓ | - |
| current_part_name | VARCHAR(200) | ✓ | - |

**Indexes**:

- `idx_offline_records_status`
- `idx_offline_records_machine`
- `idx_offline_records_offline_time`
- `idx_offline_mold_number_trgm`
- `idx_offline_mold_name_trgm`

---

### Table: `mold_type_dict`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('mold_type_dict_id_seq'::regclass) |
| code | VARCHAR(50) | ✗ | - |
| name | VARCHAR(100) | ✗ | - |
| name_en | VARCHAR(100) | ✓ | - |
| description | TEXT | ✓ | - |
| typical_lifecycle | INTEGER | ✓ | - |
| complexity_level | VARCHAR(50) | ✓ | - |
| typical_tonnage_range | VARCHAR(100) | ✓ | - |
| is_active | BOOLEAN | ✗ | - |
| sort_order | INTEGER | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |

**Indexes**:

- `mold_type_dict_code_key` (UNIQUE)
- `idx_mold_type_dict_code`

---

### Table: `mold_types`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('mold_types_id_seq'::regclass) |
| code | VARCHAR(50) | ✗ | - |
| name | VARCHAR(100) | ✗ | - |
| sort_order | INTEGER | ✓ | 0 |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |

**Indexes**:

- `mold_types_code_key` (UNIQUE)

---

### Table: `tooling_maintenance_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('tooling_maintenance_logs_id_seq'::regclass) |
| tooling_id | INTEGER | ✗ | - |
| machine_id | INTEGER | ✓ | - |
| fault_time | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| fault_reason | TEXT | ✓ | - |
| repair_plan | TEXT | ✓ | - |
| repair_start_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| repair_end_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| repair_completed_by | INTEGER | ✓ | - |
| is_active | BOOLEAN | ✗ | - |
| notes | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `tooling_id` → `tooling_molds.id`

**Indexes**:

- `ix_tooling_maintenance_logs_tooling_id`
- `ix_tooling_maintenance_logs_machine_id`

---

### Table: `tooling_molds`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('tooling_molds_id_seq'::regclass) |
| customer_id | INTEGER | ✓ | - |
| mold_number | VARCHAR(100) | ✗ | - |
| customer_product_no | VARCHAR(100) | ✓ | - |
| customer_product_name | VARCHAR(200) | ✓ | - |
| mold_type | VARCHAR(100) | ✓ | - |
| cavity_count | VARCHAR(20) | ✓ | - |
| material | VARCHAR(100) | ✓ | - |
| spec_twph | VARCHAR(100) | ✓ | - |
| press_tonnage | VARCHAR(50) | ✓ | - |
| remark | TEXT | ✓ | - |
| ppap_no | VARCHAR(100) | ✓ | - |
| vehicle_model | VARCHAR(100) | ✓ | - |
| seq | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| cavity_status | VARCHAR(16) | ✓ | '待审核'::character varying |
| mold_count | INTEGER | ✓ | - |
| mold_status | VARCHAR(20) | ✗ | '生产中'::character varying |

**Foreign Keys**:

- `customer_id` → `tooling_customers.id`

**Indexes**:

- `tooling_molds_mold_number_seq_key` (UNIQUE)
- `idx_tmolds_customer`
- `idx_tmolds_number`

---

## Machine


### Table: `machine_status_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('machine_status_logs_id_seq'::regclass) |
| machine_id | INTEGER | ✗ | - |
| from_state | VARCHAR(50) | ✓ | - |
| to_state | machinestate | ✗ | - |
| reason | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `machine_id` → `machines.id`

**Indexes**:

- `ix_machine_status_logs_machine_id`

---

### Table: `machine_tonnage_dict`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('machine_tonnage_dict_id_seq'::regclass) |
| tonnage | INTEGER | ✗ | - |
| machine_type | VARCHAR(50) | ✗ | - |
| display_name | VARCHAR(100) | ✗ | - |
| size_category | VARCHAR(50) | ✓ | - |
| type_category | VARCHAR(50) | ✓ | - |
| min_stroke | INTEGER | ✓ | - |
| max_stroke | INTEGER | ✓ | - |
| work_table_size | VARCHAR(100) | ✓ | - |
| is_active | BOOLEAN | ✗ | - |
| sort_order | INTEGER | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |

**Indexes**:

- `uq_tonnage_machine_type` (UNIQUE)
- `idx_machine_tonnage_dict_tonnage`

---

### Table: `machines`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('machines_id_seq'::regclass) |
| machine_number | VARCHAR(30) | ✗ | - |
| machine_name | VARCHAR(100) | ✓ | ''::character varying |
| press_tonnage | VARCHAR(30) | ✓ | ''::character varying |
| status | VARCHAR(20) | ✗ | 'idle'::character varying |
| current_mold_id | INTEGER | ✓ | - |
| current_part_id | INTEGER | ✓ | - |
| current_operator_id | INTEGER | ✓ | - |
| remark | TEXT | ✓ | ''::text |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | CURRENT_TIMESTAMP |
| active_plan_id | INTEGER | ✓ | - |
| fault_reason | TEXT | ✓ | ''::text |
| fault_reported_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| tech_arrival_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| diagnosing_start_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| mold_offline_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| tech_user_id | INTEGER | ✓ | - |

**Foreign Keys**:

- `current_part_id` → `parts.id`
- `current_operator_id` → `users.id`
- `active_plan_id` → `production_plans.id`

**Indexes**:

- `machines_machine_number_key` (UNIQUE)
- `idx_machines_status`
- `idx_machines_fault_reported`

---

### Table: `plan_machine_assignments`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('plan_machine_assignments_id_seq'::regclass) |
| plan_id | INTEGER | ✗ | - |
| machine_id | INTEGER | ✗ | - |
| assigned_qty | INTEGER | ✗ | - |
| completed_qty | INTEGER | ✗ | - |
| is_active | BOOLEAN | ✗ | - |
| assigned_by | INTEGER | ✓ | - |
| assigned_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `plan_id` → `production_plans.id`
- `machine_id` → `machines.id`

**Indexes**:

- `ix_plan_machine_assignments_machine_id`
- `ix_plan_machine_assignments_plan_id`

---

### Table: `plan_machines`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('plan_machines_id_seq'::regclass) |
| plan_id | INTEGER | ✗ | - |
| machine_id | INTEGER | ✗ | - |
| assigned_by | INTEGER | ✓ | - |
| assigned_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | CURRENT_TIMESTAMP |
| status | VARCHAR(20) | ✗ | 'active'::character varying |

**Foreign Keys**:

- `plan_id` → `production_plans.id`
- `machine_id` → `machines.id`
- `assigned_by` → `users.id`

**Indexes**:

- `plan_machines_plan_id_machine_id_key` (UNIQUE)

---

## Sampling


### Table: `sample_inventory`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('sample_inventory_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| sample_qty | INTEGER | ✗ | 0 |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `part_id` → `parts.id`

---

### Table: `sample_tasks`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('sample_tasks_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| quote_id | INTEGER | ✓ | - |
| sample_type | VARCHAR(30) | ✓ | 'FIRST_SAMPLE'::character varying |
| sample_fee | NUMERIC | ✓ | 0 |
| proof_file_path | TEXT | ✓ | - |
| tech_sign_by | INTEGER | ✓ | - |
| tech_sign_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| qa_sign_by | INTEGER | ✓ | - |
| qa_sign_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| sales_sign_by | INTEGER | ✓ | - |
| sales_sign_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| task_status | VARCHAR(20) | ✗ | 'IN_PROGRESS'::character varying |
| mass_prod_activated_by | INTEGER | ✓ | - |
| mass_prod_activated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| related_mold_id | INTEGER | ✓ | - |
| remarks | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| assigned_machine_id | INTEGER | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `quote_id` → `quotes.id`
- `tech_sign_by` → `users.id`
- `qa_sign_by` → `users.id`
- `sales_sign_by` → `users.id`
- `mass_prod_activated_by` → `users.id`
- `related_mold_id` → `dies.id`
- `assigned_machine_id` → `machines.id`

**Indexes**:

- `idx_sample_part_id`
- `idx_sample_status`

---

## Production


### Table: `oqc_reports`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('oqc_reports_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| created_by | INTEGER | ✓ | - |
| status | VARCHAR(20) | ✓ | 'draft'::character varying |
| qty_inspected | INTEGER | ✓ | 0 |
| qty_passed | INTEGER | ✓ | 0 |
| qty_failed | INTEGER | ✓ | 0 |
| report_no | VARCHAR(50) | ✓ | - |
| report_file | TEXT | ✓ | - |
| remark | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| auditor_id | INTEGER | ✓ | - |
| audited_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `created_by` → `users.id`
- `auditor_id` → `users.id`

**Indexes**:

- `oqc_reports_report_no_key` (UNIQUE)
- `idx_oqc_part_id`
- `idx_oqc_status`

---

### Table: `production_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('production_logs_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| worker_id | INTEGER | ✓ | - |
| qty_good | INTEGER | ✓ | 0 |
| qty_bad | INTEGER | ✓ | 0 |
| report_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| status | VARCHAR(20) | ✓ | '待初审'::character varying |
| scrap_reason | VARCHAR(200) | ✓ | - |
| auditor_id | INTEGER | ✓ | - |
| machine_id | INTEGER | ✓ | - |
| plan_id | INTEGER | ✓ | - |
| material_id | INTEGER | ✓ | - |
| actual_date | DATE | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `worker_id` → `users.id`
- `auditor_id` → `users.id`
- `machine_id` → `machines.id`
- `plan_id` → `production_plans.id`
- `material_id` → `materials.id`

**Indexes**:

- `idx_pl_part_status`
- `idx_prod_actual_date`

---

### Table: `production_plans`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('production_plans_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| total_qty | INTEGER | ✗ | 0 |
| delivered_qty | INTEGER | ✗ | 0 |
| due_date | DATE | ✓ | - |
| urgency | VARCHAR(10) | ✗ | 'normal'::character varying |
| machine_id | INTEGER | ✓ | - |
| plan_order | INTEGER | ✗ | 0 |
| assigned_by | INTEGER | ✓ | - |
| assigned_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| status | VARCHAR(20) | ✗ | 'planned'::character varying |
| remark | TEXT | ✓ | ''::text |
| force_order | BOOLEAN | ✗ | false |
| created_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | CURRENT_TIMESTAMP |
| progress_qty | INTEGER | ✗ | 0 |

**Foreign Keys**:

- `part_id` → `parts.id`
- `machine_id` → `machines.id`
- `assigned_by` → `users.id`
- `created_by` → `users.id`

---

### Table: `production_reports`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('production_reports_id_seq'::regclass) |
| session_id | INTEGER | ✗ | - |
| strokes | INTEGER | ✗ | - |
| cavity_count | INTEGER | ✗ | - |
| output | INTEGER | ✗ | - |
| good_qty | INTEGER | ✗ | - |
| reject_qty | INTEGER | ✗ | - |
| material_used | DOUBLE PRECISION | ✓ | - |
| report_time | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| operator_id | INTEGER | ✓ | - |
| notes | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `session_id` → `production_sessions.id`

**Indexes**:

- `ix_production_reports_session_id`

---

### Table: `production_scrap`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('production_scrap_id_seq'::regclass) |
| material_id | INTEGER | ✓ | - |
| material_number | VARCHAR(100) | ✓ | - |
| scrap_type | VARCHAR(30) | ✗ | - |
| scrap_width | NUMERIC | ✗ | 0 |
| scrap_weight | NUMERIC | ✗ | 0 |
| reason | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| operator_name | VARCHAR(100) | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| remark | TEXT | ✓ | - |

**Foreign Keys**:

- `material_id` → `materials.id`
- `operator_id` → `users.id`

**Indexes**:

- `idx_scrap_material_id`
- `idx_scrap_type`

---

### Table: `production_sessions`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('production_sessions_id_seq'::regclass) |
| machine_id | INTEGER | ✗ | - |
| work_order_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| material_qr_uid | VARCHAR(50) | ✓ | - |
| session_type | VARCHAR(20) | ✗ | 'Continuous'::character varying |
| status | VARCHAR(30) | ✗ | 'RUNNING'::character varying |
| start_time | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| end_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| reported_qty | INTEGER | ✗ | 0 |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| material_batch_id | INTEGER | ✓ | - |
| work_hours | DOUBLE PRECISION | ✓ | - |

**Foreign Keys**:

- `machine_id` → `equipments.id`
- `work_order_id` → `work_orders.id`
- `operator_id` → `users.id`
- `material_qr_uid` → `material_batches.qr_uid`
- `material_batch_id` → `material_batches.id`

**Indexes**:

- `idx_production_sessions_material_batch_id`

---

### Table: `sf_production_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('sf_production_logs_id_seq'::regclass) |
| work_order_id | INTEGER | ✗ | - |
| equipment_id | INTEGER | ✗ | - |
| material_qr_uid | VARCHAR(50) | ✓ | - |
| strokes | INTEGER | ✗ | - |
| yield_qty | INTEGER | ✗ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| consumed_weight | NUMERIC | ✓ | 0 |

**Foreign Keys**:

- `work_order_id` → `work_orders.id`
- `equipment_id` → `equipments.id`
- `material_qr_uid` → `material_batches.qr_uid`
- `operator_id` → `users.id`

**Indexes**:

- `idx_sfpl_wo`

---

## Process Flow


### Table: `process_flow_cards`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('process_flow_cards_id_seq'::regclass) |
| card_no | VARCHAR(50) | ✗ | - |
| session_id | INTEGER | ✗ | - |
| part_id | INTEGER | ✗ | - |
| machine_id | INTEGER | ✗ | - |
| tooling_id | INTEGER | ✓ | - |
| material_batch_no | VARCHAR(100) | ✓ | - |
| planned_qty | INTEGER | ✗ | - |
| actual_output | INTEGER | ✗ | - |
| good_qty | INTEGER | ✗ | - |
| reject_qty | INTEGER | ✗ | - |
| status | processflowstatus | ✗ | - |
| start_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| end_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| inbound_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| inbound_operator_id | INTEGER | ✓ | - |
| inbound_notes | TEXT | ✓ | - |
| qr_code | VARCHAR(200) | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `session_id` → `production_sessions.id`
- `part_id` → `parts.id`
- `machine_id` → `machines.id`
- `tooling_id` → `tooling_molds.id`

**Indexes**:

- `ix_process_flow_cards_card_no` (UNIQUE)
- `ix_process_flow_cards_machine_id`
- `ix_process_flow_cards_part_id`
- `ix_process_flow_cards_qr_code`
- `ix_process_flow_cards_status`
- `ix_process_flow_cards_session_id`

---

## Warehouse/Material


### Table: `batch_transactions`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('batch_transactions_id_seq'::regclass) |
| batch_id | INTEGER | ✓ | - |
| batch_no | VARCHAR(100) | ✓ | - |
| transaction_type | VARCHAR(20) | ✗ | - |
| quantity_change | NUMERIC | ✗ | 0 |
| weight_after | NUMERIC | ✗ | - |
| reference_type | VARCHAR(50) | ✓ | - |
| reference_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| notes | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `batch_id` → `material_batches.id`
- `operator_id` → `users.id`

**Indexes**:

- `idx_bt_batch_id`

---

### Table: `material_base_prices`

**Primary Key**: material_name

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **material_name** [PK] | VARCHAR(100) | ✗ | - |
| default_density | NUMERIC | ✗ | 7.85 |
| default_price | NUMERIC | ✗ | 0 |
| scrap_price | NUMERIC | ✓ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

---

### Table: `material_batch_children`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('material_batch_children_id_seq'::regclass) |
| parent_batch_id | INTEGER | ✗ | - |
| child_batch_no | VARCHAR(100) | ✗ | - |
| child_qr_code | VARCHAR(200) | ✓ | - |
| width | NUMERIC | ✓ | - |
| length | NUMERIC | ✓ | - |
| current_weight | NUMERIC | ✗ | 0 |
| status | VARCHAR(20) | ✗ | 'AVAILABLE'::character varying |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `parent_batch_id` → `material_batches.id`

**Indexes**:

- `idx_mbc_parent`
- `idx_mbc_child_qr`
- `idx_mbc_child_no`

---

### Table: `material_batches`

**Primary Key**: qr_uid

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **qr_uid** [PK] | VARCHAR(50) | ✗ | - |
| parent_qr_uid | VARCHAR(50) | ✓ | - |
| material_category | VARCHAR(20) | ✗ | 'PROD'::character varying |
| material_name | VARCHAR(100) | ✗ | - |
| spec | VARCHAR(100) | ✓ | - |
| supplier_name | VARCHAR(150) | ✓ | - |
| heat_number | VARCHAR(100) | ✓ | - |
| cert_file_path | TEXT | ✓ | - |
| purchase_unit_price | NUMERIC | ✓ | - |
| initial_weight | NUMERIC | ✗ | - |
| current_weight | NUMERIC | ✗ | - |
| lifecycle_status | VARCHAR(20) | ✗ | 'IN_STOCK'::character varying |
| created_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| unit | VARCHAR(10) | ✗ | 'kg'::character varying |
| batch_code | VARCHAR(100) | ✗ | - |
| supplier | VARCHAR(150) | ✓ | - |
| material_spec | VARCHAR(100) | ✓ | - |
| id | INTEGER | ✗ | nextval('material_batches_id_seq'::regclass) |
| qr_code | VARCHAR(200) | ✓ | - |
| batch_no | VARCHAR(100) | ✓ | - |
| parent_batch_id | INTEGER | ✓ | - |
| is_deleted | BOOLEAN | ✗ | false |
| po_no | VARCHAR(100) | ✓ | - |
| gross_weight | NUMERIC | ✓ | - |
| net_weight | NUMERIC | ✓ | - |
| iqc_result | VARCHAR(20) | ✓ | - |
| received_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| thickness | NUMERIC | ✓ | - |
| width | NUMERIC | ✓ | - |
| length | NUMERIC | ✓ | - |
| iqc_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| iqc_by | INTEGER | ✓ | - |
| iqc_notes | TEXT | ✓ | - |
| material_id | INTEGER | ✓ | - |
| status | VARCHAR(20) | ✓ | - |
| supplier_id | INTEGER | ✓ | - |

**Foreign Keys**:

- `parent_qr_uid` → `material_batches.qr_uid`
- `created_by` → `users.id`
- `parent_batch_id` → `material_batches.id`
- `iqc_by` → `users.id`
- `material_id` → `materials.id`

**Indexes**:

- `idx_mb_category`
- `idx_mb_parent`
- `idx_mb_status`
- `material_batches_id_key` (UNIQUE)
- `uq_material_batches_batch_code` (UNIQUE)
- `uq_mb_qr_code` (UNIQUE)
- `idx_mb_parent_batch`
- `idx_mb_qr_code`
- `idx_mb_batch_no`

---

### Table: `material_cost_history`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('material_cost_history_id_seq'::regclass) |
| material_name | VARCHAR(100) | ✗ | - |
| old_unit_price | NUMERIC | ✓ | - |
| new_unit_price | NUMERIC | ✗ | - |
| old_scrap_price | NUMERIC | ✓ | - |
| new_scrap_price | NUMERIC | ✓ | - |
| effective_date | DATE | ✗ | CURRENT_DATE |
| reason | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

---

### Table: `material_dict`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('material_dict_id_seq'::regclass) |
| code | VARCHAR(50) | ✗ | - |
| name | VARCHAR(100) | ✗ | - |
| name_cn | VARCHAR(100) | ✓ | - |
| density | NUMERIC | ✓ | - |
| thickness_range | VARCHAR(100) | ✓ | - |
| category | VARCHAR(50) | ✓ | - |
| standard | VARCHAR(100) | ✓ | - |
| default_price | NUMERIC | ✓ | - |
| scrap_price | NUMERIC | ✓ | - |
| is_active | BOOLEAN | ✗ | - |
| sort_order | INTEGER | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| created_by | INTEGER | ✓ | - |

**Indexes**:

- `material_dict_code_key` (UNIQUE)
- `idx_material_dict_code`

---

### Table: `material_slitting_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('material_slitting_logs_id_seq'::regclass) |
| parent_id | INTEGER | ✗ | - |
| child_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| operator_name | VARCHAR(100) | ✓ | - |
| slit_width | NUMERIC | ✗ | - |
| slit_count | INTEGER | ✗ | 1 |
| slit_weight | NUMERIC | ✓ | - |
| parent_consumed_width | NUMERIC | ✗ | - |
| parent_remain_width | NUMERIC | ✓ | - |
| parent_auto_closed | BOOLEAN | ✗ | false |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `parent_id` → `materials.id`
- `child_id` → `materials.id`
- `operator_id` → `users.id`

**Indexes**:

- `idx_slit_parent`
- `idx_slit_child`

---

### Table: `material_transactions`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('material_transactions_id_seq'::regclass) |
| qr_uid | VARCHAR(50) | ✗ | - |
| transaction_type | VARCHAR(20) | ✗ | - |
| weight_change | NUMERIC | ✗ | - |
| current_balance | NUMERIC | ✗ | - |
| related_work_order_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `qr_uid` → `material_batches.qr_uid`
- `operator_id` → `users.id`

**Indexes**:

- `idx_mt_qr_uid`

---

### Table: `materials`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('materials_id_seq'::regclass) |
| material_number | VARCHAR(100) | ✗ | - |
| material_name | VARCHAR(200) | ✓ | - |
| material_type | VARCHAR(50) | ✓ | '卷料'::character varying |
| original_width | NUMERIC | ✗ | - |
| current_width | NUMERIC | ✗ | - |
| parent_id | INTEGER | ✓ | - |
| scrap_threshold | NUMERIC | ✓ | 0 |
| is_active | BOOLEAN | ✓ | true |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| remark | TEXT | ✓ | - |
| thickness | NUMERIC | ✓ | 0 |
| batch_no | VARCHAR(100) | ✓ | - |
| current_weight | NUMERIC | ✓ | 0 |
| status | VARCHAR(30) | ✓ | '待入库'::character varying |
| iqc_status | VARCHAR(20) | ✗ | 'pending'::character varying |
| iqc_result | TEXT | ✓ | - |
| iqc_by | INTEGER | ✓ | - |
| iqc_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| supplier_name | VARCHAR(100) | ✓ | - |
| material_status | VARCHAR(20) | ✗ | 'pending'::character varying |
| is_whse_confirmed | BOOLEAN | ✗ | false |
| is_qc_confirmed | BOOLEAN | ✗ | false |
| whse_confirmed_by | INTEGER | ✓ | - |
| qc_confirmed_by | INTEGER | ✓ | - |
| original_weight | NUMERIC | ✓ | - |

**Foreign Keys**:

- `parent_id` → `materials.id`
- `iqc_by` → `users.id`
- `qc_confirmed_by` → `users.id`
- `whse_confirmed_by` → `users.id`

**Indexes**:

- `materials_material_number_key` (UNIQUE)
- `idx_materials_parent_id`
- `idx_materials_is_active`

---

### Table: `spraying_material_consumption`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('spraying_material_consumption_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| recipe_id | INTEGER | ✓ | - |
| log_id | INTEGER | ✓ | - |
| material_name | VARCHAR(200) | ✗ | - |
| material_type | VARCHAR(30) | ✗ | - |
| consumed_qty | NUMERIC | ✗ | 0 |
| unit_cost | NUMERIC | ✗ | 0 |
| total_cost | NUMERIC | ✗ | 0 |
| calculated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `log_id` → `spraying_logs.id`
- `part_id` → `parts.id`
- `recipe_id` → `spraying_recipes.id`

**Indexes**:

- `idx_consumption_part_id`
- `idx_consumption_mat_name`

---

### Table: `suppliers`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('suppliers_id_seq'::regclass) |
| supplier_no | VARCHAR(50) | ✗ | - |
| name | VARCHAR(200) | ✗ | - |
| contact_person | VARCHAR(100) | ✓ | - |
| contact_phone | VARCHAR(50) | ✓ | - |
| address | TEXT | ✓ | - |
| notes | TEXT | ✓ | - |
| is_active | BOOLEAN | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Indexes**:

- `ix_suppliers_supplier_no` (UNIQUE)

---

## Quality


### Table: `first_piece_inspections`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('first_piece_inspections_id_seq'::regclass) |
| inspection_no | VARCHAR(50) | ✗ | - |
| part_id | INTEGER | ✗ | - |
| session_id | INTEGER | ✓ | - |
| inspected_qty | INTEGER | ✗ | - |
| inspected_by | INTEGER | ✓ | - |
| dimension_ok | BOOLEAN | ✗ | - |
| dimension_notes | TEXT | ✓ | - |
| appearance_ok | BOOLEAN | ✗ | - |
| appearance_notes | TEXT | ✓ | - |
| function_ok | BOOLEAN | ✗ | - |
| function_notes | TEXT | ✓ | - |
| result | inspectionresult | ✗ | - |
| notes | TEXT | ✓ | - |
| inspected_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `session_id` → `production_sessions.id`

**Indexes**:

- `ix_first_piece_inspections_part_id`
- `ix_first_piece_inspections_session_id`
- `ix_first_piece_inspections_inspection_no` (UNIQUE)

---

### Table: `oqc_inspections`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('oqc_inspections_id_seq'::regclass) |
| inspection_no | VARCHAR(50) | ✗ | - |
| part_id | INTEGER | ✗ | - |
| shipment_qty | INTEGER | ✗ | - |
| order_no | VARCHAR(100) | ✓ | - |
| sample_size | INTEGER | ✗ | - |
| inspected_by | INTEGER | ✓ | - |
| aql_level | VARCHAR(20) | ✓ | - |
| major_defects | INTEGER | ✗ | - |
| minor_defects | INTEGER | ✗ | - |
| critical_defects | INTEGER | ✗ | - |
| result | inspectionresult | ✗ | - |
| notes | TEXT | ✓ | - |
| inspected_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `ix_oqc_inspections_part_id`
- `ix_oqc_inspections_inspection_no` (UNIQUE)

---

### Table: `patrol_inspections`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('patrol_inspections_id_seq'::regclass) |
| inspection_no | VARCHAR(50) | ✗ | - |
| machine_id | INTEGER | ✓ | - |
| session_id | INTEGER | ✓ | - |
| inspected_by | INTEGER | ✓ | - |
| dimension_check | BOOLEAN | ✗ | - |
| appearance_check | BOOLEAN | ✗ | - |
| process_parameter_check | BOOLEAN | ✗ | - |
| sample_size | INTEGER | ✗ | - |
| defect_count | INTEGER | ✗ | - |
| result | inspectionresult | ✗ | - |
| notes | TEXT | ✓ | - |
| corrective_action | TEXT | ✓ | - |
| action_taken_by | INTEGER | ✓ | - |
| inspected_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `session_id` → `production_sessions.id`

**Indexes**:

- `ix_patrol_inspections_machine_id`
- `ix_patrol_inspections_session_id`
- `ix_patrol_inspections_inspection_no` (UNIQUE)

---

### Table: `qa_audit_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('qa_audit_logs_id_seq'::regclass) |
| work_order_id | INTEGER | ✗ | - |
| machine_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| action_type | VARCHAR(50) | ✗ | - |
| reason | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `work_order_id` → `work_orders.id`
- `machine_id` → `equipments.id`
- `operator_id` → `users.id`

---

### Table: `qa_exemptions`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('qa_exemptions_id_seq'::regclass) |
| exemption_no | VARCHAR(50) | ✗ | - |
| part_id | INTEGER | ✗ | - |
| exemption_type | exemptiontype | ✗ | - |
| issue_description | TEXT | ✗ | - |
| affected_qty | INTEGER | ✗ | - |
| approved_by | INTEGER | ✓ | - |
| approved_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| exemption_reason | TEXT | ✓ | - |
| is_approved | BOOLEAN | ✗ | - |
| is_active | BOOLEAN | ✗ | - |
| notes | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `ix_qa_exemptions_part_id`
- `ix_qa_exemptions_exemption_no` (UNIQUE)

---

### Table: `qc_inspection_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('qc_inspection_logs_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| inspection_type | VARCHAR(30) | ✓ | 'first_piece'::character varying |
| result | VARCHAR(20) | ✓ | 'pass'::character varying |
| defect_reason | TEXT | ✓ | - |
| remark | TEXT | ✓ | - |
| inspected_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| is_blocked | BOOLEAN | ✓ | false |
| blocked_reason | TEXT | ✓ | - |
| auditor_id | INTEGER | ✓ | - |
| auditor_result | VARCHAR(20) | ✓ | - |
| audited_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `operator_id` → `users.id`
- `auditor_id` → `users.id`

**Indexes**:

- `idx_insp_part_id`
- `idx_insp_inspected_at`
- `idx_insp_blocked`

---

### Table: `qc_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('qc_logs_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| qty_checked | INTEGER | ✗ | 0 |
| qty_passed | INTEGER | ✗ | 0 |
| qty_failed | INTEGER | ✗ | 0 |
| result | VARCHAR(20) | ✓ | 'pass'::character varying |
| defect_reason | TEXT | ✓ | - |
| remark | TEXT | ✓ | - |
| checked_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| is_major | BOOLEAN | ✓ | false |
| audit_status | VARCHAR(20) | ✓ | 'approved'::character varying |
| auditor_id | INTEGER | ✓ | - |
| audited_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| is_blocked | BOOLEAN | ✓ | false |

**Foreign Keys**:

- `part_id` → `parts.id`
- `operator_id` → `users.id`
- `auditor_id` → `users.id`

**Indexes**:

- `idx_qc_part_id`
- `idx_qc_checked_at`
- `idx_qc_audit_status`

---

## Packaging


### Table: `packaging_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('packaging_logs_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| user_id | INTEGER | ✗ | - |
| qty | INTEGER | ✗ | 0 |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |

**Foreign Keys**:

- `part_id` → `parts.id`
- `user_id` → `users.id`

---

### Table: `packaging_records`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('packaging_records_id_seq'::regclass) |
| package_no | VARCHAR(100) | ✗ | - |
| part_id | INTEGER | ✗ | - |
| session_id | INTEGER | ✓ | - |
| package_qty | INTEGER | ✗ | - |
| box_no | VARCHAR(100) | ✓ | - |
| status | packagingstatus | ✗ | - |
| inspected_by | INTEGER | ✓ | - |
| inspected_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| inspection_notes | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| notes | TEXT | ✓ | - |
| scanned_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `session_id` → `production_sessions.id`

**Indexes**:

- `ix_packaging_records_package_no` (UNIQUE)
- `ix_packaging_records_part_id`
- `ix_packaging_records_session_id`
- `ix_packaging_records_status`

---

### Table: `pkg_packaging_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('pkg_packaging_logs_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| qty_checked | INTEGER | ✗ | 0 |
| qty_passed | INTEGER | ✗ | 0 |
| qty_failed | INTEGER | ✗ | 0 |
| box_no | VARCHAR(50) | ✓ | - |
| result | VARCHAR(20) | ✓ | 'pass'::character varying |
| defect_reason | TEXT | ✓ | - |
| remark | TEXT | ✓ | - |
| packed_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| is_blocked | BOOLEAN | ✓ | false |
| blocked_reason | TEXT | ✓ | - |
| auditor_id | INTEGER | ✓ | - |
| auditor_result | VARCHAR(20) | ✓ | - |
| audited_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| actual_date | DATE | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `operator_id` → `users.id`
- `auditor_id` → `users.id`

**Indexes**:

- `idx_pkg_part_id`
- `idx_pkg_packed_at`
- `idx_pkg_pkg_actual_date`

---

## Coating


### Table: `coating_recipes`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('coating_recipes_id_seq'::regclass) |
| recipe_no | VARCHAR(50) | ✗ | - |
| name | VARCHAR(200) | ✗ | - |
| coating_type | coatingtype | ✗ | - |
| color_type | coatingcolor | ✗ | - |
| color_code | VARCHAR(50) | ✓ | - |
| primer_type | VARCHAR(100) | ✓ | - |
| primer_thickness | DOUBLE PRECISION | ✓ | - |
| topcoat_type | VARCHAR(100) | ✓ | - |
| topcoat_thickness | DOUBLE PRECISION | ✓ | - |
| spray_pressure | DOUBLE PRECISION | ✓ | - |
| spray_distance | DOUBLE PRECISION | ✓ | - |
| spray_speed | DOUBLE PRECISION | ✓ | - |
| curing_temp | DOUBLE PRECISION | ✓ | - |
| curing_time | INTEGER | ✓ | - |
| material_consumption | DOUBLE PRECISION | ✓ | - |
| notes | TEXT | ✓ | - |
| is_active | BOOLEAN | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Indexes**:

- `ix_coating_recipes_recipe_no` (UNIQUE)

---

### Table: `coating_records`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('coating_records_id_seq'::regclass) |
| record_no | VARCHAR(50) | ✗ | - |
| recipe_id | INTEGER | ✗ | - |
| part_id | INTEGER | ✗ | - |
| processed_qty | INTEGER | ✗ | - |
| qualified_qty | INTEGER | ✗ | - |
| rejected_qty | INTEGER | ✗ | - |
| material_used | DOUBLE PRECISION | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| batch_no | VARCHAR(100) | ✓ | - |
| notes | TEXT | ✓ | - |
| coating_date | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `recipe_id` → `coating_recipes.id`
- `part_id` → `parts.id`

**Indexes**:

- `ix_coating_records_recipe_id`
- `ix_coating_records_record_no` (UNIQUE)
- `ix_coating_records_batch_no`
- `ix_coating_records_part_id`

---

### Table: `spraying_recipes`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('spraying_recipes_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| sand_material | VARCHAR(200) | ✗ | ''::character varying |
| sand_dosage | NUMERIC | ✗ | 0 |
| coating_material | VARCHAR(200) | ✗ | ''::character varying |
| coating_dosage | NUMERIC | ✗ | 0 |
| surface_type | VARCHAR(30) | ✗ | 'single'::character varying |
| coating_color | VARCHAR(100) | ✓ | ''::character varying |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_by | INTEGER | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `updated_by` → `users.id`

**Indexes**:

- `idx_recipe_part_id` (UNIQUE)

---

## Dictionary


### Table: `part_name_dict`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('part_name_dict_id_seq'::regclass) |
| name | VARCHAR(200) | ✗ | - |
| name_en | VARCHAR(200) | ✓ | - |
| category | VARCHAR(100) | ✓ | - |
| sub_category | VARCHAR(100) | ✓ | - |
| description | TEXT | ✓ | - |
| usage_count | INTEGER | ✗ | - |
| is_active | BOOLEAN | ✗ | - |
| sort_order | INTEGER | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| created_by | INTEGER | ✓ | - |
| primary_category | VARCHAR(100) | ✗ | - |
| secondary_category | VARCHAR(100) | ✓ | - |
| customer_part_name | VARCHAR(200) | ✓ | - |
| remark | TEXT | ✓ | - |

**Indexes**:

- `part_name_dict_name_key` (UNIQUE)
- `idx_part_name_dict_name`
- `idx_part_name_unique` (UNIQUE)

---

### Table: `system_dicts`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('system_dicts_id_seq'::regclass) |
| dict_type | VARCHAR(64) | ✗ | - |
| dict_value | VARCHAR(256) | ✗ | - |
| sort_order | INTEGER | ✓ | 0 |
| is_active | BOOLEAN | ✓ | true |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |

**Indexes**:

- `system_dicts_dict_type_dict_value_key` (UNIQUE)

---

### Table: `treatment_dicts`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('treatment_dicts_id_seq'::regclass) |
| name | VARCHAR(128) | ✗ | - |
| calc_mode | VARCHAR(32) | ✗ | 'manual'::character varying |
| rate | NUMERIC | ✗ | 0 |
| unit | VARCHAR(16) | ✗ | '元/件'::character varying |
| is_active | BOOLEAN | ✗ | true |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Indexes**:

- `treatment_dicts_name_key` (UNIQUE)

---

## Audit & Logging


### Table: `audit_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('audit_logs_id_seq'::regclass) |
| action | auditaction | ✗ | - |
| entity_type | VARCHAR(100) | ✗ | - |
| entity_id | INTEGER | ✓ | - |
| user_id | INTEGER | ✓ | - |
| username | VARCHAR(50) | ✓ | - |
| ip_address | VARCHAR(50) | ✓ | - |
| user_agent | VARCHAR(500) | ✓ | - |
| old_values | JSONB | ✓ | - |
| new_values | JSONB | ✓ | - |
| changes_summary | VARCHAR(500) | ✓ | - |
| request_id | VARCHAR(100) | ✓ | - |
| session_id | VARCHAR(100) | ✓ | - |
| extra_data | JSONB | ✓ | - |
| status | VARCHAR(20) | ✗ | - |
| error_message | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `user_id` → `users.id`

**Indexes**:

- `ix_audit_logs_action_time`
- `ix_audit_logs_user_time`
- `ix_audit_logs_created_at`
- `ix_audit_logs_entity`

---

### Table: `defect_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('defect_logs_id_seq'::regclass) |
| work_order_id | INTEGER | ✗ | - |
| defect_qty | INTEGER | ✗ | 1 |
| reason | TEXT | ✓ | - |
| reporter_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| source | VARCHAR(30) | ✗ | 'Manual'::character varying |

**Foreign Keys**:

- `reporter_id` → `users.id`
- `work_order_id` → `work_orders.id`

---

### Table: `maintenance_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('maintenance_logs_id_seq'::regclass) |
| target_type | VARCHAR(20) | ✗ | - |
| equipment_id | INTEGER | ✓ | - |
| mold_id | INTEGER | ✓ | - |
| repair_mode | VARCHAR(50) | ✓ | - |
| status | VARCHAR(20) | ✗ | 'REPAIRING'::character varying |
| tech_id | INTEGER | ✓ | - |
| start_time | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| end_time | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| remarks | TEXT | ✓ | - |

**Foreign Keys**:

- `equipment_id` → `equipments.id`
- `mold_id` → `dies.id`
- `tech_id` → `users.id`

**Indexes**:

- `idx_ml_target`

---

### Table: `pkg_error_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('pkg_error_logs_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| error_type | VARCHAR(50) | ✗ | - |
| detail | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |

**Foreign Keys**:

- `part_id` → `parts.id`
- `operator_id` → `users.id`

---

### Table: `pkg_shipping_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('pkg_shipping_logs_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| qty | INTEGER | ✗ | 0 |
| box_no | VARCHAR(50) | ✓ | - |
| vehicle_no | VARCHAR(50) | ✓ | - |
| result | VARCHAR(20) | ✓ | 'success'::character varying |
| remark | TEXT | ✓ | - |
| shipped_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |
| actual_date | DATE | ✓ | - |
| customer_id | INTEGER | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `operator_id` → `users.id`
- `customer_id` → `tooling_customers.id`

**Indexes**:

- `idx_ship_part_id`
- `idx_pkg_ship_actual_date`
- `idx_pkg_shipping_customer`

---

### Table: `price_adjustment_log`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('price_adjustment_log_id_seq'::regclass) |
| adjust_type | VARCHAR(32) | ✗ | - |
| target_name | VARCHAR(200) | ✓ | - |
| old_value | JSONB | ✓ | - |
| new_value | JSONB | ✓ | - |
| effective_date | DATE | ✗ | CURRENT_DATE |
| reason | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

---

### Table: `qr_scan_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('qr_scan_logs_id_seq'::regclass) |
| scan_type | VARCHAR(20) | ✗ | - |
| entity_id | INTEGER | ✗ | - |
| entity_no | VARCHAR(100) | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| operation | VARCHAR(20) | ✗ | - |
| notes | TEXT | ✓ | - |
| scanned_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `operator_id` → `users.id`

**Indexes**:

- `idx_qr_scan_entity`
- `idx_qr_scan_operator`
- `idx_qr_scan_time`

---

### Table: `shipping_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('shipping_logs_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| user_id | INTEGER | ✗ | - |
| qty | INTEGER | ✗ | 0 |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |

**Foreign Keys**:

- `part_id` → `parts.id`
- `user_id` → `users.id`

---

### Table: `spraying_logs`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('spraying_logs_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| quantity | INTEGER | ✗ | 0 |
| operator_id | INTEGER | ✓ | - |
| manager_id | INTEGER | ✓ | - |
| actual_date | DATE | ✗ | CURRENT_DATE |
| is_calculated | BOOLEAN | ✗ | false |
| remark | TEXT | ✓ | ''::text |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `part_id` → `parts.id`
- `operator_id` → `users.id`
- `manager_id` → `users.id`

**Indexes**:

- `idx_spray_log_part_id`
- `idx_spray_log_actual_date`
- `idx_spray_log_uncalc`

---

## Other


### Table: `admin_context_switches`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('admin_context_switches_id_seq'::regclass) |
| user_id | INTEGER | ✗ | - |
| original_role_level | INTEGER | ✗ | - |
| original_dept | VARCHAR(50) | ✓ | - |
| switched_to_dept | VARCHAR(50) | ✗ | - |
| switched_to_role_level | INTEGER | ✗ | - |
| switch_type | contextswitchtype | ✗ | - |
| is_active | BOOLEAN | ✗ | - |
| session_key | VARCHAR(200) | ✓ | - |
| switched_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| switched_back_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| expires_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |

**Foreign Keys**:

- `user_id` → `users.id`

**Indexes**:

- `ix_admin_context_switches_session_key` (UNIQUE)
- `ix_admin_context_switches_is_active`
- `ix_admin_context_switches_user_id`

---

### Table: `alembic_version`

**Primary Key**: version_num

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **version_num** [PK] | VARCHAR(64) | ✗ | - |

**Indexes**:

- `alembic_version_pkc` (UNIQUE)

---

### Table: `annual_price_records_placeholder`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('annual_price_records_placeholder_id_seq'::regclass) |

---

### Table: `annual_price_reduction`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('annual_price_reduction_id_seq'::regclass) |
| customer_id | INTEGER | ✓ | - |
| part_id | INTEGER | ✓ | - |
| reduction_rate | NUMERIC | ✗ | - |
| start_year | INTEGER | ✗ | - |
| end_year | INTEGER | ✓ | - |
| note | TEXT | ✓ | - |
| created_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| is_active | BOOLEAN | ✗ | true |

---

### Table: `annual_reductions`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('annual_reductions_id_seq'::regclass) |
| price_id | INTEGER | ✗ | - |
| reduction_pct | NUMERIC | ✗ | 0 |
| start_year | INTEGER | ✗ | - |
| duration_years | INTEGER | ✓ | 0 |
| reason | VARCHAR(200) | ✓ | - |
| created_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |

**Foreign Keys**:

- `price_id` → `prices.id`

**Indexes**:

- `idx_annual_reductions_price_id`

---

### Table: `assignments`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('assignments_id_seq'::regclass) |
| part_id | INTEGER | ✓ | - |
| worker_id | INTEGER | ✓ | - |
| leader_id | INTEGER | ✓ | - |
| assign_date | DATE | ✓ | CURRENT_DATE |

**Foreign Keys**:

- `part_id` → `parts.id`
- `worker_id` → `users.id`
- `leader_id` → `users.id`

---

### Table: `bom_routings`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('bom_routings_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| step_seq | INTEGER | ✗ | - |
| process_name | VARCHAR(100) | ✗ | - |
| process_code | VARCHAR(50) | ✓ | - |
| mold_id | INTEGER | ✓ | - |
| is_outsource | BOOLEAN | ✗ | false |
| outsource_vendor_id | INTEGER | ✓ | - |
| labor_minutes | NUMERIC | ✓ | 0 |
| is_critical | BOOLEAN | ✓ | false |
| remarks | TEXT | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `part_id` → `parts.id`
- `mold_id` → `dies.id`

**Indexes**:

- `uq_bom_part_step` (UNIQUE)
- `idx_bom_part_seq`
- `idx_bom_mold_id`

---

### Table: `delivery_items`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('delivery_items_id_seq'::regclass) |
| dn_id | INTEGER | ✗ | - |
| part_id | INTEGER | ✗ | - |
| qty | INTEGER | ✗ | - |
| lot_no | VARCHAR(100) | ✓ | - |
| remark | VARCHAR(200) | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `dn_id` → `delivery_notes.id`
- `part_id` → `parts.id`

**Indexes**:

- `idx_di_dn`

---

### Table: `delivery_notes`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('delivery_notes_id_seq'::regclass) |
| dn_no | VARCHAR(50) | ✗ | - |
| customer_name | VARCHAR(150) | ✗ | - |
| shipped_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| status | VARCHAR(20) | ✗ | 'SHIPPED'::character varying |
| notes | TEXT | ✓ | - |
| created_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `created_by` → `users.id`

**Indexes**:

- `delivery_notes_dn_no_key` (UNIQUE)
- `idx_dn_customer`
- `idx_dn_status`

---

### Table: `equipments`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('equipments_id_seq'::regclass) |
| equipment_code | VARCHAR(50) | ✗ | - |
| equipment_name | VARCHAR(100) | ✓ | - |
| tonnage | VARCHAR(50) | ✓ | - |
| current_status | VARCHAR(50) | ✗ | 'IDLE'::character varying |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Indexes**:

- `equipments_equipment_code_key` (UNIQUE)
- `idx_eq_status`

---

### Table: `finished_goods_inventory`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('finished_goods_inventory_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| stock_qty | INTEGER | ✗ | - |
| reserved_qty | INTEGER | ✗ | - |
| location | VARCHAR(100) | ✓ | - |
| last_update_by | INTEGER | ✓ | - |
| last_update_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `ix_finished_goods_inventory_part_id`

---

### Table: `finished_inventory`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('finished_inventory_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| quantity | INTEGER | ✗ | 0 |
| location | VARCHAR(100) | ✗ | ''::character varying |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `uq_finished_inventory_part_location` (UNIQUE)
- `idx_finished_inventory_part_id`

---

### Table: `inbound_orders`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('inbound_orders_id_seq'::regclass) |
| order_no | VARCHAR(64) | ✗ | - |
| supplier | VARCHAR(128) | ✓ | ''::character varying |
| material_type | VARCHAR(32) | ✓ | '卷料'::character varying |
| expected_width | NUMERIC | ✓ | 0 |
| expected_weight | NUMERIC | ✓ | 0 |
| actual_width | NUMERIC | ✓ | - |
| actual_weight | NUMERIC | ✓ | - |
| status | VARCHAR(16) | ✓ | 'pending'::character varying |
| approved_by | INTEGER | ✓ | - |
| approved_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| remark | TEXT | ✓ | ''::text |
| created_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | CURRENT_TIMESTAMP |

**Indexes**:

- `inbound_orders_order_no_key` (UNIQUE)

---

### Table: `inventory_transactions`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('inventory_transactions_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| transaction_type | VARCHAR(50) | ✗ | - |
| quantity | INTEGER | ✗ | - |
| stock_before | INTEGER | ✗ | - |
| stock_after | INTEGER | ✗ | - |
| reference_type | VARCHAR(50) | ✓ | - |
| reference_id | INTEGER | ✓ | - |
| reason | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | - |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `ix_inventory_transactions_part_id`

---

### Table: `manual_adjustments`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('manual_adjustments_id_seq'::regclass) |
| price_id | INTEGER | ✗ | - |
| adjusted_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| old_price | NUMERIC | ✓ | - |
| new_price | NUMERIC | ✓ | - |
| adjustment_type | VARCHAR(30) | ✓ | - |
| reason | VARCHAR(200) | ✓ | - |
| operator_id | INTEGER | ✓ | - |

**Foreign Keys**:

- `price_id` → `prices.id`

**Indexes**:

- `idx_manual_adjustments_price_id`
- `idx_manual_adjustments_adjusted_at`

---

### Table: `price_adjustments_placeholder`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('price_adjustments_placeholder_id_seq'::regclass) |

---

### Table: `price_years`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('price_years_id_seq'::regclass) |
| price_id | INTEGER | ✗ | - |
| year | INTEGER | ✗ | - |
| unit_price | NUMERIC | ✓ | - |
| annual_sales | INTEGER | ✓ | 0 |
| operator_id | INTEGER | ✓ | - |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |

**Foreign Keys**:

- `price_id` → `prices.id`

**Indexes**:

- `price_years_price_id_year_key` (UNIQUE)
- `idx_price_years_price_id`
- `idx_price_years_year`

---

### Table: `prices`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('prices_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| customer_id | INTEGER | ✓ | - |
| material_name | VARCHAR(100) | ✓ | - |
| net_weight | NUMERIC | ✓ | - |
| surface_treatment | JSONB | ✓ | '[]'::jsonb |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | now() |
| gross_weight | NUMERIC | ✓ | - |
| material_unit_price | NUMERIC | ✓ | - |
| scrap_price | NUMERIC | ✓ | - |
| surface_treatment_cost | NUMERIC | ✓ | - |
| cost_override | NUMERIC | ✓ | - |
| material_cost | NUMERIC | ✓ | - |
| remark | TEXT | ✓ | - |

**Foreign Keys**:

- `part_id` → `parts.id`
- `customer_id` → `tooling_customers.id`

**Indexes**:

- `prices_part_id_customer_id_key` (UNIQUE)
- `idx_prices_part_id`
- `idx_prices_customer_id`

---

### Table: `remnant_inventory`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('remnant_inventory_id_seq'::regclass) |
| part_id | INTEGER | ✗ | - |
| quantity | INTEGER | ✗ | 0 |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `part_id` → `parts.id`

**Indexes**:

- `uq_remnant_inventory_part` (UNIQUE)

---

### Table: `routing_records`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('routing_records_id_seq'::regclass) |
| ticket_no | VARCHAR(50) | ✗ | - |
| step_seq | INTEGER | ✗ | - |
| produced_qty | INTEGER | ✗ | - |
| defect_qty | INTEGER | ✗ | 0 |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `ticket_no` → `routing_tickets.ticket_no`
- `operator_id` → `users.id`

**Indexes**:

- `idx_rr_ticket`

---

### Table: `routing_tickets`

**Primary Key**: ticket_no

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **ticket_no** [PK] | VARCHAR(50) | ✗ | - |
| work_order_id | INTEGER | ✗ | - |
| current_step_seq | INTEGER | ✗ | 10 |
| current_good_qty | INTEGER | ✗ | 0 |
| ticket_status | VARCHAR(20) | ✗ | 'WIP'::character varying |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

**Foreign Keys**:

- `work_order_id` → `work_orders.id`

**Indexes**:

- `idx_rt_wo`

---

### Table: `treatment_cost_history`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('treatment_cost_history_id_seq'::regclass) |
| treatment_name | VARCHAR(200) | ✗ | - |
| old_calc_mode | VARCHAR(32) | ✓ | - |
| new_calc_mode | VARCHAR(32) | ✗ | - |
| old_rate | NUMERIC | ✓ | - |
| new_rate | NUMERIC | ✗ | - |
| old_unit | VARCHAR(50) | ✓ | - |
| new_unit | VARCHAR(50) | ✓ | - |
| effective_date | DATE | ✗ | CURRENT_DATE |
| reason | TEXT | ✓ | - |
| operator_id | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |

---

### Table: `work_orders`

**Primary Key**: id

| Column | Type | Nullable | Default |
|--------|------|----------|----------|
| **id** [PK] | INTEGER | ✗ | nextval('work_orders_id_seq'::regclass) |
| order_no | VARCHAR(50) | ✗ | - |
| part_id | INTEGER | ✗ | - |
| equipment_id | INTEGER | ✓ | - |
| target_qty | INTEGER | ✗ | - |
| produced_qty | INTEGER | ✗ | 0 |
| priority | VARCHAR(20) | ✗ | 'NORMAL'::character varying |
| order_status | VARCHAR(20) | ✗ | 'PENDING'::character varying |
| created_by | INTEGER | ✓ | - |
| created_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| updated_at | TIMESTAMP WITHOUT TIME ZONE | ✗ | now() |
| is_routing_enabled | BOOLEAN | ✗ | false |
| is_first_piece_required | BOOLEAN | ✗ | false |
| first_piece_passed_at | TIMESTAMP WITHOUT TIME ZONE | ✓ | - |
| first_piece_passed_by | INTEGER | ✓ | - |
| die_id | INTEGER | ✓ | - |
| wip_pcs | INTEGER | ✗ | 0 |
| is_pkg_closed | BOOLEAN | ✗ | false |

**Foreign Keys**:

- `part_id` → `parts.id`
- `equipment_id` → `equipments.id`
- `created_by` → `users.id`
- `first_piece_passed_by` → `users.id`
- `die_id` → `dies.id`

**Indexes**:

- `idx_wo_part`
- `idx_wo_equip`
- `work_orders_order_no_key` (UNIQUE)
- `idx_wo_status`
- `idx_wo_routing`
- `idx_work_orders_mold_id`

---
