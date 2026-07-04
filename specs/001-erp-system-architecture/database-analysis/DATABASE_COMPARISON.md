# 数据库表对比总结

**日期**: 2026-06-22  
**目的**: 对比 data-model.md 设计文档与实际云端PostgreSQL数据库

---

## 📊 总体情况

### 设计文档 (data-model.md)
- **表数量**: 约 30+ 张表（根据13个实体组估算）
- **设计阶段**: 规范化设计，符合业务需求

### 实际数据库 (远程PostgreSQL)
- **表数量**: **90 张表**
- **状态**: 已部署运行，包含大量实际业务表

---

## 🔍 关键发现

### 1. Quote（报价单）实体组对比

#### data-model.md 设计的表结构

```
1. quotes (报价单主表)
   - 使用 UUID 作为主键
   - 字段: id, quote_number, customer_id, status, submitted_by, 
          boss_approved_by, is_fixed, fix_path, quote_snapshot...
   - 状态: waiting_tech_review/tech_approved/draft/pending_boss/boss_approved...

2. quote_items (报价单明细)
   - 一个报价单包含多个零件项
   - 字段: part_name, t_parameter, w_parameter, p_parameter, 
          tooling_fee, stamping_fee, total_price...

3. surface_treatments (表面处理)
   - 多道表面处理工序
   - 字段: treatment_name, treatment_fee, sequence

4. quote_tech_reviews (技术审核记录)
   - 技术审核历史记录

5. customers (客户表)
   - 客户基础信息
```

#### 实际数据库 quotes 表结构

```python
class Quote(Base):
    __tablename__ = "quotes"
    
    # 主键: INTEGER (不是UUID!)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 关联零件: part_id (不是 quote_items 多对多!)
    part_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # 报价单号
    quote_serial: Mapped[Optional[str]]  # 不是 quote_number
    
    # 技术参数 (直接存在 quotes 表中!)
    thickness, width, press_stroke, cavity_count, scrap_rate, gross_weight
    
    # 价格字段 (直接存在 quotes 表中!)
    material_net_cost, stamping_fee, surface_fee, treatment_fee, 
    profit_margin, final_price
    
    # 材料快照
    snapshot_mat_price, snapshot_mat_name, snapshot_density, snapshot_scrap_price
    
    # 审批流程
    approval_status  # 不是 status
    rejection_reason
    submitted_by, submitted_at, approved_by, approved_at
    
    # 定点相关
    nomination_status, nomination_confirmed_at, nomination_confirmed_by
    price_snapshot  # JSONB
    
    # 模具相关 (直接存在 quotes 表中!)
    mold_cost, machine_type, press_tonnage, mold_life, 
    mold_type, mold_discount_mode, mold_discount_rate
    
    # 其他
    customer_id, die_id, customer_product_no, vehicle_model
    inspection_fee, packaging_fee, treatment_items (JSON)
```

---

## ⚠️ 重大差异

### 差异 1: 表结构设计理念完全不同

| 维度 | data-model.md 设计 | 实际数据库 |
|------|-------------------|-----------|
| **报价单-零件关系** | 一对多（quotes → quote_items） | **一对一**（quotes.part_id 直接关联） |
| **主键类型** | UUID | **INTEGER** |
| **字段名称** | quote_number, status | **quote_serial, approval_status** |
| **数据范式** | 高度规范化（3NF） | **反范式化**（大宽表） |

### 差异 2: quote_items 表在实际数据库中不存在

**设计文档假设**：
```sql
quotes (1) ──→ (N) quote_items
一个报价单可以包含多个零件
```

**实际情况**：
```sql
quotes.part_id → parts
一个报价单只能对应一个零件
```

**影响**：
- 如果一个客户询价包含5个零件，需要创建 **5 个独立的 quotes 记录**
- 无法在一个报价单中管理多个零件项

### 差异 3: 表面处理数据存储方式

| data-model.md | 实际数据库 |
|--------------|-----------|
| `surface_treatments` 独立表 | `quotes.treatment_items` **JSONB** 字段 |
| 多道工序多条记录 | 单个JSON对象存储 |

### 差异 4: 技术审核记录

| data-model.md | 实际数据库 |
|--------------|-----------|
| `quote_tech_reviews` 独立表 | 未发现独立表 |
| 记录审核历史 | 可能没有审核历史追踪 |

---

## 📋 实际数据库中的其他 Quote 相关表

从90张表中筛选出与报价相关的表：

1. **quotes** - 报价单主表 ✅
2. **parts** - 零件表 ✅
3. **customers** - 客户表（实际可能有不同命名）
4. **dies** - 模具表 ✅
5. **prices** - 价格表 ✅
6. **price_years** - 年份价格 ✅
7. **annual_price_reduction** - 年降记录 ✅
8. **part_aliases** / **part_customer_alias** - 零件别名 ✅
9. **material_dict** - 材料字典 ✅
10. **mold_type_dict** - 模具类型字典 ✅

---

## 🎯 关键问题

### 问题 1: 继续按 data-model.md 设计，还是适配实际数据库？

**选项 A**: 保持 data-model.md 设计不变
- ✅ 优点：更规范、更灵活、易扩展
- ❌ 缺点：与现有数据库不兼容，需要**重新迁移**

**选项 B**: 修改 data-model.md 以匹配实际数据库
- ✅ 优点：与现有系统兼容
- ❌ 缺点：设计不够规范，一个报价单无法包含多个零件

**选项 C**: 逐步迁移（混合模式）
- 保留现有 quotes 表结构
- 新增 quote_items 表用于多零件报价
- 通过应用层兼容两种模式

### 问题 2: data-model.md 的用途是什么？

**如果是设计新系统**：
- 应该按照 data-model.md 的规范化设计重建数据库

**如果是描述现有系统**：
- 应该修改 data-model.md 以反映实际数据库结构

### 问题 3: 权限控制基于哪个表结构？

前面讨论的数据权限矩阵基于 data-model.md 的设计：
- `quote_items.tooling_fee`
- `quote_items.total_price`
- `quote_items.t_parameter`

但实际数据库中这些字段都在 `quotes` 表中：
- `quotes.mold_cost`
- `quotes.final_price`
- `quotes.thickness`

---

## 📝 建议

### 立即需要明确：

1. **data-model.md 的定位**：
   - 是"未来理想设计"？
   - 还是"当前系统文档"？

2. **是否进行数据库重构**：
   - 如果是，何时进行？
   - 如果否，是否更新 data-model.md 以匹配现实？

3. **权限控制实施基准**：
   - 基于设计文档实现（需要先重构数据库）
   - 基于实际数据库实现（需要修改权限矩阵的字段名）

---

## 🔄 下一步行动

建议先回答以下问题：

1. **当前系统是否在生产环境运行**？是否有真实数据？
2. **data-model.md 是新设计还是旧文档**？
3. **是否计划重构数据库**？时间表？
4. **如何处理设计与现实的差异**？

根据您的回答，我们可以：
- 选项A：更新 data-model.md 以匹配实际数据库
- 选项B：制定数据库迁移计划
- 选项C：两套文档并存（current-db.md + future-design.md）
