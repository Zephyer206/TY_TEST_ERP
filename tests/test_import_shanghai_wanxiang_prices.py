#!/usr/bin/env python3
"""Tests for import_shanghai_wanxiang_prices.py"""
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import import_shanghai_wanxiang_prices as imp


def test_sharedstrings_index_no_offset():
    """Verify OOXML sharedStrings index has no +1 offset after removing empty prepend."""
    source = Path(__file__).parent.parent / 'scripts' / 'wanxiang_shanghai_prices_2025.xlsx'
    if not source.exists():
        # Skip if test file doesn't exist
        return

    sheets, cells, formulas, merges, merged_values = imp.parse_xlsx(source)

    # Sheet3 row 2, column C (customer_part_name) must parse as the exact string
    c2 = cells.get('C2')
    assert c2 == '弹簧片-摩擦片保持', f"C2 should be '弹簧片-摩擦片保持', got {repr(c2)}"

    # Sheet3 row 2, column E (material_name) must parse as the exact string
    e2 = cells.get('E2')
    assert e2 == 'SUS301-CSP 3/4H（JIS G4305）', f"E2 should be 'SUS301-CSP 3/4H（JIS G4305）', got {repr(e2)}"


def test_preview_parses_expected_columns():
    """Verify preview() extracts the correct columns after sharedStrings fix."""
    source = Path(__file__).parent.parent / 'scripts' / 'wanxiang_shanghai_prices_2025.xlsx'
    if not source.exists():
        return

    result = imp.preview(source)
    rows = result['rows']

    # Find row 2 (first data row with index 0 in rows array)
    if len(rows) > 0:
        row0 = rows[0]
        # Verify customer_part_name from column C
        assert row0.get('customer_part_name') == '弹簧片-摩擦片保持', \
            f"First row customer_part_name should be '弹簧片-摩擦片保持', got {repr(row0.get('customer_part_name'))}"

        # Verify material_name from column E
        assert row0.get('material_name') == 'SUS301-CSP 3/4H（JIS G4305）', \
            f"First row material_name should be 'SUS301-CSP 3/4H（JIS G4305）', got {repr(row0.get('material_name'))}"


def test_price_years_only_for_non_null_price_2025():
    """Verify apply logic only creates price_years when price_2025 is non-null."""
    # This is a unit test of the logic - we can't easily test the full database operation
    # So we verify the preview identifies which rows have non-null prices
    source = Path(__file__).parent.parent / 'scripts' / 'wanxiang_shanghai_prices_2025.xlsx'
    if not source.exists():
        return

    result = imp.preview(source)
    rows = result['rows']

    # Count rows with non-null price_2025
    rows_with_price = [r for r in rows if r['price_2025'] is not None]

    # According to the requirement, exactly 22 price_years rows should be produced
    # This means 22 rows should have non-null price_2025
    assert len(rows_with_price) == 22, \
        f"Expected 22 rows with non-null price_2025, got {len(rows_with_price)}"

    # Verify the preview reports the correct count
    assert result['price_rows'] == 22, \
        f"preview() should report 22 price_rows, got {result['price_rows']}"


def test_missing_price_part_numbers():
    """Verify preview correctly identifies rows without prices."""
    source = Path(__file__).parent.parent / 'scripts' / 'wanxiang_shanghai_prices_2025.xlsx'
    if not source.exists():
        return

    result = imp.preview(source)
    rows = result['rows']

    # Count rows without price
    rows_without_price = [r for r in rows if r['price_2025'] is None]

    # Missing price part numbers should match
    assert len(result['missing_price_part_numbers']) == len(rows_without_price), \
        f"missing_price_part_numbers count mismatch"

    # Verify the part numbers match
    expected_missing = {r['part_number'] for r in rows_without_price}
    actual_missing = set(result['missing_price_part_numbers'])
    assert expected_missing == actual_missing, \
        f"missing_price_part_numbers mismatch"


if __name__ == '__main__':
    # Run tests manually
    print("Running test_sharedstrings_index_no_offset...")
    test_sharedstrings_index_no_offset()
    print("PASS")

    print("Running test_preview_parses_expected_columns...")
    test_preview_parses_expected_columns()
    print("PASS")

    print("Running test_price_years_only_for_non_null_price_2025...")
    test_price_years_only_for_non_null_price_2025()
    print("PASS")

    print("Running test_missing_price_part_numbers...")
    test_missing_price_part_numbers()
    print("PASS")

    print("\nAll tests passed!")
