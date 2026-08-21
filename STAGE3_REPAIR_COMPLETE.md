# Stage 3 Backend Repair - Completion Summary

**Date:** 2026-07-30  
**Status:** ✅ Complete

## Changes Made

### 1. Schema Updates (`app/schemas/part_editor_relationships.py`)

#### Added `extra='forbid'` to All Request Schemas
- `CustomerAliasItem` - blocks source field inputs
- `CustomerAliasesUpdateRequest` - rejects unexpected fields
- `ToolingPartItem` - validates strict input
- `ToolingPartsUpdateRequest` - enforces schema
- `TWPSpecItem` - **rejects source_sheet/source_row/source_note at validation time**
- `TWPSpecsUpdateRequest` - strict validation
- `PartEditorBulkUpdateRequest` - no extra fields allowed

#### Added Explicit Delete Lists
- `delete_alias_ids: list[int]` - explicit alias deletion
- `delete_tooling_part_ids: list[int]` - explicit tooling association deletion
- `delete_spec_ids: list[int]` - explicit TWP spec deletion

#### Added Optimistic Locking
- `expected_updated_at: datetime` (required field in bulk request)
- Returns 409 Conflict on timestamp mismatch

#### Added ID Fields for Upsert
- `CustomerAliasItem.id: Optional[int]` - update if present, create if null
- `ToolingPartItem.id: Optional[int]` - update if present, create if null
- `TWPSpecItem.id: Optional[int]` - update if present, create if null (preserves source)

### 2. API Implementation (`app/api/part_editor_relationships.py`)

Complete rewrite implementing:

#### Upsert by ID (Preserves Existing Records)
```python
if spec_item.id:
    # Update existing by ID, preserving source fields
    existing = await db.get(PartToolingSpec, spec_item.id)
    if existing and existing.part_id == part_id:
        existing.thickness = spec_item.thickness  # Update business fields
        # source_sheet/source_row/source_note NOT TOUCHED - preserved
else:
    # Create new (source fields remain NULL for editor-created specs)
```

#### Explicit Delete Lists (No Wholesale Delete/Recreate)
```python
# Delete only explicit IDs
if request.delete_spec_ids:
    await db.execute(
        delete(PartToolingSpec).where(
            and_(
                PartToolingSpec.part_id == part_id,
                PartToolingSpec.id.in_(request.delete_spec_ids)
            )
        )
    )
```

#### Optimistic Locking
```python
server_ts_sec = server_ts.replace(microsecond=0)
client_ts_sec = client_ts.replace(microsecond=0)

if server_ts_sec != client_ts_sec:
    raise HTTPException(status_code=409, detail={
        "error": "optimistic_lock_conflict",
        "client_timestamp": client_ts.isoformat(),
        "server_timestamp": server_ts.isoformat(),
    })
```

#### Validation Constraints

**Deleted Tooling Rejection:**
```python
deleted_ids = [tid for tid, t in tooling_map.items() if t.is_deleted]
if deleted_ids:
    raise HTTPException(400, detail=f"Cannot associate deleted tooling: {deleted_ids}")
```

**Max One Primary ToolingPart Total:**
```python
if len(primary_requested) > 1:
    raise HTTPException(400, detail="At most one tooling may be marked as primary")
```

**Continuous Tooling Primary Enforcement:**
```python
if has_continuous and primary_requested:
    primary_tp = primary_requested[0]
    if not tooling_map[primary_tp.tooling_id].is_continuous:
        raise HTTPException(400, detail="When any tooling is continuous, only continuous may be primary")
```

**Deletion Ordering (Specs Before Tooling):**
```python
# Check for specs that would be orphaned
orphaned_spec_ids = [...]
if orphaned_spec_ids:
    raise HTTPException(400, detail=f"Cannot remove tooling while specs exist. Delete specs first.")
```

#### Bulk Flush (Autoflush=False Support)
```python
# Upsert tooling associations
for tp_item in request.tooling_parts:
    # ... upsert logic

# Flush to make new associations visible for TWP validation
await db.flush()

# Now query associations for TWP spec validation
result = await db.execute(
    select(ToolingPart.tooling_id).where(ToolingPart.part_id == part_id)
)
associated_tooling_ids = {row[0] for row in result.fetchall()}
```

### 3. Route Deduplication (`app/api/parts.py`)

**Removed duplicate PATCH `/{part_id}/editor` route (lines 961-1052)**

Only `app/api/part_editor.py` now provides the editor PATCH route.

### 4. Tests (`tests/test_part_editor_stage3.py`)

Created mock-only tests covering:

✅ **Source field rejection** - `extra='forbid'` blocks source_sheet/source_row/source_note input  
✅ **Valid field acceptance** - TWPSpecItem accepts id/tooling_id/thickness/width/pitch/is_primary  
✅ **No duplicate routes** - Verifies only one PATCH /editor endpoint exists

**Test Results:**
```
tests/test_part_editor_stage3.py::test_forbid_source_input_in_request PASSED
tests/test_part_editor_stage3.py::test_twp_spec_accepts_valid_fields PASSED
tests/test_part_editor_stage3.py::test_no_duplicate_patch_editor_route PASSED

3 passed in 0.05s
```

### 5. Compilation Verification

✅ All Python files compile successfully:
- `app/api/part_editor_relationships.py`
- `app/schemas/part_editor_relationships.py`
- `app/api/part_editor.py`
- `app/api/parts.py`

## Design Compliance

### Data Model Authority (`specs/001-erp-system-architecture/data-model.md`)

✅ **No client writes to source fields** - Enforced by Pydantic `extra='forbid'`  
✅ **Source preservation** - Upsert by ID leaves source_sheet/source_row/source_note untouched  
✅ **No wholesale delete/recreate** - Explicit delete_*_ids lists only  
✅ **Tooling.is_deleted validation** - Cannot associate deleted tooling  
✅ **Primary constraints** - Max one primary total; continuous-first when mixed  
✅ **Deletion ordering** - Cannot remove tooling while specs exist unless explicitly deleted together  
✅ **Optimistic locking** - expected_updated_at prevents lost updates  

## API Contract Examples

### Successful Upsert (Preserves Source)

**Request:**
```json
{
  "expected_updated_at": "2026-07-30T10:00:00Z",
  "twp_specs": [
    {
      "id": 42,
      "tooling_id": 1,
      "thickness": 1.6,
      "is_primary": true
    }
  ]
}
```

**Behavior:**
- Finds existing PartToolingSpec ID=42
- Updates thickness to 1.6
- **Preserves source_sheet="Sheet1", source_row=100, source_note="Import 2026-01-15"**
- Returns 200 with updated spec (source fields intact)

### Explicit Delete

**Request:**
```json
{
  "expected_updated_at": "2026-07-30T10:00:00Z",
  "delete_spec_ids": [42, 43],
  "twp_specs": [
    {"id": 44, "tooling_id": 1, "thickness": 1.5, "is_primary": true}
  ]
}
```

**Behavior:**
- Deletes specs 42, 43
- Updates spec 44
- Does not touch other specs (no wholesale delete)

### Validation Failure: Source Input Rejected

**Request (INVALID):**
```json
{
  "twp_specs": [
    {
      "tooling_id": 1,
      "thickness": 1.5,
      "source_sheet": "Sheet1"  // ❌ Extra field
    }
  ]
}
```

**Response:** 422 Unprocessable Entity (Pydantic validation error)

### Validation Failure: Deleted Tooling

**Request:**
```json
{
  "tooling_parts": [
    {"tooling_id": 99, "is_primary": true}  // Tooling 99 has is_deleted=true
  ]
}
```

**Response:** 400 Bad Request - "Cannot associate deleted tooling: [99]"

### Validation Failure: Stale Timestamp

**Request:**
```json
{
  "expected_updated_at": "2026-07-30T09:00:00Z",  // Server: 10:00:00Z
  "twp_specs": [...]
}
```

**Response:** 409 Conflict with server timestamp

## Files Modified

1. `backend/app/schemas/part_editor_relationships.py` - Added extra='forbid', delete lists, optimistic lock
2. `backend/app/api/part_editor_relationships.py` - Complete rewrite with upsert/preserve/validate
3. `backend/app/api/parts.py` - Removed duplicate PATCH /editor route (lines 961-1052)
4. `backend/tests/test_part_editor_stage3.py` - Created mock-only tests
5. `backend/tests/conftest.py` - Created for test path configuration

## Verification Steps

```bash
# 1. Compile check
python -m py_compile app/api/part_editor_relationships.py \
    app/schemas/part_editor_relationships.py \
    app/api/part_editor.py \
    app/api/parts.py

# 2. Run tests
python -m pytest tests/test_part_editor_stage3.py -v

# 3. Verify no duplicate routes
grep -n "def update_part_editor" app/api/parts.py app/api/part_editor.py
# Should only show: app/api/part_editor.py:130
```

## Next Steps

✅ **Backend repair complete** - No further backend changes needed  
⏭️ **Frontend/service/data/migration** - Explicitly excluded per requirements  
⏭️ **No commits** - As requested  

## Constraints Honored

✅ **Backend only** - No frontend, service, data, or migration changes  
✅ **No commits** - Changes not committed to git  
✅ **Mock-only tests** - No cloud writes, no database required  
✅ **Compilation verified** - All files compile with py_compile  
✅ **Data model compliance** - Follows specs/001-erp-system-architecture/data-model.md  

---

**Implementation complete. Ready for integration testing when frontend/service are implemented.**
