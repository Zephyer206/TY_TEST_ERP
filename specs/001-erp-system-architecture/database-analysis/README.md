# Database Analysis Documentation

本目录包含 Zephyr ERP 数据库的分析文档。

---

## 📁 文档清单

### [current-schema.md](current-schema.md)
**当前云端数据库的实际结构**
- 90 张表的完整定义
- 字段、类型、索引、外键
- 自动生成，反映真实状态
- **用途**：开发时查询实际表结构作为参考

### [gap-analysis.md](gap-analysis.md)
**设计文档与实际数据库的差异对比**
- 逐个实体组对比分析
- 缺失表、额外表清单
- Part 实体组详细差异
- 影响评估和迁移建议
- **用途**：了解设计与现实的差距

### [maintenance-guide.md](maintenance-guide.md)
**current-schema.md 的维护指南**
- 如何生成和更新文档
- 三种建立方法对比
- 维护策略和最佳实践
- **用途**：定期更新实际数据库文档

### Part 实体组设计文档
- [part-entity-parts-table-final.md](part-entity-parts-table-final.md) — parts / part_name_dict
- [part-entity-aliases-table-final.md](part-entity-aliases-table-final.md) — part_customer_aliases
- [part-entity-price-tables-final.md](part-entity-price-tables-final.md) — price_accounts / price_adjustments
- [material-treatment-price-history-final.md](material-treatment-price-history-final.md) — material_dict / treatment_dict / 客户材料&工序价格历史

---

## 🎯 项目策略

### 开发方向

**主导**: data-model.md（目标设计，规范化架构）
- 使用 UUID 主键
- 规范化表结构
- 按设计实施新功能

**参考**: current-schema.md（实际数据库）
- 了解已实现的功能
- 参考命名和字段设计
- 避免与现有表冲突

**执行**: 逐项验证推进
- 每个实体组对比分析
- 决定保留/重构/新建
- 数据迁移计划

---

## 📊 当前状态

| 实体组 | 设计状态 | 实际状态 | 下一步 |
|-------|---------|---------|--------|
| User & Auth | ✅ 已设计 | 🟡 部分实现 | 补齐特殊权限系统 |
| Quote | ✅ 已设计 | 🟡 简化版 | 讨论一对多 vs 一对一 |
| **Part（含材料/工序价格）** | ✅ 已设计 | 🟡 替代方案 | ✅ **讨论完成** |
| Tooling | ✅ 已设计 | 🟢 已实现 | 待验证 |
| Machine | ✅ 已设计 | 🟢 已实现 | 待验证 |
| Production | ✅ 已设计 | 🟢 已实现 | 待验证 |
| Quality | ✅ 已设计 | 🟢 已实现 | 待验证 |
| Warehouse | ✅ 已设计 | 🟢 增强版 | 待验证 |

---

## 🔄 更新频率

- **current-schema.md**: 每次数据库结构变更后运行脚本更新
- **gap-analysis.md**: 每完成一个实体组讨论后更新
- **maintenance-guide.md**: 维护流程变化时更新

---

## 🛠️ 快速命令

```bash
# 更新 current-schema.md
cd backend
python inspect_cloud_schema.py

# 移动到正确位置
mv current-schema.md ../specs/001-erp-system-architecture/database-analysis/
```
