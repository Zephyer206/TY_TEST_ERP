# 历史数据迁移脚本

本目录包含已完成的一次性数据迁移脚本，保留用于历史参考。

---

## 迁移记录

### 零件名称重构（2026-06-22）

- **fix_part_names.py** - 修复零件名称数据
- **refix_part_names.py** - 再次修复零件名称
- **update_part_names.py** - 更新零件名称结构
- **restructure_part_names.py** - 重构零件名称为三级分类
- **migration_restructure_part_name.py** - 执行零件名称迁移

**背景**: 将零件名称字典从单一 name 字段重构为三级分类结构（primary_category, secondary_category, customer_part_name）

---

### 字典表迁移（2026-06-22）

- **migrate_dict_tables.py** - 迁移字典表数据
- **migrate_remote_db.py** - 迁移远程数据库

**背景**: 同步本地和远程数据库的字典表数据

---

### 测试工具

- **test_api_direct.py** - API 直接测试工具

---

## ⚠️ 重要提示

**这些脚本已完成任务，不应再次运行。**

如果需要类似的迁移操作，请：
1. 参考这些脚本的逻辑
2. 创建新的迁移脚本
3. 在测试环境验证后再运行

---

**归档日期**: 2026-07-04
