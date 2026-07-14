#!/usr/bin/env python3
"""
Unit tests for B1 execution flow: unified action plan and executor.

Tests cover:
- execute_action_plan dry-run vs apply mode
- Field whitelist validation
- Multi-field UPDATE consolidation
- Empty action filtering
- Warning deduplication
- Position conflict detection
- Duplicate conflict handling
- Main flow orchestration
"""

import sys
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from scripts.correct_left_right_shared_specs import (
    execute_action_plan,
    build_action_plan,
    merge_duplicate_targets,
    consolidate_duplicate_targets,
    add_or_merge_action,
)


class TestExecuteActionPlan(unittest.TestCase):
    """Test execute_action_plan function."""

    def test_dry_run_no_updates(self):
        """Dry-run should not execute UPDATE statements."""
        cur = MagicMock()

        plan = {
            'staging_updates': {
                1: {'parsed_material': 'SPCC', 'parsed_thickness': 1.5},
                2: {'parsed_width': 100.0},
            },
            'part_updates': {
                10: {'material_name': 'SPCC'},
            },
            'tooling_part_updates': {
                20: {'position': 'left'},
            },
            'tooling_updates': {
                30: {'cavity_count': 2},
            },
            'warnings': [],
            'conflicts': [],
        }

        stats = execute_action_plan(cur, plan, dry_run=True)

        # Should not execute any UPDATE
        cur.execute.assert_not_called()

        # Should return planned counts
        self.assertEqual(stats['planned_staging_rows'], 2)
        self.assertEqual(stats['planned_parts'], 1)
        self.assertEqual(stats['planned_tooling_parts'], 1)
        self.assertEqual(stats['planned_tooling'], 1)

    def test_apply_executes_updates(self):
        """Apply mode should execute UPDATE statements."""
        cur = MagicMock()

        plan = {
            'staging_updates': {
                1: {'parsed_material': 'SPCC', 'parsed_thickness': 1.5},
            },
            'part_updates': {
                10: {'material_name': 'SPCC', 'thickness': 1.5},
            },
            'tooling_part_updates': {
                20: {'position': 'left'},
            },
            'tooling_updates': {
                30: {'cavity_count': 2},
            },
            'warnings': [],
            'conflicts': [],
        }

        stats = execute_action_plan(cur, plan, dry_run=False)

        # Should execute 4 UPDATEs
        self.assertEqual(cur.execute.call_count, 4)

        # Should return updated counts
        self.assertEqual(stats['updated_staging_rows'], 1)
        self.assertEqual(stats['updated_parts'], 1)
        self.assertEqual(stats['updated_tooling_parts'], 1)
        self.assertEqual(stats['updated_tooling'], 1)

    def test_multi_field_single_update(self):
        """Multiple fields for same record should use single UPDATE."""
        cur = MagicMock()

        plan = {
            'staging_updates': {
                1: {'parsed_material': 'SPCC', 'parsed_thickness': 1.5, 'parsed_width': 100.0},
            },
            'part_updates': {},
            'tooling_part_updates': {},
            'tooling_updates': {},
            'warnings': [],
            'conflicts': [],
        }

        stats = execute_action_plan(cur, plan, dry_run=False)

        # Should execute exactly 1 UPDATE
        self.assertEqual(cur.execute.call_count, 1)

        # Check the SQL includes all three fields
        sql = cur.execute.call_args[0][0]
        self.assertIn('parsed_material', sql)
        self.assertIn('parsed_thickness', sql)
        self.assertIn('parsed_width', sql)

        # Check values
        values = cur.execute.call_args[0][1]
        self.assertEqual(values, ['SPCC', 1.5, 100.0, 1])  # [field values..., record_id]

    def test_empty_actions_not_counted(self):
        """Records with empty action dicts should not be counted."""
        cur = MagicMock()

        plan = {
            'staging_updates': {
                1: {'parsed_material': 'SPCC'},
                2: {},  # Empty - should be skipped
            },
            'part_updates': {
                10: {},  # Empty - should be skipped
            },
            'tooling_part_updates': {},
            'tooling_updates': {},
            'warnings': [],
            'conflicts': [],
        }

        stats = execute_action_plan(cur, plan, dry_run=False)

        # Should only count non-empty records
        self.assertEqual(stats['updated_staging_rows'], 1)
        self.assertEqual(stats['updated_parts'], 0)
        self.assertEqual(cur.execute.call_count, 1)

    def test_field_whitelist_validation(self):
        """Invalid field names should raise ValueError."""
        cur = MagicMock()

        plan = {
            'staging_updates': {
                1: {'invalid_field': 'value'},
            },
            'part_updates': {},
            'tooling_part_updates': {},
            'tooling_updates': {},
            'warnings': [],
            'conflicts': [],
        }

        with self.assertRaises(ValueError) as ctx:
            execute_action_plan(cur, plan, dry_run=False)

        self.assertIn('invalid_field', str(ctx.exception))
        self.assertIn('excel_import_rows', str(ctx.exception))

    def test_parts_table_updated_at(self):
        """Parts table updates should include updated_at = NOW()."""
        cur = MagicMock()

        plan = {
            'staging_updates': {},
            'part_updates': {
                10: {'material_name': 'SPCC'},
            },
            'tooling_part_updates': {},
            'tooling_updates': {},
            'warnings': [],
            'conflicts': [],
        }

        execute_action_plan(cur, plan, dry_run=False)

        sql = cur.execute.call_args[0][0]
        self.assertIn('updated_at = NOW()', sql)


class TestAddOrMergeAction(unittest.TestCase):
    """Test add_or_merge_action conflict detection."""

    def test_same_value_deduplicates(self):
        """Same record+field with same value should deduplicate."""
        plan = {
            'staging_updates': {},
            'conflicts': [],
        }

        add_or_merge_action(plan, 'staging_updates', 1, 'parsed_material', 'SPCC', 'source1')
        add_or_merge_action(plan, 'staging_updates', 1, 'parsed_material', 'SPCC', 'source2')

        # Should only have one entry
        self.assertEqual(len(plan['staging_updates']), 1)
        self.assertEqual(plan['staging_updates'][1]['parsed_material'], 'SPCC')
        self.assertEqual(len(plan['conflicts']), 0)

    def test_different_value_creates_conflict(self):
        """Same record+field with different value should create conflict."""
        plan = {
            'staging_updates': {},
            'conflicts': [],
        }

        add_or_merge_action(plan, 'staging_updates', 1, 'parsed_material', 'SPCC', 'source1')
        add_or_merge_action(plan, 'staging_updates', 1, 'parsed_material', 'DC01', 'source2')

        # Should record conflict
        self.assertEqual(len(plan['conflicts']), 1)
        conflict = plan['conflicts'][0]
        self.assertEqual(conflict['type'], 'action_conflict')
        self.assertEqual(conflict['record_id'], 1)
        self.assertEqual(conflict['field'], 'parsed_material')
        self.assertEqual(conflict['existing_value'], 'SPCC')
        self.assertEqual(conflict['proposed_value'], 'DC01')

    def test_numeric_tolerance_deduplication(self):
        """Numerically equal values should deduplicate."""
        plan = {
            'staging_updates': {},
            'conflicts': [],
        }

        add_or_merge_action(plan, 'staging_updates', 1, 'parsed_thickness', 1.5, 'source1')
        add_or_merge_action(plan, 'staging_updates', 1, 'parsed_thickness', 1.5000001, 'source2')

        # Should deduplicate (within tolerance)
        self.assertEqual(len(plan['conflicts']), 0)


class TestWarningDeduplication(unittest.TestCase):
    """Test warning deduplication in build_action_plan."""

    def test_warnings_deduplicated_by_key(self):
        """Warnings with same table+record_id+field should be deduplicated."""
        # Create a mock cursor that returns empty results
        cur = MagicMock()
        cur.fetchone.return_value = (None, None, None, None, None)
        cur.fetchall.return_value = []

        merged_target = {
            'sources': [
                {
                    'sheet': 'Sheet1',
                    'base_tooling': 'TYAA-Q0001',
                    'left': {
                        'row_id': 1,
                        'part_id': 100,
                        'source_row': 10,
                        'staging_material': 'OLD_MAT',
                        'staging_thickness': None,
                        'staging_width': None,
                        'staging_pitch': None,
                        'staging_cavity_count': None,
                        'staging_position': None,
                        'position': 'left',
                        'excel_data': {},
                    },
                    'right': {
                        'row_id': 2,
                        'part_id': 101,
                        'source_row': 11,
                        'staging_material': 'OLD_MAT',
                        'staging_thickness': None,
                        'staging_width': None,
                        'staging_pitch': None,
                        'staging_cavity_count': None,
                        'staging_position': None,
                        'position': 'right',
                        'excel_data': {},
                    },
                },
            ],
            'canonical_left': {
                'row_id': 1,
                'part_id': 100,
                'staging_material': 'OLD_MAT',
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'staging_position': None,
                'position': 'left',
                'internal_name': 'Part-L',
                'excel_data': {},
            },
            'canonical_right': {
                'row_id': 2,
                'part_id': 101,
                'staging_material': 'OLD_MAT',
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'staging_position': None,
                'position': 'right',
                'internal_name': 'Part-R',
                'excel_data': {},
            },
            'sheet': 'Sheet1',
            'base_tooling': 'TYAA-Q0001',
            'merged_analysis': {
                'can_fill_material': True,
                'shared_material': 'NEW_MAT',
                'can_fill_thickness': False,
                'shared_thickness': None,
                'can_fill_width': False,
                'shared_width': None,
                'can_fill_pitch': False,
                'shared_pitch': None,
                'can_fill_cavity': False,
                'shared_cavity': None,
                'has_explicit_cavity_source': False,
                'conflicts': [],
            },
        }

        plan = build_action_plan([merged_target], cur)

        # Should have warnings for staging material conflicts (left and right)
        # But should be deduplicated if same record appears multiple times
        warning_keys = set((w['table'], w['record_id'], w['field']) for w in plan['warnings'])

        # Each unique (table, record_id, field) should appear only once
        self.assertEqual(len(plan['warnings']), len(warning_keys))


class TestMainFlowOrchestration(unittest.TestCase):
    """Test main flow orchestration logic."""

    def test_two_sources_one_target_four_staging(self):
        """Two source groups merging to one target should preserve all 4 staging rows."""
        # Create two source groups with same target parts
        groups = [
            {
                'sheet': 'Sheet1',
                'base_tooling': 'TYAA-Q0001',
                'left': {
                    'row_id': 1,
                    'part_id': 100,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'left',
                    'source_row': 10,
                    'excel_data': {'material': 'SPCC'},
                },
                'right': {
                    'row_id': 2,
                    'part_id': 101,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'right',
                    'source_row': 11,
                    'excel_data': {'material': 'SPCC'},
                },
            },
            {
                'sheet': 'Sheet2',
                'base_tooling': 'TYAA-Q0001',
                'left': {
                    'row_id': 3,
                    'part_id': 100,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'left',
                    'source_row': 20,
                    'excel_data': {'material': 'SPCC'},
                },
                'right': {
                    'row_id': 4,
                    'part_id': 101,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'right',
                    'source_row': 21,
                    'excel_data': {'material': 'SPCC'},
                },
            },
        ]

        # Merge duplicates
        target_map = merge_duplicate_targets(groups)
        self.assertEqual(len(target_map), 1)

        # Consolidate
        target_key = list(target_map.keys())[0]
        result = consolidate_duplicate_targets(target_map[target_key])
        self.assertTrue(result['consistent'])

        merged_target = result['merged_target']
        self.assertEqual(len(merged_target['sources']), 2)

        # Build plan
        cur = MagicMock()
        cur.fetchone.return_value = (None, None, None, None, None)
        cur.fetchall.return_value = []

        plan = build_action_plan([merged_target], cur)

        # Should plan updates for all 4 staging rows
        self.assertEqual(len(plan['target_ids']['unique_staging_rows']), 4)
        self.assertIn(1, plan['target_ids']['unique_staging_rows'])
        self.assertIn(2, plan['target_ids']['unique_staging_rows'])
        self.assertIn(3, plan['target_ids']['unique_staging_rows'])
        self.assertIn(4, plan['target_ids']['unique_staging_rows'])

        # But only 2 unique parts
        self.assertEqual(len(plan['target_ids']['unique_parts']), 2)

    def test_duplicate_conflict_skips_entire_target(self):
        """Duplicate conflict should skip the entire target including staging."""
        groups = [
            {
                'sheet': 'Sheet1',
                'base_tooling': 'TYAA-Q0001',
                'left': {
                    'row_id': 1,
                    'part_id': 100,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'left',
                    'source_row': 10,
                    'excel_data': {'material': 'SPCC'},
                },
                'right': {
                    'row_id': 2,
                    'part_id': 101,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'right',
                    'source_row': 11,
                    'excel_data': {'material': 'SPCC'},
                },
            },
            {
                'sheet': 'Sheet2',
                'base_tooling': 'TYAA-Q0001',
                'left': {
                    'row_id': 3,
                    'part_id': 100,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'left',
                    'source_row': 20,
                    'excel_data': {'material': 'DC01'},  # Different material - conflict!
                },
                'right': {
                    'row_id': 4,
                    'part_id': 101,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'right',
                    'source_row': 21,
                    'excel_data': {'material': 'DC01'},
                },
            },
        ]

        # Merge and consolidate
        target_map = merge_duplicate_targets(groups)
        target_key = list(target_map.keys())[0]
        result = consolidate_duplicate_targets(target_map[target_key])

        # Should have conflict
        self.assertFalse(result['consistent'])
        self.assertIsNone(result['merged_target'])
        self.assertIn('Material conflict', result['conflicts'][0])


class TestPositionWarnings(unittest.TestCase):
    """Test position conflict warnings."""

    def test_staging_position_conflict_warning(self):
        """Different staging position should generate warning."""
        cur = MagicMock()
        cur.fetchone.return_value = (None, None, None, None, None)
        cur.fetchall.return_value = []

        merged_target = {
            'sources': [{
                'sheet': 'Sheet1',
                'base_tooling': 'TYAA-Q0001',
                'left': {
                    'row_id': 1,
                    'part_id': 100,
                    'source_row': 10,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': 'right',  # Differs from detected 'left'
                    'position': 'left',
                    'excel_data': {},
                },
                'right': {
                    'row_id': 2,
                    'part_id': 101,
                    'source_row': 11,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'right',
                    'excel_data': {},
                },
            }],
            'canonical_left': {
                'row_id': 1,
                'part_id': 100,
                'staging_position': 'right',
                'position': 'left',
                'internal_name': 'Part-L',
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {},
            },
            'canonical_right': {
                'row_id': 2,
                'part_id': 101,
                'staging_position': None,
                'position': 'right',
                'internal_name': 'Part-R',
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {},
            },
            'sheet': 'Sheet1',
            'base_tooling': 'TYAA-Q0001',
            'merged_analysis': {
                'can_fill_material': False,
                'shared_material': None,
                'can_fill_thickness': False,
                'shared_thickness': None,
                'can_fill_width': False,
                'shared_width': None,
                'can_fill_pitch': False,
                'shared_pitch': None,
                'can_fill_cavity': False,
                'shared_cavity': None,
                'has_explicit_cavity_source': False,
                'conflicts': [],
            },
        }

        plan = build_action_plan([merged_target], cur)

        # Should have warning for staging position
        position_warnings = [w for w in plan['warnings']
                           if w['table'] == 'excel_import_rows' and w['field'] == 'parsed_position']
        self.assertEqual(len(position_warnings), 1)
        self.assertEqual(position_warnings[0]['db_value'], 'right')
        self.assertEqual(position_warnings[0]['proposed_value'], 'left')

    def test_parts_position_conflict_warning(self):
        """Different parts position should generate warning."""
        cur = MagicMock()
        cur.fetchone.return_value = (None, None, None, None, 'right')  # DB has 'right'
        cur.fetchall.return_value = []

        merged_target = {
            'sources': [{
                'sheet': 'Sheet1',
                'base_tooling': 'TYAA-Q0001',
                'left': {
                    'row_id': 1,
                    'part_id': 100,
                    'source_row': 10,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'left',  # Detected as left, but DB has right
                    'excel_data': {},
                },
                'right': {
                    'row_id': 2,
                    'part_id': 101,
                    'source_row': 11,
                    'staging_material': None,
                    'staging_thickness': None,
                    'staging_width': None,
                    'staging_pitch': None,
                    'staging_cavity_count': None,
                    'staging_position': None,
                    'position': 'right',
                    'excel_data': {},
                },
            }],
            'canonical_left': {
                'row_id': 1,
                'part_id': 100,
                'position': 'left',
                'internal_name': 'Part-L',
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'staging_position': None,
                'excel_data': {},
            },
            'canonical_right': {
                'row_id': 2,
                'part_id': 101,
                'position': 'right',
                'internal_name': 'Part-R',
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'staging_position': None,
                'excel_data': {},
            },
            'sheet': 'Sheet1',
            'base_tooling': 'TYAA-Q0001',
            'merged_analysis': {
                'can_fill_material': False,
                'shared_material': None,
                'can_fill_thickness': False,
                'shared_thickness': None,
                'can_fill_width': False,
                'shared_width': None,
                'can_fill_pitch': False,
                'shared_pitch': None,
                'can_fill_cavity': False,
                'shared_cavity': None,
                'has_explicit_cavity_source': False,
                'conflicts': [],
            },
        }

        plan = build_action_plan([merged_target], cur)

        # Should have warning for parts position
        position_warnings = [w for w in plan['warnings']
                           if w['table'] == 'parts' and w['field'] == 'part_position']
        self.assertEqual(len(position_warnings), 1)
        self.assertEqual(position_warnings[0]['db_value'], 'right')
        self.assertEqual(position_warnings[0]['proposed_value'], 'left')


if __name__ == '__main__':
    unittest.main()
