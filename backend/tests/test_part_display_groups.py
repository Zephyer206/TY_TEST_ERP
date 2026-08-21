"""Tests for explicit part display grouping API.

Stage 2: User-confirmed explicit grouping without name-based inference.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.part import Part
from app.models.tooling import Tooling
from app.models.part_display_group import (
    PartDisplayGroupDef,
    PartDisplayGroupMember,
    SharedFieldGroupDef,
    SharedFieldGroupMember,
)


@pytest.mark.asyncio
async def test_create_left_right_group(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test creating a left/right part display group."""
    # Create two test parts
    left_part = Part(
        part_number="TEST-L-001",
        internal_name="Test Left Part",
        part_position="left",
        part_status="DRAFT",
    )
    right_part = Part(
        part_number="TEST-R-001",
        internal_name="Test Right Part",
        part_position="right",
        part_status="DRAFT",
    )
    db.add_all([left_part, right_part])
    await db.commit()
    await db.refresh(left_part)
    await db.refresh(right_part)

    # Create left/right group
    payload = {
        "group_type": "left_right",
        "group_key": "pair:TEST-001",
        "display_name": "Test Left-Right Pair",
        "members": [
            {"part_id": left_part.id, "position": "left", "sequence": 0},
            {"part_id": right_part.id, "position": "right", "sequence": 1},
        ]
    }

    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["group_type"] == "left_right"
    assert data["group_key"] == "pair:TEST-001"
    assert len(data["members"]) == 2
    assert {m["position"] for m in data["members"]} == {"left", "right"}


@pytest.mark.asyncio
async def test_create_left_right_group_validation(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test left/right group validation constraints."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Must have exactly 2 members
    payload = {
        "group_type": "left_right",
        "group_key": "pair:TEST-SINGLE",
        "members": [
            {"part_id": part1.id, "position": "left", "sequence": 0},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 400
    assert "exactly 2 members" in response.json()["detail"]

    # Must have left and right positions
    payload = {
        "group_type": "left_right",
        "group_key": "pair:TEST-WRONG-POS",
        "members": [
            {"part_id": part1.id, "position": "left", "sequence": 0},
            {"part_id": part2.id, "position": "left", "sequence": 1},  # Wrong: both left
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 400
    assert "left" in response.json()["detail"] and "right" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_shared_source_group(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test creating a shared-source display group."""
    part1 = Part(part_number="TEST-S1-001", internal_name="Shared Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-S2-001", internal_name="Shared Part 2", part_status="DRAFT")
    part3 = Part(part_number="TEST-S3-001", internal_name="Shared Part 3", part_status="DRAFT")
    db.add_all([part1, part2, part3])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)
    await db.refresh(part3)

    # Create shared-source group
    payload = {
        "group_type": "shared_source",
        "group_key": "source:Sheet1:10,11,12",
        "display_name": "Shared Material Group",
        "source_sheet": "Sheet1",
        "source_rows": "10,11,12",
        "members": [
            {"part_id": part1.id, "sequence": 0, "source_row": 10},
            {"part_id": part2.id, "sequence": 1, "source_row": 11},
            {"part_id": part3.id, "sequence": 2, "source_row": 12},
        ]
    }

    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["group_type"] == "shared_source"
    assert data["group_key"] == "source:Sheet1:10,11,12"
    assert len(data["members"]) == 3
    assert data["source_sheet"] == "Sheet1"
    assert data["source_rows"] == "10,11,12"


@pytest.mark.asyncio
async def test_shared_source_group_validation(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test shared-source group validation constraints."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    db.add(part1)
    await db.commit()
    await db.refresh(part1)

    # Must have at least 2 members
    payload = {
        "group_type": "shared_source",
        "group_key": "source:TEST-SINGLE",
        "members": [
            {"part_id": part1.id, "sequence": 0},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 400
    assert "at least 2 members" in response.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_group_key(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that duplicate group keys are rejected."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    part3 = Part(part_number="TEST-003", internal_name="Test Part 3", part_status="DRAFT")
    db.add_all([part1, part2, part3])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)
    await db.refresh(part3)

    # Create first group
    payload1 = {
        "group_type": "shared_source",
        "group_key": "source:DUP-TEST",
        "members": [
            {"part_id": part1.id, "sequence": 0},
            {"part_id": part2.id, "sequence": 1},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload1, headers=lv2_headers)
    assert response.status_code == 201

    # Try to create second group with same key
    payload2 = {
        "group_type": "shared_source",
        "group_key": "source:DUP-TEST",  # Same key
        "members": [
            {"part_id": part3.id, "sequence": 0},
            {"part_id": part1.id, "sequence": 1},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload2, headers=lv2_headers)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_part_in_multiple_active_groups(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that a part cannot be in multiple active groups."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    part3 = Part(part_number="TEST-003", internal_name="Test Part 3", part_status="DRAFT")
    db.add_all([part1, part2, part3])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)
    await db.refresh(part3)

    # Create first group with part1 and part2
    payload1 = {
        "group_type": "shared_source",
        "group_key": "source:GROUP1",
        "members": [
            {"part_id": part1.id, "sequence": 0},
            {"part_id": part2.id, "sequence": 1},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload1, headers=lv2_headers)
    assert response.status_code == 201

    # Try to create second group with part1 (already in group1)
    payload2 = {
        "group_type": "shared_source",
        "group_key": "source:GROUP2",
        "members": [
            {"part_id": part1.id, "sequence": 0},  # Conflict
            {"part_id": part3.id, "sequence": 1},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload2, headers=lv2_headers)
    assert response.status_code == 400
    assert "already in active groups" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_groups_by_type(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test listing groups filtered by type."""
    # Create test parts
    parts = []
    for i in range(4):
        part = Part(
            part_number=f"TEST-{i:03d}",
            internal_name=f"Test Part {i}",
            part_status="DRAFT"
        )
        db.add(part)
        parts.append(part)
    await db.commit()
    for p in parts:
        await db.refresh(p)

    # Create left/right group
    lr_payload = {
        "group_type": "left_right",
        "group_key": "pair:TEST-LR",
        "members": [
            {"part_id": parts[0].id, "position": "left", "sequence": 0},
            {"part_id": parts[1].id, "position": "right", "sequence": 1},
        ]
    }
    await client.post("/api/part-display-groups", json=lr_payload, headers=lv2_headers)

    # Create shared-source group
    ss_payload = {
        "group_type": "shared_source",
        "group_key": "source:TEST-SS",
        "members": [
            {"part_id": parts[2].id, "sequence": 0},
            {"part_id": parts[3].id, "sequence": 1},
        ]
    }
    await client.post("/api/part-display-groups", json=ss_payload, headers=lv2_headers)

    # List all groups
    response = await client.get("/api/part-display-groups", headers=lv2_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2

    # List left_right only
    response = await client.get("/api/part-display-groups?group_type=left_right", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["group_type"] == "left_right"

    # List shared_source only
    response = await client.get("/api/part-display-groups?group_type=shared_source", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["group_type"] == "shared_source"


@pytest.mark.asyncio
async def test_update_group(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test updating a group's metadata."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Create group
    payload = {
        "group_type": "shared_source",
        "group_key": "source:TEST-UPDATE",
        "display_name": "Original Name",
        "members": [
            {"part_id": part1.id, "sequence": 0},
            {"part_id": part2.id, "sequence": 1},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 201
    group_id = response.json()["id"]

    # Update group
    update_payload = {
        "display_name": "Updated Name",
        "remark": "Test remark",
        "is_active": False,
    }
    response = await client.patch(f"/api/part-display-groups/{group_id}", json=update_payload, headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated Name"
    assert data["remark"] == "Test remark"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_group(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test deleting a group and cascade deletion of members."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Create group
    payload = {
        "group_type": "shared_source",
        "group_key": "source:TEST-DELETE",
        "members": [
            {"part_id": part1.id, "sequence": 0},
            {"part_id": part2.id, "sequence": 1},
        ]
    }
    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 201
    group_id = response.json()["id"]

    # Verify group exists
    result = await db.execute(
        select(PartDisplayGroupDef).where(PartDisplayGroupDef.id == group_id)
    )
    assert result.scalar_one_or_none() is not None

    # Delete group
    response = await client.delete(f"/api/part-display-groups/{group_id}", headers=lv2_headers)
    assert response.status_code == 204

    # Verify group deleted
    result = await db.execute(
        select(PartDisplayGroupDef).where(PartDisplayGroupDef.id == group_id)
    )
    assert result.scalar_one_or_none() is None

    # Verify members cascade deleted
    result = await db.execute(
        select(PartDisplayGroupMember).where(PartDisplayGroupMember.group_id == group_id)
    )
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_create_shared_field_group(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test creating a shared field group."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    tooling1 = Tooling(tooling_number="TOOL-001", mold_type="continuous")
    db.add_all([part1, part2, tooling1])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)
    await db.refresh(tooling1)

    # Create shared field group
    payload = {
        "group_key": "shared:MAT-001",
        "display_name": "Shared Material Group",
        "shares_material": True,
        "shares_thickness": True,
        "source_sheet": "Sheet1",
        "source_rows": "10,11",
        "members": [
            {"part_id": part1.id, "source_row": 10},
            {"part_id": part2.id, "source_row": 11},
            {"tooling_id": tooling1.id, "source_row": 10},
        ]
    }

    response = await client.post("/api/part-display-groups/shared-fields", json=payload, headers=lv2_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["group_key"] == "shared:MAT-001"
    assert data["shares_material"] is True
    assert data["shares_thickness"] is True
    assert data["shares_width"] is False
    assert len(data["members"]) == 3


@pytest.mark.asyncio
async def test_shared_field_group_requires_shared_field(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that shared field group requires at least one shared field."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Try to create group with no shared fields
    payload = {
        "group_key": "shared:NONE",
        "shares_material": False,
        "shares_thickness": False,
        "shares_width": False,
        "shares_pitch": False,
        "shares_cavity": False,
        "members": [
            {"part_id": part1.id},
            {"part_id": part2.id},
        ]
    }

    response = await client.post("/api/part-display-groups/shared-fields", json=payload, headers=lv2_headers)
    assert response.status_code == 400
    assert "at least one shared field" in response.json()["detail"]


@pytest.mark.asyncio
async def test_lv1_cannot_create_groups(client: AsyncClient, db, lv1_headers, sample_parts):
    """Test that LV1 users cannot create groups."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    payload = {
        "group_type": "shared_source",
        "group_key": "source:TEST-LV1",
        "members": [
            {"part_id": part1.id, "sequence": 0},
            {"part_id": part2.id, "sequence": 1},
        ]
    }

    response = await client.post("/api/part-display-groups", json=payload, headers=lv1_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_source_metadata_preserved(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that source_sheet and source_row metadata is preserved as read-only."""
    part1 = Part(part_number="TEST-001", internal_name="Test Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-002", internal_name="Test Part 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Create group with source metadata
    payload = {
        "group_type": "shared_source",
        "group_key": "source:METADATA-TEST",
        "source_sheet": "CustomerA",
        "source_rows": "45,46",
        "members": [
            {"part_id": part1.id, "sequence": 0, "source_row": 45},
            {"part_id": part2.id, "sequence": 1, "source_row": 46},
        ]
    }

    response = await client.post("/api/part-display-groups", json=payload, headers=lv2_headers)
    assert response.status_code == 201
    data = response.json()

    # Verify source metadata preserved
    assert data["source_sheet"] == "CustomerA"
    assert data["source_rows"] == "45,46"
    assert data["members"][0]["source_row"] == 45
    assert data["members"][1]["source_row"] == 46

    # Verify in database
    result = await db.execute(
        select(PartDisplayGroupDef).where(PartDisplayGroupDef.group_key == "source:METADATA-TEST")
    )
    group = result.scalar_one()
    assert group.source_sheet == "CustomerA"
    assert group.source_rows == "45,46"
