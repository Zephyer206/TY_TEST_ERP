-- Query TYAA-Q0093 left and right parts
SELECT 
    p.id as part_id,
    p.internal_name,
    p.material,
    p.thickness,
    p.width,
    p.pitch,
    p.part_position,
    t.tooling_number,
    tp.position as tooling_position,
    eir.parsed_material,
    eir.parsed_thickness,
    eir.parsed_width,
    eir.parsed_pitch,
    eir.parsed_position,
    eir.source_sheet,
    eir.source_row
FROM parts p
JOIN tooling_parts tp ON tp.part_id = p.id
JOIN tooling t ON t.id = tp.tooling_id
LEFT JOIN excel_import_rows eir ON eir.resolved_part_id = p.id
WHERE t.tooling_number LIKE 'TYAA-Q0093%'
ORDER BY t.tooling_number, p.id;
