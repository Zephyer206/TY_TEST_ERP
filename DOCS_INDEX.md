# 📚 Zephyr ERP 文档导航

欢迎来到 Zephyr 冲压工厂 ERP 系统的文档中心。

---

## 🗂️ 文档结构

```
Zephyr_test_Erp/
├── 📖 DOCS_INDEX.md                      ← 你在这里
├── 📋 README.md                          (项目介绍)
│
├── specs/                                (规格文档)
│   └── 001-erp-system-architecture/      (系统架构规格)
│       ├── 📘 spec.md                    (功能规格说明书)
│       ├── 📐 data-model.md              (目标数据模型设计)
│       ├── 📋 plan.md                    (实施计划)
│       ├── ✅ tasks.md                    (任务清单)
│       ├── contracts/                    (接口契约)
│       └── database-analysis/            (数据库分析)
│           ├── README.md                 (分析文档索引)
│           ├── current-schema.md         (实际数据库结构)
│           ├── gap-analysis.md           (差异对比分析)
│           └── maintenance-guide.md      (维护指南)
│
├── backend/                              (后端代码)
│   ├── app/                              (FastAPI 应用)
│   ├── migrations/                       (数据库迁移)
│   └── *.py                              (工具脚本)
│
└── frontend/                             (前端代码)
    └── src/                              (Vue3 源码)
```

---

## 🎯 快速导航

### 我想了解...

#### 业务需求和功能
👉 **[功能规格说明书](specs/001-erp-system-architecture/spec.md)**
- 用户故事和验收场景
- 功能需求 (FR-001 ~ FR-085)
- 成功标准和假设条件

#### 数据库设计（目标架构）
👉 **[数据模型设计](specs/001-erp-system-architecture/data-model.md)**
- 13 个实体组定义
- 表结构、字段、索引
- 状态转换和验证规则
- **这是我们的目标架构**

#### 当前数据库（实际状态）
👉 **[数据库分析文档](specs/001-erp-system-architecture/database-analysis/)**
- [current-schema.md](specs/001-erp-system-architecture/database-analysis/current-schema.md) - 云端实际表结构
- [gap-analysis.md](specs/001-erp-system-architecture/database-analysis/gap-analysis.md) - 设计 vs 实际差异
- **开发时作为参考**

#### API 接口契约
👉 **[接口契约目录](specs/001-erp-system-architecture/contracts/)**
- RESTful API 定义
- 请求/响应格式
- 认证和权限

#### 开发任务
👉 **[任务清单](specs/001-erp-system-architecture/tasks.md)**
- 按实体组划分的开发任务
- 依赖关系和优先级
- 完成状态追踪

---

## 📍 当前进度

### 已完成 ✅
- ✅ User & Auth 实体组设计
- ✅ Quote 实体组设计
- ✅ 报价单字段级权限矩阵
- ✅ 特殊权限系统设计
- ✅ 数据库现状分析

### 进行中 🔄
- 🔄 **Part 实体组设计讨论**（当前）
  - 零件主表
  - 价格台账
  - 年降管理
  - 客户件号别名

### 待办 📝
- ⬜ Tooling 实体组验证
- ⬜ Machine 实体组验证
- ⬜ Production 实体组验证
- ⬜ Warehouse 实体组验证
- ⬜ Quality 实体组验证
- ⬜ 其余实体组验证

---

## 🎓 新成员入门

### 第一次接触项目？

1. **了解业务**: 阅读 [spec.md](specs/001-erp-system-architecture/spec.md) 的"概述"和"用户场景"部分
2. **理解架构**: 查看 [data-model.md](specs/001-erp-system-architecture/data-model.md) 的实体关系图
3. **查看现状**: 浏览 [数据库分析](specs/001-erp-system-architecture/database-analysis/) 了解实际状态
4. **开始开发**: 查看 [tasks.md](specs/001-erp-system-architecture/tasks.md) 认领任务

### 开发流程

```
1. spec.md          → 了解要做什么功能
2. data-model.md    → 查看目标表结构设计
3. current-schema.md → 参考实际数据库情况
4. contracts/       → 确认 API 接口定义
5. 编写代码         → 实现功能
6. tasks.md         → 标记任务完成
```

---

## 📖 文档分类索引

### 规格与设计

| 文档 | 用途 | 受众 |
|------|------|------|
| [spec.md](specs/001-erp-system-architecture/spec.md) | 功能需求定义 | 产品、开发、测试 |
| [data-model.md](specs/001-erp-system-architecture/data-model.md) | 目标数据库设计 | 架构师、后端开发 |
| [plan.md](specs/001-erp-system-architecture/plan.md) | 实施计划 | 项目经理、团队 |
| [tasks.md](specs/001-erp-system-architecture/tasks.md) | 开发任务清单 | 开发团队 |

### 数据库分析

| 文档 | 用途 | 受众 |
|------|------|------|
| [current-schema.md](specs/001-erp-system-architecture/database-analysis/current-schema.md) | 实际数据库结构 | 后端开发、DBA |
| [gap-analysis.md](specs/001-erp-system-architecture/database-analysis/gap-analysis.md) | 设计与实际差异 | 架构师、技术负责人 |
| [maintenance-guide.md](specs/001-erp-system-architecture/database-analysis/maintenance-guide.md) | 文档维护方法 | 文档维护者 |

### 接口契约

| 文档 | 用途 | 受众 |
|------|------|------|
| [contracts/README.md](specs/001-erp-system-architecture/contracts/README.md) | 接口契约索引 | 前后端开发 |
| contracts/*.md | 各模块 API 定义 | 前后端开发 |

---

## 🔄 项目策略说明

### 开发方向

**主导方向**: 按 **data-model.md** 的目标设计实施
- ✅ 采用 UUID 主键
- ✅ 规范化表结构
- ✅ 完整的约束和索引

**参考对象**: **current-schema.md** 实际数据库
- 📋 了解已实现的功能
- 📋 参考命名和字段设计
- 📋 评估迁移策略

**执行方式**: 逐项验证推进
- 每个实体组对比设计与实际
- 决定新建/重构/迁移
- 制定数据迁移方案

---

## 🛠️ 常用命令

```bash
# 查看当前数据库结构
cd backend
python inspect_cloud_schema.py

# 启动后端服务
cd backend
python -m app.main

# 启动前端开发服务器
cd frontend
npm run dev

# 运行数据库迁移
cd backend
alembic upgrade head
```

---

## 📞 联系方式

- **项目负责人**: [待填写]
- **技术架构**: [待填写]
- **文档维护**: [待填写]

---

## 📝 更新日志

| 日期 | 更新内容 |
|------|---------|
| 2026-07-04 | 创建文档索引，整理数据库分析文档 |
| 2026-06-20 | 完成 User & Auth、Quote 实体组设计 |
| 2026-06-12 | 创建初始规格文档 |

---

**💡 提示**: 如果找不到需要的文档，请先查看各目录的 README.md 文件。
