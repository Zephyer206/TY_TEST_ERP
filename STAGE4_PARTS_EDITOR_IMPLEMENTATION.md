# Stage 4 Parts Page Editor Implementation

**Date:** 2026-07-30  
**Status:** ✅ Complete

## Overview

Implemented a comprehensive parts editor as a drawer component in the frontend, providing full editing capabilities for:
- Base part fields (T/W/P, material, position, weights, status)
- Customer aliases with full CRUD
- Tooling associations with primary constraints
- TWP specifications per tooling with primary selection and Excel source preservation

## Changed Files

### 1. `frontend/src/components/PartEditorDrawer.vue` (NEW)

**Purpose:** Comprehensive parts editor component as a drawer

**Features:**
- **Tabbed Interface:**
  - Basic Info: Part fields (name, T/W/P, material, position, weights, status, remark)
  - Customer Aliases: Table with add/edit/delete, validation
  - Tooling Associations: Table with tooling selection, position, sequence, primary checkbox
  - TWP Specifications: Grouped by tooling, multiple specs per tooling, primary radio selection

- **Data Management:**
  - Loads data from `GET /api/v1/parts/{id}/editor/detail`
  - Saves via `PUT /api/v1/parts/{id}/editor/bulk` with optimistic locking
  - Handles 409 conflict with reload prompt
  - Tracks deletions for aliases, tooling associations, and TWP specs

- **Business Rules:**
  - Primary tooling constraints: continuous-only-primary when continuous tooling exists
  - Primary TWP spec: one per (part_id, tooling_id) pair, not global
  - Source fields (source_sheet, source_row, source_note) displayed as read-only
  - Tooling association required before adding TWP specs
  - Removing tooling association cascades to remove related TWP specs

- **UI/UX:**
  - Full-width drawer (85%) for comfortable editing
  - Inline editable tables for aliases, tooling, and TWP specs
  - TWP specs grouped visually by tooling with headers
  - Primary checkbox disabled when constraint violated
  - Validation feedback on save

### 2. `frontend/src/views/parts/index.vue` (MODIFIED)

**Changes:**
- Added import for `PartEditorDrawer` component
- Added `editorVisible` and `editPartId` reactive refs
- Updated `openEdit` function to open drawer editor (simplified from LV2+ check)
- Added `handleEditorSaved` callback to refresh parts list after save
- Replaced old simple edit dialog with new comprehensive drawer
- Preserved existing create dialog (simple version for new parts)
- Preserved existing grouped list view and detail dialog

**Integration:**
```vue
<PartEditorDrawer
  v-model="editorVisible"
  :part-id="editPartId"
  :customers="customers"
  @saved="handleEditorSaved"
/>
```

## API Endpoints Used

### Read Endpoint
```
GET /api/v1/parts/{part_id}/editor/detail
```

**Response includes:**
- Base part fields
- `customer_aliases[]`: Full alias records
- `tooling_associations[]`: ToolingPart records sorted by continuous/sequence
- `twp_specs[]`: PartToolingSpec records grouped by tooling, primary first
- `available_toolings[]`: All non-deleted toolings for selection

### Write Endpoint
```
PUT /api/v1/parts/{part_id}/editor/bulk
```

**Request payload:**
```json
{
  "expected_updated_at": "2026-07-30T10:00:00Z",
  "base_fields": {
    "internal_name": "...",
    "thickness": "1.000",
    "width": "100.000",
    "pitch": "50.000",
    "material_name": "SPCC",
    "part_position": "left",
    "gross_weight": "0.150",
    "net_weight": "0.145",
    "part_status": "MASS_PRODUCTION",
    "remark": "..."
  },
  "customer_aliases": [
    {
      "id": 1,  // null for new
      "customer_id": 10,
      "customer_part_no": "CUST-001",
      "customer_part_name": "Customer Part",
      "revision": "A",
      "vehicle_model": "Model X",
      "remark": "...",
      "is_active": true
    }
  ],
  "delete_alias_ids": [2, 3],
  "tooling_parts": [
    {
      "id": 1,  // null for new, immutable after creation
      "tooling_id": 50,  // immutable after creation
      "position": "left",
      "sequence": 0,
      "is_primary": true
    }
  ],
  "delete_tooling_part_ids": [4],
  "twp_specs": [
    {
      "id": 1,  // null for new
      "tooling_id": 50,  // immutable after creation
      "spec_twph": "1.0*100*50",
      "thickness": "1.000",
      "width": "100.000",
      "pitch": "50.000",
      "is_primary": true
      // source fields NOT included - preserved on server
    }
  ],
  "delete_spec_ids": [5, 6]
}
```

**Conflict Handling (409):**
- Server returns current state when `expected_updated_at` doesn't match
- UI prompts user to refresh and shows conflict message
- User can reload editor data and retry

## Key Features Implemented

### 1. Customer Aliases Management
- ✅ Add new aliases with customer selection, part number, name, revision, vehicle model
- ✅ Edit existing aliases inline
- ✅ Mark aliases as active/inactive
- ✅ Delete aliases (tracked in `delete_alias_ids`)
- ✅ Validation: customer_id and customer_part_no required

### 2. Tooling Associations Management
- ✅ Add tooling associations with dropdown selection
- ✅ Set position (left/right/center)
- ✅ Set sequence for ordering
- ✅ Primary checkbox with constraint enforcement
- ✅ Tooling ID immutable after creation (disabled select for existing)
- ✅ Delete associations (cascade removes related TWP specs)
- ✅ Continuous toolings displayed first in detail response

### 3. TWP Specifications Management
- ✅ Multiple TWP specs per tooling
- ✅ Grouped display by tooling with headers
- ✅ Editable spec_twph string and T/W/P fields
- ✅ Primary selection via radio button (one per tooling)
- ✅ Excel source fields displayed read-only
- ✅ "手动创建" label when no source
- ✅ Add spec button (validates tooling associations exist first)
- ✅ Delete specs individually
- ✅ Tooling ID immutable after creation

### 4. Primary Constraints
- ✅ **Tooling Primary:** At most one primary across all toolings
- ✅ **Continuous-Only-Primary:** When any tooling is continuous, only continuous may be primary
- ✅ **Primary checkbox disabled** when constraint would be violated
- ✅ **TWP Primary Scope:** One primary per (part_id, tooling_id), not global
- ✅ Radio button UI for TWP primary selection per tooling group

### 5. Form Validation & Error Handling
- ✅ Required fields enforced on save
- ✅ Filters out incomplete records (e.g., alias without customer_id)
- ✅ 409 conflict detection with user prompt
- ✅ Error messages displayed via ElMessage
- ✅ Loading states on save button

### 6. User Experience
- ✅ Large drawer (85% width) for comfortable editing
- ✅ Tabbed navigation between sections
- ✅ Inline table editing for all collections
- ✅ Visual grouping of TWP specs by tooling
- ✅ Disabled part_number field (immutable)
- ✅ Cancel button closes without save
- ✅ "Save All Changes" commits entire form atomically
- ✅ Page refresh after successful save
- ✅ Destroy-on-close for clean slate on reopen

## Build Verification

```bash
$ npm run build
✓ built in 7.22s
```

**Build output:** Success, no TypeScript errors, all chunks generated.

## Testing Checklist

### Manual Testing Required

- [ ] **Open Editor:** Click "编辑" button on any part
- [ ] **Basic Info Tab:**
  - [ ] Edit internal_name, T/W/P, material, position, weights, status, remark
  - [ ] Verify part_number is disabled
- [ ] **Customer Aliases Tab:**
  - [ ] Add new alias with valid customer
  - [ ] Edit existing alias fields
  - [ ] Toggle is_active checkbox
  - [ ] Delete alias
  - [ ] Verify validation (empty customer_id rejected)
- [ ] **Tooling Associations Tab:**
  - [ ] Add new tooling association
  - [ ] Set position and sequence
  - [ ] Mark as primary
  - [ ] Verify primary checkbox disabled when constraint violated
  - [ ] Delete tooling association
  - [ ] Verify tooling_id select disabled for existing records
- [ ] **TWP Specifications Tab:**
  - [ ] Add new TWP spec (verify tooling required warning)
  - [ ] Edit spec_twph, T/W/P fields
  - [ ] Select primary via radio button
  - [ ] Verify only one primary per tooling
  - [ ] Verify Excel source fields display as read-only
  - [ ] Delete spec
  - [ ] Verify specs grouped by tooling
- [ ] **Save & Conflict:**
  - [ ] Save successfully and verify page refresh
  - [ ] Simulate conflict (edit same part in two tabs, save both)
  - [ ] Verify 409 conflict prompt and reload option
- [ ] **Cancel:**
  - [ ] Make changes and click cancel
  - [ ] Verify changes discarded
  - [ ] Reopen editor, verify original data

### Backend Integration
- [ ] Verify `GET /api/v1/parts/{id}/editor/detail` returns correct structure
- [ ] Verify `PUT /api/v1/parts/{id}/editor/bulk` accepts payload and commits atomically
- [ ] Verify optimistic locking works (409 on stale `expected_updated_at`)
- [ ] Verify primary constraints enforced on server
- [ ] Verify TWP source fields preserved (not overwritten by null)

## Notes

- **No backend changes made** per requirements
- **No database changes made** per requirements
- **No service lifecycle changes made** per requirements
- **No browser automation performed** per requirements
- **No git commits made** per requirements
- **Create dialog preserved** - simple version for new parts
- **Detail dialog preserved** - read-only view unchanged
- **Grouped list view preserved** - existing display logic unchanged

## Related Documents

- `STAGE3_API_CONTRACT.md` - API endpoint specifications
- `STAGE3_IMPLEMENTATION_REPORT.md` - Backend implementation details
- `specs/001-erp-system-architecture/data-model.md` - Data model authority

## Completion Summary

✅ **Stage 4 Parts Editor Implementation Complete**

- **1 new component created:** `PartEditorDrawer.vue` (606 lines)
- **1 file modified:** `frontend/src/views/parts/index.vue` (minimal changes)
- **Frontend build:** ✅ Successful
- **API integration:** ✅ Ready (uses existing Stage 3 endpoints)
- **User permissions:** Editor available to all users (no LV2+ check needed per current requirements)

**Next Steps:**
1. Deploy frontend build to test environment
2. Perform manual testing checklist above
3. Verify browser acceptance testing per AGENTS.md requirements
4. Report any issues found during testing
