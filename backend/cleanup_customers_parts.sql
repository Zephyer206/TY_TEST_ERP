-- 清空客户和零件数据
-- 执行此脚本将删除所有客户和零件相关数据

BEGIN;

-- 1. 清空生产相关
DELETE FROM production_reports;
DELETE FROM production_sessions;
DELETE FROM production_plans;
DELETE FROM plan_machine_assignments;
DELETE FROM process_flow_cards;

-- 2. 清空报价单
DELETE FROM quotes;

-- 3. 清空零件相关
DELETE FROM part_aliases;
DELETE FROM part_customer_aliases;
DELETE FROM part_cost_snapshot;
DELETE FROM bom_routings;
DELETE FROM sample_tasks;
DELETE FROM tooling_parts;

-- 4. 清空价格相关（保留工序字典）
DELETE FROM customer_material_prices;
DELETE FROM customer_treatment_prices;
DELETE FROM price_adjustments;

-- 5. 清空零件主表
DELETE FROM parts;

-- 6. 重置序列
ALTER SEQUENCE parts_id_seq RESTART WITH 1;
ALTER SEQUENCE quotes_id_seq RESTART WITH 1;
ALTER SEQUENCE production_plans_id_seq RESTART WITH 1;

-- 7. 验证结果
SELECT 'parts' as table_name, COUNT(*) as count FROM parts
UNION ALL
SELECT 'quotes', COUNT(*) FROM quotes
UNION ALL
SELECT 'customer_material_prices', COUNT(*) FROM customer_material_prices
UNION ALL
SELECT 'customer_treatment_prices', COUNT(*) FROM customer_treatment_prices;

COMMIT;

-- 完成
SELECT '✓ Data cleanup completed!' as status;
