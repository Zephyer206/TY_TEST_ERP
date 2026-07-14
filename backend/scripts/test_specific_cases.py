#!/usr/bin/env python3
"""
Focused test for the specific bug cases mentioned by the user.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from import_excel_authoritative import parse_combined_spec


def test_specific_bug_cases():
    """Test the specific cases that were failing before the fix."""
    print("="*80)
    print("Testing Specific Bug Cases")
    print("="*80)

    # Test cases from user requirements
    cases = [
        # Cases that were failing due to isalpha() rejecting Chinese "出"
        ("0.5*96*165(1出2)", (0.5, 96.0, 165.0), "CRITICAL: Was failing due to Chinese char"),
        ("1.6*98*19（一出二，左右各一个）", (1.6, 98.0, 19.0), "CRITICAL: Was failing due to Chinese char"),

        # Complete/partial valid cases
        ("0.8*34*34.5", (0.8, 34.0, 34.5), "Complete spec"),
        ("0.4*", (0.4, None, None), "Partial with trailing *"),
        ("0.4*92", (0.4, 92.0, None), "Partial T+W"),

        # Invalid cases that should return all None
        ("4.0**155*43", (None, None, None), "Double separator - ambiguous"),
        ("XC2.39.81/XC2.39.16", (None, None, None), "Part number with letter prefix"),
        ("SUS301", (None, None, None), "Material code"),

        # T/W/P prefix support
        ("T1.2*W50*P40", (1.2, 50.0, 40.0), "T/W/P prefixes"),
    ]

    all_passed = True

    for i, (input_str, expected, description) in enumerate(cases, 1):
        result = parse_combined_spec(input_str)
        passed = result == expected

        status = "[PASS]" if passed else "[FAIL]"
        all_passed = all_passed and passed

        print(f"\n{status} Test #{i}: {description}")
        print(f"  Input:    {repr(input_str)}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")

        if not passed:
            print("  >>> MISMATCH <<<")

    print("\n" + "="*80)
    if all_passed:
        print("SUCCESS: All specific bug cases passed!")
    else:
        print("FAILURE: Some tests failed")
    print("="*80)

    return all_passed


if __name__ == "__main__":
    success = test_specific_bug_cases()
    sys.exit(0 if success else 1)
