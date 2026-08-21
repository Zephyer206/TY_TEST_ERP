from types import SimpleNamespace
from decimal import Decimal

import pytest

from scripts.import_after_sales_gaibo import (
    legacy_document_payload,
    legacy_price_evidence,
    normalize_legacy_document_status,
)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, "not_started"),
        ("Drawing OK", "ok"),
        ("Drawing approval date :6.22", "ok"),
        ("Sample sent date:7.10", "in_progress"),
        ("PPAP re_sent date:7.23", "in_progress"),
        ("Estimated sample shipping date: August 20th", "in_progress"),
        ("PPAP NOT OK", "not_ok"),
    ],
)
def test_legacy_document_status_keeps_submission_distinct_from_approval(raw_value, expected):
    assert normalize_legacy_document_status(raw_value) == expected


def test_legacy_document_payload_preserves_yearless_source_text_without_guessing_date():
    kit = SimpleNamespace(
        id=7,
        ppap_status="PPAP send date:7.18",
        source_file_name="FMG.xlsx",
        source_sheet="汇总表1",
        source_row=12,
    )

    payload = legacy_document_payload(kit, "ppap_status", "ppap")

    assert payload["status"] == "in_progress"
    assert payload["submitted_at"] is None
    assert payload["concluded_at"] is None
    assert payload["remark"] == "Excel 原始状态：PPAP send date:7.18"
    assert payload["source_data"]["date_precision"] == "source_text_only_year_missing"


def test_legacy_price_evidence_keeps_fmg_comparison_separate_from_fca_price():
    kit = SimpleNamespace(
        price=Decimal("8.7500"),
        source_data={
            "tianyue_plant_price": 8.75,
            "fmg_price": 8.5,
            "difference": -0.25,
            "price_mismatch": True,
        },
    )

    assert legacy_price_evidence(kit) == {
        "fca_tianyue_plant_price_ttop_usd": 8.75,
        "fmg_price_usd": 8.5,
        "source_difference": -0.25,
        "price_mismatch": True,
    }


def test_legacy_price_evidence_does_not_treat_missing_fmg_price_as_a_mismatch():
    kit = SimpleNamespace(
        price=Decimal("8.7500"),
        source_data={
            "tianyue_plant_price": 8.75,
            "fmg_price": None,
            # The legacy marker can be incomplete or stale.  The new archive
            # determines a discrepancy from the two actual source values.
            "price_mismatch": True,
        },
    )

    evidence = legacy_price_evidence(kit)

    assert evidence["fca_tianyue_plant_price_ttop_usd"] == 8.75
    assert evidence["fmg_price_usd"] is None
    assert evidence["price_mismatch"] is False
