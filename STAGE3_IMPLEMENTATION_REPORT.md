# Stage 3: Part Relationship Editor API - Implementation Report

**Date:** 2026-07-30  
**Scope:** Backend APIs for complete, transactional editing of part relationships  
**Status:** ✅ Complete

---

## Summary

Implemented Stage 3 backend APIs for atomic, transactional editing of part relationships required by the frontend editor:

1. **Customer aliases** - Complete replacement with validation
2. **Tooling-part associations** - Add/remove with primary constraints
3. **TWP specifications** - Per (part, tooling) with scoped primary enforcement

All source fields (`source_sheet`, `source_row`, `source_note`) are read-only. The editor never guesses missing T/W/P values or mutates `raw_data`.

---

## Created Files

### 1. Schemas
**File:** `backend/app/schemas/part_editor_relationships.py` (6,380 bytes)

Pydantic models for request/response:
- `CustomerAliasItem`, `CustomerAliasesUpdateRequest`, `CustomerAliasResponse`
- `ToolingPartItem`, `ToolingPartsUpdateRequest`, `ToolingPartResponse`
- `TWPSpecItem`, `TWPSpecsUpdateRequest`, `TWPSpecResponse`
- `PartEditorDetailResponse` - Complete editor context
- `PartEditorBulkUpdateRequest`, `PartEditorBulkUpdateResponse`

**Validation:**
- Decimal precision enforced (max 3 decimal places for T/W/P)
- Field length constraints
- No source field exposure in request models

---

### 2. API Endpoints
**File:** `backend/app/api/part_editor_relationships.py` (24,453 bytes)

**Base URL:** `/api/v1/parts/{part_id}/editor`

#### Endpoints:

**GET `/api/v1/parts/{part_id}/editor/detail`**
- Returns complete part editor context
- Includes customer aliases, tooling associations, TWP specs
- Lists available toolings for selection
- Sorted: continuous toolings first, then by sequence

**PUT `/api/v1/parts/{part_id}/editor/customer-aliases`**
- Atomic replacement of all customer aliases
- Validates customer IDs exist
- Prevents duplicate (customer_id, customer_part_no, revision)
- Transaction: delete all + create new

**PUT `/api/v1/parts/{part_id}/editor/tooling-parts`**
- Update tooling-part associations
- Validates tooling IDs exist
- Enforces primary constraints:
  - If any tooling is continuous → only continuous may be primary
  - Otherwise → at most one may be primary
- Transaction: delete all + create new

**PUT `/api/v1/parts/{part_id}/editor/twp-specs`**
- Update TWP specifications
- Validates tooling IDs and associations
- Enforces at most one primary per (part_id, tooling_id)
- Source fields remain NULL (editor cannot set)
- Transaction: delete all + create new

**PUT `/api/v1/parts/{part_id}/editor/bulk`**
- Atomic update of all three categories in one transaction
- Processes in order: aliases → tooling parts → TWP specs
- All succeed or all fail
- Updates part.updated_at timestamp

---

### 3. Validation Logic

**Customer validation:**
- All customer IDs must exist in `customers` table
- No duplicate aliases within request

**Tooling validation:**
- All tooling IDs must exist and not be deleted
- No duplicate tooling_id in associations
- Primary constraints enforced per continuous/non-continuous rules

**TWP validation:**
- Toolings must be associated with part before adding specs
- At most one primary per (part_id, tooling_id)
- Decimal precision validated

**Cross-reference validation:**
- Prevents editing wrong part_id
- Prevents editing across toolings (scoped operations)

---

### 4. Tests
**File:** `backend/tests/test_part_editor_relationships.py` (16,771 bytes)

**Test Results:** ✅ 25 tests passed, 0 failed

**Test Coverage:**

- **Schema Validation (9 tests)**
  - Valid/minimal customer alias items
  - Tooling part items with defaults
  - TWP spec decimal precision validation
  - Bulk update request structure

- **Business Logic (7 tests)**
  - Primary constraints: continuous-only rules
  - Primary constraints: single non-continuous primary
  - TWP primary scope: one per tooling
  - Multiple primaries detection

- **API Endpoints (4 tests)**
  - GET detail: 404 for missing part
  - GET detail: 403 for insufficient permissions
  - Duplicate key detection
  - Duplicate tooling detection

- **Integration Scenarios (3 tests)**
  - Continuous + simple tooling workflow
  - Multi-customer part
  - Bulk update all relationships

- **Error Handling (2 tests)**
  - Rollback on integrity error
  - Source fields read-only enforcement

**Test Approach:**
- Safe: No data insertion into cloud SQL
- Mocks database operations
- Tests schema, validation, and business logic
- Verifies API contract

---

## Integration

### Router Registration
**File:** `backend/app/main.py` (modified)

Added:
```python
from app.api.part_editor_relationships import router as part_editor_relationships_router
app.include_router(part_editor_relationships_router, prefix=settings.API_V1_PREFIX)
```

---

## API Contract

### Authorization
- All endpoints require **LV2+** role level
- Returns 403 Forbidden for insufficient permissions

### Common Responses

**404 Not Found:**
```json
{
  "detail": "Part {part_id} not found"
}
```

**400 Bad Request:**
```json
{
  "detail": "Customer IDs not found: [1, 2, 3]"
}
```

**409 Conflict:**
```json
{
  "detail": "Integrity constraint violation: ..."
}
```

---

## Validation Evidence

### 1. Python Compilation
```bash
✅ python -m py_compile app/schemas/part_editor_relationships.py
✅ python -m py_compile app/api/part_editor_relationships.py
✅ python -m py_compile app/main.py
```

### 2. Test Collection
```bash
✅ 25 tests collected successfully
```

### 3. Test Execution
```bash
✅ 25 passed, 0 failed in 0.15s
```

---

## Key Design Decisions

### 1. Complete Replacement Strategy
- Customer aliases: Replace all at once
- Tooling associations: Replace all at once
- TWP specs: Replace all at once
- **Rationale:** Simpler conflict resolution, clear editor state

### 2. Primary Enforcement
- Continuous tooling rules: If any continuous exists, only continuous may be primary
- Non-continuous: At most one primary
- TWP primary: Scoped to (part_id, tooling_id), not global
- **Rationale:** Matches data model specification and business rules

### 3. Source Field Protection
- `source_sheet`, `source_row`, `source_note` read-only
- Not in request schemas
- Set to NULL in editor-created records
- **Rationale:** Preserve Excel import provenance, prevent corruption

### 4. No Guessing
- Missing T/W/P values remain NULL
- No automatic derivation from other fields
- **Rationale:** Data integrity, explicit user input required

### 5. Validation Order
- Existence checks first (part, customer, tooling)
- Business rules second (primary constraints, uniqueness)
- Database constraints last (foreign keys, unique indexes)
- **Rationale:** Clear error messages, fail fast

---

## Database Schema Requirements

### Tables Used
- `parts` - Part master data
- `customers` - Customer master data
- `tooling` - Tooling/mold master data
- `part_customer_aliases` - Customer aliases (many-to-many)
- `tooling_parts` - Tooling associations (many-to-many)
- `part_tooling_specs` - TWP specifications per (part, tooling)

### Constraints Enforced
- Foreign key integrity
- Unique constraints:
  - `part_customer_aliases`: (customer_id, customer_part_no, revision)
  - `tooling_parts`: (tooling_id, part_id, position)
- Primary scoping (application-level validation)

---

## Adherence to Requirements

✅ **Scope (a):** Active customer aliases - create/update/remove as validated list  
✅ **Scope (b):** Zero-to-many ToolingPart associations - add/remove, position, sequence, primary  
✅ **Scope (c):** Zero-to-many PartToolingSpec T/W/P - add/update/delete, one primary per pair  
✅ **Read-only:** Excel source fields never altered  
✅ **No guessing:** Missing T/W/P values preserved as NULL  
✅ **No batch mutation:** Scoped to single part only  
✅ **Atomic:** LV2+ endpoint with transaction boundaries  
✅ **Validation:** Customer/tooling/spec IDs checked, constraints enforced  
✅ **Primary rules:** Continuous tooling rules enforced  
✅ **Sorting:** Continuous first, then sequence  
✅ **TWP scope:** Primary per (part_id, tooling_id)  
✅ **Tests:** 25 safe tests, no cloud SQL insertion  
✅ **Compilation:** All modules compile successfully  
✅ **No frontend:** Backend only as specified  
✅ **No migration:** Uses existing schema  
✅ **No commit:** Changes ready for review  

---

## Usage Example

### Get Editor Detail
```http
GET /api/v1/parts/123/editor/detail
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 123,
  "internal_name": "Part Name",
  "customer_aliases": [...],
  "tooling_associations": [...],
  "twp_specs": [...],
  "available_toolings": [...]
}
```

### Update Customer Aliases
```http
PUT /api/v1/parts/123/editor/customer-aliases
Content-Type: application/json

{
  "aliases": [
    {
      "customer_id": 1,
      "customer_part_no": "CUST-001",
      "customer_part_name": "Customer Part",
      "revision": "A",
      "is_active": true
    }
  ]
}
```

### Update Tooling Associations
```http
PUT /api/v1/parts/123/editor/tooling-parts

{
  "tooling_parts": [
    {
      "tooling_id": 10,
      "position": "left",
      "sequence": 0,
      "is_primary": true
    }
  ]
}
```

### Update TWP Specs
```http
PUT /api/v1/parts/123/editor/twp-specs

{
  "specs": [
    {
      "tooling_id": 10,
      "thickness": "1.000",
      "width": "100.000",
      "pitch": "50.000",
      "is_primary": true
    }
  ]
}
```

### Bulk Update (All at Once)
```http
PUT /api/v1/parts/123/editor/bulk

{
  "customer_aliases": [...],
  "tooling_parts": [...],
  "twp_specs": [...]
}
```

---

## Next Steps

1. **Frontend Integration:** Connect editor UI to these APIs
2. **Migration Review:** Ensure schema matches data-model.md
3. **Deployment:** Test endpoints in staging environment
4. **Documentation:** Update API documentation with examples
5. **Monitoring:** Add logging for relationship changes

---

## Files Changed

**Created:**
- `backend/app/schemas/part_editor_relationships.py`
- `backend/app/api/part_editor_relationships.py`
- `backend/tests/test_part_editor_relationships.py`

**Modified:**
- `backend/app/main.py` (router registration)

**Total:** 3 new files, 1 modified file

---

## Verification Commands

```bash
# Compile check
cd backend
python -m py_compile app/schemas/part_editor_relationships.py
python -m py_compile app/api/part_editor_relationships.py
python -m py_compile app/main.py

# Test collection and execution
python -m pytest tests/test_part_editor_relationships.py --collect-only
python -m pytest tests/test_part_editor_relationships.py -v

# Expected: 25 passed, 0 failed
```

---

**Implementation Complete** ✅
