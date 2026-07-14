"""Tests for reconcile_staging_authoritative.py customer and part resolution."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add backend to path so we can import the script
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

import reconcile_staging_authoritative as rsa  # noqa: E402


class TestPureFunctions:
    """Test pure functions that don't require database or file system."""

    def test_compute_file_sha256(self):
        """Test SHA256 computation with a temporary file."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"test content\n")
            temp_path = Path(f.name)

        try:
            result = rsa.compute_file_sha256(temp_path)
            expected = hashlib.sha256(b"test content\n").hexdigest()
            assert result == expected
        finally:
            temp_path.unlink()

    def test_expected_sha256_constant(self):
        """Verify the expected SHA256 constant is defined correctly."""
        assert rsa.EXPECTED_SHA256 == "ca35e3e654bfb9b2ce68e220904d8b9ca48f91f978029ed2df7fcba1374cf117"
        assert len(rsa.EXPECTED_SHA256) == 64  # SHA256 is 64 hex chars

    def test_canonical_tables_list(self):
        """Verify canonical tables list is complete."""
        expected_tables = {
            "customers",
            "parts",
            "part_customer_aliases",
            "tooling",
            "tooling_parts",
            "tooling_customer_links",
        }
        assert set(rsa.CANONICAL_TABLES) == expected_tables

    def test_staging_tables_list(self):
        """Verify staging tables list."""
        assert "excel_import_rows" in rsa.STAGING_TABLES

    def test_customer_aliases_constant(self):
        """Verify customer alias mapping."""
        assert "温州力邦企业" in rsa.CUSTOMER_ALIASES
        assert rsa.CUSTOMER_ALIASES["温州力邦企业"] == "温州力邦企业有限公司"

    def test_required_customers_constant(self):
        """Verify required customer IDs and names."""
        assert rsa.REQUIRED_CUSTOMERS[16] == "温州力邦企业有限公司"
        assert rsa.REQUIRED_CUSTOMERS[7272] == "日立安斯泰莫底盘系统（苏州）有限公司"
        assert rsa.REQUIRED_CUSTOMERS[7328] == "H4287"
        assert rsa.REQUIRED_CUSTOMERS[7329] == "日立安斯泰莫底盘系统（武汉）有限公司"

    def test_is_template_value(self):
        """Test template value detection."""
        assert rsa.is_template_value("客户名称") is True
        assert rsa.is_template_value("本厂产品编号") is True
        assert rsa.is_template_value("___") is True
        assert rsa.is_template_value("实际客户名") is False
        assert rsa.is_template_value(None) is False


class TestArgparse:
    """Test argument parsing without database connection."""

    def test_parse_args_help_exits(self):
        """Test that --help exits without connecting to database."""
        with patch("sys.argv", ["script.py", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                rsa.parse_args()
            # --help should exit with code 0
            assert exc_info.value.code == 0

    def test_parse_args_default_dry_run(self):
        """Test default arguments result in dry-run mode."""
        with patch("sys.argv", ["script.py"]):
            args = rsa.parse_args()
            assert args.apply is False
            assert args.report_dir is not None
            assert args.plan_file is None

    def test_parse_args_apply_flag(self):
        """Test --apply flag is parsed correctly."""
        with patch("sys.argv", ["script.py", "--apply"]):
            args = rsa.parse_args()
            assert args.apply is True

    def test_parse_args_custom_report_dir(self):
        """Test --report-dir argument is parsed."""
        with patch("sys.argv", ["script.py", "--report-dir", "/tmp/reports"]):
            args = rsa.parse_args()
            assert args.report_dir == Path("/tmp/reports")

    def test_parse_args_plan_file(self):
        """Test --plan-file argument is parsed."""
        with patch("sys.argv", ["script.py", "--plan-file", "/tmp/plan.json"]):
            args = rsa.parse_args()
            assert args.plan_file == Path("/tmp/plan.json")


class TestApplyAbort:
    """Test that --apply mode explicitly aborts before connecting to database."""

    def test_main_aborts_on_apply(self):
        """Test that main() returns 1 and prints error when --apply is used."""
        with patch("sys.argv", ["script.py", "--apply"]):
            with patch("sys.stdout"), patch("sys.stderr"):
                result = rsa.main()
                assert result == 1

    def test_apply_error_message(self, capsys):
        """Test that --apply produces the correct error message."""
        with patch("sys.argv", ["script.py", "--apply"]):
            result = rsa.main()
            assert result == 1

            captured = capsys.readouterr()
            assert "not implemented" in captured.err.lower()
            assert "3A2b" in captured.err or "phase" in captured.err.lower()


class TestNormalizationFunctions:
    """Test normalization functions from audit script."""

    def test_norm_removes_whitespace_and_uppercases(self):
        """Test norm() normalization."""
        assert rsa.norm("TY-001-Q1") == "TY-001-Q1"
        assert rsa.norm("TY - 001 - Q1") == "TY-001-Q1"
        assert rsa.norm("ty-001-q1") == "TY-001-Q1"
        assert rsa.norm("  TY-001-Q1  ") == "TY-001-Q1"
        assert rsa.norm(None) == ""

    def test_norm_name_preserves_single_spaces_and_lowercases(self):
        """Test norm_name() normalization."""
        assert rsa.norm_name("Internal Name") == "internal name"
        assert rsa.norm_name("INTERNAL  NAME") == "internal name"
        assert rsa.norm_name("  Internal   Name  ") == "internal name"
        assert rsa.norm_name(None) == ""

    def test_looks_like_tooling(self):
        """Test tooling number pattern detection."""
        assert rsa.looks_like_tooling("TY-001-Q1") is True
        assert rsa.looks_like_tooling("GB-002-M1") is True
        assert rsa.looks_like_tooling("TY001Q1") is False
        assert rsa.looks_like_tooling("XY-001-Q1") is False
        assert rsa.looks_like_tooling(None) is False


class TestCustomerResolution:
    """Test customer resolution logic."""

    def test_resolve_customer_exact_match(self):
        """Test exact customer name match."""
        customers_by_name = {
            "温州力邦企业有限公司": [16],
            "H4287": [7328],
        }

        resolved_id, status, candidates = rsa.resolve_customer("温州力邦企业有限公司", customers_by_name)
        assert resolved_id == 16
        assert status == "resolved"
        assert candidates == [16]

    def test_resolve_customer_with_alias(self):
        """Test customer resolution with alias mapping."""
        customers_by_name = {
            "温州力邦企业有限公司": [16],
        }

        # "温州力邦企业" should map to "温州力邦企业有限公司"
        resolved_id, status, candidates = rsa.resolve_customer("温州力邦企业", customers_by_name)
        assert resolved_id == 16
        assert status == "resolved"
        assert candidates == [16]

    def test_resolve_customer_wuhan_suzhou_separation(self):
        """Test that 武汉 resolves to 7329, not 7272."""
        customers_by_name = {
            "日立安斯泰莫底盘系统（武汉）有限公司": [7329],
            "日立安斯泰莫底盘系统（苏州）有限公司": [7272],
        }

        # 武汉 must resolve to 7329
        resolved_id, status, candidates = rsa.resolve_customer(
            "日立安斯泰莫底盘系统（武汉）有限公司",
            customers_by_name
        )
        assert resolved_id == 7329
        assert status == "resolved"

        # 苏州 should resolve to 7272
        resolved_id, status, candidates = rsa.resolve_customer(
            "日立安斯泰莫底盘系统（苏州）有限公司",
            customers_by_name
        )
        assert resolved_id == 7272
        assert status == "resolved"

    def test_resolve_customer_wuhan_yuanfeng_not_affected(self):
        """Test that 武汉元丰 (id=30) resolves normally, not blocked by 武汉 substring."""
        customers_by_name = {
            "武汉元丰": [30],
            "日立安斯泰莫底盘系统（武汉）有限公司": [7329],
        }

        # 武汉元丰 should resolve to 30, not be flagged as not_unique
        resolved_id, status, candidates = rsa.resolve_customer("武汉元丰", customers_by_name)
        assert resolved_id == 30
        assert status == "resolved"
        assert candidates == [30]

    def test_resolve_customer_wuhan_wanxiang_not_affected(self):
        """Test that 武汉万向汽车制动器有限公司 resolves normally."""
        customers_by_name = {
            "武汉万向汽车制动器有限公司": [999],  # Any ID that's not 7329
            "日立安斯泰莫底盘系统（武汉）有限公司": [7329],
        }

        # 武汉万向 should resolve normally
        resolved_id, status, candidates = rsa.resolve_customer(
            "武汉万向汽车制动器有限公司",
            customers_by_name
        )
        assert resolved_id == 999
        assert status == "resolved"
        assert candidates == [999]

    def test_resolve_customer_wuhan_hitachi_wrong_id(self):
        """Test that full 武汉 Hitachi name with wrong ID fails with required_customer_id_mismatch."""
        customers_by_name = {
            "日立安斯泰莫底盘系统（武汉）有限公司": [9999],  # Wrong ID, should be 7329
        }

        resolved_id, status, candidates = rsa.resolve_customer(
            "日立安斯泰莫底盘系统（武汉）有限公司",
            customers_by_name
        )
        assert resolved_id is None
        assert status == "required_customer_id_mismatch"
        assert candidates == [9999]

    def test_resolve_customer_suzhou_hitachi_wrong_id(self):
        """Test that full 苏州 Hitachi name with wrong ID fails with required_customer_id_mismatch."""
        customers_by_name = {
            "日立安斯泰莫底盘系统（苏州）有限公司": [9999],  # Wrong ID, should be 7272
        }

        resolved_id, status, candidates = rsa.resolve_customer(
            "日立安斯泰莫底盘系统（苏州）有限公司",
            customers_by_name
        )
        assert resolved_id is None
        assert status == "required_customer_id_mismatch"
        assert candidates == [9999]

    def test_resolve_customer_other_suzhou_companies_not_affected(self):
        """Test that other companies containing 苏州 resolve normally."""
        customers_by_name = {
            "苏州某某公司": [888],
            "日立安斯泰莫底盘系统（苏州）有限公司": [7272],
        }

        # Other 苏州 company should resolve normally
        resolved_id, status, candidates = rsa.resolve_customer("苏州某某公司", customers_by_name)
        assert resolved_id == 888
        assert status == "resolved"
        assert candidates == [888]

    def test_resolve_customer_not_found(self):
        """Test customer not found scenario."""
        customers_by_name = {
            "温州力邦企业有限公司": [16],
        }

        resolved_id, status, candidates = rsa.resolve_customer("不存在的客户", customers_by_name)
        assert resolved_id is None
        assert status == "customer_not_found"
        assert candidates == []

    def test_resolve_customer_not_unique(self):
        """Test customer not unique scenario."""
        customers_by_name = {
            "重复客户": [100, 101],
        }

        resolved_id, status, candidates = rsa.resolve_customer("重复客户", customers_by_name)
        assert resolved_id is None
        assert status == "customer_not_unique"
        assert candidates == [100, 101]

    def test_process_customer_resolution(self):
        """Test full customer resolution processing."""
        staging_rows = [
            {
                "id": 1,
                "parsed_customer_name": "温州力邦企业有限公司",
                "parsed_tooling_number": "TY-001-Q1",
                "source_sheet": "Sheet1",
                "source_row": 10,
                "resolved_customer_id": None,
            },
            {
                "id": 2,
                "parsed_customer_name": "温州力邦企业",  # Alias
                "parsed_tooling_number": "TY-002-Q1",
                "source_sheet": "Sheet1",
                "source_row": 11,
                "resolved_customer_id": None,
            },
            {
                "id": 3,
                "parsed_customer_name": "不存在的客户",
                "parsed_tooling_number": "TY-003-Q1",
                "source_sheet": "Sheet1",
                "source_row": 12,
                "resolved_customer_id": None,
            },
            {
                "id": 4,
                "parsed_customer_name": None,  # Skip
                "parsed_tooling_number": "TY-004-Q1",
                "source_sheet": "Sheet1",
                "source_row": 13,
                "resolved_customer_id": None,
            },
            {
                "id": 5,
                "parsed_customer_name": "客户名称",  # Template value
                "parsed_tooling_number": "TY-005-Q1",
                "source_sheet": "Sheet1",
                "source_row": 14,
                "resolved_customer_id": None,
            },
        ]

        customers_by_name = {
            "温州力邦企业有限公司": [16],
        }

        result = rsa.process_customer_resolution(staging_rows, customers_by_name)

        assert result["candidate_rows"] == 3  # Rows 1, 2, 3 (not 4 or 5)
        assert result["resolved_rows"] == 2  # Rows 1, 2
        assert result["customer_not_found"] == 1  # Row 3
        assert result["customer_not_unique"] == 0
        assert len(result["details"]) == 3


class TestPartResolution:
    """Test part resolution logic."""

    def test_build_part_indexes_from_tooling(self):
        """Test building part indexes from tooling relationships."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "mold_number": None},
            2: {"id": 2, "internal_name": "Part B", "mold_number": "TY-001-Q1"},
        }
        aliases = []
        tooling_links = [
            {"part_id": 1, "tooling_number": "TY-002-Q1", "tooling_no": None},
        ]

        indexes = rsa.build_part_indexes(parts, aliases, tooling_links)

        assert 1 in indexes["parts_by_tooling"]["TY-002-Q1"]
        assert 2 in indexes["parts_by_tooling"]["TY-001-Q1"]

    def test_build_part_indexes_from_aliases(self):
        """Test building part indexes from aliases."""
        parts = {1: {"id": 1, "internal_name": "Part A"}}
        aliases = [
            {"customer_id": 16, "part_id": 1, "customer_part_no": "CUST-001"},
        ]
        tooling_links = []

        indexes = rsa.build_part_indexes(parts, aliases, tooling_links)

        assert 1 in indexes["alias_parts"][(16, "CUST-001")]

    def test_choose_part_tooling_only(self):
        """Test part matching with tooling number only."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": None},
        }
        parts_by_tooling = {"TY-001-Q1": {1}}
        alias_parts = {}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-001-Q1",
            "parsed_customer_part_no": None,
            "parsed_internal_name": None,
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id == 1
        assert status == "unique"

    def test_choose_part_alias_only(self):
        """Test part matching with alias only."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": None},
        }
        parts_by_tooling = {}
        alias_parts = {(16, "CUST-001"): {1}}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-999-Q1",
            "parsed_customer_part_no": "CUST-001",
            "parsed_internal_name": None,
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id == 1
        assert status == "unique"

    def test_choose_part_tooling_and_alias_intersection(self):
        """Test part matching prefers tooling+alias intersection."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": None},
            2: {"id": 2, "internal_name": "Part B", "part_position": None},
        }
        parts_by_tooling = {"TY-001-Q1": {1, 2}}
        alias_parts = {(16, "CUST-001"): {1}}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-001-Q1",
            "parsed_customer_part_no": "CUST-001",
            "parsed_internal_name": None,
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id == 1
        assert status == "unique"

    def test_choose_part_no_intersection_falls_back_to_tooling(self):
        """Test that no intersection falls back to tooling candidates."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": None},
            2: {"id": 2, "internal_name": "Part B", "part_position": None},
        }
        parts_by_tooling = {"TY-001-Q1": {1}}
        alias_parts = {(16, "CUST-001"): {2}}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-001-Q1",
            "parsed_customer_part_no": "CUST-001",
            "parsed_internal_name": None,
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id == 1
        assert status == "unique"

    def test_choose_part_no_candidate(self):
        """Test no part candidate scenario."""
        parts = {}
        parts_by_tooling = {}
        alias_parts = {}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-999-Q1",
            "parsed_customer_part_no": "UNKNOWN",
            "parsed_internal_name": None,
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id is None
        assert status == "no_part_candidate"
        assert candidates == []

    def test_choose_part_multiple_candidates(self):
        """Test multiple part candidates scenario."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": None},
            2: {"id": 2, "internal_name": "Part B", "part_position": None},
        }
        parts_by_tooling = {"TY-001-Q1": {1, 2}}
        alias_parts = {}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-001-Q1",
            "parsed_customer_part_no": None,
            "parsed_internal_name": None,
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id is None
        assert status == "multiple_part_candidates"
        assert set(candidates) == {1, 2}

    def test_choose_part_narrow_by_internal_name(self):
        """Test narrowing multiple candidates by internal_name."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": None},
            2: {"id": 2, "internal_name": "Part B", "part_position": None},
        }
        parts_by_tooling = {"TY-001-Q1": {1, 2}}
        alias_parts = {}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-001-Q1",
            "parsed_customer_part_no": None,
            "parsed_internal_name": "Part A",
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id == 1
        assert status == "unique"

    def test_choose_part_narrow_by_position(self):
        """Test narrowing multiple candidates by position."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": "left"},
            2: {"id": 2, "internal_name": "Part A", "part_position": "right"},
        }
        parts_by_tooling = {"TY-001-Q1": {1, 2}}
        alias_parts = {}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-001-Q1",
            "parsed_customer_part_no": None,
            "parsed_internal_name": "Part A",
            "parsed_position": "left",
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id == 1
        assert status == "unique"

    def test_choose_part_never_match_by_name_only(self):
        """Test that matching never happens by internal_name alone without tooling/alias."""
        parts = {
            1: {"id": 1, "internal_name": "Part A", "part_position": None},
        }
        parts_by_tooling = {}
        alias_parts = {}
        indexes = {"parts": parts, "parts_by_tooling": parts_by_tooling, "alias_parts": alias_parts}

        row = {
            "parsed_tooling_number": "TY-999-Q1",
            "parsed_customer_part_no": None,
            "parsed_internal_name": "Part A",
            "parsed_position": None,
        }

        part_id, status, candidates = rsa.choose_part(row, 16, indexes)
        assert part_id is None
        assert status == "no_part_candidate"


class TestAliassDiagnostics:
    """Test alias relationship diagnostics."""

    def test_alias_resolved_exact_match(self):
        """Test alias resolved when active alias exists with same part."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
            },
        ]
        existing_aliases = [
            {
                "id": 1,
                "customer_id": 16,
                "part_id": 100,
                "customer_part_no": "CUST-001",
                "customer_part_name": "Part Name",
                "revision": "",
                "is_active": True,
            },
        ]

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert result["alias_resolved"] == 1
        assert result["missing_alias"] == 0
        assert result["alias_conflict"] == 0
        assert result["empty_customer_part_no"] == 0
        assert len(result["alias_insert_candidates"]) == 0

    def test_alias_empty_customer_part_no_deferred(self):
        """Test that empty customer_part_no is deferred."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": None,
            },
            {
                "staging_id": 2,
                "source_sheet": "Sheet1",
                "source_row": 11,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 101,
                "parsed_customer_part_no": "",
            },
        ]
        existing_aliases = []

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert result["empty_customer_part_no"] == 2
        assert len(result["deferred"]) == 2
        assert result["missing_alias"] == 0
        assert len(result["alias_insert_candidates"]) == 0

    def test_alias_conflict_different_part(self):
        """Test alias conflict when same key maps to different part."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": None,
            },
        ]
        existing_aliases = [
            {
                "id": 1,
                "customer_id": 16,
                "part_id": 999,  # Different part
                "customer_part_no": "CUST-001",
                "customer_part_name": None,
                "revision": "",
                "is_active": True,
            },
        ]

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert result["alias_conflict"] == 1
        assert result["alias_resolved"] == 0
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["reason"] == "existing_alias_conflict"
        assert len(result["alias_insert_candidates"]) == 0

    def test_alias_conflict_multiple_entries(self):
        """Test alias conflict when multiple entries for same normalized key."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": None,
            },
        ]
        existing_aliases = [
            {
                "id": 1,
                "customer_id": 16,
                "part_id": 100,
                "customer_part_no": "CUST-001",
                "customer_part_name": None,
                "revision": "",
                "is_active": True,
            },
            {
                "id": 2,
                "customer_id": 16,
                "part_id": 100,
                "customer_part_no": "CUST - 001",  # Normalized same
                "customer_part_name": None,
                "revision": "",
                "is_active": True,
            },
        ]

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert result["alias_conflict"] == 1
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["reason"] == "existing_alias_conflict"

    def test_alias_missing_generates_candidate(self):
        """Test missing alias generates insert candidate."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
            },
        ]
        existing_aliases = []

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert result["missing_alias"] == 1
        assert len(result["alias_insert_candidates"]) == 1
        candidate = result["alias_insert_candidates"][0]
        assert candidate["customer_id"] == 16
        assert candidate["part_id"] == 100
        assert candidate["customer_part_no"] == "CUST-001"
        assert candidate["revision"] == ""
        assert 1 in candidate["source_staging_ids"]

    def test_alias_candidate_deduplication(self):
        """Test that duplicate candidates are deduplicated."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": "Part Name",
            },
            {
                "staging_id": 2,
                "source_sheet": "Sheet1",
                "source_row": 11,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST - 001",  # Normalized same
                "parsed_customer_part_name": "Part Name",
            },
        ]
        existing_aliases = []

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert result["missing_alias"] == 2  # Both rows count
        assert len(result["alias_insert_candidates"]) == 1  # But only one candidate
        candidate = result["alias_insert_candidates"][0]
        assert len(candidate["source_staging_ids"]) == 2
        assert set(candidate["source_staging_ids"]) == {1, 2}
        assert len(candidate["source_refs"]) == 2
        assert candidate["source_refs"][0]["staging_id"] == 1
        assert candidate["source_refs"][1]["staging_id"] == 2

    def test_alias_planned_cross_part_conflict(self):
        """Test planned cross-part conflict when same business key maps to different parts in staging."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": None,
            },
            {
                "staging_id": 2,
                "source_sheet": "Sheet1",
                "source_row": 11,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 200,  # Different part!
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": None,
            },
        ]
        existing_aliases = []  # No existing alias

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        # Both rows should be conflicts, no candidate generated
        assert result["alias_conflict"] == 2
        assert result["missing_alias"] == 0
        assert len(result["alias_insert_candidates"]) == 0
        assert len(result["conflicts"]) == 2

        # Check conflict reasons
        assert result["conflicts"][0]["reason"] == "planned_cross_part_conflict"
        assert result["conflicts"][1]["reason"] == "planned_cross_part_conflict"
        assert result["conflicts"][0]["expected_part_id"] == 100
        assert result["conflicts"][1]["expected_part_id"] == 200
        assert result["conflicts"][0]["planned_part_ids"] == [100, 200]

    def test_alias_existing_conflict_takes_precedence(self):
        """Test that existing alias conflict is reported even if staging also has cross-part conflict."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": None,
            },
            {
                "staging_id": 2,
                "source_sheet": "Sheet1",
                "source_row": 11,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 200,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": None,
            },
        ]
        existing_aliases = [
            {
                "id": 1,
                "customer_id": 16,
                "part_id": 300,  # Yet another different part
                "customer_part_no": "CUST-001",
                "customer_part_name": None,
                "revision": "",
                "is_active": True,
            },
        ]

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert result["alias_conflict"] == 2
        assert len(result["conflicts"]) == 2
        # Existing conflict takes precedence in reason
        assert result["conflicts"][0]["reason"] == "existing_alias_conflict"
        assert result["conflicts"][1]["reason"] == "existing_alias_conflict"

    def test_alias_candidate_no_part_id_in_dedup_key(self):
        """Test that candidate deduplication does NOT use part_id."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": "Name A",
            },
        ]
        existing_aliases = []

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert len(result["alias_insert_candidates"]) == 1
        candidate = result["alias_insert_candidates"][0]

        # Business key assertion: (customer_id, norm(cpn), revision)
        # Should NOT include part_id in the key
        assert candidate["customer_id"] == 16
        assert candidate["part_id"] == 100
        assert candidate["customer_part_no"] == "CUST-001"
        assert candidate["revision"] == ""

    def test_alias_candidate_customer_part_name_unique(self):
        """Test that customer_part_name is set when all staging rows have the same normalized value."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": "Part Name",
            },
            {
                "staging_id": 2,
                "source_sheet": "Sheet1",
                "source_row": 11,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": "Part  Name",  # Extra space, normalizes same
            },
        ]
        existing_aliases = []

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert len(result["alias_insert_candidates"]) == 1
        candidate = result["alias_insert_candidates"][0]
        # Both normalize to "PARTNAME", so unique
        assert candidate["customer_part_name"] == "PARTNAME"
        assert len(candidate["customer_part_name_values"]) == 1

    def test_alias_candidate_customer_part_name_multiple_values(self):
        """Test that customer_part_name is None when staging rows have different values."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": "Part Name A",
            },
            {
                "staging_id": 2,
                "source_sheet": "Sheet1",
                "source_row": 11,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": "Part Name B",  # Different
            },
        ]
        existing_aliases = []

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        assert len(result["alias_insert_candidates"]) == 1
        candidate = result["alias_insert_candidates"][0]
        # Different values, so None
        assert candidate["customer_part_name"] is None
        assert len(candidate["customer_part_name_values"]) == 2
        assert "PARTNAMEA" in candidate["customer_part_name_values"]
        assert "PARTNAMEB" in candidate["customer_part_name_values"]

    def test_alias_fingerprint_stability(self):
        """Test that candidate fingerprint (business key) is stable and doesn't include part_id."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
                "parsed_customer_part_name": "Name A",
            },
            {
                "staging_id": 2,
                "source_sheet": "Sheet1",
                "source_row": 11,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST - 001",  # Normalized same
                "parsed_customer_part_name": "Name A",
            },
        ]
        existing_aliases = []

        result = rsa.process_alias_diagnostics(part_resolution_details, existing_aliases)

        # Should generate exactly one candidate
        assert len(result["alias_insert_candidates"]) == 1

        # Verify source_refs are sorted and complete
        candidate = result["alias_insert_candidates"][0]
        assert len(candidate["source_refs"]) == 2
        assert candidate["source_refs"][0]["staging_id"] == 1
        assert candidate["source_refs"][0]["source_sheet"] == "Sheet1"
        assert candidate["source_refs"][0]["source_row"] == 10
        assert candidate["source_refs"][1]["staging_id"] == 2


class TestToolingDiagnostics:
    """Test tooling master diagnostics."""

    def test_tooling_resolved_unique_match(self):
        """Test tooling resolved when unique match found."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_tooling_number": "TY-001-Q1",
            },
        ]
        tooling_data = [
            {"id": 1, "tooling_number": "TY-001-Q1", "tooling_no": None, "is_deleted": False},
        ]

        result = rsa.process_tooling_diagnostics(part_resolution_details, tooling_data)

        assert result["tooling_resolved"] == 1
        assert result["tooling_not_found"] == 0
        assert result["tooling_not_unique"] == 0
        assert len(result["details"]) == 1
        assert result["details"][0]["tooling_id"] == 1
        assert result["details"][0]["status"] == "resolved"

    def test_tooling_not_found(self):
        """Test tooling not found scenario."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_tooling_number": "TY-999-Q1",
            },
        ]
        tooling_data = []

        result = rsa.process_tooling_diagnostics(part_resolution_details, tooling_data)

        assert result["tooling_not_found"] == 1
        assert result["tooling_resolved"] == 0
        assert result["details"][0]["status"] == "tooling_not_found"
        assert result["details"][0]["tooling_id"] is None

    def test_tooling_not_unique(self):
        """Test tooling not unique scenario."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_tooling_number": "TY-001-Q1",
            },
        ]
        tooling_data = [
            {"id": 1, "tooling_number": "TY-001-Q1", "tooling_no": None, "is_deleted": False},
            {"id": 2, "tooling_number": "TY-001-Q1", "tooling_no": None, "is_deleted": False},
        ]

        result = rsa.process_tooling_diagnostics(part_resolution_details, tooling_data)

        assert result["tooling_not_unique"] == 1
        assert result["details"][0]["status"] == "tooling_not_unique"
        assert result["details"][0]["tooling_id"] is None
        assert set(result["details"][0]["tooling_candidates"]) == {1, 2}


class TestToolingPartDiagnostics:
    """Test tooling-part relationship diagnostics."""

    def test_tooling_part_resolved(self):
        """Test tooling-part resolved when relationship exists."""
        tooling_diagnostics = {
            "details": [
                {
                    "staging_id": 1,
                    "source_sheet": "Sheet1",
                    "source_row": 10,
                    "customer_id": 16,
                    "part_id": 100,
                    "tooling_id": 1,
                    "status": "resolved",
                },
            ],
        }
        existing_tooling_parts = [
            {"tooling_id": 1, "part_id": 100, "position": "left"},
        ]
        part_resolution_details = [
            {"staging_id": 1, "parsed_position": "left"},
        ]

        result = rsa.process_tooling_part_diagnostics(
            tooling_diagnostics, existing_tooling_parts, part_resolution_details
        )

        assert result["resolved"] == 1
        assert result["missing_tooling_part"] == 0
        assert len(result["tooling_part_insert_candidates"]) == 0

    def test_tooling_part_missing_generates_candidate(self):
        """Test missing tooling-part generates candidate."""
        tooling_diagnostics = {
            "details": [
                {
                    "staging_id": 1,
                    "source_sheet": "Sheet1",
                    "source_row": 10,
                    "customer_id": 16,
                    "part_id": 100,
                    "tooling_id": 1,
                    "status": "resolved",
                },
            ],
        }
        existing_tooling_parts = []
        part_resolution_details = [
            {"staging_id": 1, "parsed_position": "left"},
        ]

        result = rsa.process_tooling_part_diagnostics(
            tooling_diagnostics, existing_tooling_parts, part_resolution_details
        )

        assert result["missing_tooling_part"] == 1
        assert len(result["tooling_part_insert_candidates"]) == 1
        candidate = result["tooling_part_insert_candidates"][0]
        assert candidate["tooling_id"] == 1
        assert candidate["part_id"] == 100
        assert candidate["position"] == "left"

    def test_tooling_part_position_conflict(self):
        """Test position conflict cancels candidate."""
        tooling_diagnostics = {
            "details": [
                {
                    "staging_id": 1,
                    "source_sheet": "Sheet1",
                    "source_row": 10,
                    "customer_id": 16,
                    "part_id": 100,
                    "tooling_id": 1,
                    "status": "resolved",
                },
                {
                    "staging_id": 2,
                    "source_sheet": "Sheet1",
                    "source_row": 11,
                    "customer_id": 16,
                    "part_id": 100,
                    "tooling_id": 1,
                    "status": "resolved",
                },
            ],
        }
        existing_tooling_parts = []
        part_resolution_details = [
            {"staging_id": 1, "parsed_position": "left"},
            {"staging_id": 2, "parsed_position": "right"},  # Different position
        ]

        result = rsa.process_tooling_part_diagnostics(
            tooling_diagnostics, existing_tooling_parts, part_resolution_details
        )

        assert result["missing_tooling_part"] == 2
        assert len(result["tooling_part_insert_candidates"]) == 0  # Cancelled due to conflict
        assert len(result["position_conflicts"]) == 1
        conflict = result["position_conflicts"][0]
        assert set(conflict["conflicting_positions"]) == {"left", "right"}

    def test_tooling_part_candidate_deduplication(self):
        """Test candidate deduplication and position aggregation."""
        tooling_diagnostics = {
            "details": [
                {
                    "staging_id": 1,
                    "source_sheet": "Sheet1",
                    "source_row": 10,
                    "customer_id": 16,
                    "part_id": 100,
                    "tooling_id": 1,
                    "status": "resolved",
                },
                {
                    "staging_id": 2,
                    "source_sheet": "Sheet1",
                    "source_row": 11,
                    "customer_id": 16,
                    "part_id": 100,
                    "tooling_id": 1,
                    "status": "resolved",
                },
            ],
        }
        existing_tooling_parts = []
        part_resolution_details = [
            {"staging_id": 1, "parsed_position": "left"},
            {"staging_id": 2, "parsed_position": "left"},  # Same position
        ]

        result = rsa.process_tooling_part_diagnostics(
            tooling_diagnostics, existing_tooling_parts, part_resolution_details
        )

        assert result["missing_tooling_part"] == 2
        assert len(result["tooling_part_insert_candidates"]) == 1  # Deduplicated
        candidate = result["tooling_part_insert_candidates"][0]
        assert candidate["position"] == "left"
        assert len(candidate["source_staging_ids"]) == 2


class TestToolingCustomerDiagnostics:
    """Test tooling-customer relationship diagnostics."""

    def test_tooling_customer_resolved_any_type(self):
        """Test tooling-customer resolved when any relation_type exists."""
        tooling_diagnostics = {
            "details": [
                {
                    "staging_id": 1,
                    "customer_id": 16,
                    "tooling_id": 1,
                    "status": "resolved",
                },
            ],
        }
        existing_links = [
            {"tooling_id": 1, "customer_id": 16, "relation_type": "user"},
        ]

        result = rsa.process_tooling_customer_diagnostics(tooling_diagnostics, existing_links)

        assert result["resolved"] == 1
        assert result["missing_tooling_customer"] == 0
        assert len(result["tooling_customer_insert_candidates"]) == 0

    def test_tooling_customer_missing_generates_candidate(self):
        """Test missing tooling-customer generates candidate with type='user'."""
        tooling_diagnostics = {
            "details": [
                {
                    "staging_id": 1,
                    "customer_id": 16,
                    "tooling_id": 1,
                    "status": "resolved",
                },
            ],
        }
        existing_links = []

        result = rsa.process_tooling_customer_diagnostics(tooling_diagnostics, existing_links)

        assert result["missing_tooling_customer"] == 1
        assert len(result["tooling_customer_insert_candidates"]) == 1
        candidate = result["tooling_customer_insert_candidates"][0]
        assert candidate["tooling_id"] == 1
        assert candidate["customer_id"] == 16
        assert candidate["relation_type"] == "user"

    def test_tooling_customer_no_duplicate_for_existing_user(self):
        """Test that existing user relationship prevents candidate generation."""
        tooling_diagnostics = {
            "details": [
                {
                    "staging_id": 1,
                    "customer_id": 16,
                    "tooling_id": 1,
                    "status": "resolved",
                },
            ],
        }
        existing_links = [
            {"tooling_id": 1, "customer_id": 16, "relation_type": "user"},
        ]

        result = rsa.process_tooling_customer_diagnostics(tooling_diagnostics, existing_links)

        assert result["resolved"] == 1
        assert len(result["tooling_customer_insert_candidates"]) == 0


class TestStagingUpdateCandidates:
    """Test staging update candidate generation."""

    def test_staging_update_all_criteria_met(self):
        """Test staging update candidate when all criteria met."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
            },
        ]
        tooling_diagnostics = {
            "details": [
                {"staging_id": 1, "tooling_id": 1, "status": "resolved"},
            ],
        }
        alias_diagnostics = {
            "conflicts": [],
            "deferred": [],
            "alias_insert_candidates": [],
        }
        tooling_part_diagnostics = {
            "position_conflicts": [],
        }

        result = rsa.generate_staging_update_candidates(
            part_resolution_details,
            tooling_diagnostics,
            alias_diagnostics,
            tooling_part_diagnostics,
        )

        assert len(result) == 1
        assert result[0]["staging_id"] == 1
        assert result[0]["customer_id"] == 16
        assert result[0]["part_id"] == 100
        assert result[0]["tooling_id"] == 1

    def test_staging_update_excluded_empty_customer_part_no(self):
        """Test staging update excluded when customer_part_no is empty."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": None,
            },
        ]
        tooling_diagnostics = {
            "details": [
                {"staging_id": 1, "tooling_id": 1, "status": "resolved"},
            ],
        }
        alias_diagnostics = {
            "conflicts": [],
            "deferred": [{"staging_id": 1}],  # Deferred due to empty
            "alias_insert_candidates": [],
        }
        tooling_part_diagnostics = {
            "position_conflicts": [],
        }

        result = rsa.generate_staging_update_candidates(
            part_resolution_details,
            tooling_diagnostics,
            alias_diagnostics,
            tooling_part_diagnostics,
        )

        assert len(result) == 0

    def test_staging_update_excluded_alias_conflict(self):
        """Test staging update excluded when alias has conflict."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
            },
        ]
        tooling_diagnostics = {
            "details": [
                {"staging_id": 1, "tooling_id": 1, "status": "resolved"},
            ],
        }
        alias_diagnostics = {
            "conflicts": [{"staging_id": 1}],  # Conflict
            "deferred": [],
            "alias_insert_candidates": [],
        }
        tooling_part_diagnostics = {
            "position_conflicts": [],
        }

        result = rsa.generate_staging_update_candidates(
            part_resolution_details,
            tooling_diagnostics,
            alias_diagnostics,
            tooling_part_diagnostics,
        )

        assert len(result) == 0

    def test_staging_update_excluded_tooling_not_resolved(self):
        """Test staging update excluded when tooling not resolved."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
            },
        ]
        tooling_diagnostics = {
            "details": [
                {"staging_id": 1, "tooling_id": None, "status": "tooling_not_found"},
            ],
        }
        alias_diagnostics = {
            "conflicts": [],
            "deferred": [],
            "alias_insert_candidates": [],
        }
        tooling_part_diagnostics = {
            "position_conflicts": [],
        }

        result = rsa.generate_staging_update_candidates(
            part_resolution_details,
            tooling_diagnostics,
            alias_diagnostics,
            tooling_part_diagnostics,
        )

        assert len(result) == 0

    def test_staging_update_excluded_position_conflict(self):
        """Test staging update excluded when tooling-part has position conflict."""
        part_resolution_details = [
            {
                "staging_id": 1,
                "source_sheet": "Sheet1",
                "source_row": 10,
                "status": "unique",
                "customer_id": 16,
                "resolved_part_id": 100,
                "parsed_customer_part_no": "CUST-001",
            },
        ]
        tooling_diagnostics = {
            "details": [
                {"staging_id": 1, "tooling_id": 1, "status": "resolved"},
            ],
        }
        alias_diagnostics = {
            "conflicts": [],
            "deferred": [],
            "alias_insert_candidates": [],
        }
        tooling_part_diagnostics = {
            "position_conflicts": [
                {"tooling_id": 1, "part_id": 100}  # Conflict
            ],
        }

        result = rsa.generate_staging_update_candidates(
            part_resolution_details,
            tooling_diagnostics,
            alias_diagnostics,
            tooling_part_diagnostics,
        )

        assert len(result) == 0


class TestReportGeneration:
    """Test report generation logic."""

    def test_generate_report_structure_3a2c(self):
        """Test that generate_report creates the expected structure for 3A2c."""
        excel_verification = {"status": "ok", "sha256": "abc123"}
        table_counts = {"customers": 10, "parts": 100}
        unique_indexes = [{"indexname": "idx_test"}]
        database_read_only = True
        customer_resolution = {
            "candidate_rows": 100,
            "resolved_rows": 95,
            "customer_not_found": 5,
        }
        part_resolution = {
            "customer_resolved_rows": 95,
            "unique_part_rows": 90,
        }
        relation_resolution = {
            "alias": {"alias_resolved": 80, "missing_alias": 10},
            "tooling": {"tooling_resolved": 85},
        }
        action_candidates = {
            "counts": {"alias_inserts": 10, "staging_updates": 80},
        }

        report = rsa.generate_report(
            excel_verification,
            table_counts,
            unique_indexes,
            database_read_only,
            customer_resolution,
            part_resolution,
            relation_resolution,
            action_candidates,
        )

        assert "metadata" in report
        assert "excel_verification" in report
        assert "database_state" in report
        assert "customer_resolution" in report
        assert "part_resolution" in report
        assert "relation_resolution" in report
        assert "action_candidates" in report
        assert "operations" in report

        assert report["metadata"]["database_read_only"] is True
        assert report["metadata"]["script_version"] == "3A2c_relationship_diagnostics"
        assert report["operations"]["dry_run"] is True


class TestFingerprintComputation:
    """Test report fingerprint computation."""

    def test_compute_report_fingerprint_stable(self):
        """Test that fingerprint is stable across identical reports."""
        report1 = {
            "metadata": {
                "generated_at": "2024-01-01T10:00:00",
                "script_version": "3A2c",
                "report_path": "/path/to/report1.json",
            },
            "data": {"value": 123},
        }
        report2 = {
            "metadata": {
                "generated_at": "2024-01-01T11:00:00",  # Different time
                "script_version": "3A2c",
                "report_path": "/path/to/report2.json",  # Different path
            },
            "data": {"value": 123},
        }

        fingerprint1 = rsa.compute_report_fingerprint(report1)
        fingerprint2 = rsa.compute_report_fingerprint(report2)

        assert fingerprint1 == fingerprint2
        assert len(fingerprint1) == 64  # SHA256 is 64 hex chars

    def test_compute_report_fingerprint_different_data(self):
        """Test that fingerprint differs when data differs."""
        report1 = {
            "metadata": {"script_version": "3A2c"},
            "data": {"value": 123},
        }
        report2 = {
            "metadata": {"script_version": "3A2c"},
            "data": {"value": 456},  # Different value
        }

        fingerprint1 = rsa.compute_report_fingerprint(report1)
        fingerprint2 = rsa.compute_report_fingerprint(report2)

        assert fingerprint1 != fingerprint2
        """Test that generate_report creates the expected structure."""
        excel_verification = {"status": "ok", "sha256": "abc123"}
        table_counts = {"customers": 10, "parts": 100}
        unique_indexes = [{"indexname": "idx_test"}]
        database_read_only = True
        customer_resolution = {
            "candidate_rows": 100,
            "resolved_rows": 95,
            "customer_not_found": 5,
            "customer_not_unique": 0,
            "changed_from_old_resolved_customer": 10,
            "by_customer_name": {},
            "details": [],
        }
        part_resolution = {
            "customer_resolved_rows": 95,
            "unique_part_rows": 90,
            "no_part_candidate": 3,
            "multiple_part_candidates": 2,
            "customer_unresolved": 5,
            "changed_from_old_resolved_part": 0,
            "details": [],
        }

        report = rsa.generate_report(
            excel_verification,
            table_counts,
            unique_indexes,
            database_read_only,
            customer_resolution,
            part_resolution,
        )

        assert "metadata" in report
        assert "excel_verification" in report
        assert "database_state" in report
        assert "customer_resolution" in report
        assert "part_resolution" in report
        assert "operations" in report

        assert report["metadata"]["database_read_only"] is True
        assert report["metadata"]["script_version"] == "3A2c_relationship_diagnostics"
        assert report["operations"]["dry_run"] is True
        assert report["operations"]["apply_attempted"] is False

    def test_generate_report_includes_counts(self):
        """Test that table counts are included in report."""
        excel_verification = {"status": "ok"}
        table_counts = {"customers": 5, "parts": 10}
        unique_indexes = []
        database_read_only = True
        customer_resolution = {"candidate_rows": 0, "resolved_rows": 0}
        part_resolution = {"customer_resolved_rows": 0, "unique_part_rows": 0}

        report = rsa.generate_report(
            excel_verification,
            table_counts,
            unique_indexes,
            database_read_only,
            customer_resolution,
            part_resolution,
        )

        assert report["database_state"]["table_counts"] == table_counts
        assert report["database_state"]["unique_indexes_count"] == 0

    def test_generate_report_includes_indexes(self):
        """Test that unique indexes are included in report."""
        excel_verification = {"status": "ok"}
        table_counts = {}
        unique_indexes = [
            {"indexname": "idx1", "tablename": "parts"},
            {"indexname": "idx2", "tablename": "customers"},
        ]
        database_read_only = True
        customer_resolution = {"candidate_rows": 0, "resolved_rows": 0}
        part_resolution = {"customer_resolved_rows": 0, "unique_part_rows": 0}

        report = rsa.generate_report(
            excel_verification,
            table_counts,
            unique_indexes,
            database_read_only,
            customer_resolution,
            part_resolution,
        )

        assert len(report["database_state"]["unique_indexes"]) == 2
        assert report["database_state"]["unique_indexes_count"] == 2


class TestWriteReport:
    """Test report writing to disk."""

    def test_write_report_creates_file(self):
        """Test that write_report creates a JSON file."""
        report = {"test": "data", "metadata": {"generated_at": "2024-01-01"}}

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            report_path = rsa.write_report(report, report_dir)

            assert report_path.exists()
            assert report_path.suffix == ".json"
            assert "part_candidate_resolution_" in report_path.name

            # Verify content
            content = json.loads(report_path.read_text(encoding="utf-8"))
            assert content["test"] == "data"

    def test_write_report_creates_directory(self):
        """Test that write_report creates the directory if it doesn't exist."""
        report = {"test": "data"}

        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir) / "nested" / "reports"
            assert not report_dir.exists()

            report_path = rsa.write_report(report, report_dir)

            assert report_dir.exists()
            assert report_path.exists()


class TestDatabaseFunctions:
    """Test database-related functions with mocked connections."""

    def test_verify_database_readonly_true(self):
        """Test verify_database_readonly when transaction is read-only."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": "on"}

        result = rsa.verify_database_readonly(mock_cursor)

        assert result is True
        mock_cursor.execute.assert_called_once()

    def test_verify_database_readonly_false(self):
        """Test verify_database_readonly when transaction is not read-only."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": "off"}

        result = rsa.verify_database_readonly(mock_cursor)

        assert result is False

    def test_get_unique_indexes_query(self):
        """Test that get_unique_indexes uses pg_indexes, not just pg_constraint."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "schemaname": "public",
                "tablename": "parts",
                "indexname": "idx_parts_unique",
                "indexdef": "CREATE UNIQUE INDEX idx_parts_unique ON parts (id) WHERE is_deleted = false",
            }
        ]

        result = rsa.get_unique_indexes(mock_cursor)

        # Verify the query uses pg_indexes
        call_args = mock_cursor.execute.call_args[0][0]
        assert "pg_indexes" in call_args.lower()
        assert "indexdef" in call_args.lower()
        assert len(result) == 1
        assert "WHERE" in result[0]["indexdef"]  # Partial index clause


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
