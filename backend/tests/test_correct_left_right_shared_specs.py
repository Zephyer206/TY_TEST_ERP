#!/usr/bin/env python3
"""
Tests for correct_left_right_shared_specs.py
"""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
import tempfile
import json

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Import functions to test
from scripts.correct_left_right_shared_specs import (
    analyze_group,
    safe_numeric_compare,
    detect_position_from_name,
    extract_base_tooling_number,
    merge_duplicate_targets,
    consolidate_duplicate_targets,
    build_action_plan,
    execute_action_plan,
    apply_corrections,
    generate_report,
)


class TestSafeNumericCompare(unittest.TestCase):
    """Test numeric comparison with tolerance."""

    def test_equal_floats(self):
        are_equal, diff = safe_numeric_compare(1.5, 1.5)
        self.assertTrue(are_equal)

    def test_equal_within_tolerance(self):
        are_equal, diff = safe_numeric_compare(1.5001, 1.5)
        self.assertTrue(are_equal)

    def test_not_equal_outside_tolerance(self):
        are_equal, diff = safe_numeric_compare(1.5, 2.0)
        self.assertFalse(are_equal)

    def test_none_values(self):
        are_equal, diff = safe_numeric_compare(None, None)
        self.assertTrue(are_equal)

        are_equal, diff = safe_numeric_compare(1.5, None)
        self.assertFalse(are_equal)


class TestPositionDetection(unittest.TestCase):
    """Test position detection from names."""

    def test_chinese_left(self):
        self.assertEqual(detect_position_from_name("零件左"), "left")

    def test_chinese_right(self):
        self.assertEqual(detect_position_from_name("零件右"), "right")

    def test_suffix_left(self):
        self.assertEqual(detect_position_from_name("零件-1"), "left")

    def test_suffix_right(self):
        self.assertEqual(detect_position_from_name("零件-2"), "right")

    def test_english_left(self):
        self.assertEqual(detect_position_from_name("left-part"), "left")

    def test_english_right(self):
        self.assertEqual(detect_position_from_name("right-part"), "right")

    def test_no_position(self):
        self.assertIsNone(detect_position_from_name("零件"))


class TestToolingNumberExtraction(unittest.TestCase):
    """Test base tooling number extraction."""

    def test_with_suffix_1(self):
        self.assertEqual(extract_base_tooling_number("TYAA-Q0093-1"), "TYAA-Q0093")

    def test_with_suffix_2(self):
        self.assertEqual(extract_base_tooling_number("TYAA-Q0093-2"), "TYAA-Q0093")

    def test_without_suffix(self):
        self.assertEqual(extract_base_tooling_number("TYAA-Q0093"), "TYAA-Q0093")

    def test_none(self):
        self.assertIsNone(extract_base_tooling_number(None))


class TestAnalyzeGroup(unittest.TestCase):
    """Test group analysis logic."""

    def test_shared_material_both_present_same(self):
        """When both have same material, should be fillable."""
        group = {
            'left': {
                'staging_material': 'SPCC',
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {'material': 'SPCC'},
            },
            'right': {
                'staging_material': 'SPCC',
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {'material': 'SPCC'},
            },
        }

        result = analyze_group(group)
        self.assertTrue(result['can_fill_material'])
        self.assertEqual(result['shared_material'], 'SPCC')
        self.assertEqual(len(result['conflicts']), 0)

    def test_shared_material_conflict(self):
        """When materials differ, should report conflict."""
        group = {
            'left': {
                'staging_material': 'SPCC',
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {'material': 'SPCC'},
            },
            'right': {
                'staging_material': 'DC01',
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {'material': 'DC01'},
            },
        }

        result = analyze_group(group)
        self.assertFalse(result['can_fill_material'])
        self.assertEqual(len(result['conflicts']), 1)
        self.assertIn('Material conflict', result['conflicts'][0])

    def test_shared_material_one_missing(self):
        """When one has material, should fill the other."""
        group = {
            'left': {
                'staging_material': 'SPCC',
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
                'excel_data': {},
            },
        }

        result = analyze_group(group)
        self.assertTrue(result['can_fill_material'])
        self.assertEqual(result['shared_material'], 'SPCC')
        self.assertEqual(len(result['conflicts']), 0)

    def test_cavity_count_explicit_source(self):
        """When cavity count found in Excel, should have explicit source."""
        group = {
            'left': {
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {'cavity_count': 2},
            },
            'right': {
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {'cavity_count': 2},
            },
        }

        result = analyze_group(group)
        self.assertTrue(result['has_explicit_cavity_source'])
        self.assertTrue(result['can_fill_cavity'])
        self.assertEqual(result['shared_cavity'], 2)

    def test_cavity_count_no_explicit_source(self):
        """When no cavity count in Excel, should not have explicit source."""
        group = {
            'left': {
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {},
            },
            'right': {
                'staging_material': None,
                'staging_thickness': None,
                'staging_width': None,
                'staging_pitch': None,
                'staging_cavity_count': None,
                'excel_data': {},
            },
        }

        result = analyze_group(group)
        self.assertFalse(result['has_explicit_cavity_source'])
        self.assertFalse(result['can_fill_cavity'])


class TestMergeDuplicateTargets(unittest.TestCase):
    """Test merging duplicate target part pairs."""

    def test_no_duplicates(self):
        """When all targets are unique, each gets its own entry."""
        groups = [
            {'left': {'part_id': 1}, 'right': {'part_id': 2}},
            {'left': {'part_id': 3}, 'right': {'part_id': 4}},
        ]

        result = merge_duplicate_targets(groups)
        self.assertEqual(len(result), 2)
        self.assertIn((1, 2), result)
        self.assertIn((3, 4), result)
        self.assertEqual(len(result[(1, 2)]), 1)
        self.assertEqual(len(result[(3, 4)]), 1)

    def test_duplicate_same_order(self):
        """When same part pair appears twice, both are grouped."""
        groups = [
            {'left': {'part_id': 1}, 'right': {'part_id': 2}, 'sheet': 'Sheet1'},
            {'left': {'part_id': 1}, 'right': {'part_id': 2}, 'sheet': 'Sheet2'},
        ]

        result = merge_duplicate_targets(groups)
        self.assertEqual(len(result), 1)
        self.assertIn((1, 2), result)
        self.assertEqual(len(result[(1, 2)]), 2)
        self.assertEqual(result[(1, 2)][0]['sheet'], 'Sheet1')
        self.assertEqual(result[(1, 2)][1]['sheet'], 'Sheet2')

    def test_duplicate_reversed_order(self):
        """Part pairs are normalized to (min, max) key."""
        groups = [
            {'left': {'part_id': 1}, 'right': {'part_id': 2}},
            {'left': {'part_id': 2}, 'right': {'part_id': 1}},
        ]

        result = merge_duplicate_targets(groups)
        self.assertEqual(len(result), 1)
        self.assertIn((1, 2), result)
        self.assertEqual(len(result[(1, 2)]), 2)


class TestConsolidateDuplicateTargets(unittest.TestCase):
    """Test consolidation of duplicate targets using analyze_group."""

    def test_single_source_with_analysis_conflict(self):
        """Single source with analysis conflict (e.g., left vs right material differ) should be inconsistent."""
        groups = [
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
                    'excel_data': {'material': 'DC01'},  # Different material
                },
            },
        ]

        result = consolidate_duplicate_targets(groups)
        self.assertFalse(result['consistent'], "Single source with analysis conflict should be inconsistent")
        self.assertGreater(len(result['conflicts']), 0)
        self.assertIsNone(result['merged_target'])
        # Check that conflict mentions material
        has_material_conflict = any('material' in str(c).lower() for c in result['conflicts'])
        self.assertTrue(has_material_conflict)

    def test_single_source_always_consistent(self):
        """Single source without conflicts is always consistent."""
        groups = [
            {
                'left': {'staging_material': 'SPCC', 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
                'right': {'staging_material': 'SPCC', 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
            },
        ]

        result = consolidate_duplicate_targets(groups)
        self.assertTrue(result['consistent'])
        self.assertEqual(len(result['conflicts']), 0)
        self.assertIsNotNone(result['merged_target'])
        self.assertEqual(len(result['merged_target']['sources']), 1)

    def test_duplicate_consistent_excel_data(self):
        """Multiple sources with identical Excel data are consistent."""
        groups = [
            {
                'left': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'SPCC', 'thickness': 1.5}},
                'right': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'SPCC', 'thickness': 1.5}},
            },
            {
                'left': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'SPCC', 'thickness': 1.5}},
                'right': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'SPCC', 'thickness': 1.5}},
            },
        ]

        result = consolidate_duplicate_targets(groups)
        self.assertTrue(result['consistent'])
        self.assertEqual(len(result['conflicts']), 0)
        self.assertEqual(len(result['merged_target']['sources']), 2)

    def test_duplicate_conflicting_material(self):
        """Multiple sources with different materials are inconsistent."""
        groups = [
            {
                'left': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'SPCC'}},
                'right': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'SPCC'}},
            },
            {
                'left': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'DC01'}},
                'right': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'material': 'DC01'}},
            },
        ]

        result = consolidate_duplicate_targets(groups)
        self.assertFalse(result['consistent'])
        self.assertGreater(len(result['conflicts']), 0)
        self.assertIn('material', result['conflicts'][0].lower())

    def test_cavity_no_conflict_when_one_empty_one_explicit(self):
        """One source without cavity and one with explicit cavity should not conflict."""
        groups = [
            {
                'left': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
                'right': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
            },
            {
                'left': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'cavity_count': 2}},
                'right': {'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {'cavity_count': 2}},
            },
        ]

        result = consolidate_duplicate_targets(groups)
        self.assertTrue(result['consistent'])
        self.assertEqual(result['merged_target']['merged_analysis']['shared_cavity'], 2)

    def test_position_mapping_conflict(self):
        """When part_id->position mapping is inconsistent, should conflict."""
        groups = [
            {
                'left': {'part_id': 1, 'position': 'left', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
                'right': {'part_id': 2, 'position': 'right', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
            },
            {
                'left': {'part_id': 1, 'position': 'right', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
                'right': {'part_id': 2, 'position': 'left', 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'excel_data': {}},
            },
        ]

        result = consolidate_duplicate_targets(groups)
        self.assertFalse(result['consistent'])
        self.assertGreater(len(result['conflicts']), 0)


class TestBuildActionPlan(unittest.TestCase):
    """Test action plan building from merged targets."""

    def test_plan_all_staging_rows_from_all_sources(self):
        """All staging rows from all sources should appear in plan."""
        mock_cur = Mock()
        mock_cur.fetchone.return_value = (None, None, None, None, None)
        mock_cur.fetchall.return_value = []

        merged_target = {
            'sources': [
                {
                    'sheet': 'Sheet1',
                    'base_tooling': 'TOOL-1',
                    'left': {'row_id': 100, 'part_id': 1, 'source_row': 10, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'left', 'excel_data': {'material': 'SPCC'}},
                    'right': {'row_id': 101, 'part_id': 2, 'source_row': 11, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'right', 'excel_data': {'material': 'SPCC'}},
                },
                {
                    'sheet': 'Sheet2',
                    'base_tooling': 'TOOL-1',
                    'left': {'row_id': 200, 'part_id': 1, 'source_row': 20, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'left', 'excel_data': {'material': 'SPCC'}},
                    'right': {'row_id': 201, 'part_id': 2, 'source_row': 21, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'right', 'excel_data': {'material': 'SPCC'}},
                },
            ],
            'canonical_left': {'row_id': 100, 'part_id': 1, 'source_row': 10, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'left', 'internal_name': 'Part-L', 'excel_data': {'material': 'SPCC'}},
            'canonical_right': {'row_id': 101, 'part_id': 2, 'source_row': 11, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'right', 'internal_name': 'Part-R', 'excel_data': {'material': 'SPCC'}},
            'sheet': 'Sheet1',
            'base_tooling': 'TOOL-1',
            'merged_analysis': {
                'can_fill_material': True,
                'shared_material': 'SPCC',
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
            }
        }

        plan = build_action_plan([merged_target], mock_cur)

        self.assertEqual(len(plan['staging_updates']), 4)
        self.assertIn(100, plan['staging_updates'])
        self.assertIn(101, plan['staging_updates'])
        self.assertIn(200, plan['staging_updates'])
        self.assertIn(201, plan['staging_updates'])

    def test_plan_parts_only_once_from_canonical(self):
        """Parts should be planned only once using canonical left/right."""
        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            (None, None, None, None, None),  # part 1
            (None, None, None, None, None),  # part 2
        ]
        mock_cur.fetchall.return_value = []

        merged_target = {
            'sources': [
                {
                    'sheet': 'Sheet1',
                    'base_tooling': 'TOOL-1',
                    'left': {'row_id': 100, 'part_id': 1, 'source_row': 10, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'left', 'excel_data': {}},
                    'right': {'row_id': 101, 'part_id': 2, 'source_row': 11, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'right', 'excel_data': {}},
                },
                {
                    'sheet': 'Sheet2',
                    'base_tooling': 'TOOL-1',
                    'left': {'row_id': 200, 'part_id': 1, 'source_row': 20, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'left', 'excel_data': {}},
                    'right': {'row_id': 201, 'part_id': 2, 'source_row': 21, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'right', 'excel_data': {}},
                },
            ],
            'canonical_left': {'row_id': 100, 'part_id': 1, 'source_row': 10, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'left', 'internal_name': 'Part-L', 'excel_data': {}},
            'canonical_right': {'row_id': 101, 'part_id': 2, 'source_row': 11, 'staging_material': None, 'staging_thickness': None, 'staging_width': None, 'staging_pitch': None, 'staging_cavity_count': None, 'staging_position': None, 'position': 'right', 'internal_name': 'Part-R', 'excel_data': {}},
            'sheet': 'Sheet1',
            'base_tooling': 'TOOL-1',
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
            }
        }

        plan = build_action_plan([merged_target], mock_cur)

        # Should query parts table exactly twice (once for each unique part)
        self.assertEqual(mock_cur.fetchone.call_count, 2)
        self.assertEqual(len(plan['part_updates']), 2)
        self.assertIn(1, plan['part_updates'])
        self.assertIn(2, plan['part_updates'])

    def test_action_conflict_blocks_record(self):
        """Consolidate detects when same row has conflicting values across sources."""
        # This test verifies that consolidate_duplicate_targets detects conflicts
        # when the same staging row appears in multiple sources with different values

        groups = [
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
                    'excel_data': {'material': 'SPCC'},
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
                    'excel_data': {'material': 'DC01'},  # Different material!
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

        result = consolidate_duplicate_targets(groups)

        self.assertFalse(result['consistent'])
        self.assertGreater(len(result['conflicts']), 0)
        # Should detect material conflict
        has_material_conflict = any('material' in str(c).lower() for c in result['conflicts'])
        self.assertTrue(has_material_conflict)


class TestApplyCorrectionsDeprecated(unittest.TestCase):
    """Test that apply_corrections raises RuntimeError."""

    def test_apply_corrections_raises_error(self):
        """apply_corrections should raise RuntimeError directing to unified flow."""
        mock_cur = Mock()
        groups = []

        with self.assertRaises(RuntimeError) as cm:
            apply_corrections(mock_cur, groups, dry_run=True)

        error_msg = str(cm.exception)
        self.assertIn("deprecated", error_msg.lower())
        self.assertIn("merge_duplicate_targets", error_msg)
        self.assertIn("consolidate_duplicate_targets", error_msg)
        self.assertIn("build_action_plan", error_msg)
        self.assertIn("execute_action_plan", error_msg)


class TestExecuteActionPlanUniqueSQL(unittest.TestCase):
    """Test that only execute_action_plan contains UPDATE statements."""

    def test_only_execute_action_plan_has_update_sql(self):
        """Verify that UPDATE SQL only appears in execute_action_plan."""
        import inspect

        # Read the source file
        source_file = Path(__file__).parent.parent / 'scripts' / 'correct_left_right_shared_specs.py'
        with open(source_file, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Find function definitions
        lines = source_code.split('\n')
        functions = {}
        current_func = None
        func_start = 0

        for i, line in enumerate(lines):
            if line.startswith('def '):
                if current_func:
                    functions[current_func] = (func_start, i)
                func_name = line.split('def ')[1].split('(')[0]
                current_func = func_name
                func_start = i

        if current_func:
            functions[current_func] = (func_start, len(lines))

        # Check for UPDATE statements in each function
        update_functions = []
        for func_name, (start, end) in functions.items():
            func_code = '\n'.join(lines[start:end])
            if 'UPDATE ' in func_code and any(table in func_code for table in ['excel_import_rows', 'parts', 'tooling_parts', 'tooling']):
                update_functions.append(func_name)

        # Only execute_action_plan should have UPDATE statements
        self.assertEqual(
            update_functions,
            ['execute_action_plan'],
            f"Only execute_action_plan should contain UPDATE SQL, but found in: {update_functions}"
        )


class TestGenerateReportWithWarningsAndConflicts(unittest.TestCase):
    """Test that generate_report includes warnings and conflicts in JSON."""

    def test_json_report_includes_warnings_and_conflicts(self):
        """JSON report should include warnings, action_conflicts, and target_conflicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)

            plan = {
                'summary': {'source_groups': 1, 'unique_target_groups': 1},
                'warnings': [
                    {'table': 'parts', 'record_id': 1, 'field': 'material_name', 'db_value': 'SPCC', 'proposed_value': 'DC01', 'reason': 'test'}
                ],
                'conflicts': [
                    {'type': 'action_conflict', 'table': 'staging_updates', 'record_id': 100, 'field': 'parsed_material'},
                    {'type': 'analysis_conflict', 'sheet': 'Sheet1', 'base_tooling': 'TOOL-1', 'left_part_id': 1, 'right_part_id': 2, 'conflicts': ['test conflict']},
                ],
                'staging_updates': {},
                'part_updates': {},
                'tooling_part_updates': {},
                'tooling_updates': {},
            }

            stats = {'safe_targets': 0, 'duplicate_conflict_targets': 0}
            backup_files = {}
            all_targets = []

            result = generate_report(all_targets, plan, stats, backup_files, report_dir, dry_run=True)

            # Verify report files exist
            self.assertIn('json', result)
            self.assertTrue(Path(result['json']).exists())

            # Read JSON report
            with open(result['json'], 'r', encoding='utf-8') as f:
                json_report = json.load(f)

            # Check that warnings and conflicts are present
            self.assertIn('warnings', json_report)
            self.assertIn('action_conflicts', json_report)
            self.assertIn('target_conflicts', json_report)

            self.assertEqual(len(json_report['warnings']), 1)
            self.assertEqual(len(json_report['action_conflicts']), 1)
            self.assertEqual(len(json_report['target_conflicts']), 1)

            # Check warning structure
            self.assertEqual(json_report['warnings'][0]['table'], 'parts')
            self.assertEqual(json_report['warnings'][0]['record_id'], 1)

            # Check conflict types
            self.assertEqual(json_report['action_conflicts'][0]['type'], 'action_conflict')
            self.assertEqual(json_report['target_conflicts'][0]['type'], 'analysis_conflict')


if __name__ == '__main__':
    unittest.main()
