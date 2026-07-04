# 数据库结构差异分析报告

**日期**: 2026-07-04
**对比对象**: data-model.md 设计 vs 云端 PostgreSQL 实际数据库

---

## 执行摘要

### 关键发现

| 指标 | 数值 |
|------|------|
| **设计表数量** | 38 张 |
| **实际表数量** | 90 张 |
| **共同表** | 27 张 (71% 的设计已实现) |
| **缺失表** | 11 张 (29% 的设计未实现) |
| **额外表** | 63 张 (实际系统有大量未设计的表) |

**结论**: 云端数据库与 data-model.md 设计存在**显著差异**。实际系统远比设计文档复杂，包含许多未在设计中体现的业务功能。

---

## Part 实体组对比分析

### 设计中的 Part 相关表 (data-model.md)

```
✅ parts                      - 零件主表
✅ part_name_dict             - 零件名称字典（三级分类）
✅ part_customer_aliases      - 客户件号别名
❌ price_accounts             - 价格台账（未实现）
❌ annual_price_records       - 年降记录（未实现）
❌ price_adjustments          - 手动调价记录（未实现）
```

### 实际数据库中的 Part 相关表

```
✅ parts                      - 零件主表（INTEGER PK，不是UUID）
✅ part_name_dict             - 零件名称字典
✅ part_customer_aliases      - 客户件号别名
✅ part_customer_alias        - 客户件号别名（另一个版本）
✅ part_aliases               - 零件别名
✅ part_cost_snapshot         - 零件成本快照
✅ die_parts                  - 模具-零件关联
✅ tooling_parts              - 模具-零件关联

价格相关:
✅ prices                     - 价格表（替代 price_accounts）
✅ price_years                - 年份价格（替代 annual_price_records）
✅ annual_price_reduction     - 年降记录
✅ annual_reductions          - 年降记录（另一个版本）
❌ annual_price_records_placeholder  - 占位表（空表）
❌ price_adjustments_placeholder     - 占位表（空表）
✅ price_adjustment_log       - 价格调整日志
```

### 核心差异

#### 1. 主键类型不同

| 表 | 设计 | 实际 |
|----|------|------|
| parts | UUID | INTEGER |
| 所有表 | UUID | INTEGER |

**影响**: 
- 设计文档中所有外键引用（UUID REFERENCES）与实际不符
- 需要全面修改设计文档的主键和外键定义

#### 2. 价格体系完全不同

**设计方案 (data-model.md)**:
```
price_accounts (价格台账主表)
├── 一个 (part_id, customer_id) 对应一个账户
├── 字段: base_price, material_unit_price, waste_price, price_snapshot
└── annual_price_records (年降子表)
    ├── 记录每年的价格
    └── UNIQUE(price_account_id, year)
```

**实际方案 (云端数据库)**:
```
prices (价格主表)
├── 直接关联 part_id
├── 字段未知（需要进一步查询）
└── price_years (年份价格)
    ├── 记录每年的价格
    └── 关联到 prices 表
```

**问题**: 两种设计思路完全不同，需要二选一或统一。

#### 3. 零件别名管理重复

实际数据库中存在三个类似的表：
- `part_customer_aliases` (设计中有)
- `part_customer_alias` (实际额外的)
- `part_aliases` (实际额外的)

**问题**: 可能是历史遗留或迁移过程中的重复，需要确认哪个是当前使用的。

---

## User & Auth 实体组对比

### 设计缺失的表

| 设计表 | 实际状态 | 说明 |
|-------|---------|------|
| departments | ❌ 不存在 | 设计中有独立部门表，实际用 users.dept 字段 |
| special_permissions_dict | ❌ 不存在 | 特殊权限字典未实现 |

### 实际表结构差异

**users 表字段对比**:

| 设计字段 | 实际字段 | 差异 |
|---------|---------|------|
| id (UUID) | id (INTEGER) | 主键类型不同 |
| password_hash | password | 字段名不同 |
| department_id (FK) | dept (VARCHAR) | 外键 vs 字符串 |
| role_level | role_level | ✅ 相同 |
| special_permissions (JSONB) | ❌ 不存在 | 特殊权限未实现 |
| is_active | ❌ 不存在 | 账户启用状态未实现 |
| last_login_at | ❌ 不存在 | 最后登录时间未实现 |
| - | is_tech (BOOLEAN) | 设计中没有 |
| - | is_superadmin (BOOLEAN) | 设计中没有 |
| - | position (VARCHAR) | 设计中没有 |

**结论**: 
- 设计的 4 级权限体系 (role_level 1-4) 已实现
- 特殊权限系统 (special_permissions) **完全未实现**
- 部门管理采用字符串而非外键关联

---

## Quote 实体组对比

### 设计缺失的表

| 设计表 | 实际状态 | 说明 |
|-------|---------|------|
| quote_items | ❌ 不存在 | 设计的一对多关系未实现 |
| surface_treatments | ❌ 不存在 | 多道表面处理独立表未实现 |
| quote_tech_reviews | ❌ 不存在 | 技术审核记录未实现 |
| customers | ❌ 不存在 | 客户表用 tooling_customers 替代 |

### 实际表结构差异

**quotes 表**:
- 设计: `quotes (1) -> (N) quote_items` (一对多)
- 实际: `quotes.part_id` 直接关联 (一对一)

**影响**: 
- **一个报价单无法包含多个零件**
- 如果客户询价 5 个零件，需要创建 5 个独立的 quotes 记录

**surface_treatments**:
- 设计: 独立表，多道工序多条记录
- 实际: `quotes.treatment_items` (JSONB) 单字段存储

**quote_tech_reviews**:
- 设计: 独立审核记录表，保留审核历史
- 实际: ❌ 不存在，可能没有审核历史追踪

---

## 实际数据库中未设计的表 (63 张)

### 重要的额外功能模块

#### 1. 高级仓库管理
```
✅ batch_transactions          - 批次交易
✅ material_transactions       - 材料交易
✅ inventory_transactions      - 库存交易
✅ manual_adjustments          - 手动调整
✅ remnant_inventory           - 余料库存
✅ finished_goods_inventory    - 成品库存
✅ finished_inventory          - 成品库存（另一个）
✅ sample_inventory            - 样品库存
```

#### 2. 工单与路由系统
```
✅ work_orders                 - 工单
✅ routing_tickets             - 路由票据
✅ routing_records             - 路由记录
✅ bom_routings                - BOM 路由
✅ assignments                 - 任务分配
```

#### 3. 发货与交付
```
✅ delivery_notes              - 发货单
✅ delivery_items              - 发货明细
✅ shipping_logs               - 发货日志
✅ pkg_shipping_logs           - 包装发货日志
✅ inbound_orders              - 入库订单
```

#### 4. 材料成本管理
```
✅ material_base_prices        - 材料基准价
✅ material_cost_history       - 材料成本历史
✅ treatment_cost_history      - 处理成本历史
```

#### 5. 设备管理
```
✅ equipments                  - 设备台账
✅ maintenance_logs            - 维修日志
```

#### 6. 喷涂管理
```
✅ spraying_recipes            - 喷涂配方
✅ spraying_logs               - 喷涂日志
✅ spraying_material_consumption - 喷涂材料消耗
```

**结论**: 实际系统包含**大量高级功能**，远超 data-model.md 的设计范围。

---

## 关键问题

### 问题 1: 设计文档的作用是什么？

**选项 A**: data-model.md 是"理想未来架构"
- 保持设计不变
- 将实际数据库视为"技术债务"
- 逐步重构到设计目标

**选项 B**: data-model.md 应描述"当前系统"
- 废弃设计文档
- 用 current-schema.md 替代
- 基于实际数据库讨论改进

**选项 C**: 双轨并行
- data-model.md = 目标架构
- current-schema.md = 当前状态
- 制定迁移路线图

### 问题 2: Part 实体组如何推进？

#### 场景 A: 如果采用设计文档

需要实现：
1. 创建 `price_accounts` 表（UUID 主键）
2. 创建 `annual_price_records` 表
3. 创建 `price_adjustments` 表
4. 迁移 `prices` 和 `price_years` 数据
5. 修改所有主键从 INTEGER 改为 UUID

**工作量**: 巨大，需要数据库重构。

#### 场景 B: 如果适配实际数据库

需要修改设计文档：
1. 所有主键改为 INTEGER
2. `price_accounts` 改名为 `prices`
3. `annual_price_records` 改名为 `price_years`
4. 补充实际存在的表（part_cost_snapshot 等）

**工作量**: 中等，主要是文档工作。

### 问题 3: 额外的 63 张表如何处理？

这些表代表**已实现的功能**：
- 高级仓库管理
- 工单路由系统
- 发货交付流程
- 材料成本追踪

**选项**:
1. 全部纳入设计文档（工作量大）
2. 仅文档化核心表，额外表标记为"扩展功能"
3. 创建独立的 extended-features.md

---

## 建议方案

### 推荐: 选项 C（双轨并行）

#### 第一步: 文档分层

```
📁 specs/001-erp-system-architecture/
├── spec.md                    (功能规格，保持不变)
├── data-model.md              (目标架构设计)
├── current-schema.md          (当前数据库结构)
├── migration-roadmap.md       (迁移路线图)
└── extended-features.md       (扩展功能说明)
```

#### 第二步: 明确各文档定位

| 文档 | 定位 | 维护策略 |
|------|------|---------|
| **data-model.md** | 规范化目标架构 | 保持设计理念，标注"目标状态" |
| **current-schema.md** | 实际生产结构 | 自动生成，反映真实情况 |
| **migration-roadmap.md** | 迁移计划 | 记录从当前到目标的路径 |
| **extended-features.md** | 扩展功能 | 描述额外 63 张表的用途 |

#### 第三步: Part 实体组推进策略

**短期（1-2 周）**: 基于实际数据库开发
- 使用 `prices` 和 `price_years` 表
- 主键使用 INTEGER
- 快速实现功能

**中期（1-3 个月）**: 局部重构
- 统一零件别名表（合并重复表）
- 实现 price_adjustments 功能
- 补充缺失索引

**长期（3-6 个月）**: 架构演进
- 评估 UUID 迁移的必要性
- 考虑规范化价格体系
- 重构报价单为一对多关系

---

## 下一步行动

### 立即执行

1. ✅ **已完成**: 生成 current-schema.md
2. **待办**: 检查 prices 和 price_years 表的详细字段
3. **待办**: 确认哪些别名表是当前使用的
4. **待办**: 检查是否有真实业务数据（决定迁移风险）

### 需要您决策

请回答以下问题：

**Q1**: 采用哪种方案？
- [ ] A. 保持设计，计划重构数据库
- [ ] B. 废弃设计，基于实际数据库开发
- [ ] C. 双轨并行（推荐）

**Q2**: Part 实体组开发基于哪个？
- [ ] A. data-model.md 设计（需要先重构数据库）
- [ ] B. 实际数据库（使用 prices/price_years）

**Q3**: 是否需要详细检查额外的 63 张表？
- [ ] A. 是，全部纳入文档
- [ ] B. 否，仅关注核心表
- [ ] C. 部分，仅文档化与 Part 相关的表

---

## 附录: 快速检查脚本

可运行以下脚本获取更多细节：

```bash
# 检查 prices 表结构
cd backend
python -c "
import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        host='124.222.29.229', port=5432,
        user='postgres', password='thehaoshi5DE',
        database='stamping_system'
    )
    
    # 检查 prices 表字段
    cols = await conn.fetch('''
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'prices'
        ORDER BY ordinal_position
    ''')
    
    print('prices 表字段:')
    for col in cols:
        print(f"  {col['column_name']}: {col['data_type']}")
    
    await conn.close()

asyncio.run(check())
"
```
