# Stage 3 Part Editor API Contract

**Base URL:** `/api/v1/parts/{part_id}/editor`  
**Authorization:** All endpoints require role level >= 2 (LV2+)

---

## Endpoints

### 1. GET Detail - Complete Editor Context

**Endpoint:** `GET /api/v1/parts/{part_id}/editor/detail`

**Response 200:**
```json
{
  "id": 123,
  "internal_name": "Internal Part Name",
  "internal_part_no": "IP-001",
  "material_id": 5,
  "material_name": "SPCC",
  "thickness": "1.000",
  "width": "100.000",
  "pitch": "50.000",
  "gross_weight": "0.150",
  "net_weight": "0.145",
  "part_position": "left",
  "status": "MASS_PRODUCTION",
  "is_deleted": false,
  "created_at": "2026-07-01T10:00:00Z",
  "updated_at": "2026-07-30T10:00:00Z",
  
  "customer_aliases": [
    {
      "id": 1,
      "part_id": 123,
      "customer_id": 10,
      "customer_part_no": "CUST-001",
      "customer_part_name": "Customer Part Name",
      "revision": "A",
      "vehicle_model": "Model X",
      "remark": "Notes",
      "is_active": true,
      "created_at": "2026-07-01T10:00:00Z",
      "updated_at": "2026-07-30T10:00:00Z"
    }
  ],
  
  "tooling_associations": [
    {
      "id": 1,
      "tooling_id": 50,
      "part_id": 123,
      "position": "left",
      "sequence": 0,
      "is_primary": true,
      "created_at": "2026-07-01T10:00:00Z"
    }
  ],
  
  "twp_specs": [
    {
      "id": 1,
      "part_id": 123,
      "tooling_id": 50,
      "spec_twph": "1.0*100*50",
      "thickness": "1.000",
      "width": "100.000",
      "pitch": "50.000",
      "is_primary": true,
      "source_sheet": "CustomerA",
      "source_row": 42,
      "source_note": "Imported from Excel",
      "created_at": "2026-07-01T10:00:00Z",
      "updated_at": "2026-07-30T10:00:00Z"
    }
  ],
  
  "available_toolings": [
    {
      "id": 50,
      "tooling_number": "T001",
      "tooling_name": "Continuous Mold A",
      "mold_type": "continuous",
      "is_continuous": true
    }
  ]
}
```

**Sorting:**
- `tooling_associations`: Continuous toolings first, then by sequence, then by id
- `twp_specs`: Grouped by tooling_id, primary first, then by id
- `available_toolings`: Continuous first, then by tooling_number

---

### 2. PUT Customer Aliases - Atomic Replacement

**Endpoint:** `PUT /api/v1/parts/{part_id}/editor/customer-aliases`

**Request Body:**
```json
{
  "aliases": [
    {
      "id": null,
      "customer_id": 10,
      "customer_part_no": "CUST-001",
      "customer_part_name": "Customer Part Name",
      "revision": "A",
      "vehicle_model": "Model X",
      "remark": "Notes",
      "is_active": true
    }
  ]
}
```

**Field Constraints:**
- `customer_id`: required, must exist in `customers` table
- `customer_part_no`: required, 1-150 chars
- `customer_part_name`: optional, max 200 chars
- `revision`: default "", max 50 chars
- `vehicle_model`: optional, max 100 chars
- `remark`: optional
- `is_active`: default true

**Validation:**
- No duplicate (customer_id, customer_part_no, revision) within request
- All customer IDs must exist
- Part must exist and not be deleted

**Response 200:**
```json
{
  "success": true,
  "part_id": 123,
  "aliases_count": 1,
  "message": "Updated 1 customer aliases"
}
```

---

### 3. PUT Tooling Parts - Atomic Replacement

**Endpoint:** `PUT /api/v1/parts/{part_id}/editor/tooling-parts`

**Request Body:**
```json
{
  "tooling_parts": [
    {
      "tooling_id": 50,
      "position": "left",
      "sequence": 0,
      "is_primary": true
    },
    {
      "tooling_id": 51,
      "position": "right",
      "sequence": 1,
      "is_primary": false
    }
  ]
}
```

**Field Constraints:**
- `tooling_id`: required, must exist in `tooling` table
- `position`: optional, max 20 chars (e.g., "left", "right", "center")
- `sequence`: default 0, >= 0
- `is_primary`: default false

**Primary Constraints:**
1. **If any linked tooling is continuous:**
   - Only continuous toolings may have `is_primary: true`
   - Non-continuous toolings must have `is_primary: false`

2. **If no continuous toolings:**
   - At most one tooling may have `is_primary: true`

**Validation:**
- All tooling IDs must exist and not be deleted
- No duplicate tooling_id within request
- Primary constraints enforced

**Response 200:**
```json
{
  "success": true,
  "part_id": 123,
  "tooling_parts_count": 2,
  "message": "Updated 2 tooling associations"
}
```

---

### 4. PUT TWP Specs - Atomic Replacement

**Endpoint:** `PUT /api/v1/parts/{part_id}/editor/twp-specs`

**Request Body:**
```json
{
  "specs": [
    {
      "id": null,
      "tooling_id": 50,
      "spec_twph": "1.0*100*50",
      "thickness": "1.000",
      "width": "100.000",
      "pitch": "50.000",
      "is_primary": true
    },
    {
      "id": null,
      "tooling_id": 50,
      "spec_twph": "1.2*100*50",
      "thickness": "1.200",
      "width": "100.000",
      "pitch": "50.000",
      "is_primary": false
    }
  ]
}
```

**Field Constraints:**
- `tooling_id`: required, must exist and be associated with part
- `spec_twph`: optional, max 100 chars
- `thickness`: optional, decimal(10,3), >= 0
- `width`: optional, decimal(10,3), >= 0
- `pitch`: optional, decimal(10,3), >= 0
- `is_primary`: default false

**Decimal Precision:**
- All T/W/P fields: maximum 3 decimal places
- Example: `1.234` ✅, `1.2345` ❌

**Primary Scope:**
- Each (part_id, tooling_id) pair can have at most one `is_primary: true` spec
- Primary is NOT global across all toolings

**Validation:**
- All tooling IDs must exist
- Toolings must be associated with part (via `tooling_parts`)
- At most one primary per (part_id, tooling_id)

**Read-Only Fields:**
- `source_sheet`, `source_row`, `source_note` are NOT in request
- These fields remain NULL for editor-created specs
- Existing source provenance is preserved

**Response 200:**
```json
{
  "success": true,
  "part_id": 123,
  "specs_count": 2,
  "message": "Updated 2 TWP specifications"
}
```

---

### 5. PUT Bulk Update - Atomic All-in-One

**Endpoint:** `PUT /api/v1/parts/{part_id}/editor/bulk`

**Request Body:**
```json
{
  "customer_aliases": [
    {
      "customer_id": 10,
      "customer_part_no": "CUST-001"
    }
  ],
  "tooling_parts": [
    {
      "tooling_id": 50,
      "is_primary": true
    }
  ],
  "twp_specs": [
    {
      "tooling_id": 50,
      "thickness": "1.000",
      "is_primary": true
    }
  ]
}
```

**Processing Order:**
1. Customer aliases (if provided)
2. Tooling associations (if provided)
3. TWP specs (if provided)

**Atomicity:**
- All updates in one transaction
- All succeed or all fail
- Updates `part.updated_at` timestamp

**Partial Updates:**
- Omit any category to skip updating it
- `null` vs omitted: both skip that category

**Response 200:**
```json
{
  "success": true,
  "part_id": 123,
  "updated_at": "2026-07-30T11:30:00Z",
  "customer_aliases_count": 1,
  "tooling_parts_count": 1,
  "twp_specs_count": 1,
  "message": "Bulk update completed successfully"
}
```

---

## Error Responses

### 403 Forbidden - Insufficient Permissions
```json
{
  "detail": "Minimum role level required: LV2, you have LV1"
}
```

### 404 Not Found - Part Missing
```json
{
  "detail": "Part 123 not found"
}
```

### 400 Bad Request - Validation Error
```json
{
  "detail": "Customer IDs not found: [10, 20]"
}
```

```json
{
  "detail": "Tooling IDs not found: [50]"
}
```

```json
{
  "detail": "Duplicate alias: customer_id=10, customer_part_no=CUST-001, revision=A"
}
```

```json
{
  "detail": "Duplicate tooling_id: 50"
}
```

```json
{
  "detail": "When any tooling is continuous, only continuous toolings may be primary"
}
```

```json
{
  "detail": "At most one tooling may be marked as primary"
}
```

```json
{
  "detail": "Each tooling may have at most one primary TWP spec. Toolings with multiple primaries: [50]"
}
```

```json
{
  "detail": "Toolings not associated with part: [51]. Add tooling associations first."
}
```

### 409 Conflict - Constraint Violation
```json
{
  "detail": "Integrity constraint violation: unique constraint failed"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Unexpected error during update: ..."
}
```

---

## Business Rules Summary

### Customer Aliases
- ✅ Multiple customers per part allowed
- ✅ Same customer can have multiple part numbers
- ✅ Unique on (customer_id, customer_part_no, revision)
- ✅ Complete replacement strategy

### Tooling Associations
- ✅ Zero to many toolings per part
- ✅ Continuous toolings sort/display first
- ✅ Primary constraints based on continuous/non-continuous mix
- ✅ No cross-part or cross-tooling edits

### TWP Specifications
- ✅ Zero to many specs per (part, tooling) pair
- ✅ Primary is scoped to (part_id, tooling_id), not global
- ✅ Source fields read-only (Excel provenance)
- ✅ No guessing of missing T/W/P values
- ✅ Tooling must be associated before adding specs

### Transaction Boundaries
- ✅ Each endpoint is atomic
- ✅ Bulk endpoint wraps all three categories in one transaction
- ✅ Rollback on any error
- ✅ Updates part.updated_at on success

---

## Usage Patterns

### Pattern 1: Add New Customer Alias
```http
# 1. Get current state
GET /api/v1/parts/123/editor/detail

# 2. Merge new alias with existing
PUT /api/v1/parts/123/editor/customer-aliases
{
  "aliases": [
    ...existing_aliases,
    {
      "customer_id": 20,
      "customer_part_no": "NEW-001",
      "revision": "A",
      "is_active": true
    }
  ]
}
```

### Pattern 2: Add Tooling and TWP Spec
```http
# 1. Add tooling association
PUT /api/v1/parts/123/editor/tooling-parts
{
  "tooling_parts": [
    ...existing_associations,
    {
      "tooling_id": 60,
      "sequence": 2,
      "is_primary": false
    }
  ]
}

# 2. Add TWP spec for new tooling
PUT /api/v1/parts/123/editor/twp-specs
{
  "specs": [
    ...existing_specs,
    {
      "tooling_id": 60,
      "thickness": "1.500",
      "width": "120.000",
      "pitch": "60.000",
      "is_primary": true
    }
  ]
}
```

### Pattern 3: Bulk Replace Everything
```http
PUT /api/v1/parts/123/editor/bulk
{
  "customer_aliases": [...new_complete_list],
  "tooling_parts": [...new_complete_list],
  "twp_specs": [...new_complete_list]
}
```

---

## Frontend Integration Notes

### Optimistic Locking
- `part.updated_at` serves as version token
- Frontend should track last known `updated_at`
- If 409 returned, fetch latest state and prompt user

### Continuous Tooling UI
- Display continuous toolings at top of list
- Disable "primary" checkbox for non-continuous if continuous exists
- Show warning if user tries to violate primary constraints

### TWP Spec Management
- Group specs by tooling_id in UI
- Allow multiple specs per tooling
- Show radio buttons for primary selection per tooling
- Indicate read-only source provenance

### Validation Feedback
- Show which customer/tooling IDs are invalid
- Highlight duplicate entries before submit
- Explain primary constraint violations clearly

---

**API Contract Version:** 1.0  
**Last Updated:** 2026-07-30
