# 📁 项目文件结构

**最后更新**: 2026-07-04

---

## 根目录结构

```
Zephyr_test_Erp/
│
├── 📄 主文档和配置
│   ├── README.md                    # 项目主文档
│   ├── DOCS_INDEX.md                # 文档导航索引
│   ├── main.py                      # 主入口程序
│   ├── requirements.txt             # Python 依赖清单
│   ├── package.json                 # Node.js 依赖清单
│   │
│   ├── .env                         # 环境变量配置
│   ├── .gitignore                   # Git 忽略规则
│   ├── .cursorrules                 # Cursor 编辑器规则
│   │
│   ├── Dockerfile                   # Docker 镜像配置
│   ├── docker-compose.yml           # Docker 编排配置
│   └── alembic.ini                  # 数据库迁移配置
│
├── 📂 源代码目录
│   ├── backend/                     # FastAPI 后端
│   │   ├── app/                     # 应用代码
│   │   │   ├── api/                 # API 路由
│   │   │   ├── models/              # 数据模型
│   │   │   ├── schemas/             # Pydantic 模式
│   │   │   ├── services/            # 业务逻辑
│   │   │   └── main.py              # 应用入口
│   │   │
│   │   ├── migrations/              # Alembic 迁移脚本
│   │   ├── tests/                   # 自动化测试
│   │   └── *.py                     # 工具脚本
│   │
│   ├── frontend/                    # Vue3 前端
│   │   ├── src/                     # 源代码
│   │   │   ├── views/               # 页面组件
│   │   │   ├── components/          # 通用组件
│   │   │   ├── router/              # 路由配置
│   │   │   ├── stores/              # Pinia 状态管理
│   │   │   └── main.ts              # 应用入口
│   │   │
│   │   ├── public/                  # 静态资源
│   │   └── vite.config.ts           # Vite 配置
│   │
│   ├── miniprogram/                 # 微信小程序（待开发）
│   └── mobile-h5/                   # H5 移动端（待开发）
│
├── 📚 文档目录
│   ├── specs/                       # 规格文档
│   │   └── 001-erp-system-architecture/
│   │       ├── spec.md              # 功能规格说明书
│   │       ├── data-model.md        # 目标数据模型
│   │       ├── plan.md              # 实施计划
│   │       ├── tasks.md             # 开发任务清单
│   │       │
│   │       ├── contracts/           # API 接口契约
│   │       │   ├── README.md
│   │       │   └── *.md             # 各模块接口定义
│   │       │
│   │       └── database-analysis/   # 数据库分析
│   │           ├── README.md        # 分析文档索引
│   │           ├── current-schema.md # 实际数据库结构
│   │           ├── gap-analysis.md  # 差异对比分析
│   │           ├── maintenance-guide.md # 维护指南
│   │           └── part-entity-discussion.md # Part 实体组讨论
│   │
│   └── docs/                        # 其他文档
│       ├── CHANGELOG.md             # 变更日志
│       │
│       ├── screenshots/             # 界面截图
│       │   ├── README.md
│       │   └── *.png                # 各模块截图
│       │
│       └── archive/                 # 历史归档文档
│           ├── README.md
│           └── *.md                 # 过时的设计文档
│
├── 🧪 测试目录
│   └── tests/
│       └── manual/                  # 手动测试脚本
│           ├── README.md
│           ├── test-*.js            # JavaScript 测试
│           └── *.py                 # Python 测试
│
├── 🗄️ 数据库迁移
│   └── alembic/                     # Alembic 迁移目录
│       ├── versions/                # 迁移版本脚本
│       └── env.py                   # 迁移环境配置
│
├── 🔧 工具脚本
│   └── scripts/                     # 各类工具脚本
│       ├── db_*.py                  # 数据库工具
│       └── init_db.py               # 数据库初始化
│
└── 📦 资源目录
    ├── static/                      # 静态文件
    └── uploads/                     # 上传文件存储
```

---

## 目录职责说明

### 源代码 (backend/, frontend/)
- 应用程序的核心代码
- 遵循模块化架构
- 包含单元测试

### 规格文档 (specs/)
- 产品需求和技术设计
- 版本化管理
- 每个功能一个独立目录

### 文档 (docs/)
- 开发文档、截图、历史记录
- 按类型分类存放
- 过时文档归档到 archive/

### 测试 (tests/)
- 手动测试脚本
- 自动化测试在各模块内部

### 配置文件（根目录）
- 项目级配置
- 环境配置
- 容器化配置

---

## 文件命名规范

### 文档文件
- `README.md` - 目录说明文档
- `UPPERCASE.md` - 重要的顶级文档
- `kebab-case.md` - 一般性文档

### 代码文件
- `snake_case.py` - Python 文件
- `kebab-case.ts/js` - TypeScript/JavaScript 文件
- `PascalCase.vue` - Vue 组件

### 测试文件
- `test_*.py` - Python 测试（自动化）
- `test-*.js` - JavaScript 测试（手动）
- `*.test.ts` - TypeScript 测试（自动化）

---

## 导航提示

**查找文档**: [DOCS_INDEX.md](DOCS_INDEX.md)
**项目介绍**: [README.md](README.md)
**规格文档**: [specs/001-erp-system-architecture/](specs/001-erp-system-architecture/)
**数据库分析**: [specs/001-erp-system-architecture/database-analysis/](specs/001-erp-system-architecture/database-analysis/)
