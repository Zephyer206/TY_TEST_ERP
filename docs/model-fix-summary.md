# 后端模型与云端数据库匹配修复总结

## 修复日期
2026-06-21

## 问题描述
后端 SQLAlchemy 模型定义与云端 PostgreSQL 数据库的实际表结构不匹配，导致 API 无法正常工作。

## 修复的主要问题

### 1. Quote 模型 (quotes 表)
**修复内容：**
- ✅ 添加缺失字段：`press_stroke`, `cavity_count`, `scrap_rate`, `gross_weight`
- ✅ 添加材料快照字段：`snapshot_mat_price`, `snapshot_mat_name`, `snapshot_density`, `snapshot_scrap_price`
- ✅ 修复价格字段命名：`material_net_cost`, `stamping_fee`, `surface_fee`, `treatment_fee`
- ✅ 添加价格覆盖字段：`unit_price_override`, `material_cost_override`, `final_price_override`, `override_fields`
- ✅ 修复审批字段：`approval_status`, `rejection_reason`, `parent_quote_id`
- ✅ 修复字段类型和默认值以匹配数据库约束

### 2. Part 模型 (parts 表)
**修复内容：**
- ✅ 字段名修正：`part_no` → `part_number`, `part_name` → `internal_name`
- ✅ 简化模型：移除不存在的关系（`customer`, `price_accounts`, `sampling_tasks`, `production_plans`）
- ✅ 添加实际字段：`drawing_url`, `spec_info`, `status`, `part_status`, `spray_status`
- ✅ 添加定点相关字段：`nomination_status`, `nomination_attachment`, `price_snapshot`
- ✅ 添加版本和库存字段：`version`, `stock_pcs`, `remark`
- ✅ 修复可选性：`customer_id` 改为可选（nullable=True）

### 3. Customer 模型 (tooling_customers 表)
**修复内容：**
- ✅ 表名修正：`customers` → `tooling_customers`
- ✅ 大幅简化模型，仅保留实际字段：`id`, `name`, `sheet_key`, `created_at`
- ✅ 移除所有不存在的字段（联系信息、地址、业务信息等）
- ✅ 移除关系定义

### 4. Die 模型 (dies 表)
**新建模型：**
- ✅ 创建新的 Die 模型来匹配 `dies` 表
- ✅ 包含字段：`mold_number`, `part_id`, `mold_name`, `mold_type`, `cavity_count`
- ✅ 生命周期字段：`lifecycle_status`, `lifespan_strokes`, `current_strokes`
- ✅ 技术规格：`thickness_mm`, `width_mm`, `pitch_mm`, `press_tonnage`

### 5. PriceAccount 模型 (prices 表)
**修复内容：**
- ✅ 表名修正：`price_accounts` → `prices`
- ✅ 简化模型，移除不存在的关系和字段
- ✅ 匹配实际字段：`material_name`, `net_weight`, `gross_weight`, `surface_treatment` (JSONB)
- ✅ 价格字段：`material_unit_price`, `scrap_price`, `surface_treatment_cost`, `cost_override`, `material_cost`
- ✅ 注释掉不存在的表：`AnnualPriceRecord`, `PriceAdjustment`

### 6. User 模型 (users 表)
**已经正确：**
- ✅ 模型已经与数据库匹配
- ✅ 字段：`username`, `password`, `real_name`, `dept`, `role_level`, `position`, `is_tech`, `is_superadmin`

### 7. 关系清理
**修复内容：**
- ✅ ProductionPlan: 移除 `back_populates="production_plans"` 关系
- ✅ ProductionSession: 移除 Part 关系定义
- ✅ ProcessFlowCard: 移除 Part 关系定义
- ✅ SamplingTask: 移除 `back_populates="sampling_tasks"` 和 Customer 关系

## 数据库表映射清单

| 模型名 | 数据库表名 | 状态 |
|--------|-----------|------|
| User | users | ✅ 匹配 |
| Customer | tooling_customers | ✅ 修复 |
| Part | parts | ✅ 修复 |
| Quote | quotes | ✅ 修复 |
| Die | dies | ✅ 新建 |
| PriceAccount | prices | ✅ 修复 |
| Machine | machines | ✅ 匹配 |
| Material | materials | ⚠️ 待检查 |
| ProductionPlan | production_plans | ✅ 修复 |
| ProductionSession | production_sessions | ✅ 修复 |
| SamplingTask | sample_tasks | ✅ 修复 |

## 待验证的功能
1. ✅ 后端服务启动
2. ⏳ 登录 API
3. ⏳ 报价管理 API
4. ⏳ 零件管理 API
5. ⏳ 客户管理 API

## 后续工作
1. 逐步测试各个模块的 API 端点
2. 根据测试结果继续修复其他可能的不匹配
3. 更新前端以适应后端模型的变化
4. 完善 API 文档

## 技术说明
- 移除了 SQLAlchemy 的 `back_populates` 关系，因为简化后的模型不再需要双向关系
- 保留了基本的 `relationship` 定义用于查询，但不建立反向引用
- 所有外键约束根据数据库实际情况进行了调整
