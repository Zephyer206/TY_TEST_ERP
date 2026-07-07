# Zephyr ERP - 工具和技能使用指南

**创建日期**: 2026-07-07  
**文档版本**: v1.0

本文档记录项目中可用的 MCP 服务器和 Skills，以及它们的使用方法。

---

## 📦 已安装的 MCP 服务器

### 1. PostgreSQL MCP Server

**功能**: 直接访问和操作云端 PostgreSQL 数据库

**连接信息**:
- 数据库地址: `124.222.29.229:5432`
- 数据库用户: `postgres`
- 当前连接的表: 90 张（完整列表见下文）

**主要用途**:
- 查询表结构（schema）
- 检查数据库现状
- 读取表数据
- 执行 SQL 查询

**使用示例**:

```python
# 通过 MCP 读取表结构
# 在 Claude Code 中，可以直接要求：
# "查询 tooling_customers 表的结构"
# "检查 parts 表有哪些字段"
# "读取 material_dict 表的数据"
```

**可用的表资源** (90 张表):

**核心业务表**:
- `users` - 用户表
- `quotes` - 报价单
- `parts` - 零件主表
- `tooling_customers` - 客户表（需重命名为 customers）
- `part_customer_aliases` - 零件客户别名（一卖多）
- `machines` - 机台表
- `production_plans` - 生产计划
- `production_reports` - 报工记录
- `material_batches` - 原料批次
- `process_flow_cards` - 工艺流转单

**字典表**:
- `material_dict` - 材料字典
- `treatment_dicts` - 工序字典（待重建）
- `machine_tonnage_dict` - 机床吨位字典
- `part_name_dict` - 零件名称字典
- `system_dicts` - 系统字典

**价格相关表**:
- `material_base_prices` - 材料基础价格（待废弃）
- `prices` - 价格表
- `annual_reductions` - 年降记录
- `price_years` - 价格年份
- `price_adjustment_log` - 调价日志

**质量检验表**:
- `first_piece_inspections` - 首件检验
- `oqc_inspections` - OQC 检验
- `qa_exemptions` - 质量特赦
- `patrol_inspections` - 巡检记录
- `qc_logs` - 质检日志

**仓库物流表**:
- `material_batches` - 原料批次
- `material_batch_children` - 子卷
- `suppliers` - 供应商
- `finished_goods_inventory` - 成品库存
- `inventory_transactions` - 库存事务
- `delivery_notes` - 发货单
- `packaging_records` - 包装记录

**审计日志表**:
- `audit_logs` - 审计日志
- `qr_scan_logs` - 二维码扫描日志
- `machine_status_logs` - 机台状态日志

**其他表** (完整列表):
- `admin_context_switches`, `alembic_version`, `assignments`
- `batch_transactions`, `bom_routings`, `coating_recipes`, `coating_records`
- `defect_logs`, `delivery_items`, `die_parts`, `dies`, `equipments`
- `finished_inventory`, `inbound_orders`, `maintenance_logs`, `manual_adjustments`
- `material_cost_history`, `material_slitting_logs`, `material_transactions`
- `mold_offline_records`, `mold_type_dict`, `mold_types`
- `oqc_reports`, `packaging_logs`, `part_aliases`, `part_cost_snapshot`
- `part_customer_alias`, `pkg_error_logs`, `pkg_packaging_logs`, `pkg_shipping_logs`
- `plan_machine_assignments`, `plan_machines`, `production_logs`, `production_scrap`
- `production_sessions`, `qa_audit_logs`, `qc_inspection_logs`, `remnant_inventory`
- `routing_records`, `routing_tickets`, `sample_inventory`, `sample_tasks`
- `sf_production_logs`, `shipping_logs`, `spraying_logs`, `spraying_material_consumption`
- `spraying_recipes`, `tooling_maintenance_logs`, `tooling_molds`, `tooling_parts`
- `treatment_cost_history`, `work_orders`

---

## 🛠️ 可用的 Skills

> Skills 是预定义的命令，通过 `/skill-name` 语法调用。

### 当前项目 Skills

**检查方式**:
```bash
# 查看项目中定义的 skills
ls .claude/skills/
```

**常用 Skills**:
- 如果项目中有自定义 skills，它们会显示在聊天界面的技能列表中
- 使用 `/help` 查看所有可用的内置命令

---

## 📝 常用操作示例

### 1. 查询数据库表结构

**方式A - 使用 MCP**:
```
"查询 tooling_customers 表的完整结构"
"显示 parts 表的所有列和类型"
```

**方式B - 使用 Python 脚本**:
```bash
cd backend
python scripts/tools/inspect_cloud_schema.py
```

### 2. 查询表数据

**通过 MCP**:
```
"查询 tooling_customers 表有多少行数据"
"显示 material_dict 表的前10条记录"
"检查 treatment_dicts 表的所有数据"
```

### 3. 执行数据库迁移

**使用 Alembic**:
```bash
cd backend

# 创建迁移脚本
alembic revision -m "add customer material prices table"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 4. 检查设计与实际的差异

**使用检查脚本**:
```bash
cd backend
python scripts/tools/inspect_cloud_schema.py
# 会生成 current-schema.md 并对比设计文档
```

---

## 🔍 数据库当前状态（2026-07-07）

### 统计信息
- **总表数**: 90 张
- **设计表数**: 38 张
- **已实现**: 27 张（共同表）
- **缺失**: 11 张（设计了但未创建）
- **多余**: 63 张（云端有但设计中没有）

### 缺失的核心表（需要创建）

1. **customers** - 客户主表（tooling_customers 需重命名）
2. **price_accounts** - 零件价格台账
3. **price_adjustments** - 调价记录（带审批）
4. **customer_material_prices** - 客户材料价格历史（新设计）
5. **customer_treatment_prices** - 客户工序价格历史（新设计）
6. **departments** - 部门表
7. **special_permissions_dict** - 特殊权限字典
8. **quote_items** - 报价明细（待整合）
9. **quote_tech_reviews** - 技术审核记录
10. **surface_treatments** - 表面处理明细
11. **sampling_tasks** - 打样任务（实际有 sample_tasks）

### 需要重构的表

| 现有表 | 操作 | 目标 |
|-------|------|------|
| `tooling_customers` | 重命名 | `customers` |
| `material_base_prices` | 迁移+废弃 | 数据迁移到 `material_dict` |
| `treatment_dicts` | 清理+重建 | 新建 `treatment_dict` |
| `material_cost_history` | 废弃 | 改为 `customer_material_prices` |
| `treatment_cost_history` | 废弃 | 改为 `customer_treatment_prices` |

---

## 📚 相关文档

### 数据库设计文档
- [complete-database-design-summary.md](specs/001-erp-system-architecture/database-analysis/complete-database-design-summary.md) - 完整设计总结
- [data-model.md](specs/001-erp-system-architecture/data-model.md) - 数据模型文档
- [current-schema.md](backend/current-schema.md) - 云端数据库实际结构（自动生成）

### 实体组设计文档
- [customer-entity-group-final.md](specs/001-erp-system-architecture/database-analysis/customer-entity-group-final.md)
- [part-entity-parts-table-final.md](specs/001-erp-system-architecture/database-analysis/part-entity-parts-table-final.md)
- [material-treatment-price-history-final.md](specs/001-erp-system-architecture/database-analysis/material-treatment-price-history-final.md)

### 维护指南
- [maintenance-guide.md](specs/001-erp-system-architecture/database-analysis/maintenance-guide.md)
- [gap-analysis.md](specs/001-erp-system-architecture/database-analysis/gap-analysis.md)

---

## 🚀 下一步操作

### 立即可做的
1. ✅ 使用 PostgreSQL MCP 查询任何表的结构和数据
2. ✅ 通过 MCP 执行 SQL 查询（只读）
3. ✅ 检查表数据内容，验证迁移策略

### 需要创建的
1. 📝 数据库迁移脚本（Alembic）
2. 📝 数据迁移脚本（material_base_prices → material_dict）
3. 📝 表重命名脚本（tooling_customers → customers）

### 注意事项
- ⚠️ PostgreSQL MCP 可以读取数据，但**写操作需要谨慎**
- ⚠️ 建议先在本地测试迁移脚本，再应用到云端
- ⚠️ 重要表操作前先备份数据

---

## 💡 使用提示

### 如何快速查询表信息
```
直接问: "tooling_customers 表有哪些字段？"
直接问: "material_dict 表有多少条数据？"
直接问: "查询 treatment_dicts 表的所有记录"
```

### 如何检查某个设计是否已实现
```
直接问: "检查云端数据库是否有 customer_material_prices 表"
直接问: "对比设计文档和实际数据库的差异"
```

### 如何生成迁移脚本
```
直接说: "创建数据库迁移脚本，添加 customer_material_prices 表"
直接说: "生成重命名 tooling_customers 为 customers 的迁移脚本"
```

---

**文档维护**: 当添加新的 MCP 服务器或 Skills 时，请更新此文档。
