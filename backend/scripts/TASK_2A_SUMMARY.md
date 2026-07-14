# Task 2a: Safe Decimal Comparison Fix

## Problem
Dry-run encountered TypeError when comparing database NUMERIC fields (Decimal) with analysis float values:
- Database fields: `decimal.Decimal` type
- Analysis shared values: `float` type  
- Direct arithmetic operation `abs(db_value - shared) >= 0.001` caused TypeError

## Solution Implemented

### 1. Added Safe Numeric Comparison Helper (Line 40-65)
```python
def safe_numeric_compare(val1, val2, tolerance=None):
    """
    Safely compare two numeric values that may be float or Decimal.
    Converts both to Decimal for precise comparison.
    
    Args:
        val1: First value (float, Decimal, int, or None)
        val2: Second value (float, Decimal, int, or None)
        tolerance: Optional Decimal tolerance (default: Decimal('0.001'))
    
    Returns:
        tuple: (are_equal: bool, diff: Decimal or None)
    """
```

**Key Features:**
- Handles None values safely
- Converts all numeric types to `Decimal(str(value))` for consistent precision
- Uses `Decimal('0.001')` tolerance by default
- Fallback to direct comparison if conversion fails

### 2. Updated All Numeric Comparisons

#### In `analyze_group()` function (Lines 475, 495, 515)
- **Thickness comparison**: Replaced `abs(left_t - right_t) < 0.001` with `safe_numeric_compare(left_t, right_t)`
- **Width comparison**: Replaced `abs(left_w - right_w) < 0.001` with `safe_numeric_compare(left_w, right_w)`
- **Pitch comparison**: Replaced `abs(left_p - right_p) < 0.001` with `safe_numeric_compare(left_p, right_p)`

#### In `apply_corrections()` function (Lines 717, 724, 731)
- **Thickness DB check**: Replaced `abs(db_thickness - shared) >= 0.001` with `safe_numeric_compare()` check
- **Width DB check**: Replaced `abs(db_width - shared) >= 0.001` with `safe_numeric_compare()` check
- **Pitch DB check**: Replaced `abs(db_pitch - shared) >= 0.001` with `safe_numeric_compare()` check

### 3. Import Statement Updated
Added `InvalidOperation` to decimal imports (Line 26):
```python
from decimal import Decimal, InvalidOperation
```

### 4. Rollback Logic Preserved
- Existing exception handling in `main()` (Line 1057) remains unchanged
- `conn.rollback()` on exception ensures transaction safety
- Dry-run mode always rolls back (Line 1030)

## Testing

### Unit Tests (test_safe_numeric_compare.py)
Created comprehensive test suite with 10 test cases:
- ✓ Float vs float comparisons
- ✓ Decimal vs float comparisons (the bug scenario)
- ✓ None value handling
- ✓ Integer comparisons
- ✓ Tolerance boundary testing
- ✓ Exact bug scenario: `Decimal('0.500')` vs `float(0.5)`

**Result**: All tests passed

### Syntax Validation
- ✓ `py_compile` passed without errors
- ✓ No database connection required for testing
- ✓ No main() execution during validation

## Changes Summary

| File | Lines Modified | Type |
|------|---------------|------|
| `correct_left_right_shared_specs.py` | Line 26 | Import update |
| `correct_left_right_shared_specs.py` | Lines 40-65 | New helper function |
| `correct_left_right_shared_specs.py` | Lines 475, 495, 515 | analyze_group() comparisons |
| `correct_left_right_shared_specs.py` | Lines 717, 724, 731 | apply_corrections() comparisons |
| `test_safe_numeric_compare.py` | New file | Unit tests |

## Constraints Followed
✓ Only modified `correct_left_right_shared_specs.py`
✓ No database connection made
✓ No main() execution
✓ Rollback logic unchanged
✓ All numeric comparisons now use safe helper
✓ py_compile validation passed
✓ Pure helper function tested without DB

## Next Steps
Ready for Task 2b: Dry-run execution with database connection to verify the fix in practice.
