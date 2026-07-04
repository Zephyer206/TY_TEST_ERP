# 数据库工具脚本

常用的数据库检查和管理工具。

---

## 工具清单

### check_remote_db.py

**功能**: 检查远程 PostgreSQL 数据库连接和数据状态

**使用方法**:
```bash
cd backend
python scripts/tools/check_remote_db.py
```

**用途**:
- 验证数据库连接
- 检查表结构
- 查看示例数据
- 验证迁移状态

---

### inspect_cloud_schema.py

**功能**: 生成云端数据库的完整结构文档

**使用方法**:
```bash
cd backend
python scripts/tools/inspect_cloud_schema.py
```

**输出**: 
- `current-schema.md` - 完整的数据库结构文档
- 包含所有表、字段、索引、外键信息

**用途**:
- 生成数据库文档
- 对比设计与实际结构
- 定期更新数据库快照

---

## 配置

这些工具使用硬编码的数据库连接信息。如需修改，请编辑脚本中的连接参数。

**数据库连接**:
- Host: 124.222.29.229
- Port: 5432
- Database: stamping_system
- User: postgres

---

**最后更新**: 2026-07-04
