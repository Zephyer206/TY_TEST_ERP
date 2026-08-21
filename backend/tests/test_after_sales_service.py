from decimal import Decimal

import pytest

from app.services.after_sales_service import (
    GaiboValidationError,
    audit_value,
    changed_values,
    creation_change_data,
    normalize_currency,
    validate_package_item_reference,
)


def test_changed_values_only_audits_real_changes():
    entity = type("Record", (), {"status": "draft", "price": Decimal("1.00")})()

    fields, data = changed_values(entity, {"status": "approved", "price": Decimal("1.00")})

    assert fields == ["status"]
    assert data == {"status": {"before": "draft", "after": "approved"}}
    assert entity.status == "approved"


def test_creation_data_is_json_safe_for_decimal():
    assert creation_change_data({"price": Decimal("12.50")}) == {
        "price": {"before": None, "after": "12.50"}
    }
    assert audit_value(None) is None


def test_currency_is_normalized_and_rejects_invalid_values():
    assert normalize_currency(" usd ") == "USD"
    with pytest.raises(GaiboValidationError):
        normalize_currency("US")
    with pytest.raises(GaiboValidationError):
        normalize_currency("123")


def test_package_item_must_have_exactly_one_reference():
    validate_package_item_reference(12, None)
    validate_package_item_reference(None, "FMG-001")
    with pytest.raises(GaiboValidationError):
        validate_package_item_reference(None, None)
    with pytest.raises(GaiboValidationError):
        validate_package_item_reference(12, "FMG-001")
