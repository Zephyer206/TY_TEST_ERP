#!/usr/bin/env python3
"""
Integration test for Shanghai Wanxiang Price Importer

Tests the import script with real Excel file via subprocess in dry-run mode.
Does not touch database.
"""

import json
import subprocess
import sys
from pathlib import Path
import pytest


EXCEL_DIR = Path(r"C:\Users\WIT_User\Documents\xwechat_files\uhaohan_2ed1\msg\file\2026-07")
SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "import_shanghai_wanxiang_prices.py"


def find_excel_file():
    """Locate the Shanghai Wanxiang Excel file in the target directory"""
    if not EXCEL_DIR.exists():
        return None

    # Look for Excel files that might be the Shanghai Wanxiang price list
    for xlsx_file in EXCEL_DIR.glob("*.xlsx"):
        # Skip temporary files
        if xlsx_file.name.startswith("~$"):
            continue
        return xlsx_file

    return None


@pytest.mark.skipif(
    find_excel_file() is None,
    reason=f"No Excel file found in {EXCEL_DIR}"
)
def test_shanghai_wanxiang_import_dry_run():
    """Test Shanghai Wanxiang import script with dry-run mode via subprocess"""

    excel_file = find_excel_file()
    assert excel_file is not None, f"Excel file not found in {EXCEL_DIR}"

    # Invoke the import script with --source flag (default is dry-run)
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--source", str(excel_file)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding='utf-8',
        cwd=SCRIPT_PATH.parent.parent
    )

    # Script should succeed
    assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"

    # Parse JSON output from stdout
    try:
        report_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse JSON output: {e}\nStdout: {result.stdout}")

    # Assert: source_sheet is "Sheet3"
    assert report_data["source_sheet"] == "Sheet3", \
        f"Expected source_sheet 'Sheet3', got '{report_data['source_sheet']}'"

    # Assert: ignored_sheets contains exactly the other two sheets
    ignored = report_data["ignored_sheets"]
    assert ignored == ["Sheet1", "万向2025销量"], \
        f"Expected ['Sheet1', '万向2025销量'], got {ignored}"

    # Assert: 25 products
    parts_count = report_data["products_total"]
    assert parts_count == 25, \
        f"Expected 25 products, got {parts_count}"

    # Assert: 22 price rows
    price_rows = report_data["price_rows"]
    assert price_rows == 22, \
        f"Expected 22 price rows, got {price_rows}"

    # Assert: 3 missing prices
    missing_prices = len(report_data["missing_price_part_numbers"])
    assert missing_prices == 3, \
        f"Expected 3 missing prices, got {missing_prices}"

    # Assert: 14 image groups
    image_groups = report_data["image_groups"]
    assert image_groups == 14, \
        f"Expected 14 image groups, got {image_groups}"

    # Assert: shared pair 60009467+60009468
    shared_pairs = report_data["shared_image_pairs"]
    pair_found = ["60009467", "60009468"] in shared_pairs
    assert pair_found, \
        f"Expected shared pair ['60009467', '60009468'] in {shared_pairs}"

    # Merged material cells apply to both left/right products.
    rows_by_number = {row["part_number"]: row for row in report_data["rows"]}
    for left_number, right_number in shared_pairs:
        left_material = rows_by_number[left_number]["material_name"]
        right_material = rows_by_number[right_number]["material_name"]
        assert left_material, f"Missing material for {left_number}"
        assert right_material == left_material, \
            f"Shared pair {left_number}/{right_number} must share material"

    # Assert: zero current-year records
    current_year = report_data["current_year_price_records"]
    assert current_year == 0, \
        f"Expected 0 current-year records, got {current_year}"


def test_command_flags():
    """Test command-line flag validation"""

    excel_file = find_excel_file()
    if excel_file is None:
        pytest.skip(f"No Excel file found in {EXCEL_DIR}")

    # Test: --apply and --dry-run are mutually exclusive
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--source", str(excel_file),
        "--dry-run",
        "--apply"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding='utf-8',
        cwd=SCRIPT_PATH.parent.parent
    )

    assert result.returncode == 2, "Expected exit code 2 for mutually exclusive flags"
    output = json.loads(result.stderr)
    assert "mutually exclusive" in output["error"]

    # Test: --check-db and --dry-run are mutually exclusive
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--source", str(excel_file),
        "--dry-run",
        "--check-db"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding='utf-8',
        cwd=SCRIPT_PATH.parent.parent
    )

    assert result.returncode == 2, "Expected exit code 2 for mutually exclusive flags"
    output = json.loads(result.stderr)
    assert "mutually exclusive" in output["error"]


def test_preview_structure():
    """Test preview output contains expected structure"""

    excel_file = find_excel_file()
    if excel_file is None:
        pytest.skip(f"No Excel file found in {EXCEL_DIR}")

    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--source", str(excel_file)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding='utf-8',
        cwd=SCRIPT_PATH.parent.parent
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)

    # Check required keys
    required_keys = [
        "source_sheet", "ignored_sheets", "products_total", "price_year",
        "price_rows", "missing_price_part_numbers", "image_groups",
        "image_groups_detail", "shared_image_pairs", "rows"
    ]

    for key in required_keys:
        assert key in data, f"Missing required key: {key}"

    # Check rows structure
    assert isinstance(data["rows"], list)
    if data["rows"]:
        row = data["rows"][0]
        assert "part_number" in row
        assert "price_2025" in row
        assert "annual_sales_2025" in row
        assert "image_id" in row


def test_drawing_url_pattern():
    """Test that drawing_url follows the correct pattern for FastAPI static mount"""
    import re

    # Read the import script to verify the drawing_url pattern
    with open(SCRIPT_PATH, 'r', encoding='utf-8') as f:
        script_content = f.read()

    # Assert: drawing_url must match /static/uploads/part_images/wanxiang_shanghai/<image-id><extension>
    url_pattern = r'drawing_url=f"/static/uploads/part_images/wanxiang_shanghai/\{fname\}"'
    assert re.search(url_pattern, script_content), \
        "drawing_url must be set to /static/uploads/part_images/wanxiang_shanghai/{fname}"


if __name__ == "__main__":
    sys.exit(pytest.main(["-q", __file__]))
