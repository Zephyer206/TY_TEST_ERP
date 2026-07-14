#!/usr/bin/env python3
"""
Tests for classify_legacy_customer_refs.py

Focuses on has_explicit_template_identity() function to ensure correct
classification of parts with template/header identities vs. normal business values.
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from classify_legacy_customer_refs import (
    has_explicit_template_identity,
    is_explicit_header_or_template_value,
)


def test_explicit_value_does_not_treat_missing_as_template():
    assert is_explicit_header_or_template_value(None) is False
    assert is_explicit_header_or_template_value('') is False
    assert is_explicit_header_or_template_value('   ') is False


def test_explicit_value_detects_real_template_text():
    assert is_explicit_header_or_template_value('客户名称') is True
    assert is_explicit_header_or_template_value('模具编号') is True
    assert is_explicit_header_or_template_value('...') is True


def test_explicit_template_customer_name():
    """Test that '客户名称' in any field is detected as template."""
    part = {
        'id': 1,
        'mold_number': '客户名称',
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "Should detect '客户名称' as template"


def test_explicit_template_mold_number():
    """Test that '模具编号' in any field is detected as template."""
    part = {
        'id': 2,
        'mold_number': None,
        'press_tonnage': '模具编号',
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "Should detect '模具编号' as template"


def test_explicit_template_internal_name():
    """Test that '内部名称' in any field is detected as template."""
    part = {
        'id': 3,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': '内部名称'
    }
    assert has_explicit_template_identity(part) == True, "Should detect '内部名称' as template"


def test_explicit_template_customer_part_no():
    """Test that '客户件号' in customer_product_no is detected as template."""
    part = {
        'id': 4,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': '客户件号',
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "Should detect '客户件号' as template"


def test_explicit_template_product_name():
    """Test that '产品名称' in any field is detected as template."""
    part = {
        'id': 5,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': '产品名称',
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "Should detect '产品名称' as template"


def test_underscore_placeholder():
    """Test that underscore placeholders are detected as template."""
    part = {
        'id': 6,
        'mold_number': '___',
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "Should detect '___' as template"


def test_ellipsis_placeholder():
    """Test that ellipsis placeholders are detected as template."""
    part = {
        'id': 7,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': '...',
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "Should detect '...' as template"


def test_all_empty_fields_not_template():
    """Test that all empty/None fields does NOT count as explicit template."""
    part = {
        'id': 8,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == False, "All empty fields should NOT be template"


def test_all_empty_strings_not_template():
    """Test that all empty strings does NOT count as explicit template."""
    part = {
        'id': 9,
        'mold_number': '',
        'press_tonnage': '',
        'ppap_no': '',
        'customer_product_no': '',
        'internal_name': ''
    }
    assert has_explicit_template_identity(part) == False, "All empty strings should NOT be template"


def test_some_empty_with_normal_values_not_template():
    """Test that some empty fields with normal business values is NOT template."""
    part = {
        'id': 10,
        'mold_number': 'TY-123-Q',
        'press_tonnage': None,
        'ppap_no': '',
        'customer_product_no': 'CP-456',
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == False, "Normal business values should NOT be template"


def test_normal_business_values_not_template():
    """Test that all normal business values are NOT template."""
    part = {
        'id': 11,
        'mold_number': 'TY-789-M',
        'press_tonnage': '80',
        'ppap_no': 'PPAP-001',
        'customer_product_no': 'CP-789',
        'internal_name': '端子模'
    }
    assert has_explicit_template_identity(part) == False, "All normal business values should NOT be template"


def test_mixed_template_and_normal():
    """Test that template identity in one field triggers detection even with normal values in others."""
    part = {
        'id': 12,
        'mold_number': 'TY-999-Q',
        'press_tonnage': None,
        'ppap_no': '客户',
        'customer_product_no': 'CP-999',
        'internal_name': '冲模'
    }
    assert has_explicit_template_identity(part) == True, "Should detect template even with normal values present"


def test_whitespace_only_not_template():
    """Test that whitespace-only values do NOT count as explicit template."""
    part = {
        'id': 13,
        'mold_number': '   ',
        'press_tonnage': '\t',
        'ppap_no': None,
        'customer_product_no': '',
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == False, "Whitespace-only should NOT be explicit template"


def test_chinese_normal_text_not_template():
    """Test that normal Chinese business text is NOT detected as template."""
    part = {
        'id': 14,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': '温州力邦企业'
    }
    assert has_explicit_template_identity(part) == False, "Normal Chinese text should NOT be template"


def test_all_underscores_in_field():
    """Test that a field with all underscores is detected as template."""
    part = {
        'id': 15,
        'mold_number': '_____',
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "All underscores should be template"


def test_all_hashes_in_field():
    """Test that a field with all hash symbols is detected as template."""
    part = {
        'id': 16,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': '####',
        'customer_product_no': None,
        'internal_name': None
    }
    assert has_explicit_template_identity(part) == True, "All hash symbols should be template"


def test_partial_template_like_text_not_template():
    """Test that text containing template keywords but not exact match is NOT template."""
    part = {
        'id': 17,
        'mold_number': None,
        'press_tonnage': None,
        'ppap_no': None,
        'customer_product_no': None,
        'internal_name': '客户名称ABC'  # Contains but not equal to template keyword
    }
    assert has_explicit_template_identity(part) == False, "Partial match should NOT be template"


def run_all_tests():
    """Run all tests and report results."""
    test_functions = [
        test_explicit_template_customer_name,
        test_explicit_template_mold_number,
        test_explicit_template_internal_name,
        test_explicit_template_customer_part_no,
        test_explicit_template_product_name,
        test_underscore_placeholder,
        test_ellipsis_placeholder,
        test_all_empty_fields_not_template,
        test_all_empty_strings_not_template,
        test_some_empty_with_normal_values_not_template,
        test_normal_business_values_not_template,
        test_mixed_template_and_normal,
        test_whitespace_only_not_template,
        test_chinese_normal_text_not_template,
        test_all_underscores_in_field,
        test_all_hashes_in_field,
        test_partial_template_like_text_not_template,
    ]

    passed = 0
    failed = 0

    print("Running tests for has_explicit_template_identity()...")
    print("=" * 70)

    for test_func in test_functions:
        try:
            test_func()
            print(f"PASS {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"FAIL {test_func.__name__}: Unexpected error: {e}")
            failed += 1

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_functions)} tests")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
