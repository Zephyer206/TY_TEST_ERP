"""Integration tests for persistent group precedence in GET /api/v1/parts/grouped.

Tests that persistent PartDisplayGroupDef records take precedence over legacy
inferred/audit grouping in the grouped parts endpoint.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.part import Part
from app.models.part_display_group import PartDisplayGroupDef, PartDisplayGroupMember


@pytest.mark.asyncio
async def test_persistent_left_right_group_in_grouped_endpoint(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that persistent left/right groups appear in /parts/grouped."""
    # Create two test parts
    left_part = Part(
        part_number="TEST-LR-L-001",
        internal_name="Test Left Part",
        part_position="left",
        part_status="DRAFT",
    )
    right_part = Part(
        part_number="TEST-LR-R-001",
        internal_name="Test Right Part",
        part_position="right",
        part_status="DRAFT",
    )
    db.add_all([left_part, right_part])
    await db.commit()
    await db.refresh(left_part)
    await db.refresh(right_part)

    # Create persistent left/right group
    group = PartDisplayGroupDef(
        group_type="left_right",
        group_key="pair:TEST-LR-001",
        display_name="Test Left-Right Pair",
        is_active=True,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    member_left = PartDisplayGroupMember(
        group_id=group.id,
        part_id=left_part.id,
        position="left",
        sequence=0,
    )
    member_right = PartDisplayGroupMember(
        group_id=group.id,
        part_id=right_part.id,
        position="right",
        sequence=1,
    )
    db.add_all([member_left, member_right])
    await db.commit()

    # Fetch grouped parts
    response = await client.get("/api/v1/parts/grouped", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()

    # Find the group in response
    groups = [item for item in data["items"] if item["key"] == "pair:TEST-LR-001"]
    assert len(groups) == 1
    group_item = groups[0]

    assert group_item["is_left_right_pair"] is True
    assert group_item["is_shared_source_group"] is False
    assert len(group_item["members"]) == 2
    member_ids = {m["id"] for m in group_item["members"]}
    assert member_ids == {left_part.id, right_part.id}


@pytest.mark.asyncio
async def test_persistent_shared_source_group_in_grouped_endpoint(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that persistent shared-source groups appear in /parts/grouped."""
    part1 = Part(part_number="TEST-SS-001", internal_name="Shared Part 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-SS-002", internal_name="Shared Part 2", part_status="DRAFT")
    part3 = Part(part_number="TEST-SS-003", internal_name="Shared Part 3", part_status="DRAFT")
    db.add_all([part1, part2, part3])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)
    await db.refresh(part3)

    # Create persistent shared-source group
    group = PartDisplayGroupDef(
        group_type="shared_source",
        group_key="source:TestSheet:100,101,102",
        display_name="Shared Material Group",
        source_sheet="TestSheet",
        source_rows="100,101,102",
        is_active=True,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    for idx, part in enumerate([part1, part2, part3]):
        member = PartDisplayGroupMember(
            group_id=group.id,
            part_id=part.id,
            sequence=idx,
            source_row=100 + idx,
        )
        db.add(member)
    await db.commit()

    # Fetch grouped parts
    response = await client.get("/api/v1/parts/grouped", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()

    # Find the group in response
    groups = [item for item in data["items"] if item["key"] == "source:TestSheet:100,101,102"]
    assert len(groups) == 1
    group_item = groups[0]

    assert group_item["is_left_right_pair"] is False
    assert group_item["is_shared_source_group"] is True
    assert len(group_item["members"]) == 3
    member_ids = {m["id"] for m in group_item["members"]}
    assert member_ids == {part1.id, part2.id, part3.id}


@pytest.mark.asyncio
async def test_persistent_group_precedence_over_legacy(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that persistent groups take precedence over legacy inferred grouping."""
    # Create parts that would match legacy left/right inference pattern
    part1 = Part(
        part_number="TEST-PREC-001",
        internal_name="Precedence Test Part 1",
        part_position="left",
        part_status="DRAFT",
    )
    part2 = Part(
        part_number="TEST-PREC-002",
        internal_name="Precedence Test Part 2",
        part_position="right",
        part_status="DRAFT",
    )
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Create persistent shared-source group (different type than legacy would infer)
    group = PartDisplayGroupDef(
        group_type="shared_source",
        group_key="source:CustomSheet:200,201",
        display_name="Custom Group (Overrides Legacy)",
        is_active=True,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    for idx, part in enumerate([part1, part2]):
        member = PartDisplayGroupMember(
            group_id=group.id,
            part_id=part.id,
            sequence=idx,
        )
        db.add(member)
    await db.commit()

    # Fetch grouped parts
    response = await client.get("/api/v1/parts/grouped", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()

    # Find the group - should be shared_source (persistent), not left_right (legacy)
    groups = [item for item in data["items"] if item["key"] == "source:CustomSheet:200,201"]
    assert len(groups) == 1
    group_item = groups[0]

    assert group_item["is_left_right_pair"] is False
    assert group_item["is_shared_source_group"] is True
    assert len(group_item["members"]) == 2


@pytest.mark.asyncio
async def test_inactive_persistent_group_not_shown(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that inactive persistent groups are excluded from /parts/grouped."""
    part1 = Part(part_number="TEST-INACT-001", internal_name="Inactive Test 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-INACT-002", internal_name="Inactive Test 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Create inactive group
    group = PartDisplayGroupDef(
        group_type="shared_source",
        group_key="source:Inactive:300,301",
        is_active=False,  # Inactive
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    for idx, part in enumerate([part1, part2]):
        member = PartDisplayGroupMember(
            group_id=group.id,
            part_id=part.id,
            sequence=idx,
        )
        db.add(member)
    await db.commit()

    # Fetch grouped parts
    response = await client.get("/api/v1/parts/grouped", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()

    # Inactive group should NOT appear, parts should be ungrouped
    inactive_groups = [item for item in data["items"] if item["key"] == "source:Inactive:300,301"]
    assert len(inactive_groups) == 0

    # Parts should appear as individual entries
    individual_part_ids = {
        item["members"][0]["id"]
        for item in data["items"]
        if item["key"].startswith("part:") and len(item["members"]) == 1
    }
    assert part1.id in individual_part_ids or part2.id in individual_part_ids


@pytest.mark.asyncio
async def test_arbitrary_group_key_does_not_infer_type(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that group_type comes from database, not inferred from arbitrary group_key prefix."""
    part1 = Part(part_number="TEST-ARB-001", internal_name="Arbitrary Key Test 1", part_status="DRAFT")
    part2 = Part(part_number="TEST-ARB-002", internal_name="Arbitrary Key Test 2", part_status="DRAFT")
    db.add_all([part1, part2])
    await db.commit()
    await db.refresh(part1)
    await db.refresh(part2)

    # Create a shared_source group with a key that does NOT start with "source:"
    group = PartDisplayGroupDef(
        group_type="shared_source",
        group_key="my_custom_group_key_123",  # Arbitrary, no prefix convention
        display_name="Custom Group with Arbitrary Key",
        is_active=True,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    member1 = PartDisplayGroupMember(group_id=group.id, part_id=part1.id, sequence=0)
    member2 = PartDisplayGroupMember(group_id=group.id, part_id=part2.id, sequence=1)
    db.add_all([member1, member2])
    await db.commit()

    # Fetch grouped parts
    response = await client.get("/api/v1/parts/grouped", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()

    # Find the group
    groups = [item for item in data["items"] if item["key"] == "my_custom_group_key_123"]
    assert len(groups) == 1
    group_item = groups[0]

    # Must be shared_source (from database), not inferred as ungrouped
    assert group_item["is_left_right_pair"] is False
    assert group_item["is_shared_source_group"] is True
    assert len(group_item["members"]) == 2


@pytest.mark.asyncio
async def test_member_sequence_order_preserved(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that members are returned in sequence order, not sorted by part_id."""
    # Create parts with IDs in reverse order of desired sequence
    part_high_id = Part(part_number="TEST-SEQ-HIGH", internal_name="High ID Part", part_status="DRAFT")
    part_mid_id = Part(part_number="TEST-SEQ-MID", internal_name="Mid ID Part", part_status="DRAFT")
    part_low_id = Part(part_number="TEST-SEQ-LOW", internal_name="Low ID Part", part_status="DRAFT")
    db.add_all([part_high_id, part_mid_id, part_low_id])
    await db.commit()
    await db.refresh(part_high_id)
    await db.refresh(part_mid_id)
    await db.refresh(part_low_id)

    # Create group
    group = PartDisplayGroupDef(
        group_type="shared_source",
        group_key="sequence_test_group",
        display_name="Sequence Order Test",
        is_active=True,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    # Add members in explicit sequence order: low, mid, high (opposite of ID order)
    member_low = PartDisplayGroupMember(group_id=group.id, part_id=part_low_id.id, sequence=0)
    member_mid = PartDisplayGroupMember(group_id=group.id, part_id=part_mid_id.id, sequence=1)
    member_high = PartDisplayGroupMember(group_id=group.id, part_id=part_high_id.id, sequence=2)
    db.add_all([member_low, member_mid, member_high])
    await db.commit()

    # Fetch grouped parts
    response = await client.get("/api/v1/parts/grouped", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()

    # Find the group
    groups = [item for item in data["items"] if item["key"] == "sequence_test_group"]
    assert len(groups) == 1
    group_item = groups[0]

    assert len(group_item["members"]) == 3
    # Members must be in sequence order: low, mid, high (NOT sorted by part_id)
    member_ids = [m["id"] for m in group_item["members"]]
    assert member_ids == [part_low_id.id, part_mid_id.id, part_high_id.id]



@pytest.mark.asyncio
async def test_ungrouped_parts_retain_legacy_behavior(client: AsyncClient, db, lv2_headers, sample_parts):
    """Test that parts without persistent groups still use legacy grouping."""
    # Create a part that won't match any persistent group
    ungrouped_part = Part(
        part_number="TEST-UNGROUPED-001",
        internal_name="Ungrouped Part",
        part_status="DRAFT",
    )
    db.add(ungrouped_part)
    await db.commit()
    await db.refresh(ungrouped_part)

    # Fetch grouped parts
    response = await client.get("/api/v1/parts/grouped", headers=lv2_headers)
    assert response.status_code == 200
    data = response.json()

    # Part should appear as individual entry
    individual_entries = [
        item for item in data["items"]
        if item["key"] == f"part:{ungrouped_part.id}"
    ]
    assert len(individual_entries) == 1
    entry = individual_entries[0]
    assert entry["is_left_right_pair"] is False
    assert entry["is_shared_source_group"] is False
    assert len(entry["members"]) == 1
    assert entry["members"][0]["id"] == ungrouped_part.id
