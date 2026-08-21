import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

import import_shanghai_wanxiang_prices as price_import
from scripts.import_excel_authoritative import normalize_customer_part_no


def test_integer_excel_values_have_no_dot_zero():
    assert normalize_customer_part_no(60019492.0) == "60019492"
    assert normalize_customer_part_no("60019492.0") == "60019492"


def test_meaningful_decimals_and_identifiers_are_preserved():
    assert normalize_customer_part_no("12.5") == "12.5"
    assert normalize_customer_part_no("60008581X") == "60008581X"
    assert normalize_customer_part_no("新60007471/60004309X") == "新60007471/60004309X"
    assert price_import.canonical_part_number("12.5") == "12.5"


def test_price_import_canonicalizer_matches_legacy_suffix():
    assert price_import.canonical_part_number("60019492") == price_import.canonical_part_number("60019492.0")


def test_resolve_aliases_rejects_normalized_ambiguity():
    class Cursor:
        def execute(self, query, params):
            self.rows = [(101, "60008581.0"), (102, "60008581.0")]

        def fetchall(self):
            return self.rows

    resolved, missing, ambiguous = price_import.resolve_aliases(Cursor(), 28, ["60008581"])
    assert resolved == {}
    assert missing == []
    assert ambiguous == ["60008581"]
