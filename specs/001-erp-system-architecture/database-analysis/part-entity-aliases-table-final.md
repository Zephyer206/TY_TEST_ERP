# part_customer_aliases 表最终设计

**决策日期**: 2026-07-04  
**表名**: part_customer_aliases（统一使用复数形式）

---

## 📋 表结构设计

### part_customer_aliases（客户件号别名）

```sql
CREATE TABLE part_customer_aliases (
    -- 主键
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联关系
    part_id                   UUID REFERENCES parts(id) NOT NULL,
    customer_id               UUID REFERENCES customers(id) NOT NULL,
    
    -- 客户件号信息
    customer_part_no          VARCHAR(100) NULL,           -- 客户零件编号
    customer_part_name        VARCHAR(200) NULL,           -- 客户零件名称（可选）
    
    -- 优先级标记（动态计算）
    -- is_primary 字段不存储，而是通过销售额/订单量动态判断
    
    -- 备注
    notes                     TEXT NULL,                   -- 备注说明
    
    -- 系统字段
    created_at                TIMESTAMP DEFAULT NOW(),
    updated_at                TIMESTAMP DEFAULT NOW(),
    
    -- 唯一约束
    CONSTRAINT uq_part_customer UNIQUE(part_id, customer_id)
);

-- 索引
CREATE INDEX idx_pca_part ON part_customer_aliases(part_id);
CREATE INDEX idx_pca_customer ON part_customer_aliases(customer_id);
CREATE INDEX idx_pca_customer_part_no ON part_customer_aliases(customer_part_no) 
    WHERE customer_part_no IS NOT NULL;

-- 注释
COMMENT ON TABLE part_customer_aliases IS '零件客户别名表 - 管理同一零件在不同客户处的件号和名称';
COMMENT ON COLUMN part_customer_aliases.customer_part_no IS '客户零件编号，客户自己的编号系统';
COMMENT ON COLUMN part_customer_aliases.customer_part_name IS '客户零件名称，可选，某些客户直接使用工厂名称';
COMMENT ON CONSTRAINT uq_part_customer ON part_customer_aliases IS '一个零件对一个客户只能有一个别名记录';
```

---

## 🎯 设计要点

### 1. 唯一约束

```sql
UNIQUE(part_id, customer_id)
```

**含义**: 一个零件对一个客户只能有一个别名记录

**业务场景**:
```
✅ 允许:
  零件A + 客户比亚迪 → 1条记录
  零件A + 客户吉利   → 1条记录
  零件B + 客户比亚迪 → 1条记录

❌ 禁止:
  零件A + 客户比亚迪 → 2条记录（重复）
```

---

### 2. 字段可空性

| 字段 | 可空 | 理由 |
|------|------|------|
| part_id | NOT NULL | 必须关联零件 |
| customer_id | NOT NULL | 必须关联客户 |
| customer_part_no | NULL | 某些客户可能没有自己的编号 |
| customer_part_name | NULL | 某些客户直接用工厂的零件名称 |

**示例**:
```sql
-- 场景1: 客户有自己的编号和名称
INSERT INTO part_customer_aliases (part_id, customer_id, customer_part_no, customer_part_name)
VALUES ('零件UUID', '比亚迪UUID', 'BYD-2024-001', '支架-左前');

-- 场景2: 客户只有编号，名称用工厂的
INSERT INTO part_customer_aliases (part_id, customer_id, customer_part_no, customer_part_name)
VALUES ('零件UUID', '吉利UUID', 'GEELY-X-99', NULL);

-- 场景3: 客户直接用工厂的编号和名称（仅记录关联关系）
INSERT INTO part_customer_aliases (part_id, customer_id, customer_part_no, customer_part_name)
VALUES ('零件UUID', '长城UUID', NULL, NULL);
```

---

### 3. 主要客户判断（动态计算）

**不存储 is_primary 字段，而是动态计算**

#### 方案：通过销售数据判断主要客户

```sql
-- 创建视图：计算每个零件的主要客户
CREATE VIEW part_primary_customers AS
SELECT 
    pca.part_id,
    pca.customer_id,
    c.name as customer_name,
    COALESCE(SUM(qi.annual_volume * qi.final_price), 0) as total_sales,
    ROW_NUMBER() OVER (
        PARTITION BY pca.part_id 
        ORDER BY COALESCE(SUM(qi.annual_volume * qi.final_price), 0) DESC
    ) as priority
FROM part_customer_aliases pca
JOIN customers c ON c.id = pca.customer_id
LEFT JOIN quotes q ON q.part_id = pca.part_id AND q.customer_id = pca.customer_id
LEFT JOIN quote_items qi ON qi.quote_id = q.id
WHERE q.nomination_status = 'confirmed'  -- 只计算已定点的报价
GROUP BY pca.part_id, pca.customer_id, c.name;

-- 查询主要客户（priority = 1）
SELECT * FROM part_primary_customers WHERE priority = 1;
```

#### 优点
- ✅ **数据真实**: 基于实际销售额，不是人为标记
- ✅ **自动更新**: 销售数据变化时自动重新计算
- ✅ **无需维护**: 不需要手动设置主要客户标志

#### API 使用
```python
# 获取零件的主要客户
async def get_part_primary_customer(part_id: UUID, db: AsyncSession):
    query = """
        SELECT customer_id, customer_name
        FROM part_primary_customers
        WHERE part_id = :part_id AND priority = 1
        LIMIT 1
    """
    result = await db.execute(text(query), {"part_id": part_id})
    return result.fetchone()
```

---

## 🔄 与实际数据库的处理

### 实际数据库情况

```
part_customer_aliases  (表1 - 复数)
part_customer_alias    (表2 - 单数)
part_aliases           (表3 - 通用别名)
```

### 统一方案

#### 步骤 1: 检查现有数据

```sql
-- 检查三个表的数据量
SELECT 
    'part_customer_aliases' as table_name, 
    COUNT(*) as row_count,
    COUNT(DISTINCT part_id) as distinct_parts
FROM part_customer_aliases
UNION ALL
SELECT 
    'part_customer_alias', 
    COUNT(*), 
    COUNT(DISTINCT part_id)
FROM part_customer_alias
UNION ALL
SELECT 
    'part_aliases', 
    COUNT(*), 
    COUNT(DISTINCT part_id)
FROM part_aliases;
```

#### 步骤 2: 数据迁移（如果有数据）

```sql
-- 创建新表
CREATE TABLE part_customer_aliases_new (
    -- 上面的完整定义
);

-- 合并数据（假设三个表结构类似）
INSERT INTO part_customer_aliases_new (
    id,
    part_id,
    customer_id,
    customer_part_no,
    customer_part_name,
    notes,
    created_at,
    updated_at
)
-- 从表1迁移
SELECT 
    id, part_id, customer_id, 
    customer_part_no, customer_part_name, 
    notes, created_at, updated_at
FROM part_customer_aliases
WHERE NOT EXISTS (
    SELECT 1 FROM part_customer_aliases_new 
    WHERE part_id = part_customer_aliases.part_id 
    AND customer_id = part_customer_aliases.customer_id
)
UNION ALL
-- 从表2迁移
SELECT 
    id, part_id, customer_id, 
    customer_part_no, customer_part_name, 
    notes, created_at, updated_at
FROM part_customer_alias
WHERE NOT EXISTS (
    SELECT 1 FROM part_customer_aliases_new 
    WHERE part_id = part_customer_alias.part_id 
    AND customer_id = part_customer_alias.customer_id
)
UNION ALL
-- 从表3迁移
SELECT 
    id, part_id, customer_id, 
    alias_no as customer_part_no,      -- 字段名可能不同
    alias_name as customer_part_name,  -- 需要映射
    NULL as notes,
    created_at, 
    NOW() as updated_at
FROM part_aliases
WHERE NOT EXISTS (
    SELECT 1 FROM part_customer_aliases_new 
    WHERE part_id = part_aliases.part_id 
    AND customer_id = part_aliases.customer_id
)
ON CONFLICT (part_id, customer_id) DO NOTHING;  -- 避免重复
```

#### 步骤 3: 清理旧表

```sql
-- 备份旧表（可选）
CREATE TABLE part_customer_aliases_backup AS SELECT * FROM part_customer_aliases;
CREATE TABLE part_customer_alias_backup AS SELECT * FROM part_customer_alias;
CREATE TABLE part_aliases_backup AS SELECT * FROM part_aliases;

-- 删除旧表
DROP TABLE IF EXISTS part_customer_alias CASCADE;
DROP TABLE IF EXISTS part_aliases CASCADE;
DROP TABLE IF EXISTS part_customer_aliases CASCADE;

-- 重命名新表
ALTER TABLE part_customer_aliases_new RENAME TO part_customer_aliases;
```

---

## 📊 业务场景示例

### 场景 1: 创建零件时关联客户

```sql
-- 1. 创建零件
INSERT INTO parts (id, part_number, part_name, status)
VALUES (gen_random_uuid(), 'ZJ-2024-001', '支架-A', 'draft')
RETURNING id;  -- 假设返回 'part-uuid-123'

-- 2. 关联客户（比亚迪）
INSERT INTO part_customer_aliases (
    part_id, 
    customer_id, 
    customer_part_no, 
    customer_part_name
)
VALUES (
    'part-uuid-123',
    '比亚迪-uuid',
    'BYD-2024-001',
    '支架-左前'
);
```

### 场景 2: 客户询价时查找零件

```sql
-- 客户说："我要询价 BYD-2024-001"
SELECT 
    p.id,
    p.part_number,
    p.part_name,
    pca.customer_part_no,
    pca.customer_part_name
FROM parts p
JOIN part_customer_aliases pca ON pca.part_id = p.id
WHERE pca.customer_part_no = 'BYD-2024-001'
  AND pca.customer_id = '比亚迪-uuid';
```

### 场景 3: 查看零件的所有客户

```sql
-- 查看"支架-A"卖给了哪些客户
SELECT 
    c.name as customer_name,
    pca.customer_part_no,
    pca.customer_part_name,
    -- 动态计算是否为主要客户
    CASE 
        WHEN ppc.priority = 1 THEN '主要客户'
        ELSE '普通客户'
    END as customer_type
FROM part_customer_aliases pca
JOIN customers c ON c.id = pca.customer_id
LEFT JOIN part_primary_customers ppc 
    ON ppc.part_id = pca.part_id 
    AND ppc.customer_id = pca.customer_id
WHERE pca.part_id = 'part-uuid-123'
ORDER BY COALESCE(ppc.priority, 999);  -- 主要客户排最前
```

### 场景 4: 报价时自动填充客户件号

```python
# API 端点：创建报价单
async def create_quote(
    part_id: UUID,
    customer_id: UUID,
    db: AsyncSession
):
    # 查询客户别名
    alias = await db.execute(
        select(PartCustomerAlias)
        .where(
            PartCustomerAlias.part_id == part_id,
            PartCustomerAlias.customer_id == customer_id
        )
    )
    alias = alias.scalar_one_or_none()
    
    # 创建报价单
    quote = Quote(
        part_id=part_id,
        customer_id=customer_id,
        customer_part_no=alias.customer_part_no if alias else None,
        # 自动填充客户件号
    )
    
    return quote
```

---

## ✅ 设计总结

### 最终设计特点

1. ✅ **统一表名**: part_customer_aliases（复数形式）
2. ✅ **唯一约束**: 一个零件对一个客户只有一个别名
3. ✅ **字段可选**: customer_part_no 和 customer_part_name 可为空
4. ✅ **动态主要客户**: 通过销售额计算，不存储固定标志
5. ✅ **清理旧表**: 删除重复的 part_customer_alias 和 part_aliases

### 与 parts 表的关系

```
parts (零件主表)
  ├── id: UUID
  ├── part_number: "ZJ-2024-001"
  └── part_name: "支架-A"
       ↓ 1:N
part_customer_aliases
  ├── {part_id, customer_id: 比亚迪, customer_part_no: "BYD-2024-001"}
  ├── {part_id, customer_id: 吉利,   customer_part_no: "GEELY-X-99"}
  └── {part_id, customer_id: 长城,   customer_part_no: "GW-H6-A01"}
```

---

## 📝 下一步

part_customer_aliases 表设计已完成，接下来讨论：

1. ✅ **parts** - 已完成
2. ✅ **part_name_dict** - 已实现
3. ✅ **part_customer_aliases** - 已完成
4. 🔄 **price_accounts** - 待讨论（核心表）
5. 🔄 **annual_price_records** - 待讨论
6. 🔄 **price_adjustments** - 待讨论

---

**决策完成时间**: 2026-07-04
