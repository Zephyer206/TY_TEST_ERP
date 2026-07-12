-- 清理错误导入的客户数据
-- 问题：Excel表头和分类标签被作为客户导入了

-- 1. 删除"60T 连续模"这种明显是表头/分类的记录
DELETE FROM customers
WHERE name LIKE '%连续模%'
   OR name LIKE '%T 模%'
   OR name LIKE '%吨%模%'
   OR sheet_key ~ '^[0-9]+T$';  -- 匹配类似 "60T", "80T" 的sheet_key

-- 2. 查看将要删除的记录（仅查询，不删除）
-- SELECT id, name, sheet_key
-- FROM customers
-- WHERE name LIKE '%连续模%'
--    OR name LIKE '%T 模%'
--    OR sheet_key ~ '^[0-9]+T$';

-- 3. 如果需要删除所有在某个日期之后导入的客户（假设错误导入发生在2026-07-11）
-- DELETE FROM customers WHERE created_at >= '2026-07-11' AND created_at < '2026-07-12';

-- 查看当前客户总数
SELECT COUNT(*) as total_customers FROM customers;

-- 查看包含异常关键字的客户
SELECT id, name, sheet_key, created_at
FROM customers
WHERE name LIKE '%连续模%'
   OR name LIKE '%T 模%'
   OR sheet_key ~ '^[0-9]+T$'
ORDER BY id;
