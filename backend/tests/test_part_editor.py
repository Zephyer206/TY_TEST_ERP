"""Tests for part editor API endpoint with optimistic locking."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.part import Part
from app.models.user import User
from app.core.security import create_access_token


@pytest_asyncio.fixture
async def test_user_lv2(db) -> User:
    """Create a test user with LV2 permissions."""
    import time
    unique_suffix = str(int(time.time() * 1000))[-6:]
    user = User(
        username=f"editor_user_{unique_suffix}",
        password="hashed_password_here",
        real_name="Editor User",
        dept="engineering",
        role_level=2,
        position="工程师",
        is_tech=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_lv1(db) -> User:
    """Create a test user with LV1 permissions (insufficient)."""
    import time
    unique_suffix = str(int(time.time() * 1000))[-6:]
    user = User(
        username=f"operator_user_{unique_suffix}",
        password="hashed_password_here",
        real_name="Operator User",
        dept="prod",
        role_level=1,
        position="操作员",
        is_tech=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_part(db) -> Part:
    """Create a test part for editing."""
    # Use timestamp to ensure unique part number across test runs
    import time
    unique_suffix = str(int(time.time() * 1000))[-6:]
    part = Part(
        part_number=f"TEST-{unique_suffix}",
        internal_name="Test Part Original",
        internal_part_no=f"IP-{unique_suffix}",
        customer_product_no="CUST-001",
        customer_product_name="Customer Part Name",
        vehicle_model="Model X",
        material_name="SPCC",
        material_id=None,
        drawing_url="http://example.com/drawing.pdf",
        spec_info="Original spec info",
        spec_twph="T1.0*W50*P100",
        thickness=Decimal("1.000"),
        width=Decimal("50.000"),
        pitch=Decimal("100.000"),
        height=Decimal("10.000"),
        gross_weight=Decimal("0.150"),
        net_weight=Decimal("0.120"),
        part_position="left",
        part_status="DRAFT",
        status="待开发",
        remark="Original remark",
        press_tonnage="60T",
        ppap_no="PPAP-001",
        stock_pcs=100,
        is_deleted=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version="V1.0",
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)
    return part


@pytest.fixture
def auth_headers(test_user_lv2) -> dict:
    """Create authentication headers for LV2 user."""
    token = create_access_token({"sub": str(test_user_lv2.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_lv1(test_user_lv1) -> dict:
    """Create authentication headers for LV1 user."""
    token = create_access_token({"sub": str(test_user_lv1.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_update_part_editor_success(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test successful part update with all editable fields."""
    update_data = {
        "internal_name": "Test Part Updated",
        "internal_part_no": "IP-001-REV",
        "customer_product_no": "CUST-001-A",
        "customer_product_name": "Customer Part Updated",
        "vehicle_model": "Model Y",
        "material_name": "SECC",
        "drawing_url": "http://example.com/drawing-v2.pdf",
        "gross_weight": "0.180",
        "net_weight": "0.150",
        "part_position": "right",
        "part_status": "SAMPLING",
        "status": "样品生产中",
        "remark": "Updated remark",
        "press_tonnage": "80T",
        "ppap_no": "PPAP-002",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify all updated fields
    assert data["id"] == test_part.id
    assert data["internal_name"] == "Test Part Updated"
    assert data["internal_part_no"] == "IP-001-REV"
    assert data["customer_product_no"] == "CUST-001-A"
    assert data["vehicle_model"] == "Model Y"
    assert data["material_name"] == "SECC"
    assert data["drawing_url"] == "http://example.com/drawing-v2.pdf"
    assert data["spec_info"] == "Original spec info"
    assert data["spec_twph"] == "T1.0*W50*P100"
    assert data["thickness"] == "1.000"
    assert data["width"] == "50.000"
    assert data["part_position"] == "right"
    assert data["part_status"] == "SAMPLING"
    assert data["remark"] == "Updated remark"

    # Verify protected fields unchanged
    assert data["part_number"] == test_part.part_number  # Use actual part number, not hardcoded
    assert data["stock_pcs"] == 100
    assert data["is_deleted"] is False

    # Verify timestamp updated
    assert data["updated_at"] != test_part.updated_at.isoformat()


@pytest.mark.asyncio
async def test_update_part_editor_partial(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test partial update (only some fields)."""
    update_data = {
        "internal_name": "Partially Updated",
        "remark": "Only name and remark changed",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify updated fields
    assert data["internal_name"] == "Partially Updated"
    assert data["remark"] == "Only name and remark changed"

    # Verify other fields unchanged
    assert data["customer_product_no"] == "CUST-001"
    assert data["vehicle_model"] == "Model X"
    assert data["thickness"] == "1.000"


@pytest.mark.asyncio
async def test_update_part_editor_optimistic_lock_conflict(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test optimistic lock failure when part was modified by another user."""
    # Simulate another user updating the part
    await db.refresh(test_part)
    test_part.internal_name = "Modified by Another User"
    test_part.updated_at = datetime.utcnow()
    await db.commit()
    new_timestamp = test_part.updated_at

    # Try to update with old timestamp
    old_timestamp = new_timestamp - timedelta(seconds=10)
    update_data = {
        "internal_name": "My Update",
        "remark": "This should conflict",
        "updated_at": old_timestamp.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 409
    data = response.json()

    # Check conflict response structure
    assert "detail" in data
    conflict_detail = data["detail"]
    assert conflict_detail["conflict_type"] == "optimistic_lock"
    assert "client_timestamp" in conflict_detail
    assert "server_timestamp" in conflict_detail
    assert "conflicts" in conflict_detail
    assert "current_part" in conflict_detail

    # Verify current_part contains latest server state
    current = conflict_detail["current_part"]
    assert current["internal_name"] == "Modified by Another User"


@pytest.mark.asyncio
async def test_update_part_editor_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test update of non-existent part."""
    update_data = {
        "internal_name": "Does Not Exist",
        "updated_at": datetime.utcnow().isoformat(),
    }

    response = await client.patch(
        "/api/v1/parts/99999/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_part_editor_deleted_part(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test update of soft-deleted part."""
    # Soft delete the part
    test_part.is_deleted = True
    await db.commit()

    update_data = {
        "internal_name": "Update Deleted",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "deleted" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_part_editor_insufficient_permissions(
    client: AsyncClient,
    test_part: Part,
    auth_headers_lv1: dict,
):
    """Test update with insufficient permissions (LV1 user)."""
    update_data = {
        "internal_name": "Unauthorized Update",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers_lv1,
    )

    assert response.status_code == 403
    assert "LV2" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_part_editor_validation_errors(
    client: AsyncClient,
    test_part: Part,
    auth_headers: dict,
):
    """Test validation errors for invalid field values."""
    # Test invalid part_status
    update_data = {
        "part_status": "INVALID_STATUS",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 422

    # Test invalid part_position
    update_data = {
        "part_position": "invalid_position",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_part_editor_negative_values(
    client: AsyncClient,
    test_part: Part,
    auth_headers: dict,
):
    """Test validation prevents negative values for dimensions/weights."""
    update_data = {
        "gross_weight": "-1.0",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_part_editor_rejects_internal_ids(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test atomic updates - all changes succeed or all fail."""
    original_name = test_part.internal_name
    original_remark = test_part.remark

    # Internal IDs and historical specification fields are not editable here.
    update_data = {
        "internal_name": "Should Not Save",
        "remark": "Should Not Save",
        "material_id": 999999,  # Non-existent foreign key
        "spec_info": "Should remain source-only",
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 422

    # Verify NO changes were saved (atomic rollback)
    await db.refresh(test_part)
    assert test_part.internal_name == original_name
    assert test_part.remark == original_remark


@pytest.mark.asyncio
async def test_update_part_editor_clear_optional_fields(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test clearing optional fields by setting to null."""
    update_data = {
        "remark": None,
        "drawing_url": None,
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["remark"] is None
    assert data["drawing_url"] is None


@pytest.mark.asyncio
async def test_update_part_editor_protected_fields_ignored(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test that protected fields are not updated even if sent."""
    original_stock = test_part.stock_pcs
    original_part_number = test_part.part_number

    update_data = {
        "internal_name": "Updated Name",
        "stock_pcs": 500,  # Protected field - should be ignored
        "part_number": "HACKED-001",  # Protected field - should be ignored
        "updated_at": test_part.updated_at.isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify allowed field updated
    assert data["internal_name"] == "Updated Name"

    # Verify protected fields unchanged
    assert data["stock_pcs"] == original_stock
    assert data["part_number"] == original_part_number


@pytest.mark.asyncio
async def test_update_part_editor_concurrent_updates(
    client: AsyncClient,
    db,
    test_part: Part,
    auth_headers: dict,
):
    """Test that concurrent updates are detected by optimistic locking."""
    original_timestamp = test_part.updated_at

    # First update succeeds
    update_data_1 = {
        "internal_name": "First Update",
        "updated_at": original_timestamp.isoformat(),
    }

    response_1 = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data_1,
        headers=auth_headers,
    )

    assert response_1.status_code == 200
    new_timestamp = datetime.fromisoformat(response_1.json()["updated_at"])

    # Second update with old timestamp fails
    update_data_2 = {
        "internal_name": "Second Update",
        "updated_at": original_timestamp.isoformat(),  # Stale timestamp
    }

    response_2 = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data_2,
        headers=auth_headers,
    )

    assert response_2.status_code == 409

    # Third update with fresh timestamp succeeds
    update_data_3 = {
        "internal_name": "Third Update",
        "updated_at": new_timestamp.isoformat(),  # Fresh timestamp
    }

    response_3 = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data_3,
        headers=auth_headers,
    )

    assert response_3.status_code == 200
    assert response_3.json()["internal_name"] == "Third Update"


@pytest.mark.asyncio
async def test_update_part_editor_unauthenticated(
    client: AsyncClient,
    test_part: Part,
):
    """Test update without authentication."""
    update_data = {
        "internal_name": "Unauthorized",
        "updated_at": datetime.utcnow().isoformat(),
    }

    response = await client.patch(
        f"/api/v1/parts/{test_part.id}/editor",
        json=update_data,
    )

    assert response.status_code == 401
