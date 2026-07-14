#!/usr/bin/env python3
"""
Test parse_combined_spec function without database connection.
"""
import sys
import re
from typing import Optional, Tuple


def parse_combined_spec(spec_str: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Parse combined T*W*P spec string with strict dimension parsing.

    Supports:
    - Full: "0.8*34*34.5" -> (0.8, 34.0, 34.5)
    - Partial: "0.4*" -> (0.4, None, None), "0.4*92" -> (0.4, 92.0, None)
    - With prefixes: "T1.2*W50*P40" -> (1.2, 50.0, 40.0)
    - Separators: *, ×, x, X (ASCII and full-width)
    - Brackets: () and （）
    - Trailing patterns: (1出2), （一出二）, 左右各一个
    - Tolerance: "0.8±0.01*34*34.5"

    Rejects:
    - Double separators: "4.0**155*43" -> (None, None, None)
    - Letter prefixes not T/W/P: "XC2.39", "SUS301" -> (None, None, None)

    Range validation: T: 0.1-10mm, W/P: 1-1000mm

    Returns: (thickness, width, pitch)
    """
    if not spec_str or not isinstance(spec_str, str):
        return None, None, None

    spec_str = spec_str.strip()
    if not spec_str:
        return None, None, None

    # Remove trailing cavity patterns before parsing dimensions
    # Patterns: (1出2), （一出二）, 左右各一个, etc.
    cavity_patterns = [
        r'\s*[（(]\s*[1一]\s*出\s*\d+\s*[)）]',  # (1出2), （一出二）
        r'\s*[（(]\s*左右各一(个)?\s*[)）]',  # （左右各一个）
        r'\s*左右各一(个)?$',  # 左右各一个 at end
    ]
    for pattern in cavity_patterns:
        spec_str = re.sub(pattern, '', spec_str)

    spec_str = spec_str.strip()
    if not spec_str:
        return None, None, None

    # Normalize separators: ×, x, X -> * (handle full-width)
    spec_str = spec_str.replace('×', '*').replace('x', '*').replace('X', '*')

    # Remove mm/MM units
    spec_str = re.sub(r'\s*mm\s*', '', spec_str, flags=re.IGNORECASE)
    spec_str = spec_str.strip()

    # Check for double separators (ambiguous format like "4.0**155")
    if '**' in spec_str:
        return None, None, None

    # Check if string starts with letters (reject material/part codes)
    # Allow only T/W/P prefixes
    if spec_str and spec_str[0].isalpha():
        # Must start with T, W, or P followed by a digit
        if not re.match(r'^[TWPtwp]\s*\d', spec_str):
            return None, None, None

    # Split by * separator
    parts = spec_str.split('*')

    # Parse each part
    parsed_values = []
    for part in parts:
        part = part.strip()
        if not part:
            # Empty part (trailing * or consecutive *)
            parsed_values.append(None)
            continue

        # Extract number with optional T/W/P prefix and tolerance
        # Pattern: optional [TWP], whitespace, number with decimal, optional tolerance
        match = re.match(r'^[TWPtwp]?\s*(\d+\.?\d*)(?:\s*[±+\-]\s*[\d.]+)?', part)
        if match:
            try:
                value = float(match.group(1))
                parsed_values.append(value)
            except:
                parsed_values.append(None)
        else:
            # No valid number found
            parsed_values.append(None)

    # Extract T, W, P (up to 3 values)
    thickness = parsed_values[0] if len(parsed_values) > 0 else None
    width = parsed_values[1] if len(parsed_values) > 1 else None
    pitch = parsed_values[2] if len(parsed_values) > 2 else None

    # Validate ranges
    if thickness is not None and not (0.1 <= thickness <= 10.0):
        thickness = None

    if width is not None and not (1.0 <= width <= 1000.0):
        width = None

    if pitch is not None and not (1.0 <= pitch <= 1000.0):
        pitch = None

    return thickness, width, pitch


def test_parse_combined_spec():
    """Test parse_combined_spec with various input formats."""
    test_cases = [
        # (input, expected_output, description)
        # Valid cases with Chinese cavity patterns
        ("0.5*96*165(1出2)", (0.5, 96.0, 165.0), "Full spec with (1出2)"),
        ("1.6*98*19（一出二，左右各一个）", (1.6, 98.0, 19.0), "Full spec with （一出二，左右各一个）"),

        # Complete/partial cases
        ("0.8*34*34.5", (0.8, 34.0, 34.5), "Full spec"),
        ("0.4*", (0.4, None, None), "Thickness only with trailing *"),
        ("0.4*92", (0.4, 92.0, None), "Thickness and width"),

        # Invalid cases - should return all None
        ("4.0**155*43", (None, None, None), "Double separator (ambiguous)"),
        ("XC2.39.81/XC2.39.16", (None, None, None), "Letter prefix (not T/W/P)"),
        ("SUS301", (None, None, None), "Material code"),

        # T/W/P prefix support
        ("T1.2*W50*P40", (1.2, 50.0, 40.0), "T/W/P prefixes"),
        ("T1.2*W50", (1.2, 50.0, None), "T/W prefixes only"),
        ("t0.8*w34*p34.5", (0.8, 34.0, 34.5), "Lowercase t/w/p prefixes"),

        # Various separator formats
        ("0.8×34×34.5", (0.8, 34.0, 34.5), "× separator"),
        ("0.8x34x34.5", (0.8, 34.0, 34.5), "x separator"),
        ("0.8X34X34.5", (0.8, 34.0, 34.5), "X separator"),

        # With units
        ("0.8mm*34mm*34.5mm", (0.8, 34.0, 34.5), "With mm units"),
        ("0.8MM*34MM*34.5MM", (0.8, 34.0, 34.5), "With MM units"),

        # With tolerance
        ("0.8±0.01*34*34.5", (0.8, 34.0, 34.5), "With tolerance"),

        # Edge cases
        ("", (None, None, None), "Empty string"),
        ("   ", (None, None, None), "Whitespace only"),
        (None, (None, None, None), "None input"),

        # Range validation - out of range T
        ("15*34*34.5", (None, 34.0, 34.5), "T > 10 (out of range)"),
        ("0.05*34*34.5", (None, 34.0, 34.5), "T < 0.1 (out of range)"),

        # Range validation - out of range W/P
        ("0.8*0.5*34.5", (0.8, None, 34.5), "W < 1 (out of range)"),
        ("0.8*1500*34.5", (0.8, None, 34.5), "W > 1000 (out of range)"),
        ("0.8*34*1500", (0.8, 34.0, None), "P > 1000 (out of range)"),

        # Valid boundary cases
        ("0.1*1*1", (0.1, 1.0, 1.0), "Minimum valid values"),
        ("10*1000*1000", (10.0, 1000.0, 1000.0), "Maximum valid values"),

        # More Chinese cavity patterns
        ("0.8*34*34.5(1出4)", (0.8, 34.0, 34.5), "With (1出4)"),
        ("0.8*34*34.5（一出2）", (0.8, 34.0, 34.5), "With （一出2）"),
        ("0.8*34*34.5左右各一个", (0.8, 34.0, 34.5), "With 左右各一个"),

        # Complex cases
        ("T1.5±0.05*W100*P50mm", (1.5, 100.0, 50.0), "T with tolerance + W/P + units"),
    ]

    print("="*80)
    print("Testing parse_combined_spec")
    print("="*80)

    passed = 0
    failed = 0

    for i, (input_str, expected, description) in enumerate(test_cases, 1):
        result = parse_combined_spec(input_str)

        # Compare results
        if result == expected:
            status = "[PASS]"
            passed += 1
        else:
            status = "[FAIL]"
            failed += 1

        print(f"\n{status} Test #{i}: {description}")
        print(f"  Input:    {repr(input_str)}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")

    print("\n" + "="*80)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("="*80)

    return failed == 0


if __name__ == "__main__":
    success = test_parse_combined_spec()
    sys.exit(0 if success else 1)
