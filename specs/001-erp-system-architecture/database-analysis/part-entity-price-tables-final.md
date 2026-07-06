# price_accounts / price_adjustments 表最终设计

**决策日期**: 2026-07-06
**涉及表**: price_accounts（价格台账）、price_adjustments（调价流水）

---

## 一、决策汇总

| 决策点 | 问题 | 选择 | 说明 |
|-------|------|------|------|
| Q4.1 | 表名 | **price_accounts** | 保留"台账"语义，强调完整价格档案 |
| Q4.2 | 材料信息位置 | **两处都有** | parts 存基准值，price_accounts 可覆盖 |
| Q4.3 | 年降计算 | **手动批量调价** | current_price 为存储字段，人工触发 |
| Q4.3a | reduction_pct | **保留为参考值** | 批量调价时带出建议幅度 |
| Q4.3b | 批量筛选维度 | **客户/分类/材质/定点年份** | 多维度筛选 |
| Q4.3c | 批量调价机制 | **预览-确认-写库** | 批量操作需复核 |
| Q4.4 | 价格历史 | **独立 price_adjustments 表** | 删除 JSONB 快照 |
| Q5.1 | 估算vs实测 | **并排存储** | estimated + actual 双字段 |
| Q5.2 | 实测录入时机 | **首件填，量产可改** | 两阶段录入 |
| Q5.3 | 实测偏离处理 | **自动重算+标记复核** | 偏离报价时提示 |

---

## 二、核心概念：估算值 vs 实测值

冲压行业报价时重量/尺寸是估算值，量产后有实测值，两者存在差距。系统必须**分层留存，互不覆盖**：

| 层级 | 存储位置 | 值的性质 | 写入时机 | 用途 |
|------|---------|---------|---------|------|
| 报价估算值 | `quotes` | 估算快照 | 报价时 | 报价依据，永久不改 |
| 零件基准值 | `parts` | 定点标称值 | 定点确认时 | 零件标称参数 |
| 实测值 | `price_accounts` | 量产实测 | 首件/量产后 | 真实成本、结算 |

**关键规则**：
- quotes 的估算重量是快照，永远不动（历史凭证）
- parts 存定点时的标称值（定点那刻从报价拷入）
- price_accounts 同时存估算值和实测值，可对比差异

---

## 三、price_accounts 表设计

```sql
CREATE TABLE price_accounts (
    -- 主键
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 关联关系（一个零件对一个客户唯一）
    part_id                   UUID REFERENCES parts(id) NOT NULL,
    customer_id               UUID REFERENCES customers(id) NOT NULL,

    -- 材料信息（可覆盖 parts 的基准值）
    material                  VARCHAR(100) NULL,          -- 材质（为空则用 parts.material_type）

    -- 重量：估算值（从报价单带入，用于对比）
    estimated_net_weight_kg   DECIMAL(10,3) NULL,         -- 估算净重
    estimated_gross_weight_kg DECIMAL(10,3) NULL,         -- 估算毛重

    -- 重量：实测值（首件/量产后录入）
    actual_net_weight_kg      DECIMAL(10,3) NULL,         -- 实测净重
    actual_gross_weight_kg    DECIMAL(10,3) NULL,         -- 实测毛重
    actual_weight_source      VARCHAR(20) NULL,           -- 实测来源: first_piece/mass_production
    actual_weight_updated_at  TIMESTAMP NULL,             -- 实测更新时间
    actual_weight_updated_by  UUID REFERENCES users(id) NULL,

    -- 价格构成
    material_unit_price       DECIMAL(10,4) NULL,         -- 材料单价 (元/kg)
    scrap_price               DECIMAL(10,4) NULL,         -- 废料回收价 (元/kg)
    base_price                DECIMAL(10,4) NULL,         -- 基准单价 (元/件，定点时确定)
    current_price             DECIMAL(10,4) NULL,         -- 当前执行价（存储，手动调整）

    -- 年降参考（仅参考，不自动计算）
    reduction_pct             DECIMAL(5,2) NULL,          -- 合同年降率 (如 3.00 = 3%)
    price_year                INTEGER NULL,               -- 基准年份

    -- 成本偏离标记（Q5.3）
    cost_deviation_flag       BOOLEAN DEFAULT FALSE,      -- 实际成本偏离报价，建议复核
    cost_deviation_note       TEXT NULL,                  -- 偏离说明

    -- 状态
    notes                     TEXT NULL,
    is_active                 BOOLEAN DEFAULT TRUE,
    created_at                TIMESTAMP DEFAULT NOW(),
    updated_at                TIMESTAMP DEFAULT NOW(),

    CONSTRAINT uq_price_part_customer UNIQUE(part_id, customer_id)
);

CREATE INDEX idx_pa_part ON price_accounts(part_id);
CREATE INDEX idx_pa_customer ON price_accounts(customer_id);
CREATE INDEX idx_pa_material ON price_accounts(material) WHERE material IS NOT NULL;
CREATE INDEX idx_pa_price_year ON price_accounts(price_year) WHERE price_year IS NOT NULL;
CREATE INDEX idx_pa_deviation ON price_accounts(cost_deviation_flag) WHERE cost_deviation_flag = TRUE;

COMMENT ON TABLE price_accounts IS '价格台账 - 某零件卖给某客户的完整价格档案';
COMMENT ON COLUMN price_accounts.current_price IS '当前执行价，手动调整（非自动年降），下游开票/成本核算的权威来源';
COMMENT ON COLUMN price_accounts.estimated_net_weight_kg IS '报价估算净重，从报价单带入，用于与实测值对比';
COMMENT ON COLUMN price_accounts.actual_net_weight_kg IS '量产实测净重，首件检验录入，量产后可修正';
COMMENT ON COLUMN price_accounts.cost_deviation_flag IS '实测重量导致材料成本偏离报价，标记建议复核价格';
```

### 材料信息取值规则（Q4.2 = C）

查询零件的材质/重量时：
```
优先取 price_accounts 的值（客户特定），为空则回退 parts 的基准值
```

```sql
COALESCE(pa.material, p.material_type)              AS effective_material
COALESCE(pa.actual_net_weight_kg,                   -- 实测优先
         pa.estimated_net_weight_kg,                -- 其次估算
         p.net_weight)                              AS effective_net_weight
```

### 成本偏离自动标记逻辑（Q5.3 = A）

当实测重量录入或更新时：
```
新材料成本 = actual_net_weight_kg × material_unit_price - 废料 × scrap_price
报价材料成本 = estimated_net_weight_kg × material_unit_price - 废料 × scrap_price
若 |新成本 - 报价成本| / 报价成本 > 阈值（如 5%）:
    cost_deviation_flag = TRUE
    cost_deviation_note = "实测净重 {actual} 偏离估算 {estimated}，材料成本变化 {pct}%，建议复核价格"
```
`current_price` **不自动改**，仅打标记提示人工复核。

---

## 四、price_adjustments 表设计（调价流水）

```sql
CREATE TABLE price_adjustments (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 调价对象
    price_account_id          UUID REFERENCES price_accounts(id) NOT NULL,

    -- 调价内容
    old_price                 DECIMAL(10,4) NOT NULL,     -- 调整前
    new_price                 DECIMAL(10,4) NOT NULL,     -- 调整后（审批通过后才生效到 price_accounts.current_price）
    adjustment_type           VARCHAR(20) NOT NULL,       -- annual_reduction/manual/material_change
    adjustment_pct            DECIMAL(6,2) NULL,          -- 调整幅度百分比

    -- 批量调价关联
    batch_id                  UUID NULL,                  -- 同一批次的调价共享 batch_id，单品调价为 NULL
    batch_filter              JSONB NULL,                 -- 批量筛选条件快照

    -- 审批流程（Q4.3c 追加）
    approval_status           VARCHAR(20) NOT NULL DEFAULT 'pending_approval',
                                                            -- pending_approval/approved/rejected
    submitted_by               UUID REFERENCES users(id) NOT NULL,  -- 发起人（业务人员或老板）
    approved_by                UUID REFERENCES users(id) NULL,      -- 审批人（老板，role_level>=3）
    approved_at                 TIMESTAMP NULL,
    rejection_reason            TEXT NULL,                  -- 最近一次驳回原因，覆盖重写，不留历史

    -- 原因和审计
    reason                    TEXT NOT NULL,              -- 调价原因（发起人填写）
    adjusted_by               UUID REFERENCES users(id) NOT NULL,
    adjusted_at               TIMESTAMP DEFAULT NOW(),
    effective_date            DATE NULL                   -- 生效日期
);

CREATE INDEX idx_padj_account ON price_adjustments(price_account_id);
CREATE INDEX idx_padj_batch ON price_adjustments(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_padj_date ON price_adjustments(adjusted_at);
CREATE INDEX idx_padj_status ON price_adjustments(approval_status) WHERE approval_status = 'pending_approval';

COMMENT ON TABLE price_adjustments IS '调价流水 - 每次改价一条记录，支持单品和批量，需老板审批（老板本人操作除外）';
COMMENT ON COLUMN price_adjustments.batch_id IS '批量调价时同批共享，单品调价为 NULL';
COMMENT ON COLUMN price_adjustments.batch_filter IS '批量筛选条件快照，记录当时按什么条件筛选';
COMMENT ON COLUMN price_adjustments.approval_status IS '预览提交审批时落为 pending_approval，此时 price_accounts.current_price 尚未变动；approved 后才真正生效';
COMMENT ON COLUMN price_adjustments.rejection_reason IS '仅保留最近一次驳回意见，驳回后修改重提会覆盖此字段，不建独立历史表';
```

### 审批流程（Q4.3c 最终版）

```
① 发起人（业务人员 或 老板）设置筛选条件 + 调整方式
       ↓
② 系统生成预览清单（不落库，price_accounts 未变动）
       ↓
③ 提交审批：
   - 落库为 price_adjustments 记录，approval_status = pending_approval
   - 若发起人 role_level >= 3（老板本人）→ 跳过审批，直接进入④，approval_status 直接为 approved
       ↓ 老板审批（role_level >= 3）
   ┌── 通过 ──────────────┐    ┌── 驳回 ──────────────────┐
   │ approval_status =    │    │ approval_status = rejected │
   │ approved             │    │ rejection_reason = 老板填写 │
   │ 更新 price_accounts   │    │ 发起人修改后重新提交：       │
   │ .current_price        │    │ 复用同一条记录，                │
   │ approved_by/at 写入   │    │ approval_status 改回          │
   └──────────────────────┘    │ pending_approval，                │
                                 │ rejection_reason 被新驳回覆盖    │
                                 └──────────────────────────────┘
```

**权限规则**：
- 发起调价申请：仅业务人员 或 老板（role_level >= 3）。"业务人员"需结合 dept/岗位字段判断，不能仅用 role_level >= 2（避免班组长、技术人员等其他 level 2 岗位误获得权限），具体判断方式留待对照 User & Auth 实体组字段定义后在权限校验代码中实现。
- 审批调价申请：仅老板（role_level >= 3）。
- 老板本人发起 = 自动通过，不需要自我审批（与 quotes 报价审批的自我审批规则一致）。
- 驳回后复用原 price_adjustments 记录修改重提，不生成新 batch_id，驳回痕迹不单独留存历史表。

---

## 五、批量调价机制（Q4.3b + Q4.3c）

### 筛选维度（Q4.3b）
批量调价可按以下条件组合筛选目标 price_accounts：
- **按客户**：某客户所有零件统一调价
- **按零件分类**：part_name_dict 的某个类别
- **按材质**：所有 DC01 材质随钢价调整
- **按定点年份**：某年定点的零件集体年降

### 预览-确认-写库流程（Q4.3c）

```
1. 用户设置筛选条件 + 调整方式（按百分比 / 按固定额）
       ↓
2. 系统生成预览清单：
   ┌──────────┬────────┬────────┬────────┬────────┐
   │ 零件      │ 客户    │ 调前价  │ 调后价  │ 幅度   │
   ├──────────┼────────┼────────┼────────┼────────┤
   │ 支架-A    │ 比亚迪  │ 5.00   │ 4.85   │ -3%    │
   │ 支架-B    │ 比亚迪  │ 3.20   │ 3.10   │ -3%    │
   └──────────┴────────┴────────┴────────┴────────┘
   （reduction_pct 自动带出建议幅度）
       ↓
3. 人工复核，可剔除个别项
       ↓
4. 确认执行：
   - 更新 price_accounts.current_price
   - 每条生成 price_adjustments 记录（共享 batch_id）
```

---

## 六、表关系图

```
parts (零件物理属性，含基准材质/重量)
  │
  ├── 1:N → part_customer_aliases  (客户件号映射)
  │
  └── 1:N → price_accounts  (价格台账，可覆盖材质/重量)
                │
                └── 1:N → price_adjustments  (调价流水)

quotes (报价单，估算重量快照，永久不改)
  └── 定点确认 → 写入 parts.基准值 + price_accounts.estimated_*
```

---

## 七、数据流转全景

```
① 报价阶段
   quotes: 估算净重 0.150kg, 报价 ¥5.00/件
       ↓ 老板审批 + 定点确认
② 定点生成台账
   parts: net_weight = 0.150 (标称)
   price_accounts: estimated_net_weight = 0.150, base_price = 5.00, current_price = 5.00
       ↓ 首件检验
③ 录入实测
   price_accounts: actual_net_weight = 0.148 (source=first_piece)
   → 自动重算成本，偏离 <5%，不标记
       ↓ 量产后修正
④ 量产修正
   price_accounts: actual_net_weight = 0.155 (source=mass_production)
   → 成本偏离 +6% > 5%，cost_deviation_flag = TRUE
   → 提示："实测净重偏离估算，材料成本上升6%，建议复核价格"
       ↓ 人工决定调价
⑤ 调价申请（业务人员发起，单品或批量均需走审批）
   price_adjustments: 落库一条 (old=5.00, new=5.20, type=material_change,
                                approval_status=pending_approval, submitted_by=业务人员)
   → price_accounts.current_price 尚未变动
       ↓ 老板审批
   通过：approval_status=approved, approved_by=老板, approved_at=时间
        price_accounts.current_price 5.00 → 5.20
   驳回：approval_status=rejected, rejection_reason=老板填写
        发起人修改后复用同一条记录重新提交（回到 pending_approval，rejection_reason 被覆盖）

（例外：若发起人本身 role_level>=3，即老板本人操作，直接 approval_status=approved，
  跳过审批环节，current_price 立即生效）
```

---

## 八、决策状态：全部确认，Part 实体组价格部分收尾

| 决策点 | 结论 |
|-------|------|
| Q4.3a | 保留 reduction_pct 作为参考值（合同年降条款客户/零件不同，挂在 price_accounts 上） |
| Q4.3b | 四个筛选维度全支持：按客户/按零件分类/按材质/按定点年份 |
| Q4.3c | 预览-确认-写库，**并追加老板审批环节**（所有调价均需审批，老板本人操作直接生效） |
| 驳回痕迹 | 不单独建历史表，`rejection_reason` 覆盖重写，复用原记录重新提交 |

Part 实体组五张表全部收尾：
- ✅ parts
- ✅ part_name_dict
- ✅ part_customer_aliases
- ✅ price_accounts
- ✅ price_adjustments（替代 annual_price_records，年降并入调价流水，新增审批字段）

**注**: 原设计的 annual_price_records（年降记录表）在手动调价模式下不再需要，年降作为一种 adjustment_type 并入 price_adjustments。

**遗留技术债**：发起人权限判断"业务人员"依赖 dept/岗位字段，非纯 role_level，需在实现阶段对照 User & Auth 实体组的字段定义补充判断逻辑。
