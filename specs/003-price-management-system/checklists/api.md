# API 质量检查清单：Price Management System Backend

**Feature**: 003-price-management-system  
**Domain**: API Design & Requirements Quality  
**Created**: 2026-07-08

## 需求完整性

- [ ] CHK001 客户材料价格历史查询的响应格式是否完整定义（包含空历史情况的 suggested_price 字段）？[完整性, Spec §US1]
- [ ] CHK002 客户工序价格历史查询的快照字段（calc_mode_snapshot, unit_snapshot）是否在所有相关 API 响应中明确定义？[完整性, Spec §US3]
- [ ] CHK003 价格调整审批流程中，驳回后是否允许重新提交申请的需求是否已定义？[完整性, Gap]
- [ ] CHK004 数据迁移失败后的回滚流程是否有详细的步骤和验证标准？[完整性, Spec §US5]
- [ ] CHK005 所有 API 端点的错误响应格式（400/403/404/500）是否统一定义？[完整性, Gap]
- [ ] CHK006 审批流程中，审批人是申请人本人的情况下，系统行为是否已明确（允许或禁止）？[完整性, Spec §Edge Cases]

## 需求清晰性

- [ ] CHK007 "最近3次价格"的时间排序标准是否明确（按 quoted_at 降序还是 created_at）？[清晰性, Spec §FR-001]
- [ ] CHK008 "兜底值"的优先级逻辑是否清晰（customer_material_prices 为空时才使用 material_dict.default_price）？[清晰性, Spec §FR-013]
- [ ] CHK009 "工序字典变更"对历史记录的影响是否有具体示例说明（快照机制的作用）？[清晰性, Spec §US3]
- [ ] CHK010 "审批通过后价格自动更新"的时机是否精确定义（事务提交前还是提交后）？[清晰性, Spec §FR-010]
- [ ] CHK011 "材料单价"的单位（元/kg）是否在所有 API 文档中统一明确？[清晰性, Spec §FR-017]
- [ ] CHK012 "可并行执行"的任务在代码层面是否有数据库事务隔离的要求？[清晰性, Plan §Phase 2]

## 需求一致性

- [ ] CHK013 规格中"价格历史不允许删除"与 API 设计"只暴露 INSERT/SELECT"是否一致？[一致性, Spec §FR-016, Plan §Data Model]
- [ ] CHK014 数据模型中的 DECIMAL(10,4) 精度与 Pydantic schema 中的 Decimal 类型是否一致？[一致性, Spec §FR-017, Data Model]
- [ ] CHK015 审批状态机（pending → approved/rejected）在规格、数据模型和研究文档中的定义是否一致？[一致性, Spec §US6, Data Model, Research D1]
- [ ] CHK016 材料价格历史的"报价单ID可选"与"追溯定价来源"的需求是否一致（如何追溯补录的历史数据）？[一致性, Spec §FR-003, Data Model]
- [ ] CHK017 工序字典的 default_rate 与客户工序价格历史的 unit_price 字段语义是否清晰区分（默认参考 vs 实际成交）？[一致性, Data Model]

## 验收标准质量

- [ ] CHK018 "查询响应时间 < 2s"的性能标准是否定义了测量方法（P95、P99 还是平均值）？[验收标准, Spec §SC-001]
- [ ] CHK019 "单元测试覆盖率 80%+"的计算范围是否明确（仅服务层还是包含 API 层）？[验收标准, Spec §SC-005]
- [ ] CHK020 "数据迁移零停机时间"的验证标准是否具体（如何衡量"零停机"）？[验收标准, Spec §SC-002]
- [ ] CHK021 "审批操作 < 1s"的响应时间是否包含数据库事务提交时间？[验收标准, Spec §SC-003]
- [ ] CHK022 "50并发查询无性能降级"的"降级"阈值是否明确（响应时间增加多少算降级）？[验收标准, Spec §SC-004]

## 场景覆盖

- [ ] CHK023 是否覆盖了"同一客户同一材质在同一天多次报价"的场景及其查询排序逻辑？[场景覆盖, Spec §Edge Cases]
- [ ] CHK024 是否覆盖了"工序字典停用后，已有历史记录的工序如何展示"的场景？[场景覆盖, Spec §US8]
- [ ] CHK025 是否覆盖了"审批人在审批期间价格台账被其他方式修改"的并发冲突场景？[场景覆盖, Gap]
- [ ] CHK026 是否覆盖了"报价单删除后，关联的价格历史记录如何查询展示"的场景？[场景覆盖, Spec §Edge Cases]
- [ ] CHK027 是否覆盖了"材料字典中材质被软删除后，价格历史记录如何展示材质名称"的场景？[场景覆盖, Spec §Edge Cases]
- [ ] CHK028 是否覆盖了"数据迁移过程中服务正常运行"的零停机迁移场景？[场景覆盖, Spec §SC-002, Plan §Migration Strategy]

## 边界情况覆盖

- [ ] CHK029 客户ID或材质ID不存在时，API 返回空列表还是 404 错误的边界行为是否明确？[边界情况, Spec §Edge Cases, Research D6]
- [ ] CHK030 价格历史记录数超过 limit 参数上限（20条）时的行为是否定义？[边界情况, Spec §FR-001]
- [ ] CHK031 调价申请的 old_price 与 price_accounts 当前价格不一致时的验证逻辑是否定义？[边界情况, Gap]
- [ ] CHK032 审批申请时，price_account_id 对应的零件已被删除的情况是否处理？[边界情况, Gap]
- [ ] CHK033 迁移过程中 material_base_prices 与 material_dict 价格冲突的处理策略是否有详细规则？[边界情况, Research D3]
- [ ] CHK034 工序字典中 treatment_dicts 的测试脏数据识别白名单是否完整（10条真实工序名称）？[边界情况, Research D4, Data Model]
- [ ] CHK035 价格字段精度 DECIMAL(10,4) 的边界值（最大/最小值）是否在验证规则中定义？[边界情况, Spec §FR-017]

## 非功能性需求

- [ ] CHK036 价格历史查询的索引设计（customer_id, material_id, quoted_at DESC）是否覆盖所有查询场景？[性能, Data Model]
- [ ] CHK037 审批操作的事务隔离级别是否明确（READ COMMITTED 还是 SERIALIZABLE）？[并发控制, Research D5]
- [ ] CHK038 数据迁移脚本是否有幂等性要求（重复执行不会导致数据重复或错误）？[可靠性, Gap]
- [ ] CHK039 所有价格相关字段是否有 SQL 参数化查询要求（防止 SQL 注入）？[安全, Constitution VII]
- [ ] CHK040 审批流程的审计日志是否包含足够信息（申请人、审批人、时间戳、IP 地址）？[审计, Spec §SC-006]
- [ ] CHK041 API 响应是否有敏感信息过滤要求（如废料价、成本信息）？[安全, Gap]

## 依赖与假设

- [ ] CHK042 "现有 asyncpg 连接池配置足够支持新增查询"的假设是否有验证方法？[假设验证, Spec §Assumptions]
- [ ] CHK043 "报价单定点时触发价格历史记录写入"的集成点是否在其他模块的规格中明确？[依赖, Spec §Assumptions]
- [ ] CHK044 "material_base_prices 表有14行无脏数据"的假设是否有验证脚本？[假设验证, Spec §Assumptions]
- [ ] CHK045 "treatment_dicts 表28行中18行是测试脏数据"的识别标准是否可验证？[假设验证, Research D4]
- [ ] CHK046 "前端会提供价格历史查询界面"的依赖是否有明确的交付时间和接口契约？[依赖, Spec §Assumptions]
- [ ] CHK047 对现有 price_accounts API 的扩展是否会影响现有客户端（向后兼容性）？[依赖, Gap]

## 歧义与冲突

- [ ] CHK048 "价格调整审批只有三种状态"是否与未来可能的多级审批需求冲突？[歧义, Research D1]
- [ ] CHK049 "历史记录不允许删除"与 GDPR 数据删除权的合规要求是否有潜在冲突？[冲突, Spec §FR-016]
- [ ] CHK050 "审批通过自动更新价格"是否与"价格变更需要触发其他系统通知"的隐含需求冲突？[歧义, Gap]
- [ ] CHK051 "工序字典修改默认费率"对正在进行的报价流程的影响是否已明确？[歧义, Spec §US8]
- [ ] CHK052 "查询参数 limit 默认3最大20"的限制是否与财务审计需求（可能需要查看全部历史）冲突？[冲突, Research D2]

## 数据完整性

- [ ] CHK053 客户材料价格历史的外键约束（customer_id → customers, material_id → material_dict）是否在迁移脚本中正确定义？[数据完整性, Data Model]
- [ ] CHK054 价格调整审批的状态转换是否有数据库约束保证（CHECK 约束或触发器）？[数据完整性, Data Model]
- [ ] CHK055 工序价格历史的快照字段（calc_mode_snapshot, unit_snapshot）是否允许 NULL 值的语义是否明确？[数据完整性, Data Model]
- [ ] CHK056 迁移脚本的执行顺序依赖（001-007）是否有强制检查机制？[数据完整性, Plan §Migration Strategy]
- [ ] CHK057 价格历史记录的 quoted_at 和 created_at 字段是否有默认值和时区处理要求？[数据完整性, Data Model]

## 可追溯性

- [ ] CHK058 每条价格历史记录是否能追溯到具体的报价单（通过 quote_id）或补录操作（通过 created_by）？[可追溯性, Spec §FR-003, SC-006]
- [ ] CHK059 价格调整审批记录是否能追溯到具体的申请人和审批人（用户ID + 用户名称）？[可追溯性, Spec §US6]
- [ ] CHK060 数据迁移过程中的冲突和错误是否有日志记录机制？[可追溯性, Research D3, D4]
- [ ] CHK061 工序字典变更历史（修改默认费率、停用工序）是否有审计日志？[可追溯性, Gap]
- [ ] CHK062 价格台账批量查询的筛选条件和结果是否有审计日志（谁在什么时间查询了什么）？[可追溯性, Gap]

## 宪法符合性

- [ ] CHK063 所有数据库操作是否使用 asyncpg 而非 psycopg2（宪法 II）？[宪法符合性, Constitution II]
- [ ] CHK064 价格历史统计查询是否在 SQL 中完成聚合而非 Python 循环（宪法 III）？[宪法符合性, Constitution III]
- [ ] CHK065 所有 API 端点的权限检查是否使用 @require_role 装饰器而非内联判断（宪法 IV）？[宪法符合性, Constitution IV]
- [ ] CHK066 所有价格历史记录是否实现软删除（is_deleted 标记）而非物理删除（宪法 VII）？[宪法符合性, Constitution VII, Spec §FR-016]
- [ ] CHK067 数据迁移脚本是否避免了硬编码敏感信息（宪法 VII）？[宪法符合性, Constitution VII]

---

## 检查清单统计

- **总条目数**: 67
- **完整性**: 6 条
- **清晰性**: 6 条
- **一致性**: 5 条
- **验收标准质量**: 5 条
- **场景覆盖**: 6 条
- **边界情况覆盖**: 7 条
- **非功能性需求**: 6 条
- **依赖与假设**: 6 条
- **歧义与冲突**: 5 条
- **数据完整性**: 5 条
- **可追溯性**: 5 条
- **宪法符合性**: 5 条

## 使用方法

1. **规格审查时**: 在编写代码前，逐条检查规格文档是否满足质量标准
2. **PR 审查时**: 确认实现是否基于清晰、完整、一致的需求
3. **测试设计时**: 基于检查清单中的边界情况和场景设计测试用例
4. **迭代改进**: 未通过的检查清单项记录为技术债务，在后续迭代中补充

## 重点关注领域

- **数据完整性**: 价格历史记录的外键约束和审计完整性
- **边界情况**: 数据迁移冲突处理、并发审批冲突
- **性能**: 查询索引设计、事务隔离级别
- **宪法符合性**: asyncpg、SQL 聚合、@require_role、审计日志
