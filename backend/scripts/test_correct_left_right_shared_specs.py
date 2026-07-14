#!/usr/bin/env python3
"""
Static tests for correct_left_right_shared_specs.py
Tests functions that don't require database connection.
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Import functions to test
from correct_left_right_shared_specs import (
    json_serializer,
    extract_base_tooling_number,
    detect_position_from_name,
    build_merged_cell_map,
)


def test_json_serializer():
    """Test JSON serializer handles Decimal and Path."""
    print("\n[TEST] json_serializer")

    # Test Decimal
    result = json_serializer(Decimal("123.45"))
    assert result == 123.45, f"Expected 123.45, got {result}"
    print("  [OK] Decimal serialization")

    # Test Path
    result = json_serializer(Path("/tmp/test.txt"))
    assert result == "/tmp/test.txt" or result == "\\tmp\\test.txt", f"Expected path string, got {result}"
    print("  [OK] Path serialization")

    # Test fallback
    result = json_serializer({"key": "value"})
    assert isinstance(result, str), f"Expected string fallback, got {type(result)}"
    print("  [OK] Fallback to str()")


def test_extract_base_tooling_number():
    """Test base tooling number extraction."""
    print("\n[TEST] extract_base_tooling_number")

    tests = [
        ("TYAA-Q0093-1", "TYAA-Q0093"),
        ("TYAA-Q0093-2", "TYAA-Q0093"),
        ("TYAA-Q0093", "TYAA-Q0093"),
        ("ABC-123-1", "ABC-123"),
        ("XYZ", "XYZ"),
        (None, None),
        ("", None),
    ]

    for input_val, expected in tests:
        result = extract_base_tooling_number(input_val)
        assert result == expected, f"Input: {input_val}, Expected: {expected}, Got: {result}"
        print(f"  [OK] {input_val} -> {result}")


def test_detect_position_from_name():
    """Test position detection from name."""
    print("\n[TEST] detect_position_from_name")

    tests = [
        ("零件左", "left"),
        ("零件右", "right"),
        ("Part-Left", "left"),
        ("Part-Right", "right"),
        ("Part-L", "left"),
        ("Part-R", "right"),
        ("PART-1", "left"),
        ("PART-2", "right"),
        ("TYAA-Q0093-1", "left"),
        ("TYAA-Q0093-2", "right"),
        ("NormalPart", None),
        (None, None),
        ("", None),
    ]

    for input_val, expected in tests:
        result = detect_position_from_name(input_val)
        assert result == expected, f"Input: {input_val}, Expected: {expected}, Got: {result}"
        print(f"  [OK] {input_val} -> {result}")


def test_build_merged_cell_map():
    """Test merged cell map building (mock test)."""
    print("\n[TEST] build_merged_cell_map")

    # Create a mock sheet object
    class MockSheet:
        def __init__(self):
            # Format: (rlo, rhi, clo, chi)
            self.merged_cells = [
                (0, 2, 0, 1),  # Row 0-1, Col 0 merged
                (3, 5, 2, 4),  # Row 3-4, Col 2-3 merged
            ]

    mock_sheet = MockSheet()
    merged_map = build_merged_cell_map(mock_sheet)

    # Check expected mappings
    assert (0, 0) in merged_map and merged_map[(0, 0)] == (0, 0), "Merged cell (0,0) mapping incorrect"
    assert (1, 0) in merged_map and merged_map[(1, 0)] == (0, 0), "Merged cell (1,0) should map to (0,0)"
    assert (3, 2) in merged_map and merged_map[(3, 2)] == (3, 2), "Merged cell (3,2) mapping incorrect"
    assert (4, 3) in merged_map and merged_map[(4, 3)] == (3, 2), "Merged cell (4,3) should map to (3,2)"

    print(f"  [OK] Built merged cell map with {len(merged_map)} entries")
    print(f"  [OK] Mapping validation passed")


def main():
    """Run all tests."""
    print("="*70)
    print("Static Tests for correct_left_right_shared_specs.py")
    print("="*70)

    try:
        test_json_serializer()
        test_extract_base_tooling_number()
        test_detect_position_from_name()
        test_build_merged_cell_map()

        print("\n" + "="*70)
        print("[OK] All tests passed!")
        print("="*70)
        return 0

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
