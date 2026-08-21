# Stage 1: Part Editor Backend API Implementation

**Date:** 2026-07-30  
**Status:** ✅ Complete  
**Scope:** Backend-only API/data contract for complete part editor

## Overview

Implemented a complete backend API for transactional part updates with optimistic concurrency control. The implementation provides a single atomic PATCH endpoint that can update all editable Part model fields while protecting system-managed and accounting fields.

## Files Created/Modified

### New Files Created

1. **`backend/app/schemas/part_editor.py`** (270 lines)
   - `PartEditorUpdateRequest`: Request schema with all editable fields and optimistic lock timestamp
   - `PartEditorUpdateResponse`: Response schema with full part state
   - `PartEditorConflictDetail`: Field-level conflict information
   - `PartEditorConflictResponse`: Detailed 409 conflict response structure

2. **`backend/app/api/part_editor.py`** (252 lines)
   - `PATCH /api/v1/parts/{part_id}/editor`: Atomic update endpoint
   - Optimistic locking with `updated_at` timestamp comparison
   - Field-level conflict detection
   - Transaction rollback on any error
   - Authorization: LV2+ required

3. **`backend/tests/test_part_editor.py`** (485 lines)
   - 13 comprehensive test cases covering:
     - Successful full and partial updates
     - Optimistic lock conflicts
     - Authorization checks (LV1 vs LV2)
     - Validation errors
     - Atomicity (rollback on foreign key violation)
     - Protected field handling
     - Concurrent update scenarios
     - Soft-deleted part handling

### Modified Files

1. **`backend/app/main.py`**
   - Added import for `part_editor_router`
   - Registered router: `app.include_router(part_editor_router, prefix=settings.API_V1_PREFIX)`

2. **`backend/tests/conftest.py`**
   - Added `AsyncClient` fixture using `ASGITransport` for API testing

## API Specification

### Endpoint

```
PATCH /api/v1/parts/{part_id}/editor
```

### Authorization

- **Required Role Level:** LV2+ (Managers & business/technical staff)
- **Authentication:** Bearer token required

### Request Schema

All fields are optional except `updated_at` (required for optimistic locking):

```json
{
  "internal_part_no": "string | null",
  "internal_name": "string | null",
  "customer_product_no": "string | null",
  "customer_product_name": "string | null",
  "vehicle_model": "string | null",
  "material_name": "string | null",
  "material_id": "integer | null",
  "drawing_url": "string | null",
  "spec_info": "string | null",
  "spec_twph": "string | null",
  "thickness": "decimal(10,3) | null",
  "width": "decimal(10,3) | null",
  "pitch": "decimal(10,3) | null",
  "height": "decimal(10,3) | null",
  "gross_weight": "decimal(12,3) | null",
  "net_weight": "decimal(12,3) | null",
  "part_position": "left | right | center | single | null",
  "part_status": "DRAFT | SAMPLING | MASS_PRODUCTION | OBSOLETE",
  "status": "string | null",
  "remark": "string | null",
  "mold_number": "string | null",
  "mold_type": "string | null",
  "press_tonnage": "string | null",
  "ppap_no": "string | null",
  "updated_at": "datetime (ISO 8601, required)"
}
```

### Response Codes

- **200 OK**: Update successful, returns updated part
- **400 Bad Request**: Validation error or foreign key violation
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: Insufficient role level (requires LV2+)
- **404 Not Found**: Part not found or soft-deleted
- **409 Conflict**: Optimistic lock failure with field-level diff
- **422 Unprocessable Entity**: Pydantic validation error

### Optimistic Locking (409 Response)

When concurrent modification is detected, returns detailed conflict information:

```json
{
  "detail": {
    "detail": "Part was modified by another user. Review conflicts and retry.",
    "conflict_type": "optimistic_lock",
    "client_timestamp": "2026-07-30T10:00:00Z",
    "server_timestamp": "2026-07-30T10:05:00Z",
    "conflicts": [
      {
        "field": "internal_name",
        "client_value": "My Update",
        "server_value": "Another User's Update",
        "server_updated_at": "2026-07-30T10:05:00Z",
        "server_updated_by": null
      }
    ],
    "current_part": { /* full part state */ }
  }
}
```

## Editable Fields

### Identity
- `internal_part_no`: Internal part number (nullable, reserved for future)
- `internal_name`: Internal part name

### Customer Fallback (Legacy)
- `customer_product_no`: Customer part number (deprecated, use `part_customer_aliases`)
- `customer_product_name`: Customer part name
- `vehicle_model`: Vehicle model

### Material
- `material_name`: Material name string
- `material_id`: Foreign key to `material_dict`

### Drawing/Spec
- `drawing_url`: Drawing file URL/path
- `spec_info`: Specification text

### TWP Legacy Fields
- `spec_twph`: TWP specification string (e.g., "T1.0*W50*P100")
- `thickness`: T value in mm (3 decimal places)
- `width`: W value in mm
- `pitch`: P value in mm
- `height`: H value in mm

### Weights
- `gross_weight`: Gross weight in kg (3 decimal places)
- `net_weight`: Net weight in kg

### Position
- `part_position`: `left`, `right`, `center`, `single`, or null

### Status
- `part_status`: Lifecycle state (DRAFT/SAMPLING/MASS_PRODUCTION/OBSOLETE)
- `status`: Legacy status string (待开发/样品生产中/etc.)

### Remark
- `remark`: Free-form remarks (max 500 chars)

### Mold Summary (Legacy)
- `mold_number`: Mold identifier
- `mold_type`: Mold type (连续模/工程模/简易模)
- `press_tonnage`: Press tonnage (e.g., "60T")
- `ppap_no`: PPAP number

## Protected Fields (Not Editable)

### Identity & Keys
- `id`: Primary key
- `part_number`: Unique part number

### System Timestamps
- `created_at`: Creation timestamp (immutable)
- `updated_at`: Update timestamp (system-managed)

### Stock/Production Accounting
- `stock_pcs`: Stock quantity (managed by warehouse system)

### Nomination Workflow
- `nomination_status`, `nomination_attachment`, `price_snapshot`
- `nomination_confirmed_at`, `nomination_confirmed_by`

### Sample/Spray Status
- `sample_judgment_status`
- `spray_status`, `spray_stamped_at`

### Production Management
- `is_urgent`, `target_count`

### Versioning & Deletion
- `version`: Version string
- `is_deleted`: Soft delete flag

### Deprecated Fields
- `customer_id`: Use `part_customer_aliases` instead

## Data Integrity

### Optimistic Concurrency Control

- Uses `updated_at` timestamp for conflict detection
- Microsecond precision truncated to seconds for comparison
- Field-level conflict reporting on 409 response
- Client must resolve conflicts and retry with fresh timestamp

### Transaction Atomicity

- All updates succeed or all fail
- Database transaction with automatic rollback on error
- Foreign key violations return 400
- Unique constraint violations return 409

### Validation

- Pydantic schema validation on request
- Negative values rejected for dimensions/weights
- Enum validation for `part_status` and `part_position`
- String length limits enforced

## Testing Coverage

### Test Cases (13 total)

1. **test_update_part_editor_success**: Full update with all fields
2. **test_update_part_editor_partial**: Partial update (subset of fields)
3. **test_update_part_editor_optimistic_lock_conflict**: Concurrent modification detection
4. **test_update_part_editor_not_found**: Non-existent part
5. **test_update_part_editor_deleted_part**: Soft-deleted part handling
6. **test_update_part_editor_insufficient_permissions**: LV1 user blocked
7. **test_update_part_editor_validation_errors**: Invalid enum values
8. **test_update_part_editor_negative_values**: Negative dimension rejection
9. **test_update_part_editor_atomicity**: Rollback on foreign key violation
10. **test_update_part_editor_clear_optional_fields**: Setting fields to null
11. **test_update_part_editor_protected_fields_ignored**: Protected fields unchanged
12. **test_update_part_editor_concurrent_updates**: Multiple sequential updates
13. **test_update_part_editor_unauthenticated**: No authentication token

### Test Fixtures

- `test_user_lv2`: LV2 user with editor permissions
- `test_user_lv1`: LV1 user with insufficient permissions
- `test_part`: Complete part record with all fields populated
- `auth_headers`: JWT bearer token for LV2 user
- `auth_headers_lv1`: JWT bearer token for LV1 user

## Design Decisions

### Why PATCH instead of PUT?

- Partial updates common in editors (user only changes 2-3 fields)
- Avoids clearing unintended fields
- Better network efficiency
- Matches REST semantics for partial modification

### Why `updated_at` for Optimistic Locking?

- Already exists in Part model
- Automatic update on every change
- Sufficient precision for conflict detection
- No additional version column needed

### Why Field-Level Conflict Detection?

- Better UX: user sees exactly what conflicts
- Enables smart merge strategies in frontend
- Reduces unnecessary re-fetches
- Clear audit trail

### Why Separate `/editor` Endpoint?

- Different authorization rules than basic PATCH
- Specialized schema (only editable fields)
- Optimistic locking overhead not needed for all updates
- Clear semantic separation from other update operations

## Alignment with data-model.md

Per `specs/001-erp-system-architecture/data-model.md`:

✅ **Respects customer_id deprecation**: Field editable but documentation notes to use `part_customer_aliases`  
✅ **Protects import raw_data**: No `raw_data` or import fields exposed  
✅ **Separate tooling relations**: No inline tooling mutations (future stage)  
✅ **Protects stock accounting**: `stock_pcs` not editable  
✅ **Protects nomination audit**: All nomination fields protected  
✅ **TWP legacy preserved**: Fields editable only when explicitly supplied  

## Excluded from Stage 1 (Future Stages)

- ❌ Frontend implementation (HTML/React)
- ❌ Customer alias (part_customer_aliases) mutations
- ❌ Tooling link (tooling_parts) mutations
- ❌ TWP spec (part_tooling_spec) mutations
- ❌ Bulk data repair operations
- ❌ Material dictionary lookups
- ❌ Deployment configuration
- ❌ Git commits

## Next Steps (Future Stages)

### Stage 2: Relation Group Editors
- Add endpoints for `part_customer_aliases` (customer-specific names/numbers)
- Add endpoints for `tooling_parts` (mold linkage)
- Add endpoints for `part_tooling_spec` (TWP options)
- Maintain transactional integrity across relations

### Stage 3: Frontend Implementation
- React component for part editor form
- Optimistic lock conflict resolution UI
- Field validation with real-time feedback
- Dirty field tracking for performance

### Stage 4: Material Integration
- Material dictionary autocomplete
- Material lookup by name → ID resolution
- Material specification validation

### Stage 5: Deployment
- API documentation (OpenAPI/Swagger)
- Database migration verification
- Integration tests with full stack
- Performance benchmarking

## Files Summary

```
backend/app/api/part_editor.py              252 lines (new)
backend/app/schemas/part_editor.py          270 lines (new)
backend/tests/test_part_editor.py           485 lines (new)
backend/app/main.py                         2 lines modified
backend/tests/conftest.py                   5 lines modified
---
Total new code:                             1,007 lines
Total modified:                             7 lines
```

## Verification Checklist

- [x] Request/response schemas defined with Pydantic
- [x] PATCH endpoint implemented at `/api/v1/parts/{part_id}/editor`
- [x] Optimistic locking with `updated_at` timestamp
- [x] Field-level conflict detection
- [x] Authorization check (LV2+ required)
- [x] Atomic transaction with rollback
- [x] Protected fields excluded from updates
- [x] Validation for enums and constraints
- [x] 13 comprehensive test cases
- [x] Router registered in main.py
- [x] AsyncClient fixture for testing
- [x] No frontend implementation (as specified)
- [x] No relation group mutations (as specified)
- [x] Documentation complete

## Status

✅ **Stage 1 Complete**: Backend API contract fully implemented with comprehensive validation, authorization, optimistic locking, and test coverage. Ready for integration testing and frontend development.
