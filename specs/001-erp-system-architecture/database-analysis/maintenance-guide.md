# current-schema.md 建立指南

**目标**: 为 Zephyr ERP 项目建立一份准确、可维护的当前数据库结构文档

---

## 一、为什么需要 current-schema.md？

### 当前问题

1. **data-model.md 与实际数据库严重不符**
   - 设计: 38 张表，UUID 主键
   - 实际: 90 张表，INTEGER 主键
   - 共同表仅 27 张 (71%)

2. **开发人员困惑**
   - 看设计文档写代码，发现表不存在
   - 看数据库写代码，不知道业务逻辑
   - 两套结构导致沟通成本高

3. **维护困难**
   - 数据库改了，文档没更新
   - 文档写了，数据库没实现
   - 不知道哪个是对的

### current-schema.md 的价值

| 场景 | 作用 |
|------|------|
| **新人入职** | 快速了解实际数据库结构，不被设计文档误导 |
| **代码开发** | 查询实际字段名、类型、外键关系 |
| **API 设计** | 基于真实表结构设计响应模型 |
| **数据迁移** | 对比历史版本，了解结构演进 |
| **问题排查** | 确认索引、约束是否存在 |

---

## 二、current-schema.md 的内容结构

### 推荐结构

```markdown
# Current Database Schema

**生成时间**: 2026-07-04 15:09:05
**数据库类型**: PostgreSQL 14
**数据库名**: stamping_system
**总表数**: 90

---

## 1. 概述

本文档描述 Zephyr ERP 系统**当前生产环境**的实际数据库结构。
该文档由自动化脚本生成，定期更新。

**重要提示**:
- ✅ 本文档反映真实数据库结构（以此为准）
- 📋 设计目标见 `data-model.md`
- 🔄 差异对比见 `SCHEMA_GAP_ANALYSIS.md`

---

## 2. 实体分组

### 2.1 User & Auth（用户与权限）

#### Table: users

**用途**: 用户账户表

**主键**: id (INTEGER)

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | INTEGER | ✗ | AUTO | 用户ID |
| username | VARCHAR(50) | ✗ | - | 登录用户名 |
| password | VARCHAR(100) | ✗ | - | 密码哈希 |
| real_name | VARCHAR(50) | ✓ | - | 真实姓名 |
| dept | VARCHAR(20) | ✗ | 'prod' | 部门代码 |
| role_level | INTEGER | ✓ | 1 | 权限等级 1-4 |
| is_tech | BOOLEAN | ✗ | false | 是否技术人员 |
| is_superadmin | BOOLEAN | ✓ | false | 是否超级管理员 |
| created_at | TIMESTAMP | ✓ | NOW() | 创建时间 |

**索引**:
- `users_username_key` (UNIQUE)

**外键**: 无

**业务规则**:
- role_level: 1=普通员工, 2=管理人员, 3=老板, 4=超管
- dept: 部门字符串（不是外键，设计文档中有独立 departments 表）

**已知问题**:
- ⚠️ 缺少 is_active 字段（设计中有）
- ⚠️ 缺少 special_permissions 字段（特殊权限系统未实现）
- ⚠️ 缺少 last_login_at 字段

---

### 2.2 Quote（报价）

#### Table: quotes

**用途**: 报价单主表（一个报价单对应一个零件）

**主键**: id (INTEGER)

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | INTEGER | ✗ | AUTO | 报价单ID |
| part_id | INTEGER | ✗ | - | 关联零件（一对一） |
| quote_serial | VARCHAR(50) | ✓ | - | 报价单号 |
| approval_status | VARCHAR(20) | ✗ | 'DRAFT' | 审批状态 |
| final_price | NUMERIC | ✓ | - | 最终单价 |
| ... | ... | ... | ... | ... |

**外键**:
- part_id → parts.id
- submitted_by → users.id
- approved_by → users.id

**重要差异**:
- ⚠️ 设计中是 quotes → quote_items (一对多)
- ⚠️ 实际是 quotes.part_id (一对一)
- ⚠️ 一个报价单只能包含一个零件

---

### 2.3 Part（零件与价格）

#### Table: parts

**用途**: 零件主表

**主键**: id (INTEGER，非 UUID)

...

#### Table: prices

**用途**: 零件价格台账（替代设计中的 price_accounts）

**主键**: id (INTEGER)

[字段待查询补充]

**关系**:
- 替代设计中的 `price_accounts` 表
- 配合 `price_years` 表实现年降功能

---

## 3. 表关系图

[可选：使用 Mermaid 或其他工具生成 ERD]

---

## 4. 索引清单

### 性能关键索引

| 表 | 索引名 | 字段 | 类型 | 用途 |
|----|--------|------|------|------|
| users | users_username_key | username | UNIQUE | 登录查询 |
| quotes | idx_quotes_part_id | part_id | INDEX | 零件报价查询 |
| ... | ... | ... | ... | ... |

---

## 5. 数据字典

### 枚举值说明

#### quotes.approval_status

| 值 | 含义 | 允许转换 |
|----|------|---------|
| DRAFT | 草稿 | → PENDING_BOSS |
| PENDING_BOSS | 待老板审批 | → APPROVED / REJECTED |
| APPROVED | 已审批 | → (定点确认) |
| REJECTED | 已驳回 | → DRAFT |

---

## 6. 变更历史

| 日期 | 版本 | 主要变更 |
|------|------|---------|
| 2026-07-04 | v1.0 | 初始版本，自动生成 |
| 2026-06-22 | - | 重构 part_name_dict 三级分类 |

---

## 附录A: 生成方法

本文档由 `inspect_cloud_schema.py` 自动生成。

更新命令:
\`\`\`bash
cd backend
python inspect_cloud_schema.py
\`\`\`

---

## 附录B: 与设计文档的差异

详见 `SCHEMA_GAP_ANALYSIS.md`。

快速对比:
- 设计表: 38 张
- 实际表: 90 张
- 主键: UUID → INTEGER
- Quote 结构: 一对多 → 一对一
```

---

## 三、建立 current-schema.md 的三种方法

### 方法 1: 自动化脚本生成（推荐）✅

**已完成**: `inspect_cloud_schema.py` 脚本

**优点**:
- ✅ 准确性高，直接读取数据库元数据
- ✅ 可重复执行，保持同步
- ✅ 包含所有表、字段、索引、外键

**缺点**:
- ❌ 缺少业务说明（字段用途、枚举值含义）
- ❌ 缺少变更历史

**改进建议**:
```python
# 在脚本中添加人工注释文件
# annotations.yaml:
tables:
  users:
    description: "用户账户表"
    fields:
      role_level:
        description: "权限等级"
        values:
          1: "普通员工"
          2: "管理人员"
          3: "老板"
          4: "超级管理员"
```

**使用流程**:
1. 运行脚本生成基础结构
2. 手工补充业务说明
3. 定期重新运行，合并人工注释

---

### 方法 2: 数据库文档工具

#### 选项A: SchemaSpy

```bash
# 安装
npm install -g schemaspy

# 生成文档
schemaspy -t pgsql \
  -host 124.222.29.229 \
  -port 5432 \
  -db stamping_system \
  -u postgres \
  -p thehaoshi5DE \
  -o ./docs/schema

# 生成 HTML 交互式文档
```

**优点**:
- ✅ 生成漂亮的 HTML 文档
- ✅ 自动生成 ERD 关系图
- ✅ 支持表关系可视化

**缺点**:
- ❌ 不是 Markdown 格式
- ❌ 需要额外工具

---

#### 选项B: pg_dump + 人工整理

```bash
# 导出 DDL
pg_dump -h 124.222.29.229 \
  -U postgres \
  -d stamping_system \
  --schema-only \
  -f current-schema.sql

# 手工转换为 Markdown
```

**优点**:
- ✅ 包含完整 DDL（约束、触发器）

**缺点**:
- ❌ 需要大量手工整理
- ❌ 不易维护

---

### 方法 3: 混合方式（最佳实践）⭐

**结合自动化 + 人工注释**:

```
1. 使用 inspect_cloud_schema.py 生成基础结构
   ↓
2. 创建 schema-annotations.yaml 补充业务说明
   ↓
3. 运行增强脚本合并两者
   ↓
4. 生成最终的 current-schema.md
```

**schema-annotations.yaml 示例**:
```yaml
version: "1.0"
last_updated: "2026-07-04"

tables:
  users:
    description: "用户账户表，管理系统所有用户的基本信息和权限"
    business_rules:
      - "用户名唯一，不可重复"
      - "role_level 决定基础权限，1-4 递增"
      - "dept 为字符串，未关联 departments 表"
    known_issues:
      - "缺少 is_active 字段，无法停用账户"
      - "缺少特殊权限系统"
    
  quotes:
    description: "报价单主表，一个报价单对应一个零件"
    business_rules:
      - "一对一关系：一个报价单只能包含一个零件"
      - "审批流程: DRAFT → PENDING_BOSS → APPROVED"
    design_difference:
      - "设计中是一对多关系 (quotes → quote_items)"
      - "实际简化为一对一 (quotes.part_id)"
```

---

## 四、维护策略

### 更新频率

| 变更类型 | 更新时机 | 执行人 |
|---------|---------|--------|
| **新增表** | 立即更新 | 开发人员 + 自动脚本 |
| **修改字段** | 立即更新 | 开发人员 + 自动脚本 |
| **新增索引** | 每周汇总 | DBA + 自动脚本 |
| **业务说明** | 每次迭代后 | 产品经理 + 开发负责人 |
| **完整重建** | 每月 1 日 | 自动定时任务 |

### 版本控制

```
current-schema.md           # 当前版本
archive/
  ├── current-schema-2026-06.md
  ├── current-schema-2026-05.md
  └── ...
```

### 变更日志

在文档末尾维护变更历史：

```markdown
## 变更历史

### 2026-07-04 (v1.0)
- 初始版本
- 90 张表，自动生成

### 2026-06-22
- 重构 part_name_dict，新增三级分类
- 新增字段: primary_category, secondary_category, customer_part_name
- 废弃字段: name, category
```

---

## 五、与其他文档的关系

### 文档体系

```
specs/001-erp-system-architecture/
├── spec.md                      [功能规格]
│   └── 描述"要做什么"
│
├── data-model.md                [目标设计]
│   └── 描述"理想结构"（规范化、UUID）
│
├── current-schema.md            [实际状态] ⭐
│   └── 描述"现在是什么样"（生产数据库）
│
├── SCHEMA_GAP_ANALYSIS.md       [差异分析]
│   └── 对比 data-model 和 current-schema
│
└── migration-roadmap.md         [迁移计划]
    └── 从 current 到 data-model 的路径
```

### 使用场景

| 场景 | 查阅文档 |
|------|---------|
| 了解业务需求 | spec.md |
| 设计新功能 | data-model.md |
| **编写代码** | **current-schema.md** ⭐ |
| API 开发 | current-schema.md |
| 数据库查询 | current-schema.md |
| 重构规划 | SCHEMA_GAP_ANALYSIS.md |
| 迁移实施 | migration-roadmap.md |

---

## 六、执行步骤

### 立即执行（今天）

1. ✅ **已完成**: 运行 `inspect_cloud_schema.py`，生成基础文档
2. **待办**: 检查生成的文档是否完整
3. **待办**: 补充核心表的业务说明（users, quotes, parts）
4. **待办**: 移动到正确位置: `specs/001-erp-system-architecture/current-schema.md`

### 本周完成

1. 创建 `schema-annotations.yaml`
2. 为前 10 个核心表添加详细注释
3. 运行增强脚本合并注释
4. 生成最终版 current-schema.md v1.0

### 长期维护

1. 设置 Git pre-commit hook，检测 migration 文件变化
2. 自动触发 `inspect_cloud_schema.py`
3. 提交时提醒开发人员更新 annotations.yaml
4. 每月自动生成归档版本

---

## 七、快速开始

### 检查当前生成的文档

```bash
# 查看已生成的文档
ls -lh backend/current-schema.md

# 查看表数量和分组
head -n 100 backend/current-schema.md
```

### 补充业务说明

1. 打开 `backend/current-schema.md`
2. 找到核心表（users, quotes, parts, prices）
3. 手动添加：
   - 表用途说明
   - 字段业务含义
   - 枚举值说明
   - 已知问题

### 移动到正确位置

```bash
# 移动文档
mv backend/current-schema.md \
   specs/001-erp-system-architecture/current-schema.md

# 提交版本控制
git add specs/001-erp-system-architecture/current-schema.md
git commit -m "docs: add current database schema documentation"
```

---

## 八、常见问题

### Q1: current-schema.md 和 data-model.md 冲突怎么办？

**A**: 不冲突，定位不同：
- data-model.md = 目标设计（理想状态）
- current-schema.md = 当前状态（现实情况）
- 开发时以 current-schema.md 为准
- 重构时参考 data-model.md

### Q2: 自动生成的文档太长（90 张表），如何简化？

**A**: 分文件：
```
current-schema/
├── README.md              # 概述和索引
├── core-tables.md         # 核心 20 张表（详细）
├── extended-tables.md     # 扩展表（简略）
└── deprecated-tables.md   # 废弃表
```

### Q3: 如何保持文档与数据库同步？

**A**: 三种方式：
1. 每次 migration 后手动运行脚本
2. Git hook 自动检测 migration 变化
3. CI/CD 定时任务每周更新

### Q4: 业务说明太多，如何维护？

**A**: 使用 YAML 注释文件：
- 结构化，易维护
- 版本控制
- 脚本自动合并

---

## 总结

### 推荐方案

1. ✅ **使用自动化脚本** (`inspect_cloud_schema.py`)
2. ✅ **创建注释文件** (`schema-annotations.yaml`)
3. ✅ **双轨并行**: data-model.md (目标) + current-schema.md (现状)
4. ✅ **定期更新**: 每次结构变更后运行脚本

### 立即行动

```bash
# 1. 检查生成的文档
cat backend/current-schema.md | head -n 50

# 2. 移动到正确位置
mv backend/current-schema.md specs/001-erp-system-architecture/

# 3. 补充核心表的业务说明（手工编辑）

# 4. 提交版本控制
git add specs/001-erp-system-architecture/current-schema.md
git commit -m "docs: add current database schema v1.0"
```
