# Phase 3A2c Implementation Summary

## Objective
Add relationship diagnostics and deduped action candidates to the staging reconciliation script, building on the existing customer and part resolution from 3A2b.

## Implementation Completed

### 1. New Database Loaders
- `load_tooling_data()` - Load non-deleted tooling master records
- `load_existing_aliases_detailed()` - Load active aliases with all fields for conflict detection
- `load_tooling_customer_links()` - Load tooling-customer relationships

### 2. Alias Diagnostics (`process_alias_diagnostics`)
**Normalization**: `(customer_id, norm(customer_part_no), revision='')`

**Status Categories**:
- `alias_resolved`: Active alias exists with same normalized key and part_id
- `empty_customer_part_no`: customer_part_no is None or empty → deferred
- `alias_conflict`: Same normalized key maps to different part(s) or multiple entries
- `missing_alias`: No alias exists → generates insert candidate

**Output**:
- Conflict details with reason codes
- Deferred entries list
- Deduplicated insert candidates with source staging IDs

### 3. Tooling Master Diagnostics (`process_tooling_diagnostics`)
**Normalization**: `norm(tooling_number or tooling_no)`

**Status Categories**:
- `tooling_resolved`: Exactly one non-deleted tooling matches
- `tooling_not_found`: No match found
- `tooling_not_unique`: Multiple matches found

**Output**: Per-row details with resolved tooling_id or candidate list

### 4. Tooling-Part Relationship Diagnostics (`process_tooling_part_diagnostics`)
**Unique Index**: `(tooling_id, part_id)`

**Logic**:
- Check if relationship exists in database
- For missing relationships, aggregate non-empty parsed_position values
- If multiple different normalized positions exist → `position_conflict` and cancel candidate
- Otherwise generate deduplicated insert candidate

**Output**:
- resolved/missing counts
- Insert candidates with aggregated position (or None)
- Position conflict details

### 5. Tooling-Customer Relationship Diagnostics (`process_tooling_customer_diagnostics`)
**Unique Index**: `(tooling_id, customer_id)`

**Logic**:
- If ANY relation_type exists → resolved
- If no relationship exists → generate candidate with `relation_type='user'`
- **Important**: Does NOT add 'sale' type if 'user' already exists (prevents thousands of duplicates)

**Output**:
- resolved/missing counts
- Insert candidates (type='user' only) with source staging IDs

### 6. Staging Update Candidates (`generate_staging_update_candidates`)
**Criteria** (ALL must be met):
- status == 'unique' (customer and part resolved)
- customer_part_no is NOT empty (not in deferred list)
- NO alias conflict
- tooling status == 'resolved'
- NO tooling-part position conflict

**Output**: List of staging row IDs eligible for update with their resolved foreign keys

### 7. Report Generation
**New Sections**:
- `relation_resolution`: Aggregated counts and details for all relationship diagnostics
- `action_candidates`: All insert candidates and staging updates with counts
- `metadata.fingerprint`: Stable SHA256 hash (excludes timestamps and paths)

**Script Version**: `3A2c_relationship_diagnostics`

### 8. Fingerprint Computation (`compute_report_fingerprint`)
- Removes non-stable fields: `generated_at`, `report_path`
- Serializes with `sort_keys=True` for deterministic JSON
- SHA256 hash of UTF-8 encoded JSON

## Test Coverage (70 tests, all passing)

### New Test Classes:
1. `TestAliassDiagnostics` (6 tests)
   - Exact match resolved
   - Empty customer_part_no deferred
   - Conflict detection (different part, multiple entries)
   - Missing alias candidate generation
   - Candidate deduplication

2. `TestToolingDiagnostics` (3 tests)
   - Unique match resolved
   - Not found scenario
   - Not unique scenario

3. `TestToolingPartDiagnostics` (4 tests)
   - Existing relationship resolved
   - Missing generates candidate
   - Position conflict cancels candidate
   - Candidate deduplication with position aggregation

4. `TestToolingCustomerDiagnostics` (3 tests)
   - Existing relationship (any type) resolved
   - Missing generates user-type candidate
   - No duplicate for existing user relationship

5. `TestStagingUpdateCandidates` (5 tests)
   - All criteria met
   - Excluded: empty customer_part_no
   - Excluded: alias conflict
   - Excluded: tooling not resolved
   - Excluded: position conflict

6. `TestFingerprintComputation` (2 tests)
   - Stable across different timestamps/paths
   - Different for different data

## Expected Behavior

For 6054 unique part rows:
- **Alias**: ~832 missing (based on previous audit), with strict conflict detection
- **Tooling-part**: ~812 missing (based on previous audit)
- **Tooling-customer**: Only missing relationships generate candidates, existing 'user' types prevent duplicates
- **Empty customer_part_no**: Deferred, not counted as conflicts
- **Position conflicts**: Cancel specific tooling-part candidates only

## Key Design Decisions

1. **Normalization consistency**: Uses same `norm()` and `norm_name()` from audit script
2. **Revision handling**: Always normalizes to empty string for alias matching
3. **Conflict strictness**: Any ambiguity (multiple aliases, position disagreement) blocks candidate
4. **Deduplication**: By business key `(customer_id, part_id, norm(customer_part_no))` for aliases, `(tooling_id, part_id)` for tooling-parts
5. **Tooling-customer**: Only 'user' type generated, never 'sale' (prevents over-generation)
6. **Staging updates**: Conservative - all relationships must be clean or have clean candidates

## Files Modified
- `backend/scripts/reconcile_staging_authoritative.py` - Main implementation
- `backend/tests/test_reconcile_staging_authoritative.py` - Comprehensive tests

## Verification Status
✅ Syntax check passed (`py_compile`)
✅ All 70 tests passed
✅ Script structure validated (Excel hash, DB connection attempt)
✅ --apply still aborts before DB connection (as required)
✅ Report fingerprint stable and deterministic
