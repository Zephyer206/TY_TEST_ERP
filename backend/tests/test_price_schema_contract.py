"""Regression tests for the split price adjustment contracts."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.price import (
    CustomerPriceAdjustmentApprovalRequest,
    CustomerPriceAdjustmentCreate,
    PriceAccountAdjustmentCreate,
)


def test_customer_adjustment_contract_matches_approval_table() -> None:
    request = CustomerPriceAdjustmentCreate(
        customer_id=7,
        material_id=3,
        adjustment_type="material",
        old_price="10.0000",
        new_price="11.2500",
        reason="supplier price change",
    )

    assert request.customer_id == 7
    assert request.material_id == 3
    assert request.new_price == Decimal("11.2500")


def test_price_account_adjustment_contract_stays_separate() -> None:
    request = PriceAccountAdjustmentCreate(new_price="11.25")

    assert request.new_price == Decimal("11.25")
    assert "price_account_id" not in PriceAccountAdjustmentCreate.model_fields


def test_rejected_adjustment_requires_reason() -> None:
    with pytest.raises(ValidationError, match="rejection_reason"):
        CustomerPriceAdjustmentApprovalRequest(status="rejected")

    approved = CustomerPriceAdjustmentApprovalRequest(status="approved")
    assert approved.rejection_reason is None


def test_adjustment_requires_target_matching_adjustment_type() -> None:
    with pytest.raises(ValidationError, match="material_id"):
        CustomerPriceAdjustmentCreate(
            customer_id=7,
            adjustment_type="material",
            new_price="11.25",
        )
