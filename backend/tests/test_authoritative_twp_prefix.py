"""Regression tests for Chinese-prefixed T/W/P source specifications."""

from scripts.import_excel_authoritative import parse_combined_spec


def test_continuous_mold_chinese_prefix_preserves_full_twp():
    assert parse_combined_spec("（连续模规格：0.5*70*70）") == (0.5, 70.0, 70.0)


def test_known_spec_prefixes_keep_partial_specs_supported():
    assert parse_combined_spec("规格：0.5*70*70") == (0.5, 70.0, 70.0)
    assert parse_combined_spec("用料规格：0.4*") == (0.4, None, None)
    assert parse_combined_spec("TWP规格：W70*P70") == (None, 70.0, 70.0)


def test_two_unlabelled_values_are_not_guessed_as_width_pitch():
    assert parse_combined_spec("规格：70*70") == (None, None, None)


def test_customer_part_and_material_identifiers_are_rejected():
    assert parse_combined_spec("35D041348/35D041349") == (None, None, None)
    assert parse_combined_spec("35D041348*70*70") == (None, None, None)
    assert parse_combined_spec("SUS301-CSP3/4H") == (None, None, None)
    assert parse_combined_spec("客户件号：0.5*70*70") == (None, None, None)


def test_consecutive_asterisks_treated_as_single_separator():
    """Consecutive runs of 2+ asterisks are normalized to one separator."""
    assert parse_combined_spec("1.0**36*32") == (1.0, 36.0, 32.0)
    assert parse_combined_spec("0.4*44**41") == (0.4, 44.0, 41.0)
    assert parse_combined_spec("0.4*80**70") == (0.4, 80.0, 70.0)


def test_trailing_note_with_full_width_parentheses():
    """Trailing notes like （一出二个产品） are stripped before parsing."""
    assert parse_combined_spec("1.2**62*14（一出二个产品）") == (1.2, 62.0, 14.0)
    assert parse_combined_spec("0.8*50*45（一出二个产品）") == (0.8, 50.0, 45.0)
    # ASCII parentheses
    assert parse_combined_spec("1.2**62*14(一出二个产品)") == (1.2, 62.0, 14.0)
    # Simplified form 1出2个产品
    assert parse_combined_spec("1.2*62*14（1出2个产品）") == (1.2, 62.0, 14.0)
    assert parse_combined_spec("0.5*70*70(1出2个产品)") == (0.5, 70.0, 70.0)


def test_trailing_note_without_product_text():
    """Trailing notes like （一出二） without 个产品 are also supported."""
    assert parse_combined_spec("1.2*62*14（一出二）") == (1.2, 62.0, 14.0)
    assert parse_combined_spec("0.8*50*45(1出2)") == (0.8, 50.0, 45.0)
