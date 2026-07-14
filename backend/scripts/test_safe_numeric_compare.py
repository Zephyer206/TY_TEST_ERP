#!/usr/bin/env python3
"""
Test safe_numeric_compare helper function.
Does not connect to database - pure unit test.
"""

from decimal import Decimal

def safe_numeric_compare(val1, val2, tolerance=None):
    """
    Safely compare two numeric values that may be float or Decimal.
    Converts both to Decimal for precise comparison.
    """
    if val1 is None or val2 is None:
        return (val1 == val2, None)

    if tolerance is None:
        tolerance = Decimal('0.001')

    try:
        d1 = Decimal(str(val1))
        d2 = Decimal(str(val2))
        diff = abs(d1 - d2)
        are_equal = diff < tolerance
        return (are_equal, diff)
    except (ValueError, Exception):
        return (val1 == val2, None)


def test_safe_numeric_compare():
    """Test the safe_numeric_compare function."""
    print("Testing safe_numeric_compare function...")

    # Test 1: float vs float (equal within tolerance)
    result, diff = safe_numeric_compare(1.234, 1.234)
    assert result is True, f"Test 1 failed: {result}"
    print("[PASS] Test 1: float vs float (equal)")

    # Test 2: float vs float (different, within tolerance)
    result, diff = safe_numeric_compare(1.234, 1.2345)
    assert result is True, f"Test 2 failed: {result}, diff={diff}"
    print("[PASS] Test 2: float vs float (within tolerance)")

    # Test 3: float vs float (different, outside tolerance)
    result, diff = safe_numeric_compare(1.234, 1.240)
    assert result is False, f"Test 3 failed: {result}, diff={diff}"
    print("[PASS] Test 3: float vs float (outside tolerance)")

    # Test 4: Decimal vs float (simulating DB NUMERIC vs analysis float)
    db_value = Decimal('1.234')
    analysis_value = 1.234
    result, diff = safe_numeric_compare(db_value, analysis_value)
    assert result is True, f"Test 4 failed: {result}, diff={diff}"
    print("[PASS] Test 4: Decimal vs float (equal)")

    # Test 5: Decimal vs float (different values)
    db_value = Decimal('1.234')
    analysis_value = 1.240
    result, diff = safe_numeric_compare(db_value, analysis_value)
    assert result is False, f"Test 5 failed: {result}, diff={diff}"
    print("[PASS] Test 5: Decimal vs float (different)")

    # Test 6: None values
    result, diff = safe_numeric_compare(None, None)
    assert result is True, f"Test 6 failed: {result}"
    print("[PASS] Test 6: None vs None")

    result, diff = safe_numeric_compare(1.234, None)
    assert result is False, f"Test 6b failed: {result}"
    print("[PASS] Test 6b: float vs None")

    # Test 7: int values
    result, diff = safe_numeric_compare(5, 5)
    assert result is True, f"Test 7 failed: {result}"
    print("[PASS] Test 7: int vs int (equal)")

    # Test 8: Mixed types that should equal
    result, diff = safe_numeric_compare(Decimal('2.5'), 2.5)
    assert result is True, f"Test 8 failed: {result}, diff={diff}"
    print("[PASS] Test 8: Decimal vs float (equal)")

    # Test 9: Very small differences (at tolerance boundary)
    result, diff = safe_numeric_compare(1.0000, 1.0005)
    assert result is True, f"Test 9 failed: {result}, diff={diff}"
    print("[PASS] Test 9: Small difference (0.0005, within tolerance)")

    result, diff = safe_numeric_compare(1.0000, 1.0015)
    assert result is False, f"Test 9b failed: {result}, diff={diff}"
    print("[PASS] Test 9b: Small difference (0.0015, outside tolerance)")

    # Test 10: The exact scenario from the bug report
    db_thickness = Decimal('0.500')  # From database NUMERIC field
    shared_thickness = 0.5  # From analysis (float)
    result, diff = safe_numeric_compare(db_thickness, shared_thickness)
    assert result is True, f"Test 10 failed: {result}, diff={diff}"
    print("[PASS] Test 10: Bug scenario - Decimal('0.500') vs float(0.5)")

    print("\n[SUCCESS] All tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_safe_numeric_compare()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
