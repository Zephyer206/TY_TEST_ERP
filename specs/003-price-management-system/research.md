# Research & Design Decisions

**Feature**: Price Management System Backend  
**Date**: 2026-07-08  
**Status**: Complete

## Research Summary

本功能不维护独立数据库设计。数据库表结构只以 `specs/001-erp-system-architecture/data-model.md` 为准；本文仅记录技术研究和实施细节。

## Decision Log

### D1: 审批工作流状态机设计

**Question**: 价格调整审批流程需要几种状态？是否支持多级审批？

**Decision**: 使用三状态简单审批流（pending → approved/rejected），不支持多级审批

**Rationale**:
- 业务需求明确为"业务经理申请 → 老板审批"，只有两个角色参与
- 三状态足够覆盖所有场景：待审批（pending）、已通过（approved）、已驳回（rejected）
- 简化实现，避免过度设计（YAGNI原则）
- 如未来需要多级审批，可扩展状态机添加中间状态（如 pending_finance、pending_boss）

**Alternatives Considered**:
- ❌ 多级审批（pending_manager → pending_boss → approved）：当前业务不需要，增加复杂度
- ❌ 支持审批撤回：需求中未提及，审批记录应不可变（审计要求）
- ❌ 审批超时自动通过/驳回：业务上不合理，审批应由人工决策

**Implementation**:
```python
class ApprovalStatus(str, Enum):
    PENDING = "pending"      # 待审批
    APPROVED = "approved"    # 已通过
    REJECTED = "rejected"    # 已驳回
```

---

### D2: 价格历史查询默认返回条数

**Question**: 查询客户材料/工序价格历史时，默认返回最近几条？是否支持自定义？

**Decision**: 默认返回最近3条，支持通过查询参数 `limit` 自定义（最大20条）

**Rationale**:
- 规格中明确"查询时取最近3条作为报价参考"
- 3条记录足够展示价格趋势，避免信息过载
- 允许自定义 limit 提供灵活性（如财务需要查看更多历史）
- 限制最大20条防止性能问题和过度数据传输

**Alternatives Considered**:
- ❌ 固定返回3条，不可自定义：缺乏灵活性，财务或审计需要查看更多历史
- ❌ 返回全部历史：数据量大时性能差，前端渲染慢
- ❌ 分页查询：对于历史价格场景过于复杂，3-20条足够

**Implementation**:
```python
@router.get("/customer-prices/materials")
async def get_customer_material_prices(
    customer_id: int,
    material_id: int,
    limit: int = Query(default=3, ge=1, le=20),  # 默认3条，最大20条
    db: DbSession,
    current_user: CurrentUser
):
    ...
```

---

### D3: 数据迁移冲突处理策略

**Question**: material_base_prices 迁移到 material_dict 时，如果已存在同名材质但价格不同，如何处理？

**Decision**: 保留 material_dict 现有数据，只插入缺失的材质，冲突记录到迁移日志

**Rationale**:
- material_dict 是生产环境的真实数据源，已被现有API使用，不应覆盖
- material_base_prices 是遗留表，可能包含旧数据或测试数据
- 发生冲突说明数据源不一致，需要人工审查决策，不应自动覆盖
- 记录冲突到日志，便于后续人工核对和清理

**Alternatives Considered**:
- ❌ 覆盖 material_dict 中的现有数据：可能破坏生产数据，风险高
- ❌ 合并价格（如取平均值）：业务语义不明确，不应自动合并
- ❌ 迁移失败并回滚：过于严格，少量冲突不应阻塞整个迁移

**Implementation**:
```python
# 迁移脚本伪代码
async def migrate_material_base_prices():
    conflicts = []
    for row in material_base_prices:
        existing = await db.execute(
            select(MaterialDict).where(MaterialDict.name == row.material_name)
        )
        if existing:
            conflicts.append({
                "material_name": row.material_name,
                "base_price": row.default_price,
                "dict_price": existing.default_price
            })
            continue  # 跳过冲突，不插入
        
        # 插入缺失的材质
        await db.execute(insert(MaterialDict).values(...))
    
    # 记录冲突到日志
    if conflicts:
        logger.warning(f"Material price conflicts: {conflicts}")
        # 写入迁移报告文件
```

---

### D4: 工序字典清理白名单机制

**Question**: treatment_dicts 表有28行数据，其中18行是测试脏数据，如何识别和清理？

**Decision**: 使用白名单机制，只迁移明确的10条真实工序名称

**Rationale**:
- 测试数据混有 "RequestsTest_*"、"APIFlowTest_*"、"test_autocommit" 等明显的测试标识
- 真实工序名称是业务确定的固定列表（热处理、电镀锌、发黑、喷涂等）
- 白名单最安全，避免误删或误迁移
- 设计文档已明确列出10条真实工序名称

**Alternatives Considered**:
- ❌ 黑名单（排除 test_* 等）：可能遗漏其他测试数据模式
- ❌ 启发式规则（如名称长度 < 10）：不可靠，可能误删
- ❌ 保留全部数据，标记测试数据：保留脏数据污染生产环境

**Implementation**:
```python
REAL_TREATMENT_NAMES = [
    '热处理', '电镀锌', '发黑', '喷涂', '贴胶',
    '阳极氧化', '磷化', '压铸镀层', '电镀镍', '达克罗涂装'
]

async def migrate_treatment_dicts():
    for row in treatment_dicts:
        if row.name not in REAL_TREATMENT_NAMES:
            logger.info(f"Skipping test data: {row.name}")
            continue
        
        # 迁移真实工序
        await db.execute(insert(TreatmentDict).values(...))
```

---

### D5: 审批通过后价格更新的原子性

**Question**: 老板审批通过调价申请后，如何保证 price_adjustments 状态更新和 price_accounts 价格更新的原子性？

**Decision**: 使用数据库事务（async with session.begin()）包裹两个更新操作

**Rationale**:
- 审批通过和价格更新必须是原子操作，不能出现"审批通过但价格未更新"或反之
- PostgreSQL 事务保证 ACID 特性
- asyncpg + SQLAlchemy async 支持事务上下文管理器
- 符合宪法 VI（虽然本条针对定点写入，但原子性原则通用）

**Alternatives Considered**:
- ❌ 先更新 price_adjustments，再更新 price_accounts：中间可能失败，不原子
- ❌ 使用分布式事务（如 Saga）：过度设计，单体应用不需要
- ❌ 乐观锁 + 重试：增加复杂度，事务足够

**Implementation**:
```python
async def approve_price_adjustment(adjustment_id: int, approver_id: int, db: AsyncSession):
    async with db.begin():  # 事务开始
        # 1. 更新审批记录
        adjustment = await db.get(PriceAdjustment, adjustment_id)
        adjustment.status = ApprovalStatus.APPROVED
        adjustment.approved_by = approver_id
        adjustment.approved_at = datetime.utcnow()
        
        # 2. 更新价格台账
        price_account = await db.get(PriceAccount, adjustment.price_account_id)
        price_account.current_price = adjustment.new_price
        price_account.updated_at = datetime.utcnow()
        
        await db.commit()  # 事务提交，两个更新同时生效
```

---

### D6: 价格历史记录的兜底逻辑

**Question**: 查询客户材料价格历史时，如果没有历史记录，返回什么？

**Decision**: 返回空列表，并在响应中提供字段 `suggested_price` 包含 material_dict 的 default_price 作为参考

**Rationale**:
- 空列表明确表示"无历史记录"，语义清晰
- 不返回 404 错误，因为"无历史"是合法业务状态
- 提供 suggested_price 字段方便前端直接使用兜底值，减少额外请求
- 符合规格 FR-013 要求

**Alternatives Considered**:
- ❌ 返回 404：误导，暗示客户或材质不存在，实际是"无历史"
- ❌ 自动返回 default_price 作为历史记录：混淆真实历史和默认值
- ❌ 要求前端再查询 material_dict：增加请求次数，性能差

**Implementation**:
```python
@router.get("/customer-prices/materials")
async def get_customer_material_prices(...):
    # 查询历史记录
    history = await customer_price_service.get_material_price_history(...)
    
    if not history:
        # 查询兜底价格
        material = await db.get(MaterialDict, material_id)
        suggested_price = material.default_price if material else None
    else:
        suggested_price = None  # 有历史记录时不提供建议
    
    return {
        "history": history,
        "suggested_price": suggested_price,
        "message": "无历史记录，建议使用材料字典默认价格" if not history else None
    }
```

---

### D7: 工序价格历史的计价方式快照

**Question**: 为什么要快照工序的 calc_mode 和 unit，而材料价格不需要快照？

**Decision**: 工序的计价方式可能变化（如从"按件"改为"按重量"），快照保证历史真实性；材料单价的单位固定（元/kg），无需快照

**Rationale**:
- 工序字典中的 calc_mode 是可配置的，可能因业务变化调整
- 历史记录必须反映"当时是怎么算的"，不能被后续字典变更影响
- 材料单价的单位是行业标准（元/kg），不会变化，无需快照
- 符合设计文档中的解释："防止字典表后续变更影响历史真实性"

**Alternatives Considered**:
- ❌ 不快照，查询时 JOIN treatment_dict：历史记录会随字典变更而"改变"，失去审计意义
- ❌ 快照整个 treatment_dict 行：过度存储，只需快照影响价格解读的字段

**Implementation**:
```python
class CustomerTreatmentPrice(Base):
    ...
    unit_price = Column(Numeric(10, 4), nullable=False)
    calc_mode_snapshot = Column(String(20), nullable=True)  # 快照：manual / net_weight
    unit_snapshot = Column(String(20), nullable=True)        # 快照：元/件 / 元/kg
```

---

## Technical Constraints

- **asyncpg only**: 禁止使用 psycopg2（宪法 II）
- **SQL aggregation**: 所有统计必须在 SQL 中完成（宪法 III）
- **@require_role**: 权限检查必须使用装饰器（宪法 IV）
- **DECIMAL(10,4)**: 所有价格字段精度统一
- **No DELETE**: 历史记录只允许 INSERT 和 SELECT

## Performance Considerations

- **索引设计**:
  - customer_material_prices: `(customer_id, material_id, quoted_at DESC)`
  - customer_treatment_prices: `(customer_id, treatment_id, quoted_at DESC)`
  - price_adjustments: `(status, created_at DESC)` 用于待审批列表查询

- **查询优化**:
  - 默认 LIMIT 3，避免全表扫描
  - 使用 `ORDER BY quoted_at DESC` 利用索引排序
  - 审批列表查询使用 `WHERE status = 'pending'` 过滤

- **并发控制**:
  - 审批操作使用数据库事务保证原子性
  - 如需防止并发审批，可加行锁：`SELECT ... FOR UPDATE`

## Open Questions

**无待解决问题**。所有技术决策已完成，设计文档已定稿。

## References

- [data-model.md](../001-erp-system-architecture/data-model.md) - 唯一权威数据库设计
- [Constitution](../../.specify/memory/constitution.md) - 项目宪法
- [Existing price.py model](../../backend/app/models/price.py) - 现有价格模型
