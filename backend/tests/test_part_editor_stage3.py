"""Stage 3 Part Editor - Mock-only tests for relationship management.

Tests source preservation, validation constraints, and API behavior without cloud writes.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.part_editor_relationships import TWPSpecItem


# ==================== Test Validation Constraints ====================

def test_forbid_source_input_in_request():
    """Test that request schema rejects source_sheet/source_row/source_note."""
    # This is enforced by Pydantic extra='forbid'
    with pytest.raises(ValidationError):
        TWPSpecItem(
            tooling_id=1,
            thickness=Decimal("1.5"),
            source_sheet="Sheet1",  # Should be rejected by extra='forbid'
        )


def test_twp_spec_accepts_valid_fields():
    """Test that TWP spec accepts valid fields."""
    spec = TWPSpecItem(
        id=10,
        tooling_id=1,
        thickness=Decimal("1.5"),
        width=Decimal("100.0"),
        pitch=Decimal("50.0"),
        is_primary=True,
    )
    assert spec.id == 10
    assert spec.tooling_id == 1
    assert spec.thickness == Decimal("1.5")


@pytest.mark.asyncio
async def test_twp_upsert_preserves_source_fields():
    """Test that upserting a TWP spec preserves source fields."""
    from app.api.part_editor_relationships import bulk_update_relationships
    from app.schemas.part_editor_relationships import PartEditorBulkUpdateRequest, TWPSpecItem
    from app.models.part import Part
    from app.models.part_tooling_spec import PartToolingSpec
    from app.models.tooling import Tooling, ToolingPart

    # Setup mocks
    mock_db = AsyncMock()
    mock_user = MagicMock(role_level=2)

    # Mock part
    mock_part = Part(
        id=1,
        part_status="DRAFT",
        is_deleted=False,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    # Existing spec with source fields
    existing_spec = PartToolingSpec(
        id=100,
        part_id=1,
        tooling_id=10,
        thickness=Decimal("1.0"),
        source_sheet="ImportSheet",
        source_row=42,
        source_note="Original import",
    )

    mock_db.get.side_effect = lambda model, pk: {
        (Part, 1): mock_part,
        (PartToolingSpec, 100): existing_spec,
    }.get((model, pk))

    # Mock tooling validation
    mock_tooling = Tooling(id=10, tooling_number="T010", is_continuous=False, is_deleted=False)

    tooling_result = MagicMock()
    tooling_result.scalars.return_value.all.return_value = [mock_tooling]
    existing_spec_result = MagicMock()
    existing_spec_result.scalars.return_value.all.return_value = [existing_spec]
    associated_tooling_result = MagicMock()
    associated_tooling_result.fetchall.return_value = [(10,)]
    mock_db.execute = AsyncMock(
        side_effect=[tooling_result, existing_spec_result, associated_tooling_result]
    )
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Request to update spec without touching source fields
    request = PartEditorBulkUpdateRequest(
        expected_updated_at=datetime(2026, 1, 1, 12, 0, 0),
        twp_specs=[
            TWPSpecItem(
                id=100,
                tooling_id=10,
                thickness=Decimal("1.5"),  # Changed
                is_primary=True,
            )
        ],
    )

    # Execute
    await bulk_update_relationships(1, request, mock_db, mock_user)

    # Verify source fields were preserved
    assert existing_spec.source_sheet == "ImportSheet"
    assert existing_spec.source_row == 42
    assert existing_spec.source_note == "Original import"
    # Verify mutable fields were updated
    assert existing_spec.thickness == Decimal("1.5")
    assert existing_spec.is_primary is True


@pytest.mark.asyncio
async def test_alias_id_preserved_on_update():
    """Test that alias IDs are preserved during update, not regenerated."""
    from app.api.part_editor_relationships import bulk_update_relationships
    from app.schemas.part_editor_relationships import PartEditorBulkUpdateRequest, CustomerAliasItem
    from app.models.part import Part
    from app.models.part_customer_alias import PartCustomerAlias

    mock_db = AsyncMock()
    mock_user = MagicMock(role_level=2)

    mock_part = Part(
        id=1,
        part_status="DRAFT",
        is_deleted=False,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 1, 12, 0, 0),
    )

    existing_alias = PartCustomerAlias(
        id=50,
        part_id=1,
        customer_id=1,
        customer_part_no="OLD-123",
        revision="A",
    )

    mock_db.get.side_effect = lambda model, pk: {
        (Part, 1): mock_part,
        (PartCustomerAlias, 50): existing_alias,
    }.get((model, pk))

    customer_result = MagicMock()
    customer_result.fetchall.return_value = [(1,)]
    mock_db.execute = AsyncMock(return_value=customer_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    request = PartEditorBulkUpdateRequest(
        expected_updated_at=datetime(2026, 1, 1, 12, 0, 0),
        customer_aliases=[
            CustomerAliasItem(
                id=50,  # Existing ID
                customer_id=1,
                customer_part_no="NEW-456",  # Changed
                revision="A",
            )
        ],
    )

    # Execute
    await bulk_update_relationships(1, request, mock_db, mock_user)

    # Verify ID was preserved and part number was updated
    assert existing_alias.id == 50
    assert existing_alias.customer_part_no == "NEW-456"


@pytest.mark.asyncio
async def test_retained_primary_tooling_plus_upsert_primary_rejected():
    """Test that validation rejects when retained primary + upsert primary both exist."""
    from app.api.part_editor_relationships import _validate_effective_state
    from app.schemas.part_editor_relationships import PartEditorBulkUpdateRequest, ToolingPartItem
    from app.models.tooling import ToolingPart

    mock_db = AsyncMock()

    # Existing primary association (retained, not in request)
    existing_tp_primary = ToolingPart(
        id=200,
        part_id=1,
        tooling_id=10,
        is_primary=True,
        sequence=0,
    )

    # Another existing association
    existing_tp_other = ToolingPart(
        id=201,
        part_id=1,
        tooling_id=11,
        is_primary=False,
        sequence=1,
    )

    current_tooling_result = MagicMock()
    current_tooling_result.scalars.return_value.all.return_value = [
        existing_tp_primary,
        existing_tp_other,
    ]
    mock_db.execute = AsyncMock(return_value=current_tooling_result)

    # Request to partially update: mark existing_tp_other as primary
    # This should fail because existing_tp_primary (retained, not in request) is already primary
    request = PartEditorBulkUpdateRequest(
        expected_updated_at=datetime(2026, 1, 1, 12, 0, 0),
        tooling_parts=[
            ToolingPartItem(
                id=201,  # Update existing
                tooling_id=11,
                is_primary=True,  # Try to make this primary too
                sequence=1,
            )
        ],
    )

    # Should raise 400 due to multiple primaries in final state
    with pytest.raises(HTTPException) as exc_info:
        await _validate_effective_state(mock_db, 1, request)

    assert exc_info.value.status_code == 400
    assert "At most one tooling may be marked as primary" in exc_info.value.detail
    assert "primaries in final state" in exc_info.value.detail


@pytest.mark.asyncio
async def test_retained_primary_twp_spec_plus_upsert_primary_rejected():
    """Test that validation rejects when retained primary TWP + upsert primary both exist."""
    from app.api.part_editor_relationships import _validate_effective_state
    from app.schemas.part_editor_relationships import PartEditorBulkUpdateRequest, TWPSpecItem
    from app.models.part_tooling_spec import PartToolingSpec

    mock_db = AsyncMock()

    # Existing primary spec for tooling 10 (retained, not in request)
    existing_spec_primary = PartToolingSpec(
        id=300,
        part_id=1,
        tooling_id=10,
        thickness=Decimal("1.0"),
        is_primary=True,
    )

    # Another spec for same tooling
    existing_spec_other = PartToolingSpec(
        id=301,
        part_id=1,
        tooling_id=10,
        thickness=Decimal("1.5"),
        is_primary=False,
    )

    current_spec_result = MagicMock()
    current_spec_result.scalars.return_value.all.return_value = [
        existing_spec_primary,
        existing_spec_other,
    ]
    mock_db.execute = AsyncMock(return_value=current_spec_result)

    # Request to mark existing_spec_other as primary
    # This should fail because existing_spec_primary (retained) is already primary for tooling 10
    request = PartEditorBulkUpdateRequest(
        expected_updated_at=datetime(2026, 1, 1, 12, 0, 0),
        twp_specs=[
            TWPSpecItem(
                id=301,
                tooling_id=10,
                thickness=Decimal("1.5"),
                is_primary=True,  # Try to make this primary too
            )
        ],
    )

    # Should raise 400 due to multiple primaries for same tooling
    with pytest.raises(HTTPException) as exc_info:
        await _validate_effective_state(mock_db, 1, request)

    assert exc_info.value.status_code == 400
    assert "at most one primary TWP spec" in exc_info.value.detail


@pytest.mark.asyncio
async def test_multiple_distinct_twp_tuples_for_same_tooling_are_allowed():
    """One tooling may retain multiple source-backed TWP tuples."""
    from app.api.part_editor_relationships import _validate_effective_state
    from app.schemas.part_editor_relationships import PartEditorBulkUpdateRequest, TWPSpecItem
    from app.models.part_tooling_spec import PartToolingSpec

    retained_spec = PartToolingSpec(
        id=400,
        part_id=1,
        tooling_id=10,
        thickness=Decimal("1.0"),
        width=Decimal("100.0"),
        pitch=Decimal("50.0"),
        is_primary=True,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [retained_spec]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result)

    request = PartEditorBulkUpdateRequest(
        expected_updated_at=datetime(2026, 1, 1, 12, 0, 0),
        twp_specs=[
            TWPSpecItem(
                tooling_id=10,
                thickness=Decimal("1.0"),
                width=Decimal("120.0"),
                pitch=Decimal("50.0"),
                is_primary=False,
            )
        ],
    )

    await _validate_effective_state(mock_db, 1, request)


@pytest.mark.asyncio
async def test_duplicate_twp_tuple_for_same_tooling_is_rejected():
    """The final state must not contain duplicate T/W/P tuples for one tooling."""
    from app.api.part_editor_relationships import _validate_effective_state
    from app.schemas.part_editor_relationships import PartEditorBulkUpdateRequest, TWPSpecItem
    from app.models.part_tooling_spec import PartToolingSpec

    retained_spec = PartToolingSpec(
        id=401,
        part_id=1,
        tooling_id=10,
        thickness=Decimal("1.0"),
        width=Decimal("100.0"),
        pitch=Decimal("50.0"),
        is_primary=True,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [retained_spec]
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result)

    request = PartEditorBulkUpdateRequest(
        expected_updated_at=datetime(2026, 1, 1, 12, 0, 0),
        twp_specs=[
            TWPSpecItem(
                tooling_id=10,
                thickness=Decimal("1.0"),
                width=Decimal("100.0"),
                pitch=Decimal("50.0"),
                is_primary=False,
            )
        ],
    )

    with pytest.raises(HTTPException, match="duplicate TWP tuples"):
        await _validate_effective_state(mock_db, 1, request)


def test_exactly_one_patch_editor_route():
    """Test that there is exactly one PATCH /parts/{part_id}/editor route, not multiple."""
    import importlib
    import inspect

    # Import both modules
    try:
        part_editor = importlib.import_module('app.api.part_editor')
        parts = importlib.import_module('app.api.parts')

        # Count PATCH routes with 'editor' in the path
        editor_patch_routes = []

        # Check part_editor module
        if hasattr(part_editor, 'router'):
            for route in part_editor.router.routes:
                if hasattr(route, 'path') and 'editor' in route.path:
                    if hasattr(route, 'methods') and 'PATCH' in route.methods:
                        editor_patch_routes.append(('part_editor', route.path))

        # Check parts module
        if hasattr(parts, 'router'):
            for route in parts.router.routes:
                if hasattr(route, 'path') and 'editor' in route.path:
                    if hasattr(route, 'methods') and 'PATCH' in route.methods:
                        editor_patch_routes.append(('parts', route.path))

        # Should have exactly one PATCH editor route across both modules
        assert len(editor_patch_routes) == 1, f"Expected exactly 1 PATCH editor route, found {len(editor_patch_routes)}: {editor_patch_routes}"

    except ImportError as e:
        pytest.skip(f"Could not import modules: {e}")


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
