# Zephyr ERP 系统

冲压工厂企业资源管理系统 - 全流程数字化管理解决方案

---

## 📖 项目概述

Zephyr ERP 是一套面向冲压制造企业的综合性企业资源管理系统，覆盖从报价接单、模具开发、原料采购、生产执行、质量管控到包装出货的完整业务闭环。

### 核心特性

- ✅ **报价管理** - 从询价到定点的完整审批流程
- ✅ **生产管理** - 计划、排产、报工、机台调度
- ✅ **质量管控** - 首件检验、巡检、OQC 出货检验
- ✅ **仓库管理** - 原材料批次追踪、IQC、库存管理
- ✅ **模具管理** - 模具台账、维修、换模记录
- ✅ **权限体系** - 4 级权限 + 特殊权限系统

---

## 🚀 快速开始

### Windows 一键启动

项目根目录双击 `start-cloud.cmd`，等待显示 `READY` 后访问 `http://localhost:8080`；双击 `stop-cloud.cmd` 停止。首次运行需要 Python 3.11 或 3.12、Node.js 22+、网络连接和已配置的 `backend/.env`。启动器会准备依赖并构建前端，不会自动执行数据库迁移。部署、更新和故障排查详见 [Windows 部署指南](CLOUD_WINDOWS.md)。

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### 安装和运行

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m app.main

# 前端
cd frontend
npm install
npm run dev
```

详细安装步骤待补充；现有部署验证记录位于 `docs/` 目录。

---

## 📚 文档导航

**完整文档索引**: [DOCS_INDEX.md](DOCS_INDEX.md)

### 快速链接

| 文档 | 说明 |
|------|------|
| [功能规格](specs/001-erp-system-architecture/spec.md) | 业务需求和用户故事 |
| [数据模型](specs/001-erp-system-architecture/data-model.md) | 唯一权威数据库设计 |
| [API 契约](specs/001-erp-system-architecture/contracts/) | 接口定义 |
| [开发任务](specs/001-erp-system-architecture/tasks.md) | 任务清单 |
| [数据库分析](specs/001-erp-system-architecture/database-analysis/) | 当前数据库结构分析 |

---

## 🏗️ 项目结构

```
Zephyr_test_Erp/
├── README.md                    # 项目主文档（你在这里）
├── DOCS_INDEX.md                # 文档导航索引
├── main.py                      # 主入口
├── requirements.txt             # Python 依赖
│
├── backend/                     # 后端 FastAPI 应用
│   ├── app/                     # 应用代码
│   ├── migrations/              # 数据库迁移
│   └── *.py                     # 工具脚本
│
├── frontend/                    # 前端 Vue3 应用
│   ├── src/                     # 源代码
│   └── public/                  # 静态资源
│
├── specs/                       # 规格文档
│   └── 001-erp-system-architecture/
│       ├── spec.md              # 功能规格
│       ├── data-model.md        # 数据模型
│       ├── contracts/           # API 契约
│       └── database-analysis/   # 数据库分析
│
├── docs/                        # 其他文档
│   ├── screenshots/             # 界面截图
│   ├── archive/                 # 历史文档
│   └── CHANGELOG.md             # 变更日志
│
├── alembic/                     # 数据库迁移脚本
└── miniprogram/                 # 小程序（待开发）
```

---

## 🎯 开发状态

### 已完成 ✅

- ✅ 用户认证和权限系统
- ✅ 报价管理（含审批流程）
- ✅ 零件管理
- ✅ 客户管理
- ✅ 字典管理（零件名称、材料、模具类型）

### 进行中 🔄

- 🔄 生产计划和报工
- 🔄 质量管理
- 🔄 仓库管理

### 计划中 📝

- 📝 模具维修流转
- 📝 喷涂管理
- 📝 包装和发货
- 📝 数据分析和报表

详细进度请查看 [DOCS_INDEX.md](DOCS_INDEX.md)

---

## 🔧 技术栈

### 后端
- **框架**: FastAPI
- **数据库**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **迁移**: Alembic
- **认证**: JWT

### 前端
- **框架**: Vue 3 + TypeScript
- **UI 库**: Element Plus
- **状态管理**: Pinia
- **路由**: Vue Router
- **构建**: Vite

---

## 🤝 参与开发

### 新成员入门

1. 阅读 [功能规格](specs/001-erp-system-architecture/spec.md) 了解业务
2. 查看 [数据模型](specs/001-erp-system-architecture/data-model.md) 理解唯一权威架构
3. 浏览 [开发任务](specs/001-erp-system-architecture/tasks.md) 认领任务

### 开发流程

```
1. 查看需求 (spec.md)
   ↓
2. 查看设计 (data-model.md)
   ↓
3. 参考实际数据库 (database-analysis/)
   ↓
4. 实现功能
   ↓
5. 更新任务状态 (tasks.md)
```

---

## 📄 许可证

[待补充]

---

## 📞 联系方式

- **项目负责人**: [待填写]
- **技术支持**: [待填写]

---

**最后更新**: 2026-07-04
