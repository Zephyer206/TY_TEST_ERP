-- 清理错误导入的客户数据
-- 删除ID=90 (60T 连续模) 和 ID=107 (可能的错误记录)

BEGIN;

-- 1. 先查看要删除的记录
SELECT id, name, sheet_key, created_at
FROM customers
WHERE id IN (90, 107)
ORDER BY id;

-- 2. 删除这些记录
-- 注意：这会级联删除相关的外键引用
DELETE FROM customers WHERE id = 90;  -- 60T 连续模
DELETE FROM customers WHERE id = 107; -- B-U  IT (如果确认是错误的)

-- 3. 验证删除结果
SELECT COUNT(*) as remaining_customers FROM customers;

COMMIT;

-- 如果需要回滚，运行: ROLLBACK;
