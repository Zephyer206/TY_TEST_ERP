"""Regression coverage for the legacy price-account compatibility surface."""

from decimal import Decimal
from datetime import datetime

from app.api.price_accounts import _account_to_response
from app.models.price import PriceAccount, PriceYear


def test_price_account_legacy_fields_map_to_prices_columns() -> None:
    account = PriceAccount(
        part_id=10,
        customer_id=20,
        material="SPCC",
        net_weight_kg=Decimal("0.125"),
        gross_weight_kg=Decimal("0.140"),
        notes="legacy client",
    )

    assert account.material_name == "SPCC"
    assert account.net_weight == Decimal("0.125")
    assert account.gross_weight == Decimal("0.140")
    assert account.remark == "legacy client"


def test_price_account_response_uses_price_years_without_old_relations() -> None:
    account = PriceAccount(
        id=99,
        part_id=10,
        customer_id=20,
        material_name="SPCC",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    account.annual_records = [
        PriceYear(
            id=1,
            price_id=account.id,
            year=2026,
            unit_price=Decimal("12.3400"),
            annual_sales=100,
            operator_id=7,
            updated_at=datetime(2026, 1, 1),
        )
    ]

    response = _account_to_response(account)

    assert response.annual_records[0].price_account_id == 99
    assert response.annual_records[0].annual_qty == 100
    assert response.annual_records[0].created_by == 7
    assert response.current_price == Decimal("12.3400")
    assert response.adjustments == []
