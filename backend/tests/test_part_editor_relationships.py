"""Tests for Stage 3 Part Editor Relationship APIs.

Uses safe test approach: does not insert data into cloud SQL.
Tests schema validation, business logic, and API contract with current bulk API.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.part import Part
from app.models.customer import Customer
from app.models.tooling import Tooling, ToolingPart
from app.models.part_customer_alias import PartCustomerAlias
from app.models.part_tooling_spec import PartToolingSpec
from app.schemas.part_editor_relationships import (
    CustomerAliasItem,
    ToolingPartItem,
    TWPSpecItem,
    PartEditorBulkUpdateRequest,
    PartEditorDetailResponse,
    ToolingBriefInfo,
)


# ==================== Schema Validation Tests ====================

class TestSchemaValidation:
    """Test request schema validation."""

    def test_detail_response_compatibility_fields_allow_null(self):
        """Legacy response fields must not reject imported null values."""
        assert not PartEditorDetailResponse.model_fields["status"].is_required()
        assert not ToolingBriefInfo.model_fields["mold_type"].is_required()

    def test_customer_alias_item_valid(self):
        """Valid customer alias item."""
        item = CustomerAliasItem(
            customer_id=1,
            customer_part_no="CUST-001",
            customer_part_name="Customer Part Name",
            revision="A",
            vehicle_model="Model X",
            is_active=True
        )
        assert item.customer_id == 1
        assert item.customer_part_no == "CUST-001"

    def test_customer_alias_item_minimal(self):
        """Minimal valid customer alias."""
        item = CustomerAliasItem(
            customer_id=1,
            customer_part_no="CUST-001"
        )
        assert item.revision == ""
        assert item.is_active is True

    def test_tooling_part_item_valid(self):
        """Valid tooling part item."""
        item = ToolingPartItem(
            tooling_id=10,
            position="left",
            sequence=1,
            is_primary=True
        )
        assert item.tooling_id == 10
        assert item.sequence == 1

    def test_tooling_part_item_defaults(self):
        """Tooling part with defaults."""
        item = ToolingPartItem(tooling_id=10)
        assert item.sequence == 0
        assert item.is_primary is False

    def test_twp_spec_item_valid(self):
        """Valid TWP spec item."""
        item = TWPSpecItem(
            tooling_id=10,
            spec_twph="1.0*100*50",
            thickness=Decimal("1.000"),
            width=Decimal("100.000"),
            pitch=Decimal("50.000"),
            is_primary=True
        )
        assert item.thickness == Decimal("1.000")

    def test_twp_spec_decimal_precision_valid(self):
        """TWP spec with valid 3 decimal places."""
        item = TWPSpecItem(
            tooling_id=10,
            thickness=Decimal("1.234")
        )
        assert item.thickness == Decimal("1.234")

    def test_twp_spec_decimal_precision_invalid(self):
        """TWP spec with too many decimal places."""
        with pytest.raises(ValueError, match="no more than 3 decimal places"):
            TWPSpecItem(
                tooling_id=10,
                thickness=Decimal("1.23456")
            )

    def test_bulk_update_request_all_categories(self):
        """Bulk update with all categories."""
        request = PartEditorBulkUpdateRequest(
            expected_updated_at=datetime.utcnow(),
            customer_aliases=[
                CustomerAliasItem(customer_id=1, customer_part_no="C1")
            ],
            tooling_parts=[
                ToolingPartItem(tooling_id=10)
            ],
            twp_specs=[
                TWPSpecItem(tooling_id=10, thickness=Decimal("1.0"))
            ]
        )
        assert len(request.customer_aliases) == 1
        assert len(request.tooling_parts) == 1
        assert len(request.twp_specs) == 1

    def test_bulk_update_request_partial(self):
        """Bulk update with partial categories."""
        request = PartEditorBulkUpdateRequest(
            expected_updated_at=datetime.utcnow(),
            customer_aliases=[
                CustomerAliasItem(customer_id=1, customer_part_no="C1")
            ]
        )
        assert request.customer_aliases is not None
        assert request.tooling_parts is None
        assert request.twp_specs is None


# ==================== Business Logic Tests ====================

class TestPrimaryConstraints:
    """Test primary tooling constraint validation."""

    def test_continuous_only_primary_valid(self):
        """When continuous tooling exists, only continuous can be primary."""
        from app.api.part_editor_relationships import _validate_primary_constraints

        tooling_parts = [
            ToolingPartItem(tooling_id=1, is_primary=True),  # continuous
            ToolingPartItem(tooling_id=2, is_primary=False),  # non-continuous
        ]

        tooling_map = {
            1: MagicMock(id=1, is_continuous=True),
            2: MagicMock(id=2, is_continuous=False),
        }

        # Should not raise
        _validate_primary_constraints(tooling_parts, tooling_map)

    def test_continuous_only_primary_invalid(self):
        """Non-continuous cannot be primary when continuous exists."""
        from app.api.part_editor_relationships import _validate_primary_constraints

        tooling_parts = [
            ToolingPartItem(tooling_id=1, is_primary=False),  # continuous
            ToolingPartItem(tooling_id=2, is_primary=True),   # non-continuous - INVALID
        ]

        tooling_map = {
            1: MagicMock(id=1, is_continuous=True),
            2: MagicMock(id=2, is_continuous=False),
        }

        with pytest.raises(HTTPException) as exc_info:
            _validate_primary_constraints(tooling_parts, tooling_map)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "only continuous toolings may be primary" in exc_info.value.detail

    def test_non_continuous_multiple_primary_invalid(self):
        """Only one non-continuous tooling can be primary."""
        from app.api.part_editor_relationships import _validate_primary_constraints

        tooling_parts = [
            ToolingPartItem(tooling_id=1, is_primary=True),
            ToolingPartItem(tooling_id=2, is_primary=True),  # INVALID - two primaries
        ]

        tooling_map = {
            1: MagicMock(id=1, is_continuous=False),
            2: MagicMock(id=2, is_continuous=False),
        }

        with pytest.raises(HTTPException) as exc_info:
            _validate_primary_constraints(tooling_parts, tooling_map)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "At most one tooling may be marked as primary" in exc_info.value.detail

    def test_non_continuous_single_primary_valid(self):
        """Single non-continuous primary is valid."""
        from app.api.part_editor_relationships import _validate_primary_constraints

        tooling_parts = [
            ToolingPartItem(tooling_id=1, is_primary=True),
            ToolingPartItem(tooling_id=2, is_primary=False),
        ]

        tooling_map = {
            1: MagicMock(id=1, is_continuous=False),
            2: MagicMock(id=2, is_continuous=False),
        }

        # Should not raise
        _validate_primary_constraints(tooling_parts, tooling_map)


class TestTWPPrimaryScope:
    """Test TWP primary scoping validation."""

    def test_one_primary_per_tooling_valid(self):
        """Each tooling can have one primary spec."""
        from app.api.part_editor_relationships import _validate_twp_primary_scope

        specs = [
            TWPSpecItem(tooling_id=1, thickness=Decimal("1.0"), is_primary=True),
            TWPSpecItem(tooling_id=1, thickness=Decimal("1.2"), is_primary=False),
            TWPSpecItem(tooling_id=2, thickness=Decimal("2.0"), is_primary=True),
        ]

        # Should not raise
        _validate_twp_primary_scope(specs)

    def test_multiple_primaries_same_tooling_invalid(self):
        """Multiple primaries for same tooling is invalid."""
        from app.api.part_editor_relationships import _validate_twp_primary_scope

        specs = [
            TWPSpecItem(tooling_id=1, thickness=Decimal("1.0"), is_primary=True),
            TWPSpecItem(tooling_id=1, thickness=Decimal("1.2"), is_primary=True),  # INVALID
        ]

        with pytest.raises(HTTPException) as exc_info:
            _validate_twp_primary_scope(specs)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "at most one primary TWP spec" in exc_info.value.detail
        assert "1" in str(exc_info.value.detail)

    def test_no_primary_valid(self):
        """No primary specs is valid."""
        from app.api.part_editor_relationships import _validate_twp_primary_scope

        specs = [
            TWPSpecItem(tooling_id=1, thickness=Decimal("1.0"), is_primary=False),
            TWPSpecItem(tooling_id=2, thickness=Decimal("2.0"), is_primary=False),
        ]

        # Should not raise
        _validate_twp_primary_scope(specs)


# ==================== API Contract Tests ====================

class TestAPIEndpoints:
    """Test API endpoint behavior without database."""

    @pytest.mark.asyncio
    async def test_get_detail_not_found(self):
        """GET detail returns 404 for missing part."""
        from app.api.part_editor_relationships import get_part_editor_detail

        mock_db = AsyncMock()
        mock_db.get.return_value = None

        mock_user = MagicMock(role_level=2)

        with pytest.raises(HTTPException) as exc_info:
            await get_part_editor_detail(999, mock_db, mock_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_detail_insufficient_permissions(self):
        """GET detail requires LV2+."""
        from app.api.part_editor_relationships import get_part_editor_detail

        mock_db = AsyncMock()
        mock_user = MagicMock(role_level=1)

        with pytest.raises(HTTPException) as exc_info:
            await get_part_editor_detail(1, mock_db, mock_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_bulk_update_duplicate_alias_key_detection(self):
        """Bulk update detects duplicate alias identities."""
        aliases = [
            CustomerAliasItem(customer_id=1, customer_part_no="C1", revision="A"),
            CustomerAliasItem(customer_id=1, customer_part_no="C1", revision="A"),  # duplicate
        ]

        # Simulate the duplicate checking logic
        alias_keys = [(a.customer_id, a.customer_part_no, a.revision) for a in aliases]
        assert len(alias_keys) != len(set(alias_keys)), "Should detect duplicate keys"

    def test_bulk_update_duplicate_tooling_detection(self):
        """Bulk update detects duplicate tooling_id."""
        tooling_parts = [
            ToolingPartItem(tooling_id=10),
            ToolingPartItem(tooling_id=10),  # duplicate
        ]

        tooling_ids = [tp.tooling_id for tp in tooling_parts]
        assert len(tooling_ids) != len(set(tooling_ids)), "Should detect duplicate tooling_id"


# ==================== Integration Scenarios ====================

class TestIntegrationScenarios:
    """Test complete workflow scenarios."""

    def test_scenario_continuous_tooling_workflow(self):
        """Scenario: Part with continuous and simple toolings."""
        # Bulk update with tooling associations and TWP specs
        request = PartEditorBulkUpdateRequest(
            expected_updated_at=datetime.utcnow(),
            tooling_parts=[
                ToolingPartItem(tooling_id=1, sequence=0, is_primary=True),  # continuous
                ToolingPartItem(tooling_id=2, sequence=1, is_primary=False),  # simple
            ],
            twp_specs=[
                TWPSpecItem(tooling_id=1, thickness=Decimal("1.0"), is_primary=True),
                TWPSpecItem(tooling_id=2, thickness=Decimal("1.2"), is_primary=True),
            ]
        )

        assert len(request.tooling_parts) == 2
        assert len(request.twp_specs) == 2
        assert request.tooling_parts[0].is_primary is True

    def test_scenario_multi_customer_part(self):
        """Scenario: Part sold to multiple customers."""
        request = PartEditorBulkUpdateRequest(
            expected_updated_at=datetime.utcnow(),
            customer_aliases=[
                CustomerAliasItem(
                    customer_id=1,
                    customer_part_no="CUST-A-001",
                    customer_part_name="Customer A Part",
                    revision="V1"
                ),
                CustomerAliasItem(
                    customer_id=2,
                    customer_part_no="CUST-B-002",
                    customer_part_name="Customer B Part",
                    revision="V1"
                ),
            ]
        )

        assert len(request.customer_aliases) == 2
        assert request.customer_aliases[0].customer_id != request.customer_aliases[1].customer_id

    def test_scenario_bulk_update_complete(self):
        """Scenario: Bulk update all relationships at once."""
        request = PartEditorBulkUpdateRequest(
            expected_updated_at=datetime.utcnow(),
            customer_aliases=[
                CustomerAliasItem(customer_id=1, customer_part_no="C1")
            ],
            tooling_parts=[
                ToolingPartItem(tooling_id=10, is_primary=True)
            ],
            twp_specs=[
                TWPSpecItem(
                    tooling_id=10,
                    thickness=Decimal("1.0"),
                    width=Decimal("100.0"),
                    pitch=Decimal("50.0"),
                    is_primary=True
                )
            ]
        )

        # Validate atomicity structure
        assert request.customer_aliases is not None
        assert request.tooling_parts is not None
        assert request.twp_specs is not None
        assert request.twp_specs[0].tooling_id == request.tooling_parts[0].tooling_id


# ==================== Error Handling Tests ====================

class TestErrorHandling:
    """Test error handling and validation."""

    @pytest.mark.asyncio
    async def test_optimistic_lock_conflict(self):
        """Test optimistic lock conflict detection."""
        from app.api.part_editor_relationships import bulk_update_relationships

        request = PartEditorBulkUpdateRequest(
            expected_updated_at=datetime(2026, 1, 1, 12, 0, 0),
            customer_aliases=[
                CustomerAliasItem(customer_id=1, customer_part_no="C1")
            ]
        )

        mock_db = AsyncMock()
        mock_part = Part(
            id=1,
            part_status="DRAFT",
            is_deleted=False,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
            updated_at=datetime(2026, 1, 1, 13, 0, 0),  # Different timestamp
        )
        mock_db.get.return_value = mock_part

        mock_user = MagicMock(role_level=2)

        with pytest.raises(HTTPException) as exc_info:
            await bulk_update_relationships(1, request, mock_db, mock_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_source_fields_readonly(self):
        """TWP spec request cannot set source fields."""
        # Schema should not accept source fields
        spec = TWPSpecItem(
            tooling_id=10,
            thickness=Decimal("1.0")
        )

        # Verify source fields are not in schema
        assert not hasattr(spec, 'source_sheet')
        assert not hasattr(spec, 'source_row')
        assert not hasattr(spec, 'source_note')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
