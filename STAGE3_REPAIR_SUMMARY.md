# Stage 3 Part Editor Relationship/TWP Bulk API Repair Summary

**Date:** 2026-07-30  
**Status:** COMPLETED - All tests passing (30/30)  
**Database:** No cloud data modified (mock-only tests)

---

## Changes Made

### 1. Enhanced Primary Validation (Effective State)

**File:** `backend/app/api/part_editor_relationships.py`

Added `_validate_effective_state()` function that validates the **final effective state** after applying bulk updates, not just the incoming request:

- **ToolingPart validation:**
  - Prevents multiple primary ToolingPart records in final state
  - Validates continuous-only-primary constraint on effective state
  - Detects duplicate tooling_ids in final state
  - Enforces tooling_id immutability on existing records

- **TWP Spec validation:**
  - Prevents multiple primary specs per (part_id, tooling_id) in final state
  - Detects duplicate TWP identities in final state
  - Enforces tooling_id immutability on existing records

**Lines:** 125-231 (new function + integration into bulk_update)

---

### 2. Immutability Enforcement

**File:** `backend/app/api/part_editor_relationships.py`

**ToolingPart.tooling_id immutability (lines 520-536):**
```python
if existing.tooling_id != tp_item.tooling_id:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Cannot change tooling_id on existing ToolingPart ID {tp_item.id}"
    )
# Update mutable fields only
existing.position = tp_item.position
existing.sequence = tp_item.sequence
existing.is_primary = tp_item.is_primary
```

**PartToolingSpec.tooling_id immutability (lines 577-593):**
```python
if existing.tooling_id != spec_item.tooling_id:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Cannot change tooling_id on existing PartToolingSpec ID {spec_item.id}"
    )
# Update mutable fields only, source fields preserved
existing.spec_twph = spec_item.spec_twph
existing.thickness = spec_item.thickness
# ... source_sheet/source_row/source_note NOT touched
```

---

### 3. Duplicate/Collision Validation

**File:** `backend/app/api/part_editor_relationships.py`

Added comprehensive validation in Phase 1 (lines 393-470):

- **Deletion ID ownership:** All delete IDs must belong to the target part (400 if not)
- **Upsert/Delete collision:** IDs cannot appear in both upsert and delete lists
- **Duplicate alias identities:** (customer_id, customer_part_no, revision) uniqueness
- **Duplicate association IDs:** ToolingPart IDs must be unique in request
- **Duplicate tooling_ids:** Each tooling_id can only appear once in tooling_parts request
- **Duplicate TWP spec IDs:** Spec IDs must be unique in request

All violations return **400 Bad Request** with descriptive error messages.

---

### 4. Source Field Preservation Tests

**File:** `backend/tests/test_part_editor_stage3.py`

Added mock-only tests:

- `test_twp_upsert_preserves_source_fields()` - Proves TWP source fields survive upsert
- `test_alias_id_preserved_on_update()` - Proves alias IDs survive updates
- `test_exactly_one_patch_editor_route()` - Strengthened route assertion (exactly 1, not ≤1)

---

### 5. Updated Test Suite for Current Bulk API

**File:** `backend/tests/test_part_editor_relationships.py`

Completely rewritten to align with current single bulk API contract:

- Uses `PartEditorBulkUpdateRequest` with `expected_updated_at`
- Removed references to removed per-category endpoints
- All tests are mock-safe (no cloud DB writes)
- Added optimistic lock conflict test
- Added duplicate detection tests for bulk operations

**Test coverage:** 30 tests, all passing

---

### 6. Extended Editor Detail Response

**File:** `backend/app/schemas/part_editor_relationships.py`

Extended `PartEditorDetailResponse` to include all editable base fields from `PartEditorUpdateResponse`:

**Added fields:**
- `part_number`, `customer_id`, `customer_product_no`, `customer_product_name`, `vehicle_model`
- `drawing_url`, `spec_info`, `spec_twph`, `height`
- `part_status` (was `status`), `status`, `remark`
- `mold_number`, `mold_type`, `press_tonnage`, `ppap_no`
- `stock_pcs`, `version`

**Lines:** 166-234

---

## Validation Rules Summary

### Primary Constraints (ToolingPart)
1. **At most one primary** across all tooling associations
2. **Continuous-only-primary:** If any tooling is continuous, only continuous can be primary
3. Validated on **effective final state**, not just request

### Primary Constraints (TWP)
1. **At most one primary per (part_id, tooling_id)**
2. Scoped to each tooling, not global
3. Validated on **effective final state**, not just request

### Immutability Rules
1. **ToolingPart.tooling_id** - immutable after creation (delete + create new to move)
2. **PartToolingSpec.tooling_id** - immutable after creation (delete + create new to move)
3. **TWP source fields** - read-only, preserved during upsert, cannot be set via API

### Duplicate/Collision Detection
1. Deletion IDs must belong to target part (cross-part deletion rejected)
2. No ID can be in both upsert and delete lists
3. No duplicate alias identities in single request
4. No duplicate tooling_ids in final tooling associations
5. No duplicate TWP identities per (part_id, tooling_id)

---

## Test Results

```bash
cd backend
python -m py_compile app/api/part_editor_relationships.py app/schemas/part_editor_relationships.py
# ✓ Compilation successful

python -m pytest tests/test_part_editor_stage3.py tests/test_part_editor_relationships.py -v
# ✓ 30 passed, 0 failed, 11 warnings (unrelated deprecations) in 0.18s
```

**All Stage 3 tests passing:**
- 5 tests in `test_part_editor_stage3.py`
- 25 tests in `test_part_editor_relationships.py`

---

## Files Modified

1. `backend/app/api/part_editor_relationships.py` - Core API logic repairs
2. `backend/app/schemas/part_editor_relationships.py` - Extended detail response
3. `backend/tests/test_part_editor_stage3.py` - Source preservation tests
4. `backend/tests/test_part_editor_relationships.py` - Complete rewrite for bulk API

---

## Safety Guarantees

✓ No commits created  
✓ No deployments performed  
✓ No services started/stopped  
✓ No cloud/runtime data mutated  
✓ No secrets or database URLs printed  
✓ All tests are mock-only (no cloud SQL writes)  
✓ Source field preservation enforced at schema and API level  
✓ Immutability constraints prevent accidental data corruption  

---

## Next Steps (Not Performed)

This repair is complete and ready for:
1. Code review by Codex
2. Integration testing in development environment
3. Manual acceptance testing of bulk update flows
4. Deployment approval

**No further action taken by this bounded implementation task.**
