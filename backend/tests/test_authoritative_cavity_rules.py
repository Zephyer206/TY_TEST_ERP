"""Regression tests for authoritative cavity parsing and pairing evidence."""

from scripts.import_excel_authoritative import parse_cavity_count


def test_left_right_tooling_wording_is_not_cavity_evidence():
    assert parse_cavity_count("2.0*82*31", "注：下料模左右各一套") is None
    assert parse_cavity_count("0.4*32*64.5（左右各一条料带）", "") is None


def test_explicit_arabic_and_chinese_cavity_counts_are_parsed():
    assert parse_cavity_count("2.0*178*37（一出二，左右各1个）", "") == 2
    assert parse_cavity_count("0.5*60*21（一出三）", "") == 3
    assert parse_cavity_count("0.5*60*21", "备注：1出4") == 4


def test_dimensions_and_numbered_part_identifiers_are_not_cavity_counts():
    assert parse_cavity_count("1*90*88", "") is None
    assert parse_cavity_count("TYAI-Q0143-1 / TYAI-Q0143-2", "") is None
