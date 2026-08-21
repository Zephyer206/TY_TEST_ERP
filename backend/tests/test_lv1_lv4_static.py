"""
Static regression tests for LV1-LV4 migration.

These tests verify that legacy permission symbols are not present in runtime code.
They can run without database or FastAPI dependencies.
"""

import os
import re
from pathlib import Path


def get_python_files(directory: str) -> list[Path]:
    """Get all Python files in directory recursively."""
    path = Path(directory)
    return [
        p for p in path.rglob("*.py")
        if "__pycache__" not in str(p) and ".venv" not in str(p)
    ]


def check_file_for_legacy_symbols(filepath: Path) -> list[str]:
    """Check a Python file for legacy permission symbols using word boundaries."""
    violations = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Skip migration files and test files - they document legacy mappings
        if 'alembic/versions' in str(filepath) or 'alembic\\versions' in str(filepath):
            return []
        if 'tests/' in str(filepath) or 'tests\\' in str(filepath):
            return []

        # Check for legacy symbols with word boundaries
        if re.search(r'\bis_superuser\b', content):
            violations.append(f"{filepath}: contains 'is_superuser' (legacy field)")

        if re.search(r'\bis_superadmin\b', content):
            violations.append(f"{filepath}: contains 'is_superadmin' (legacy field)")

        if re.search(r'\bUserRole\b', content):
            violations.append(f"{filepath}: contains 'UserRole' enum reference (legacy)")

        # Check for out-of-range level values (5-10) in assignments, comparisons, defaults
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Skip comments and docstrings
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if '"""' in stripped or "'''" in stripped:
                continue

            # Pattern 1: role_level (snake_case) - avoid userRoleLevel false positive
            if re.search(r'\brole_level\b', line) and not re.search(r'\buserRoleLevel\b', line):
                for bad_level in ['5', '6', '7', '8', '9', '10']:
                    # Assignments: role_level = 5, role_level=5
                    if re.search(rf'\brole_level\s*=\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: assigns role_level={bad_level} (legacy): {stripped[:80]}")
                    # Object literals/dict: "role_level": 5, 'role_level': 5
                    if re.search(rf'["\']role_level["\']\s*:\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: object literal role_level: {bad_level} (legacy): {stripped[:80]}")
                    # All comparison operators: ==, !=, >=, >, <, <=
                    if re.search(rf'\brole_level\s*(==|!=|>=|>|<|<=)\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: compares role_level with {bad_level} (legacy): {stripped[:80]}")
                    # Nullish coalescing / default: role_level ?? 5, role_level or 5
                    if re.search(rf'\brole_level\s*(\?\?|\bor\b)\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: defaults role_level to {bad_level} (legacy): {stripped[:80]}")

            # Pattern 2: roleLevel (camelCase) - avoid userRoleLevel false positive
            if re.search(r'\broleLevel\b', line) and not re.search(r'\buserRoleLevel\b', line):
                for bad_level in ['5', '6', '7', '8', '9', '10']:
                    # Assignments: roleLevel = 5, roleLevel=5
                    if re.search(rf'\broleLevel\s*=\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: assigns roleLevel={bad_level} (legacy): {stripped[:80]}")
                    # Object literals: "roleLevel": 5, 'roleLevel': 5
                    if re.search(rf'["\']roleLevel["\']\s*:\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: object literal roleLevel: {bad_level} (legacy): {stripped[:80]}")
                    # All comparison operators
                    if re.search(rf'\broleLevel\s*(==|!=|>=|>|<|<=)\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: compares roleLevel with {bad_level} (legacy): {stripped[:80]}")
                    # Nullish coalescing / default
                    if re.search(rf'\broleLevel\s*(\?\?|\bor\b)\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: defaults roleLevel to {bad_level} (legacy): {stripped[:80]}")

            # Pattern 3: min_level in function parameters/decorators
            if re.search(r'\bmin_level\b', line):
                for bad_level in ['5', '6', '7', '8', '9', '10']:
                    # Assignments and comparisons
                    if re.search(rf'\bmin_level\s*(=|==|!=|>=|>|<|<=)\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: uses min_level {bad_level} (legacy): {stripped[:80]}")
                    # Nullish coalescing / default
                    if re.search(rf'\bmin_level\s*(\?\?|\bor\b)\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: defaults min_level to {bad_level} (legacy): {stripped[:80]}")

            # Pattern 4: default values in models/schemas
            if 'default' in line.lower():
                for bad_level in ['5', '6', '7', '8', '9', '10']:
                    if re.search(rf'default\s*=\s*{bad_level}\b', line, re.IGNORECASE):
                        # Check context to see if it's about role_level
                        if 'role' in line.lower() or 'level' in line.lower():
                            violations.append(f"{filepath}:{i}: default level {bad_level} (legacy): {stripped[:80]}")

    except Exception as e:
        violations.append(f"{filepath}: error reading file: {e}")

    return violations


def check_frontend_for_legacy_levels(filepath: Path) -> list[str]:
    """Check frontend files for legacy role level references."""
    violations = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('//') or line.strip().startswith('/*'):
                continue

            # Check for roleLevel or role_level with legacy values (avoid userRoleLevel)
            if re.search(r'\brole_?[Ll]evel\b', line) and not re.search(r'\buserRoleLevel\b', line):
                for bad_level in ['5', '6', '7', '8', '9', '10']:
                    # Assignments: roleLevel: 5, role_level: 5, roleLevel = 5
                    if re.search(rf'\brole_?[Ll]evel\s*[:=]\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: uses level {bad_level} (legacy)")
                    # Comparisons: roleLevel >= 5
                    if re.search(rf'\brole_?[Ll]evel\s*(>=|>|===|==)\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: compares level with {bad_level} (legacy)")

    except Exception as e:
        violations.append(f"{filepath}: error reading: {e}")

    return violations


def check_specs_for_legacy_levels(filepath: Path) -> list[str]:
    """Check spec files for legacy role level values in API examples."""
    violations = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Look for role_level in JSON/API examples
            if 'role_level' in line or 'role >=' in line or 'role <=' in line:
                for bad_level in ['5', '6', '7', '8', '9', '10']:
                    # JSON values: "role_level": 5
                    if re.search(rf'"role_level"\s*:\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: API example shows role_level: {bad_level} (legacy)")
                    # Permission requirements: role >= 5
                    if re.search(rf'\brole\s*(>=|>)\s*{bad_level}\b', line):
                        # Avoid false positives for unrelated numbers (like product IDs, quantities)
                        # Only flag if context suggests permissions
                        context = line.lower()
                        if 'auth' in context or 'permission' in context or 'api' in context or 'endpoint' in context:
                            violations.append(f"{filepath}:{i}: permission requirement role >= {bad_level} (legacy)")

            # Check table rows with role_level
            if 'role_level=' in line:
                for bad_level in ['5', '6', '7', '8', '9', '10']:
                    if re.search(rf'role_level\s*=\s*{bad_level}\b', line):
                        violations.append(f"{filepath}:{i}: shows role_level={bad_level} (legacy)")

    except Exception as e:
        violations.append(f"{filepath}: error reading: {e}")

    return violations


def test_no_legacy_symbols_in_backend():
    """Test that backend code has no legacy permission symbols."""
    backend_path = Path(__file__).parent.parent / "app"
    if not backend_path.exists():
        print(f"Warning: {backend_path} not found, skipping test")
        return

    violations = []
    for filepath in get_python_files(str(backend_path)):
        violations.extend(check_file_for_legacy_symbols(filepath))

    if violations:
        print("\n".join(violations))
        raise AssertionError(f"Found {len(violations)} legacy permission symbol(s) in backend")
    else:
        file_count = len(list(get_python_files(str(backend_path))))
        print(f"PASS: No legacy symbols found in {file_count} backend files")


def test_no_legacy_symbols_in_frontend():
    """Test that frontend code has no legacy level references."""
    frontend_path = Path(__file__).parent.parent.parent / "frontend" / "src"
    if not frontend_path.exists():
        print(f"Warning: {frontend_path} not found, skipping test")
        return

    violations = []

    # Check .vue files
    for filepath in frontend_path.rglob("*.vue"):
        violations.extend(check_frontend_for_legacy_levels(filepath))

    # Check .ts files
    for filepath in frontend_path.rglob("*.ts"):
        violations.extend(check_frontend_for_legacy_levels(filepath))

    if violations:
        print("\n".join(violations))
        raise AssertionError(f"Found {len(violations)} legacy level reference(s) in frontend")
    else:
        print("PASS: No legacy level references in frontend")


def test_no_legacy_levels_in_specs():
    """Test that spec documentation has no legacy role level values."""
    specs_path = Path(__file__).parent.parent.parent / "specs"
    if not specs_path.exists():
        print(f"Warning: {specs_path} not found, skipping test")
        return

    violations = []

    # Check markdown files in specs
    for filepath in specs_path.rglob("*.md"):
        violations.extend(check_specs_for_legacy_levels(filepath))

    if violations:
        print("\n".join(violations))
        raise AssertionError(f"Found {len(violations)} legacy level value(s) in specs")
    else:
        print("PASS: No legacy level values in specs")


if __name__ == "__main__":
    print("Running LV1-LV4 static regression tests...\n")

    try:
        test_no_legacy_symbols_in_backend()
        test_no_legacy_symbols_in_frontend()
        test_no_legacy_levels_in_specs()
        print("\nPASS: All static regression tests passed")
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        exit(1)
    except Exception as e:
        print(f"\nFAIL: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
