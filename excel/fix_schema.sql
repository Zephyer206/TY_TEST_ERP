-- 数据库结构修正脚本
-- 将实际数据库调整为符合设计文档

-- =============================================
-- TOOLING 表修正
-- =============================================

-- 1. 重命名字段: mold_number -> tooling_no
ALTER TABLE tooling RENAME COLUMN mold_number TO tooling_no;

-- 2. 添加 name 字段（模具名称）
ALTER TABLE tooling ADD COLUMN name VARCHAR(200);

-- 3. 从parts表迁移数据到tooling.name（如果需要）
-- 注意：parts.internal_name 存储的是"本厂产品名称"
-- 可以选择性地将这些数据复制到tooling.name

-- 选项A：不迁移数据，保持name为NULL
-- （推荐，因为parts.internal_name已经包含此信息）

-- 选项B：从parts表复制第一个匹配的internal_name
/*
UPDATE tooling t
SET name = (
    SELECT p.internal_name
    FROM parts p
    WHERE p.mold_number = t.tooling_no
    LIMIT 1
)
WHERE t.name IS NULL;
*/

-- =============================================
-- 验证修改
-- =============================================

-- 检查tooling表结构
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'tooling'
ORDER BY ordinal_position;

-- 统计数据
SELECT
    COUNT(*) as total_tooling,
    COUNT(tooling_no) as has_tooling_no,
    COUNT(name) as has_name
FROM tooling;

-- =============================================
-- 说明
-- =============================================

/*
修改后的tooling表字段：
- tooling_no VARCHAR(NOT NULL) - 模具号（本厂产品编号）[重命名自mold_number]
- name VARCHAR(200 NULL) - 模具名称 [新增]
- customer_id INTEGER - 客户ID
- customer_product_no VARCHAR - 客户零件号
- customer_product_name VARCHAR - 客户产品名称
- mold_type VARCHAR - 模具类型
- cavity_count VARCHAR - 穴数
- material VARCHAR - 材质文本
- material_id INTEGER - 材质ID
- spec_twph VARCHAR - 用料规格
- press_tonnage VARCHAR - 冲床吨位
- remark TEXT - 备注
- ppap_no VARCHAR - PPAP编号
- vehicle_model VARCHAR - 车型
- seq INTEGER - 序号
- mold_count INTEGER - 模数
- forming_steps INTEGER - 成型步数
- is_multi_product BOOLEAN - 是否左右件
- product_count INTEGER - 产品数量
- cavity_status VARCHAR - 穴状态
- mold_status VARCHAR(NOT NULL) - 模具状态
- created_at TIMESTAMP - 创建时间
- updated_at TIMESTAMP - 更新时间
*/
