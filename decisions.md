# 价格管理系统 - 关键决策记录

**日期**: 2026-07-08  
**项目**: 003-price-management-system  
**决策者**: Claude Sonnet 5 (自主模式)

---

## 架构决策

### 1. 主键类型：INTEGER vs UUID
**决策**: 使用 INTEGER 主键  
**原因**: 
- 现有数据库使用 INTEGER（customers.id, parts.id, quotes.id 等）
- 设计文档使用 UUID 与实际不符
- 保持与现有代码一致性

**影响**: 所有新表（customer_material_prices, customer_treatment_prices, price_adjustments）都使用 INTEGER

---

### 2. 外键引用表名
**决策**: 使用实际表名 `tooling_customers` 而非 `customers`  
**原因**: 
- 实际数据库表名为 `tooling_customers`
- 虽然设计文档建议重命名，但迁移未完成
- 避免外键约束错误

**影响**: 所有 customer_id 引用 `tooling_customers(id)`

---

### 3. 数据迁移策略
**决策**: 白名单 + 冲突保护  
**原因**:
- treatment_dicts 表包含 18 条测试脏数据
- material_base_prices 可能与 material_dict 重复

**实施**:
- 工序迁移：只迁移 10 条真实工序（白名单）
- 材料迁移：按名称去重，保留 material_dict 现有数据

---

### 4. 计价方式快照
**决策**: customer_treatment_prices 记录快照字段  
**原因**:
- treatment_dict 的 calc_mode 和 unit 可能变更
- 历史价格解读需要当时的计价方式

**实施**: 添加 calc_mode_snapshot 和 unit_snapshot 字段

---

### 5. 审批工作流状态机
**决策**: 简单 3 状态（pending/approved/rejected）  
**原因**:
- 当前业务只需 2 级审批（经理 → 老板）
- 避免过度设计
- 未来可扩展多级审批

**状态转换**:
```
pending → approved (触发价格更新)
pending → rejected (记录驳回原因)
```

---

### 6. 价格历史查询默认值
**决策**: 默认返回最近 3 条，最大 20 条  
**原因**:
- 平衡可用性和性能
- 3 条足够业务参考
- 限制 20 条防止滥用

**兜底逻辑**: 无历史时返回字典默认值

---

### 7. 权限级别
**决策**: 
- 业务经理 (role_level >= 2): 查询、创建价格历史、申请调价
- 老板 (role_level >= 3): 审批调价
- 管理员 (role_level >= 4): 所有操作

**原因**: 遵循项目宪法 IV（RBAC 权限）

---

### 8. 测试策略
**决策**: TDD + 集成测试  
**原因**:
- 宪法要求 80%+ 覆盖率
- 价格数据敏感，需严格测试
- 审批流程需端到端验证

**测试类型**:
- 单元测试：服务层逻辑
- API 测试：路由和参数验证
- 集成测试：数据库操作
- E2E 测试：完整业务流程

---

### 9. 前端技术选型
**决策**: Vue 3 + Element Plus + 深色主题  
**原因**:
- 项目已使用 Vue 3 + Element Plus
- UI/UX Pro Max 推荐数据密集型深色主题
- 符合 ERP 系统特性

**设计系统**:
- 字体: Fira Code (代码/数字) + Fira Sans (文本)
- 配色: #0F172A (主色) + #22C55E (强调色)
- 布局: 数据密集型、多表格、KPI 卡片

---

### 10. 实施优先级
**决策**: 基础设施优先，然后 MVP（US1-US5）  
**原因**:
- 基础设施是阻塞依赖（表、模型、schemas）
- MVP 覆盖核心业务价值
- 用户要求早上看到可用功能

**完成状态**:
- ✅ Phase 1-2: 基础设施（19/19 任务）
- ⏳ Phase 3-7: MVP 业务逻辑（0/33 任务）
- ⏳ Frontend: UI 实现

---

## 技术债务

### 短期
1. pytest 未安装 - 需运行 `pip install pytest pytest-asyncio`
2. API 路由层未实现 - 需创建 3 个 API 文件
3. 前端页面未创建 - 需创建 3 个 Vue 组件

### 长期
1. customers 表重命名 - tooling_customers → customers
2. 多级审批扩展 - 当前只支持 2 级
3. 价格历史归档 - 超过 1 年的数据归档策略

---

## 风险与缓解

### 风险 1: 迁移脚本未测试
**影响**: 可能导致数据丢失或表创建失败  
**缓解**: 
- 所有迁移脚本包含 rollback 函数
- 建议先在测试环境运行
- 生产环境前备份数据库

### 风险 2: 前端未实现
**影响**: 用户无法通过界面使用功能  
**缓解**:
- 后端 API 可独立测试（Postman/curl）
- 设计系统已生成，前端实施有明确指南
- 优先实现 US1（查询价格历史）

### 风险 3: 测试覆盖率不足
**影响**: 可能存在未发现的 bug  
**缓解**:
- TDD 方法论（先写测试）
- 审批流程需重点测试（涉及事务）
- E2E 测试验证完整流程

---

## 下一步行动

**立即（0-1小时）**:
1. 运行数据库迁移脚本
2. 验证表结构和种子数据
3. 安装 pytest

**短期（1-4小时）**:
1. 实现 API 路由层（US1-US5）
2. 编写单元测试
3. 运行测试验证

**中期（4-8小时）**:
1. 创建前端页面
2. 应用设计系统
3. 集成后端 API
4. E2E 测试

---

**记录者**: Claude Sonnet 5  
**审查**: 待用户确认
