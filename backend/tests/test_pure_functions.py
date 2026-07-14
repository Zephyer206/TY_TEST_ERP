#!/usr/bin/env python3
"""
Pure function tests for correct_left_right_shared_specs.py
Tests the merge -> plan chain with real function calls.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.correct_left_right_shared_specs import (
    merge_duplicate_targets,
    consolidate_duplicate_targets,
    build_action_plan,
)
from unittest.mock import Mock

print('='*70)
print('Pure Function Tests - Merge -> Plan Chain')
print('='*70)

# Test 1: merge_duplicate_targets
print('\nTest 1: merge_duplicate_targets - basic merging')
groups = [
    {'left': {'part_id': 1}, 'right': {'part_id': 2}},
    {'left': {'part_id': 1}, 'right': {'part_id': 2}},
]
result = merge_duplicate_targets(groups)
print(f'  Input: 2 groups with same part pair (1,2)')
print(f'  Output keys: {list(result.keys())}')
print(f'  Groups for (1,2): {len(result[(1,2)])}')
assert len(result) == 1, f"Expected 1 unique target, got {len(result)}"
assert len(result[(1,2)]) == 2, f"Expected 2 source groups, got {len(result[(1,2)])}"
print('  [PASS] Duplicate targets merged correctly')

# Test 2: consolidate_duplicate_targets - consistent staging data
print('\nTest 2: consolidate_duplicate_targets - consistent staging-only data')
groups_consistent = [
    {
        'left': {
            'staging_material': 'SPCC',
            'staging_thickness': 1.5,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},
        },
        'right': {
            'staging_material': 'SPCC',
            'staging_thickness': 1.5,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},
        },
    },
    {
        'left': {
            'staging_material': 'SPCC',
            'staging_thickness': 1.5,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},
        },
        'right': {
            'staging_material': 'SPCC',
            'staging_thickness': 1.5,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},
        },
    },
]
result = consolidate_duplicate_targets(groups_consistent)
print(f'  Consistent: {result["consistent"]}')
print(f'  Conflicts: {len(result["conflicts"])}')
assert result['consistent'] == True, "Expected consistent=True"
assert len(result['conflicts']) == 0, "Expected no conflicts"
assert result['merged_target'] is not None, "Expected merged_target"
assert len(result['merged_target']['sources']) == 2, "Expected 2 sources preserved"
print('  [PASS] Consistent duplicates accepted, both sources preserved')

# Test 3: consolidate_duplicate_targets - Excel data conflict
print('\nTest 3: consolidate_duplicate_targets - Excel data conflict')
groups_conflict = [
    {
        'left': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'material': 'SPCC'},
        },
        'right': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'material': 'SPCC'},
        },
    },
    {
        'left': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'material': 'DC01'},
        },
        'right': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'material': 'DC01'},
        },
    },
]
result = consolidate_duplicate_targets(groups_conflict)
print(f'  Consistent: {result["consistent"]}')
print(f'  Conflicts: {len(result["conflicts"])}')
assert result['consistent'] == False, "Expected consistent=False"
assert len(result['conflicts']) > 0, "Expected conflicts"
assert 'Material' in result['conflicts'][0] or 'material' in result['conflicts'][0], "Expected material conflict"
print('  [PASS] Excel data conflicts detected even with empty staging')

# Test 4: consolidate + build_action_plan - full chain with 4 staging rows
print('\nTest 4: consolidate + build_action_plan - preserves all 4 staging rows')
mock_cur = Mock()
mock_cur.fetchone.return_value = (None, None, None, None, None)
mock_cur.fetchall.return_value = []

groups_dup = [
    {
        'sheet': 'Sheet1',
        'base_tooling': 'TOOL-1',
        'left': {
            'row_id': 100,
            'part_id': 1,
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'staging_position': None,
            'position': 'left',
            'excel_data': {'material': 'SPCC'},
        },
        'right': {
            'row_id': 101,
            'part_id': 2,
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'staging_position': None,
            'position': 'right',
            'excel_data': {'material': 'SPCC'},
        },
    },
    {
        'sheet': 'Sheet2',
        'base_tooling': 'TOOL-1',
        'left': {
            'row_id': 200,
            'part_id': 1,
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'staging_position': None,
            'position': 'left',
            'excel_data': {'material': 'SPCC'},
        },
        'right': {
            'row_id': 201,
            'part_id': 2,
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'staging_position': None,
            'position': 'right',
            'excel_data': {'material': 'SPCC'},
        },
    },
]

# Step 1: Merge duplicates
target_map = merge_duplicate_targets(groups_dup)
assert len(target_map) == 1, "Expected 1 unique target"

# Step 2: Consolidate
consolidated_targets = []
for target_key, source_groups in target_map.items():
    result = consolidate_duplicate_targets(source_groups)
    if result['consistent']:
        consolidated_targets.append(result['merged_target'])

assert len(consolidated_targets) == 1, "Expected 1 consolidated target"
assert len(consolidated_targets[0]['sources']) == 2, "Expected 2 sources"

# Step 3: Build plan
plan = build_action_plan(consolidated_targets, mock_cur)

print(f'  Staging updates (unique row_ids): {len(plan["staging_updates"])}')
print(f'  Row IDs in staging: {sorted(plan["staging_updates"].keys())}')
print(f'  Part updates (unique part_ids): {len(plan["part_updates"])}')
print(f'  Part IDs in parts: {sorted(plan["part_updates"].keys())}')

assert len(plan['staging_updates']) == 4, f"Expected 4 staging rows, got {len(plan['staging_updates'])}"
assert 100 in plan['staging_updates'], "Row 100 missing"
assert 101 in plan['staging_updates'], "Row 101 missing"
assert 200 in plan['staging_updates'], "Row 200 missing"
assert 201 in plan['staging_updates'], "Row 201 missing"
assert len(plan['part_updates']) == 2, f"Expected 2 parts, got {len(plan['part_updates'])}"
assert 1 in plan['part_updates'], "Part 1 missing"
assert 2 in plan['part_updates'], "Part 2 missing"
print('  [PASS] All 4 staging rows preserved, 2 parts deduplicated')

# Test 5: Cavity count - one source no cavity, one source explicit 2
print('\nTest 5: Cavity count - one empty, one explicit -> takes explicit')
groups_cavity = [
    {
        'left': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},  # No cavity
        },
        'right': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},
        },
    },
    {
        'left': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'cavity_count': 2},  # Explicit cavity
        },
        'right': {
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'cavity_count': 2},
        },
    },
]
result = consolidate_duplicate_targets(groups_cavity)
print(f'  Consistent: {result["consistent"]}')
print(f'  Shared cavity: {result["merged_target"]["merged_analysis"]["shared_cavity"]}')
print(f'  Can fill cavity: {result["merged_target"]["merged_analysis"]["can_fill_cavity"]}')
assert result['consistent'] == True, "Expected consistent"
assert result['merged_target']['merged_analysis']['shared_cavity'] == 2, "Expected cavity=2"
assert result['merged_target']['merged_analysis']['can_fill_cavity'] == True, "Expected can_fill_cavity=True"
print('  [PASS] Explicit cavity value adopted, empty source ignored')

# Test 6: Part position mapping conflict
print('\nTest 6: Part position mapping conflict')
groups_position = [
    {
        'left': {'part_id': 1, 'position': 'left', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
        'right': {'part_id': 2, 'position': 'right', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
    },
    {
        'left': {'part_id': 1, 'position': 'right', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},  # Wrong position!
        'right': {'part_id': 2, 'position': 'left', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
    },
]
result = consolidate_duplicate_targets(groups_position)
print(f'  Consistent: {result["consistent"]}')
print(f'  Conflicts: {result["conflicts"]}')
assert result['consistent'] == False, "Expected consistent=False"
assert len(result['conflicts']) > 0, "Expected position conflicts"
print('  [PASS] Position mapping conflict detected')

# Test 7: Consolidate detects cross-source same-row conflicts
print('\nTest 7: Consolidate detects when same row appears with different values')

# Two sources, both referencing row 100 but with different thickness in excel_data
# This simulates a pathological case where the same staging row appears in multiple sheets
groups_same_row = [
    {
        'left': {
            'row_id': 100,
            'part_id': 1,
            'position': 'left',
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'thickness': 1.5},
        },
        'right': {
            'row_id': 101,
            'part_id': 2,
            'position': 'right',
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},
        },
    },
    {
        'left': {
            'row_id': 100,  # Same row!
            'part_id': 1,
            'position': 'left',
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {'thickness': 2.0},  # Different thickness!
        },
        'right': {
            'row_id': 101,
            'part_id': 2,
            'position': 'right',
            'staging_material': None,
            'staging_thickness': None,
            'staging_width': None,
            'staging_pitch': None,
            'staging_cavity_count': None,
            'excel_data': {},
        },
    },
]

result = consolidate_duplicate_targets(groups_same_row)
print(f'  Consistent: {result["consistent"]}')
print(f'  Conflicts: {result["conflicts"]}')

# Should detect thickness conflict
assert result['consistent'] == False, "Expected consistent=False for conflicting thickness"
assert len(result['conflicts']) > 0, "Expected conflicts"
assert any('thickness' in str(c).lower() for c in result['conflicts']), "Expected thickness conflict"
print('  [PASS] Consolidate detects thickness conflict across sources')

print('\n' + '='*70)
print('ALL 7 PURE FUNCTION TESTS PASSED')
print('='*70)
