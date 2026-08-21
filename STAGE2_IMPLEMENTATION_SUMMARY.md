# Stage 2 Implementation Summary: Explicit Part Display Grouping

**Date:** 2026-07-30  
**Task:** Implement Stage 2 for explicit left/right part groups and shared/merged field groups  
**Status:** ✅ Complete

---

## Overview

Implemented a minimal auditable persistent model and API for user-confirmed part grouping semantics. Groups are created explicitly by LV2+ users through API actions—no inference from names, suffixes, mold numbers, or Excel text. Source metadata (sheet/row) is preserved as read-only audit trail.

---

## Implementation Details

### 1. Database Models

**File:** `backend/app/models/part_display_group.py`

Created four new models:

#### `PartDisplayGroupDef`
- User-confirmed part display group definition
- Fields: `group_type` (left_right/shared_source), `group_key`, `display_name`
- Audit metadata: `source_sheet`, `source_rows` (read-only)
- Lifecycle: `is_active`, `created_by`, `updated_by`, timestamps

#### `PartDisplayGroupMember`
- Links a part to a display group
- Fields: `group_id`, `part_id`, `position`, `sequence`, `source_row`
- Constraint: A part can belong to at most one active group (`uq_part_display_group_member_part`)
- Position required for left_right groups, optional for shared_source

#### `SharedFieldGroupDef`
- Defines which fields are shared across parts/tooling
- Fields: `group_key`, boolean flags for each shared field (material, thickness, width, pitch, cavity)
- Audit metadata: `source_sheet`, `source_rows` (read-only)

#### `SharedFieldGroupMember`
- Links parts or tooling to a shared field group
- Fields: `group_id`, `part_id`, `tooling_id`, `source_row`
- At least one of `part_id` or `tooling_id` must be set

### 2. Database Migration

**File:** `alembic/versions/20260730_explicit_part_grouping.py`

- Revision ID: `20260730_explicit_part_grouping`
- Revises: `20260722_null_customer_part_no`
- Creates four tables with appropriate indexes and foreign keys
- Cascade deletion for members when group is deleted
- All source metadata fields marked as read-only in comments

### 3. Pydantic Schemas

**File:** `backend/app/schemas/part_display_group.py`

Request/response schemas for:
- `PartDisplayGroupDefCreate`, `PartDisplayGroupDefUpdate`, `PartDisplayGroupDefResponse`
- `PartDisplayGroupMemberCreate`, `PartDisplayGroupMemberResponse`
- `SharedFieldGroupDefCreate`, `SharedFieldGroupDefUpdate`, `SharedFieldGroupDefResponse`
- `SharedFieldGroupMemberCreate`, `SharedFieldGroupMemberResponse`

All schemas include validation and proper typing.

### 4. API Endpoints

**File:** `backend/app/api/part_display_groups.py`

All endpoints require authentication; create/update/delete require LV2+ role.

#### Part Display Groups
- `GET /api/part-display-groups` - List groups with filtering by type and active status
- `POST /api/part-display-groups` - Create new group (LV2+ only)
- `GET /api/part-display-groups/{group_id}` - Get single group
- `PATCH /api/part-display-groups/{group_id}` - Update group (LV2+ only)
- `DELETE /api/part-display-groups/{group_id}` - Delete group (LV2+ only)
- `POST /api/part-display-groups/{group_id}/members` - Add member (LV2+ only)
- `DELETE /api/part-display-groups/{group_id}/members/{member_id}` - Remove member (LV2+ only)

#### Shared Field Groups
- `GET /api/part-display-groups/shared-fields` - List shared field groups
- `POST /api/part-display-groups/shared-fields` - Create new group (LV2+ only)
- `GET /api/part-display-groups/shared-fields/{group_id}` - Get single group
- `PATCH /api/part-display-groups/shared-fields/{group_id}` - Update group (LV2+ only)
- `DELETE /api/part-display-groups/shared-fields/{group_id}` - Delete group (LV2+ only)
- `POST /api/part-display-groups/shared-fields/{group_id}/members` - Add member (LV2+ only)
- `DELETE /api/part-display-groups/shared-fields/{group_id}/members/{member_id}` - Remove member (LV2+ only)

**Validation:**
- left_right groups: exactly 2 members with positions 'left' and 'right'
- shared_source groups: at least 2 members
- shared_field groups: at least 2 members and at least one shared field flag
- group_key uniqueness enforced
- Parts cannot belong to multiple active groups
- All part_ids and tooling_ids validated for existence

### 5. Router Registration

**File:** `backend/app/main.py`

Added router import and registration:
```python
from app.api.part_display_groups import router as part_display_groups_router
app.include_router(part_display_groups_router, prefix=settings.API_V1_PREFIX)
```

### 6. Tests

**File:** `backend/tests/test_part_display_groups.py`

Comprehensive test suite covering:
- ✅ Create left/right groups with validation
- ✅ Create shared-source groups with validation
- ✅ Group type filtering
- ✅ Duplicate group key rejection
- ✅ Part membership conflict detection
- ✅ Update and delete operations
- ✅ Cascade deletion of members
- ✅ Shared field group creation and validation
- ✅ LV1 permission denial
- ✅ Source metadata preservation

Total: 17 focused test cases

---

## Validation & Constraints

### Database Level
- Foreign keys with CASCADE delete for members
- Unique constraints on group_key
- Unique constraint on part_id in part_display_group_members

### Application Level
- group_type must be "left_right" or "shared_source"
- left_right groups: exactly 2 members, positions must be "left" and "right"
- shared_source groups: minimum 2 members
- shared_field groups: minimum 2 members, at least one shared field flag true
- No part in multiple active groups
- All referenced parts/tooling must exist
- LV2+ role required for create/update/delete operations

---

## Design Principles Followed

✅ **No automatic inference** - Groups created only by explicit user actions  
✅ **Source metadata preserved** - sheet/row retained as read-only audit trail  
✅ **Auditable** - created_by, updated_by, timestamps tracked  
✅ **Minimal** - Only essential fields and relationships  
✅ **Compatible** - Existing list behavior remains unchanged  
✅ **Focused tests** - 17 tests covering key scenarios  

---

## Compilation & Syntax

✅ All Python files compile without errors:
- Migration file: `alembic/versions/20260730_explicit_part_grouping.py`
- Models: `backend/app/models/part_display_group.py`
- Schemas: `backend/app/schemas/part_display_group.py`
- API: `backend/app/api/part_display_groups.py`
- Tests: `backend/tests/test_part_display_groups.py`

---

## Integration Points

### Existing Code Preserved
- `backend/app/api/parts.py` - Existing grouped list logic remains intact
- `backend/app/schemas/part.py` - PartDisplayGroup schema unchanged
- Continuous molds still preferred in existing list behavior

### Future Integration (Not Implemented)
The existing `_load_left_right_pair_lookup()` and `_load_source_group_lookup()` in `parts.py` currently use audit files and inference. These could be replaced with queries to the new persistent groups once groups are populated through the API.

---

## Migration Path

**File:** `alembic/versions/20260730_explicit_part_grouping.py`

To apply:
```bash
cd backend
alembic upgrade head
```

To rollback:
```bash
alembic downgrade 20260722_null_customer_part_no
```

---

## API Usage Examples

### Create a Left/Right Pair Group

```bash
POST /api/part-display-groups
Authorization: Bearer <lv2-token>
Content-Type: application/json

{
  "group_type": "left_right",
  "group_key": "pair:TYAA-Q0093",
  "display_name": "TYAA-Q0093 Left/Right Pair",
  "members": [
    {"part_id": 123, "position": "left", "sequence": 0},
    {"part_id": 124, "position": "right", "sequence": 1}
  ]
}
```

### Create a Shared Source Group

```bash
POST /api/part-display-groups
Authorization: Bearer <lv2-token>
Content-Type: application/json

{
  "group_type": "shared_source",
  "group_key": "source:SheetA:45,46,47",
  "display_name": "Shared Material Block",
  "source_sheet": "SheetA",
  "source_rows": "45,46,47",
  "members": [
    {"part_id": 201, "sequence": 0, "source_row": 45},
    {"part_id": 202, "sequence": 1, "source_row": 46},
    {"part_id": 203, "sequence": 2, "source_row": 47}
  ]
}
```

### Create a Shared Field Group

```bash
POST /api/part-display-groups/shared-fields
Authorization: Bearer <lv2-token>
Content-Type: application/json

{
  "group_key": "shared:MAT-SPCC-T1.0",
  "display_name": "SPCC T1.0 Shared Material",
  "shares_material": true,
  "shares_thickness": true,
  "source_sheet": "SheetA",
  "source_rows": "45,46",
  "members": [
    {"part_id": 201, "source_row": 45},
    {"tooling_id": 301, "source_row": 45}
  ]
}
```

---

## Changed Files Summary

### New Files (5)
1. `backend/app/models/part_display_group.py` - SQLAlchemy models
2. `backend/app/schemas/part_display_group.py` - Pydantic schemas
3. `backend/app/api/part_display_groups.py` - API endpoints
4. `alembic/versions/20260730_explicit_part_grouping.py` - Migration
5. `backend/tests/test_part_display_groups.py` - Test suite

### Modified Files (1)
1. `backend/app/main.py` - Router registration

---

## Blockers & Notes

### ✅ No Blockers
- All code compiles successfully
- Migration file is valid
- Tests are comprehensive and focused
- API endpoints follow existing patterns
- No conflicts with existing functionality

### Notes
- Tests require pytest fixtures for `client`, `db`, `lv1_headers`, `lv2_headers`, `sample_parts`
- Migration must be run before API endpoints are usable
- Existing grouped list behavior (`/api/parts/grouped`) preserved and compatible
- No services were started/stopped during implementation
- No production data was mutated
- No secrets were exposed or committed
- Frontend integration not included (Stage 2 is backend only)

---

## Next Steps (Not Implemented)

1. **Populate groups** - Create groups through API based on audit findings
2. **Frontend UI** - Build interface for group management
3. **Integrate with list** - Update `/api/parts/grouped` to query persistent groups
4. **Migration script** - Convert audit file data to persistent groups
5. **Documentation** - API documentation and user guide

---

## Compliance with Requirements

✅ Explicit left/right part groups with user confirmation  
✅ Explicit shared/merged field groups with user confirmation  
✅ APIs for LV2+ users to create/update/delete groups  
✅ APIs to assign/unassign part members  
✅ APIs to query group membership  
✅ No inference from names, suffixes, mold numbers, or Excel text  
✅ User actions must be explicit  
✅ Source metadata (sheet/row) preserved as read-only  
✅ Grouped list/detail response compatibility maintained  
✅ Continuous molds remain preferred  
✅ Focused tests included  
✅ Compilation successful  
✅ No services started/stopped  
✅ No frontend changes  
✅ No production data mutations  
✅ No secrets exposed  

---

**Implementation Complete** ✅
