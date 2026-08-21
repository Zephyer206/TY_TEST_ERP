-- TWP 数据审计 SQL 查询集合
-- 日期: 2026-07-28
-- 用途: 快速检查 TWP 数据状态

-- ============================================================================
-- 1. 基础统计查询
-- ============================================================================

-- 1.1 Parts 表 TWP 统计
SELECT 
    COUNT(*) as total_parts,
    COUNT(thickness) as has_thickness,
    COUNT(width) as has_width,
    COUNT(pitch) as has_pitch,
    COUNT(spec_twph) as has_spec_twph,
    COUNT(CASE WHEN thickness IS NOT NULL AND width IS NOT NULL AND pitch IS NOT NULL THEN 1 END) as has_complete_twp
FROM parts
WHERE is_deleted = FALSE;

-- 1.2 Part_Tooling_Specs 表统计
SELECT 
    COUNT(*) as total_specs,
    COUNT(DISTINCT part_id) as distinct_parts,
    COUNT(DISTINCT tooling_id) as distinct_toolings,
    COUNT(CASE WHEN is_primary THEN 1 END) as primary_specs,
    COUNT(thickness) as has_thickness,
    COUNT(width) as has_width,
    COUNT(pitch) as has_pitch,
    COUNT(spec_twph) as has_spec_twph,
    COUNT(source_sheet) as has_source_sheet
FROM part_tooling_specs;

-- ============================================================================
-- 2. 问题检测查询
-- ============================================================================

-- 2.1 查找有 TWP 但无 part_tooling_specs 的零件
SELECT 
    p.id,
    p.part_number,
    p.internal_name,
    p.thickness,
    p.width,
    p.pitch,
    p.spec_twph
FROM parts p
LEFT JOIN part_tooling_specs pts ON pts.part_id = p.id
WHERE p.is_deleted = FALSE
  AND (p.thickness IS NOT NULL OR p.width IS NOT NULL OR p.pitch IS NOT NULL)
  AND pts.id IS NULL
ORDER BY p.id;

-- 2.2 查找有多个 spec 但无主规格的零件
SELECT 
    part_id,
    COUNT(*) as total_specs,
    COUNT(CASE WHEN is_primary THEN 1 END) as primary_count
FROM part_tooling_specs
GROUP BY part_id
HAVING COUNT(*) > 1 AND COUNT(CASE WHEN is_primary THEN 1 END) = 0
ORDER BY total_specs DESC;

-- 2.3 检查 is_primary 唯一性约束是否被违反
SELECT 
    part_id,
    tooling_id,
    COUNT(*) as primary_count
FROM part_tooling_specs
WHERE is_primary = TRUE
GROUP BY part_id, tooling_id
HAVING COUNT(*) > 1;

-- ============================================================================
-- 3. 数据分析查询
-- ============================================================================

-- 3.1 零件的 spec 数量分布
SELECT 
    spec_count,
    COUNT(*) as part_count
FROM (
    SELECT part_id, COUNT(*) as spec_count
    FROM part_tooling_specs
    GROUP BY part_id
) sub
GROUP BY spec_count
ORDER BY spec_count;

-- 3.2 is_primary 分布统计
SELECT 
    is_primary,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
FROM part_tooling_specs
GROUP BY is_primary;

-- 3.3 Source Sheet 来源统计
SELECT 
    source_sheet,
    COUNT(*) as count
FROM part_tooling_specs
WHERE source_sheet IS NOT NULL
GROUP BY source_sheet
ORDER BY count DESC
LIMIT 20;

-- 3.4 TWP 数值范围统计
SELECT 
    'part_tooling_specs' as source,
    MIN(thickness) as min_t, 
    MAX(thickness) as max_t, 
    ROUND(AVG(thickness)::numeric, 3) as avg_t,
    MIN(width) as min_w, 
    MAX(width) as max_w, 
    ROUND(AVG(width)::numeric, 3) as avg_w,
    MIN(pitch) as min_p, 
    MAX(pitch) as max_p, 
    ROUND(AVG(pitch)::numeric, 3) as avg_p
FROM part_tooling_specs
WHERE thickness IS NOT NULL

UNION ALL

SELECT 
    'parts' as source,
    MIN(thickness), 
    MAX(thickness), 
    ROUND(AVG(thickness)::numeric, 3),
    MIN(width), 
    MAX(width), 
    ROUND(AVG(width)::numeric, 3),
    MIN(pitch), 
    MAX(pitch), 
    ROUND(AVG(pitch)::numeric, 3)
FROM parts
WHERE is_deleted = FALSE AND thickness IS NOT NULL;

-- ============================================================================
-- 4. 特定问题深入分析
-- ============================================================================

-- 4.1 查看 24 个孤立零件的详细信息，包括关联的工装
SELECT 
    p.id as part_id,
    p.part_number,
    p.internal_name,
    p.thickness,
    p.width,
    p.pitch,
    tp.tooling_id,
    t.tooling_number,
    t.tooling_name,
    t.spec_twph as tooling_spec_twph
FROM parts p
LEFT JOIN part_tooling_specs pts ON pts.part_id = p.id
LEFT JOIN tooling_parts tp ON tp.part_id = p.id
LEFT JOIN tooling t ON t.id = tp.tooling_id
WHERE p.is_deleted = FALSE
  AND (p.thickness IS NOT NULL OR p.width IS NOT NULL OR p.pitch IS NOT NULL)
  AND pts.id IS NULL
ORDER BY p.id;

-- 4.2 查找只有 thickness 但没有 width/pitch 的规格
SELECT 
    pts.id,
    pts.part_id,
    pts.tooling_id,
    pts.thickness,
    pts.width,
    pts.pitch,
    pts.is_primary,
    pts.source_sheet,
    p.part_number
FROM part_tooling_specs pts
LEFT JOIN parts p ON p.id = pts.part_id
WHERE pts.thickness IS NOT NULL 
  AND pts.width IS NULL 
  AND pts.pitch IS NULL
ORDER BY pts.id DESC
LIMIT 20;

-- 4.3 查找有 part_tooling_specs 但 parts 表无 TWP 的零件
SELECT 
    p.id,
    p.part_number,
    p.internal_name,
    COUNT(pts.id) as spec_count,
    MAX(pts.thickness) as max_thickness,
    MAX(pts.width) as max_width,
    MAX(pts.pitch) as max_pitch
FROM parts p
INNER JOIN part_tooling_specs pts ON pts.part_id = p.id
WHERE p.is_deleted = FALSE
  AND p.thickness IS NULL 
  AND p.width IS NULL 
  AND p.pitch IS NULL
GROUP BY p.id, p.part_number, p.internal_name
ORDER BY spec_count DESC
LIMIT 20;

-- ============================================================================
-- 5. 采样查询
-- ============================================================================

-- 5.1 最新的 part_tooling_specs 记录
SELECT 
    pts.id,
    pts.part_id,
    pts.tooling_id,
    pts.thickness,
    pts.width,
    pts.pitch,
    pts.spec_twph,
    pts.is_primary,
    pts.source_sheet,
    p.part_number,
    p.internal_name
FROM part_tooling_specs pts
LEFT JOIN parts p ON p.id = pts.part_id
ORDER BY pts.id DESC
LIMIT 10;

-- 5.2 is_primary=FALSE 的记录采样
SELECT 
    pts.id,
    pts.part_id,
    pts.tooling_id,
    pts.thickness,
    pts.width,
    pts.pitch,
    pts.is_primary,
    pts.source_sheet,
    p.part_number
FROM part_tooling_specs pts
LEFT JOIN parts p ON p.id = pts.part_id
WHERE pts.is_primary = FALSE
ORDER BY pts.id DESC
LIMIT 10;
