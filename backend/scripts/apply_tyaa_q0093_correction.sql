-- Direct correction for TYAA-Q0093 left-right parts
-- This script fills in the shared material and thickness values

BEGIN;

-- Show current state
SELECT 'BEFORE UPDATE:' as stage;
SELECT
    p.id,
    p.internal_name,
    p.thickness,
    p.width,
    p.pitch,
    p.part_position,
    t.tooling_number,
    tp.position as tooling_position,
    eir.parsed_material
FROM parts p
JOIN tooling_parts tp ON tp.part_id = p.id
JOIN tooling t ON t.id = tp.tooling_id
LEFT JOIN excel_import_rows eir ON eir.resolved_part_id = p.id
WHERE t.tooling_number LIKE 'TYAA-Q0093%'
ORDER BY t.tooling_number;

-- Update staging: parse "0.4*" as thickness=0.4 for left part
UPDATE excel_import_rows
SET parsed_thickness = 0.4
WHERE parsed_tooling_number = 'TYAA-Q0093-1'
  AND parsed_thickness IS NULL;

-- Update staging: propagate material to right part
UPDATE excel_import_rows eir_right
SET parsed_material = (
    SELECT parsed_material
    FROM excel_import_rows eir_left
    WHERE eir_left.parsed_tooling_number = 'TYAA-Q0093-1'
    LIMIT 1
)
WHERE eir_right.parsed_tooling_number = 'TYAA-Q0093-2'
  AND eir_right.parsed_material IS NULL;

-- Update staging: propagate thickness to right part
UPDATE excel_import_rows eir_right
SET parsed_thickness = (
    SELECT parsed_thickness
    FROM excel_import_rows eir_left
    WHERE eir_left.parsed_tooling_number = 'TYAA-Q0093-1'
    LIMIT 1
)
WHERE eir_right.parsed_tooling_number = 'TYAA-Q0093-2'
  AND eir_right.parsed_thickness IS NULL;

-- Update staging: set positions
UPDATE excel_import_rows
SET parsed_position = 'left'
WHERE parsed_tooling_number = 'TYAA-Q0093-1'
  AND parsed_position IS NULL;

UPDATE excel_import_rows
SET parsed_position = 'right'
WHERE parsed_tooling_number = 'TYAA-Q0093-2'
  AND parsed_position IS NULL;

-- Update parts: set thickness for both parts
UPDATE parts p
SET thickness = 0.4, updated_at = NOW()
FROM tooling_parts tp
JOIN tooling t ON t.id = tp.tooling_id
WHERE p.id = tp.part_id
  AND t.tooling_number LIKE 'TYAA-Q0093%'
  AND p.thickness IS NULL;

-- Update parts: set positions
UPDATE parts p
SET part_position = 'left', updated_at = NOW()
FROM tooling_parts tp
JOIN tooling t ON t.id = tp.tooling_id
WHERE p.id = tp.part_id
  AND t.tooling_number = 'TYAA-Q0093-1'
  AND p.part_position IS NULL;

UPDATE parts p
SET part_position = 'right', updated_at = NOW()
FROM tooling_parts tp
JOIN tooling t ON t.id = tp.tooling_id
WHERE p.id = tp.part_id
  AND t.tooling_number = 'TYAA-Q0093-2'
  AND p.part_position IS NULL;

-- Update tooling_parts: set positions
UPDATE tooling_parts tp
SET position = 'left'
FROM tooling t
WHERE tp.tooling_id = t.id
  AND t.tooling_number = 'TYAA-Q0093-1'
  AND tp.position IS NULL;

UPDATE tooling_parts tp
SET position = 'right'
FROM tooling t
WHERE tp.tooling_id = t.id
  AND t.tooling_number = 'TYAA-Q0093-2'
  AND tp.position IS NULL;

-- Show results
SELECT 'AFTER UPDATE:' as stage;
SELECT
    p.id,
    p.internal_name,
    p.thickness,
    p.width,
    p.pitch,
    p.part_position,
    t.tooling_number,
    tp.position as tooling_position,
    eir.parsed_material,
    eir.parsed_thickness
FROM parts p
JOIN tooling_parts tp ON tp.part_id = p.id
JOIN tooling t ON t.id = tp.tooling_id
LEFT JOIN excel_import_rows eir ON eir.resolved_part_id = p.id
WHERE t.tooling_number LIKE 'TYAA-Q0093%'
ORDER BY t.tooling_number;

-- Uncomment to apply changes:
COMMIT;
-- ROLLBACK;
