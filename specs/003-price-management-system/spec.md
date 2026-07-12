# Feature Specification: Price Management System Backend

**Feature Branch**: `003-price-management-system`

**Created**: 2026-07-08

**Status**: Draft

**Input**: 实现完整的价格管理系统后端。功能范围：1) customer_material_prices 表（客户材料价格历史）2) customer_treatment_prices 表（客户工序价格历史）3) price_accounts 表（价格台账）4) price_adjustments 表（调价记录带审批）。数据库结构只参考 `specs/001-erp-system-architecture/data-model.md`。需要：创建 Alembic 迁移脚本、实现完整 CRUD API（遵循项目现有风格）、迁移 material_base_prices 旧数据到新表后废弃、实现审批工作流逻辑、添加后端测试。

## User Scenarios & Testing

### User Story 1 - 查询客户材料历史价格（优先级：P1）

业务经理在为客户报价新零件时，需要参考该客户过往同材质的价格记录，以保持价格连续性和客户关系稳定。

**Why this priority**: 这是报价业务的核心依据，影响价格决策和客户满意度。缺少历史参考会导致价格混乱或客户流失。

**Independent Test**: 业务经理登录后，选择客户"比亚迪"和材质"SUS304"，系统返回最近3次成交价格及报价时间，业务经理据此确定新报价的材料单价。

**Acceptance Scenarios**:

1. **Given** 客户"比亚迪"在过去有3次 SUS304 材料的报价记录，**When** 业务经理查询该客户该材质的历史价格，**Then** 系统返回3条记录，按时间降序排列，包含单价、废料价、报价时间、关联报价单号
2. **Given** 客户"长城汽车"从未使用过材质"铝6061"，**When** 业务经理查询该客户该材质的历史价格，**Then** 系统返回空结果，并提示使用材料字典中的默认参考价
3. **Given** 某客户某材质有超过3次历史记录，**When** 查询时，**Then** 只返回最近3次，其余历史仍保留在数据库中供审计

---

### User Story 2 - 新增客户材料价格历史记录（优先级：P1）

业务经理在报价单定点后，需要将本次使用的材料单价记录到该客户的材料价格历史中，作为未来报价参考。

**Why this priority**: 历史记录的积累是价格决策的基础，必须在报价流程中自动或手动完成。

**Independent Test**: 业务经理创建一条报价单，材质为"SUS304"，单价为18.5元/kg，报价定点后，系统自动在 customer_material_prices 表中新增一条记录，关联该报价单ID和客户ID。

**Acceptance Scenarios**:

1. **Given** 报价单已定点，**When** 系统触发价格历史记录写入，**Then** customer_material_prices 表新增一条记录，包含客户ID、材质ID、单价、废料价、报价单ID、报价时间、创建人
2. **Given** 手动补录历史数据（无报价单），**When** 业务经理手动新增客户材料价格，**Then** 报价单ID字段为空，但其他必填字段完整
3. **Given** 同一客户同一材质在同一天有两次报价，**When** 两次报价的单价不同，**Then** 两条记录都保留，查询时按时间排序

---

### User Story 3 - 查询客户工序历史价格（优先级：P1）

业务经理在报价时，需要查询客户过往使用某工序（如电镀锌、喷涂）的价格记录，以确定本次工序报价。

**Why this priority**: 工序费用与材料成本同等重要，是报价计算的核心组成部分。

**Independent Test**: 业务经理选择客户"吉利汽车"和工序"电镀锌"，系统返回最近3次该工序的成交价格和计价方式快照。

**Acceptance Scenarios**:

1. **Given** 客户有该工序的历史记录，**When** 查询时，**Then** 返回最近3次，包含单价、计价方式快照、单位快照、报价时间、关联报价单号
2. **Given** 工序字典中某工序的计价方式从"按件"改为"按重量"，**When** 查询旧历史记录，**Then** 历史记录中的计价方式快照仍保持"按件"，不受字典表变更影响
3. **Given** 客户从未使用过该工序，**When** 查询时，**Then** 返回空结果，并提示使用工序字典中的默认费率

---

### User Story 4 - 新增客户工序价格历史记录（优先级：P1）

报价单中使用的工序费用需要记录到客户的工序价格历史中，供后续报价参考。

**Why this priority**: 工序价格的历史积累与材料价格同样重要，必须同步记录。

**Independent Test**: 报价单中包含"喷涂"工序，费用为2.5元/件，报价定点后，系统在 customer_treatment_prices 表中新增记录。

**Acceptance Scenarios**:

1. **Given** 报价单包含多个工序，**When** 定点后，**Then** 每个工序都生成一条 customer_treatment_prices 记录
2. **Given** 工序价格手动补录，**When** 创建时，**Then** 报价单ID为空，但必须快照当时的计价方式和单位
3. **Given** 同一工序在不同报价单中价格不同，**When** 记录时，**Then** 每条报价都独立记录，不覆盖

---

### User Story 5 - 数据迁移：废弃旧材料价格表（优先级：P1）

系统存在多张遗留的材料和工序价格表（material_base_prices、material_cost_history、treatment_dicts、treatment_cost_history），需要清理并迁移数据到新表结构。

**Why this priority**: 旧表结构混乱，有脏数据和重复字段，必须在新功能上线前完成迁移，避免数据源冲突。

**Independent Test**: 运行数据迁移脚本，material_base_prices 中的14行数据迁移到 material_dict，treatment_dicts 中的10条真实工序数据迁移到 treatment_dict，旧表删除，现有API不受影响。

**Acceptance Scenarios**:

1. **Given** material_base_prices 表有14行数据，**When** 运行迁移脚本，**Then** 按 material_name 匹配，补充到 material_dict 中缺失的材质，保留原有 default_price 和 scrap_price
2. **Given** treatment_dicts 表有28行数据，其中18行是测试脏数据，**When** 迁移时，**Then** 只迁移10条真实工序名称（热处理、电镀锌、发黑、喷涂等），丢弃测试数据
3. **Given** 迁移完成，**When** 删除旧表，**Then** material_base_prices、material_cost_history、treatment_dicts、treatment_cost_history 四张表不再存在
4. **Given** 迁移前材料API正常工作，**When** 迁移后，**Then** 材料API仍能正常查询和创建材料，数据完整性不受影响

---

### User Story 6 - 价格调整审批流程（优先级：P2）

业务经理提出零件价格调整申请（如材料涨价、工序费用变化），需要提交审批，老板审批通过后价格才生效。

**Why this priority**: 价格变动影响利润和客户关系，需要审批机制防止随意调价。这是价格台账功能的重要补充，但不阻塞基本价格查询。

**Independent Test**: 业务经理为某零件提交调价申请（从50元/件调至55元/件，原因：材料涨价10%），老板登录后看到待审批列表，审批通过，price_accounts 表中该零件的 current_price 更新为55元。

**Acceptance Scenarios**:

1. **Given** 业务经理提交调价申请，**When** 填写旧价格、新价格、调价原因，**Then** price_adjustments 表新增一条记录，状态为"待审批"
2. **Given** 调价申请待审批，**When** 老板查看审批列表，**Then** 显示所有待审批申请，包含零件名称、旧价格、新价格、申请人、申请时间、原因
3. **Given** 老板审批通过，**When** 点击"通过"，**Then** price_adjustments 状态改为"已通过"，price_accounts 表的 current_price 更新为新价格，记录审批人和审批时间
4. **Given** 老板驳回申请，**When** 填写驳回原因，**Then** price_adjustments 状态改为"已驳回"，price_accounts 价格不变，记录驳回人和驳回原因
5. **Given** 调价申请已审批（通过或驳回），**When** 查询时，**Then** 不显示在待审批列表中，但保留在历史记录中供审计

---

### User Story 7 - 价格台账批量查询和筛选（优先级：P2）

业务经理和财务需要查看所有零件的价格台账，支持按客户、零件名称、材质、价格区间筛选，以便分析价格分布和变化趋势。

**Why this priority**: 价格台账是价格管理的核心数据，批量查询和筛选是日常运营的基础需求，但不阻塞单条记录的创建和查询。

**Independent Test**: 业务经理打开价格台账列表，筛选客户为"比亚迪"，材质为"SUS304"，价格区间为40-60元/件，系统返回符合条件的所有零件价格记录。

**Acceptance Scenarios**:

1. **Given** 价格台账有100条记录，**When** 不加筛选条件查询，**Then** 返回全部记录，支持分页（每页20条）
2. **Given** 按客户筛选，**When** 选择"比亚迪"，**Then** 只返回该客户的零件价格记录
3. **Given** 按材质筛选，**When** 选择"SUS304"，**Then** 只返回该材质的零件价格记录
4. **Given** 按价格区间筛选，**When** 输入最小值40、最大值60，**Then** 只返回 current_price 在40-60之间的记录
5. **Given** 多条件组合筛选，**When** 同时指定客户、材质、价格区间，**Then** 返回同时满足所有条件的记录

---

### User Story 8 - 工序字典管理（优先级：P3）

系统管理员需要维护表面处理工序字典（treatment_dict），包括新增工序、修改默认费率、停用工序。

**Why this priority**: 工序字典是参考数据，变动频率低，优先级低于价格历史的核心查询和记录功能。

**Independent Test**: 管理员登录后，新增工序"达克罗涂装"，默认费率3.5元/件，计价方式"按件"，保存后该工序出现在工序下拉列表中。

**Acceptance Scenarios**:

1. **Given** 工序字典有10条记录，**When** 管理员新增工序，**Then** 工序名称唯一，默认费率和计价方式必填，保存后自动激活（is_active=true）
2. **Given** 某工序的费率需要调整，**When** 管理员修改默认费率，**Then** 只影响未来的报价参考，历史记录中的工序价格不变（因为已快照）
3. **Given** 某工序不再使用，**When** 管理员停用该工序，**Then** is_active 改为 false，该工序不再出现在新报价的工序下拉列表中，但历史记录中的该工序仍可查看
4. **Given** 工序的计价方式需要从"按件"改为"按重量"，**When** 管理员修改，**Then** 只影响未来的报价，已有的客户工序价格历史中的计价方式快照保持不变

---

### Edge Cases

- 当查询客户材料价格历史时，如果客户ID或材质ID不存在，系统返回404错误还是空列表？（假设：返回空列表，不报错，因为"没有历史"是合法业务状态）
- 当材料字典中某材质被删除（软删除），customer_material_prices 表中引用该材质ID的历史记录如何处理？（假设：历史记录保留，查询时显示材质ID，但材质名称显示为"已删除的材质"）
- 当报价单被删除（软删除），关联的 customer_material_prices 和 customer_treatment_prices 记录是否也删除？（假设：不删除，历史记录必须保留供审计，但报价单ID仍保留，查询时显示"关联报价已删除"）
- 当同一客户同一材质在同一秒内有两次报价，如何区分？（假设：允许重复，时间戳精确到毫秒，按创建时间排序）
- 当价格调整审批流程中，审批人是申请人本人怎么办？（假设：系统不限制，但在审计日志中记录，由人工监督）
- 当老板审批通过调价后，业务经理又修改了 price_accounts 的价格，审批记录和实际价格不一致怎么办？（假设：price_adjustments 表只记录审批历史，不强制与 price_accounts 同步，审计时以 price_adjustments 时间戳为准）
- 当工序字典中某工序的计价方式从"按件"改为"按重量"后，客户工序价格历史中快照的计价方式与当前字典不一致，报价时如何选择？（假设：始终以字典表当前值为准，历史快照仅用于审计）
- 当数据迁移过程中 material_dict 表已存在某材质，material_base_prices 中也有同名材质但价格不同，如何处理？（假设：不覆盖 material_dict 中的现有数据，只插入缺失的材质，记录冲突到迁移日志）

## Requirements

### Functional Requirements

- **FR-001**: 系统必须提供 customer_material_prices 表的 CRUD API，支持按客户ID和材质ID查询历史价格，默认返回最近3条，按报价时间降序排列
- **FR-002**: 系统必须提供 customer_treatment_prices 表的 CRUD API，支持按客户ID和工序ID查询历史价格，默认返回最近3条，按报价时间降序排列
- **FR-003**: 新增客户材料价格记录时，必须关联客户ID、材质ID、单价（unit_price），报价单ID（quote_id）可选，创建人和创建时间自动记录
- **FR-004**: 新增客户工序价格记录时，必须快照当时的计价方式（calc_mode_snapshot）和单位（unit_snapshot），避免字典表变更影响历史真实性
- **FR-005**: 数据迁移脚本必须将 material_base_prices 表中的14行数据迁移到 material_dict 表，按 material_name 匹配，只插入 material_dict 中不存在的材质
- **FR-006**: 数据迁移脚本必须清理 treatment_dicts 表，只迁移10条真实工序（热处理、电镀锌、发黑、喷涂、贴胶、阳极氧化、磷化、压铸镀层、电镀镍、达克罗涂装），丢弃测试脏数据
- **FR-007**: 数据迁移完成后，必须删除以下旧表：material_base_prices、material_cost_history、treatment_dicts、treatment_cost_history
- **FR-008**: 系统必须提供 price_adjustments 表的创建API，业务经理（role_level >= 5）提交调价申请，包含 price_account_id、old_price、new_price、reason、adjustment_type（上涨/下降）
- **FR-009**: 系统必须提供价格调整审批列表API，老板（role_level >= 9）查看所有待审批的调价申请，按申请时间倒序排列
- **FR-010**: 系统必须提供价格调整审批API，老板可以通过或驳回申请，通过时自动更新 price_accounts 表的 current_price，记录审批人和审批时间
- **FR-011**: 价格调整驳回时，必须填写驳回原因，price_accounts 价格不变，price_adjustments 状态改为"已驳回"
- **FR-012**: 系统必须提供 treatment_dict 表的 CRUD API，超级管理员（role_level >= 10）可以新增、修改、停用工序，修改默认费率和计价方式
- **FR-013**: 查询客户材料价格历史时，如果客户从未使用过该材质，系统返回空列表，并在响应中提示使用 material_dict 的 default_price 作为参考
- **FR-014**: 查询客户工序价格历史时，如果客户从未使用过该工序，系统返回空列表，并在响应中提示使用 treatment_dict 的 default_rate 作为参考
- **FR-015**: price_accounts 表的批量查询API必须支持按客户ID、零件ID、材质、价格区间（min_price、max_price）筛选，支持分页（page、page_size）
- **FR-016**: 所有价格历史记录（customer_material_prices、customer_treatment_prices）必须保留完整审计轨迹，不允许删除，只允许查询和新增
- **FR-017**: 所有涉及价格的字段（unit_price、current_price、old_price、new_price）必须使用 Decimal 类型，精度为 DECIMAL(10,4)
- **FR-018**: 所有API必须遵循项目现有风格，使用 async/await、Pydantic v2 schema、@require_role 权限装饰器、asyncpg + PostgreSQL

### Key Entities

- **customer_material_prices（客户材料价格历史）**: 记录每个客户每次报价中使用的材料单价，包含客户ID、材质ID、单价、废料价、报价单ID（可选）、报价时间、创建人、创建时间
- **customer_treatment_prices（客户工序价格历史）**: 记录每个客户每次报价中使用的工序费用，包含客户ID、工序ID、单价、计价方式快照、单位快照、报价单ID（可选）、报价时间、创建人、创建时间
- **treatment_dict（工序字典）**: 全局表面处理工序参考数据，包含工序名称、默认费率、计价方式（按件/按重量）、单位、是否激活、排序顺序
- **price_adjustments（价格调整审批记录）**: 记录所有价格调整申请，包含价格台账ID、旧价格、新价格、调价类型、原因、申请人、申请时间、审批状态、审批人、审批时间、驳回原因

## Success Criteria

### Measurable Outcomes

- **SC-001**: 业务经理在报价时，能在2秒内查询到客户的材料或工序历史价格（最近3条），查询响应时间 < 2s
- **SC-002**: 数据迁移脚本必须在5分钟内完成，零停机时间，现有材料API功能不受影响
- **SC-003**: 价格调整审批流程从申请到审批通过，系统响应时间 < 1s，price_accounts 价格更新实时生效
- **SC-004**: 所有价格历史API的并发查询支持至少50个并发请求，无性能降级
- **SC-005**: 所有API接口的单元测试覆盖率达到80%以上，包含正常流程和边界情况
- **SC-006**: 价格历史记录的审计完整性达到100%，任何价格变动都能追溯到具体报价单或调价申请

## Assumptions

- **数据库连接**: 假设现有 asyncpg 连接池配置足够支持新增的价格历史查询，无需调整连接数
- **权限模型**: 假设业务经理（role_level >= 5）有权查询和新增价格历史，老板（role_level >= 9）有权审批调价，超级管理员（role_level >= 10）有权管理工序字典
- **报价单集成**: 假设报价单定点时会触发价格历史记录的自动写入（需要在报价API中集成，但不在本功能范围内实现，由后续任务处理）
- **数据量级**: 假设 customer_material_prices 和 customer_treatment_prices 表在第一年内各有1000-5000条记录，查询性能设计按1万条记录优化
- **旧表状态**: 假设 material_base_prices 表有14行数据无脏数据，treatment_dicts 表有28行数据其中18行是测试脏数据（需清理）
- **测试环境**: 假设开发环境有独立的测试数据库，数据迁移脚本可以在测试库中验证后再应用到生产环境
- **审批流程**: 假设价格调整审批只有"待审批"、"已通过"、"已驳回"三种状态，不支持多级审批或审批撤回
- **前端集成**: 假设前端会提供价格历史查询界面和调价审批界面，但本功能只负责后端API，前端开发不在本范围内
- **软删除**: 假设价格历史记录和价格调整记录不支持删除（包括软删除），只支持查询和新增，保证审计完整性
