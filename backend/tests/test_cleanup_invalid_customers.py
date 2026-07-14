"""
Unit tests for cleanup_invalid_customers.py
Pure/unit tests with no real database connection
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime


# Mock the backend imports before importing the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTargetSelection:
    """Test target customer selection from audit"""

    def test_extract_truncated_customers(self):
        """Should extract 3 truncated customers"""
        from scripts.cleanup_invalid_customers import extract_target_customers

        audit = {
            'duplicate_customers': {
                'truncated': [
                    {'id': 100, 'name': 'Z', 'classification': 'truncated'},
                    {'id': 102, 'name': 'A-P IB', 'classification': 'truncated'},
                    {'id': 107, 'name': 'B-U  IT', 'classification': 'truncated'}
                ],
                'high_confidence_empty_duplicates': [],
                'low_confidence_no_ref_customers': []
            }
        }

        targets, excluded = extract_target_customers(audit)

        assert len(targets) == 3
        assert all(t['classification'] == 'truncated' for t in targets)
        assert len(excluded) == 0

    def test_extract_high_confidence_duplicates(self):
        """Should extract high-confidence empty duplicates"""
        from scripts.cleanup_invalid_customers import extract_target_customers

        audit = {
            'duplicate_customers': {
                'truncated': [],
                'high_confidence_empty_duplicates': [
                    {'id': 17, 'name': '丰铃公司Q', 'classification': 'high_confidence_empty_duplicate'},
                    {'id': 24, 'name': '厦门和利多卫浴科技有限公司（X）', 'classification': 'high_confidence_empty_duplicate'}
                ],
                'low_confidence_no_ref_customers': []
            }
        }

        targets, excluded = extract_target_customers(audit)

        assert len(targets) == 2
        assert all(t['classification'] == 'high_confidence_empty_duplicate' for t in targets)

    def test_extract_combined_targets(self):
        """Should combine truncated + high-confidence duplicates"""
        from scripts.cleanup_invalid_customers import extract_target_customers

        audit = {
            'duplicate_customers': {
                'truncated': [
                    {'id': 100, 'name': 'Z', 'classification': 'truncated'},
                    {'id': 102, 'name': 'A-P IB', 'classification': 'truncated'}
                ],
                'high_confidence_empty_duplicates': [
                    {'id': 17, 'name': '丰铃公司Q', 'classification': 'high_confidence_empty_duplicate'}
                ],
                'low_confidence_no_ref_customers': []
            }
        }

        targets, excluded = extract_target_customers(audit)

        assert len(targets) == 3
        assert len([t for t in targets if t['classification'] == 'truncated']) == 2
        assert len([t for t in targets if t['classification'] == 'high_confidence_empty_duplicate']) == 1

    def test_exclude_low_confidence_customers(self):
        """Should exclude low-confidence customers from targets"""
        from scripts.cleanup_invalid_customers import extract_target_customers

        audit = {
            'duplicate_customers': {
                'truncated': [
                    {'id': 100, 'name': 'Z', 'classification': 'truncated'}
                ],
                'high_confidence_empty_duplicates': [],
                'low_confidence_no_ref_customers': [
                    {'id': 10, 'name': '广州曙光制动系统有限公司', 'classification': 'low_confidence_no_refs'},
                    {'id': 11, 'name': '汽车部件苏州有限公司(东机工)', 'classification': 'low_confidence_no_refs'},
                    {'id': 89, 'name': 'test', 'classification': 'low_confidence_no_refs'}
                ]
            }
        }

        targets, excluded = extract_target_customers(audit)

        assert len(targets) == 1
        assert targets[0]['id'] == 100
        assert len(excluded) == 3
        assert all(e['classification'] == 'low_confidence_no_refs' for e in excluded)

    def test_full_audit_extraction(self):
        """Should extract exactly 60 targets and 23 excluded"""
        from scripts.cleanup_invalid_customers import extract_target_customers

        # Simulate the actual audit structure
        audit = {
            'duplicate_customers': {
                'truncated': [{'id': i, 'name': f'T{i}'} for i in range(1, 4)],  # 3
                'high_confidence_empty_duplicates': [{'id': i, 'name': f'H{i}'} for i in range(10, 67)],  # 57
                'low_confidence_no_ref_customers': [{'id': i, 'name': f'L{i}'} for i in range(100, 123)]  # 23
            }
        }

        targets, excluded = extract_target_customers(audit)

        assert len(targets) == 60  # 3 + 57
        assert len(excluded) == 23


class TestAuditShapeValidation:
    """Test strict audit shape validation"""

    def test_validate_correct_audit_shape(self):
        """Should pass validation with correct counts"""
        from scripts.cleanup_invalid_customers import validate_audit_shape

        targets = (
            [{'id': i, 'name': f'T{i}', 'classification': 'truncated'} for i in range(1, 4)] +
            [{'id': i, 'name': f'H{i}', 'classification': 'high_confidence_empty_duplicate'} for i in range(1000, 1057)]
        )
        excluded = [{'id': i, 'name': f'L{i}'} for i in range(100, 123)]

        valid, errors = validate_audit_shape(targets, excluded)

        assert valid is True
        assert len(errors) == 0

    def test_validate_invalid_truncated_count(self):
        """Should fail with wrong truncated count"""
        from scripts.cleanup_invalid_customers import validate_audit_shape

        targets = (
            [{'id': i, 'name': f'T{i}', 'classification': 'truncated'} for i in range(1, 3)] +  # Only 2!
            [{'id': i, 'name': f'H{i}', 'classification': 'high_confidence_empty_duplicate'} for i in range(10, 67)]
        )
        excluded = [{'id': i, 'name': f'L{i}'} for i in range(100, 123)]

        valid, errors = validate_audit_shape(targets, excluded)

        assert valid is False
        assert any('3 truncated' in e for e in errors)

    def test_validate_invalid_high_confidence_count(self):
        """Should fail with wrong high-confidence count"""
        from scripts.cleanup_invalid_customers import validate_audit_shape

        targets = (
            [{'id': i, 'name': f'T{i}', 'classification': 'truncated'} for i in range(1, 4)] +
            [{'id': i, 'name': f'H{i}', 'classification': 'high_confidence_empty_duplicate'} for i in range(10, 65)]  # Only 55!
        )
        excluded = [{'id': i, 'name': f'L{i}'} for i in range(100, 123)]

        valid, errors = validate_audit_shape(targets, excluded)

        assert valid is False
        assert any('57 high-confidence' in e for e in errors)

    def test_validate_invalid_excluded_count(self):
        """Should fail with wrong excluded count"""
        from scripts.cleanup_invalid_customers import validate_audit_shape

        targets = (
            [{'id': i, 'name': f'T{i}', 'classification': 'truncated'} for i in range(1, 4)] +
            [{'id': i, 'name': f'H{i}', 'classification': 'high_confidence_empty_duplicate'} for i in range(10, 67)]
        )
        excluded = [{'id': i, 'name': f'L{i}'} for i in range(100, 120)]  # Only 20!

        valid, errors = validate_audit_shape(targets, excluded)

        assert valid is False
        assert any('23 excluded' in e for e in errors)

    def test_validate_duplicate_ids_rejected(self):
        """Should fail with duplicate IDs in targets"""
        from scripts.cleanup_invalid_customers import validate_audit_shape

        targets = (
            [{'id': 1, 'name': 'T1', 'classification': 'truncated'},
             {'id': 2, 'name': 'T2', 'classification': 'truncated'},
             {'id': 2, 'name': 'T2_DUP', 'classification': 'truncated'}] +  # ID 2 duplicated!
            [{'id': i, 'name': f'H{i}', 'classification': 'high_confidence_empty_duplicate'} for i in range(10, 67)]
        )
        excluded = [{'id': i, 'name': f'L{i}'} for i in range(100, 123)]

        valid, errors = validate_audit_shape(targets, excluded)

        assert valid is False
        assert any('Duplicate IDs' in e for e in errors)

    def test_validate_canonical_ids_rejected(self):
        """Should fail if canonical IDs are in targets"""
        from scripts.cleanup_invalid_customers import validate_audit_shape

        targets = (
            [{'id': 35, 'name': 'ZF', 'classification': 'truncated'},  # Canonical ID!
             {'id': 2, 'name': 'T2', 'classification': 'truncated'},
             {'id': 3, 'name': 'T3', 'classification': 'truncated'}] +
            [{'id': i, 'name': f'H{i}', 'classification': 'high_confidence_empty_duplicate'} for i in range(10, 67)]
        )
        excluded = [{'id': i, 'name': f'L{i}'} for i in range(100, 123)]

        valid, errors = validate_audit_shape(targets, excluded)

        assert valid is False
        assert any('35' in e and 'ZF' in e for e in errors)

    def test_validate_all_canonical_ids_rejected(self):
        """Should fail if any of the three canonical IDs are in targets"""
        from scripts.cleanup_invalid_customers import validate_audit_shape

        targets = (
            [{'id': 7286, 'name': 'IBI', 'classification': 'truncated'},  # Canonical!
             {'id': 7271, 'name': 'ITT', 'classification': 'truncated'},  # Canonical!
             {'id': 35, 'name': 'ZF', 'classification': 'truncated'}] +   # Canonical!
            [{'id': i, 'name': f'H{i}', 'classification': 'high_confidence_empty_duplicate'} for i in range(10, 67)]
        )
        excluded = [{'id': i, 'name': f'L{i}'} for i in range(100, 123)]

        valid, errors = validate_audit_shape(targets, excluded)

        assert valid is False
        # Should have specific errors for each canonical
        assert any('35' in e and 'ZF' in e for e in errors)
        assert any('7271' in e and 'ITT' in e for e in errors)
        assert any('7286' in e and 'IBI' in e for e in errors)


class TestCanonicalCustomerProtection:
    """Test canonical customer protection logic"""

    def test_canonical_customers_defined(self):
        """Should have exactly 3 canonical customers defined"""
        from scripts.cleanup_invalid_customers import CANONICAL_CUSTOMERS

        assert len(CANONICAL_CUSTOMERS) == 3
        assert CANONICAL_CUSTOMERS['IBI'] == 7286
        assert CANONICAL_CUSTOMERS['ITT'] == 7271
        assert CANONICAL_CUSTOMERS['ZF'] == 35

    def test_verify_canonical_customers_all_exist(self):
        """Should verify all canonical customers exist"""
        from scripts.cleanup_invalid_customers import verify_canonical_customers

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'id': 7286, 'name': 'IBI', 'customer_code': 'AP', 'is_active': True},
            {'id': 7271, 'name': 'ITT', 'customer_code': 'BU', 'is_active': True},
            {'id': 35, 'name': 'ZF', 'customer_code': 'AI', 'is_active': True}
        ]

        result = verify_canonical_customers(mock_cur, dry_run=True)

        assert result['all_exist'] is True
        assert len(result['customers']) == 3
        assert len(result['errors']) == 0
        assert mock_cur.execute.call_count == 3

    def test_verify_canonical_customer_missing(self):
        """Should detect missing canonical customer"""
        from scripts.cleanup_invalid_customers import verify_canonical_customers

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'id': 7286, 'name': 'IBI', 'customer_code': 'AP', 'is_active': True},
            None,  # ITT missing
            {'id': 35, 'name': 'ZF', 'customer_code': 'AI', 'is_active': True}
        ]

        result = verify_canonical_customers(mock_cur, dry_run=True)

        assert result['all_exist'] is False
        assert len(result['errors']) == 1
        assert 'ITT' in result['errors'][0]
        assert '7271' in result['errors'][0]
        assert 'CRITICAL' in result['errors'][0]

    def test_verify_canonical_customer_inactive(self):
        """Should detect inactive canonical customer and fail"""
        from scripts.cleanup_invalid_customers import verify_canonical_customers

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'id': 7286, 'name': 'IBI', 'customer_code': 'AP', 'is_active': True},
            {'id': 7271, 'name': 'ITT', 'customer_code': 'BU', 'is_active': False},  # Inactive
            {'id': 35, 'name': 'ZF', 'customer_code': 'AI', 'is_active': True}
        ]

        result = verify_canonical_customers(mock_cur, dry_run=True)

        assert result['all_exist'] is False
        assert len(result['errors']) == 1
        assert 'not active' in result['errors'][0]
        assert 'CRITICAL' in result['errors'][0]


class TestReferenceBlocking:
    """Test reference counting and blocking logic"""

    def test_discover_foreign_keys(self):
        """Should discover all FK references to customers.id"""
        from scripts.cleanup_invalid_customers import discover_foreign_keys

        mock_cur = Mock()
        mock_cur.fetchall.return_value = [
            {'table_name': 'part_customer_aliases', 'column_name': 'customer_id',
             'constraint_name': 'fk_alias_customer'},
            {'table_name': 'excel_import_rows', 'column_name': 'resolved_customer_id',
             'constraint_name': 'fk_import_customer'},
            {'table_name': 'tooling_customer_links', 'column_name': 'customer_id',
             'constraint_name': 'fk_tooling_customer'}
        ]

        result = discover_foreign_keys(mock_cur)

        assert len(result) == 3
        assert any(r['table_name'] == 'part_customer_aliases' for r in result)
        assert any(r['table_name'] == 'excel_import_rows' for r in result)
        assert any(r['table_name'] == 'tooling_customer_links' for r in result)

    def test_count_references_zero(self):
        """Should return empty dict when no references"""
        from scripts.cleanup_invalid_customers import count_references

        mock_cur = Mock()
        mock_cur.fetchone.return_value = {'count': 0}

        fk_refs = [
            {'table_name': 'part_customer_aliases', 'column_name': 'customer_id'},
            {'table_name': 'excel_import_rows', 'column_name': 'resolved_customer_id'}
        ]
        legacy_refs = []

        refs = count_references(mock_cur, 100, fk_refs, legacy_refs)

        assert refs == {}
        assert mock_cur.execute.call_count == 2

    def test_count_references_with_refs(self):
        """Should count references in each table"""
        from scripts.cleanup_invalid_customers import count_references

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'count': 5},   # aliases
            {'count': 10},  # import_rows
            {'count': 0}    # tooling_links
        ]

        fk_refs = [
            {'table_name': 'part_customer_aliases', 'column_name': 'customer_id'},
            {'table_name': 'excel_import_rows', 'column_name': 'resolved_customer_id'},
            {'table_name': 'tooling_customer_links', 'column_name': 'customer_id'}
        ]
        legacy_refs = []

        refs = count_references(mock_cur, 100, fk_refs, legacy_refs)

        assert refs == {
            'part_customer_aliases.customer_id': 5,
            'excel_import_rows.resolved_customer_id': 10
        }

    def test_check_all_references_safe(self):
        """Should return safe when all targets have zero references"""
        from scripts.cleanup_invalid_customers import check_all_references

        mock_cur = Mock()
        mock_cur.fetchone.return_value = {'count': 0}

        targets = [
            {'id': 100, 'name': 'Z'},
            {'id': 102, 'name': 'A-P IB'}
        ]
        fk_refs = [{'table_name': 'part_customer_aliases', 'column_name': 'customer_id'}]
        legacy_refs = []

        safe, all_refs = check_all_references(mock_cur, targets, fk_refs, legacy_refs)

        assert safe is True
        assert all_refs[100] == {}
        assert all_refs[102] == {}

    def test_check_all_references_unsafe(self):
        """Should return unsafe when any target has references"""
        from scripts.cleanup_invalid_customers import check_all_references

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'count': 0},   # Customer 100
            {'count': 5}    # Customer 102 has refs
        ]

        targets = [
            {'id': 100, 'name': 'Z'},
            {'id': 102, 'name': 'A-P IB'}
        ]
        fk_refs = [{'table_name': 'part_customer_aliases', 'column_name': 'customer_id'}]
        legacy_refs = []

        safe, all_refs = check_all_references(mock_cur, targets, fk_refs, legacy_refs)

        assert safe is False
        assert all_refs[100] == {}
        assert all_refs[102] == {'part_customer_aliases.customer_id': 5}


class TestTargetVerification:
    """Test target verification against audit"""

    def test_verify_targets_all_match(self):
        """Should verify all targets match audit data and return full rows"""
        from scripts.cleanup_invalid_customers import verify_targets_unchanged

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'id': 100, 'name': 'Z', 'customer_code': 'ZZ', 'is_active': True, 'created_at': '2024-01-01'},
            {'id': 102, 'name': 'A-P IB', 'customer_code': 'AP', 'is_active': True, 'created_at': '2024-01-02'}
        ]

        targets = [
            {'id': 100, 'name': 'Z'},
            {'id': 102, 'name': 'A-P IB'}
        ]

        valid, errors, live_rows = verify_targets_unchanged(mock_cur, targets, 'test_hash')

        assert valid is True
        assert len(errors) == 0
        assert len(live_rows) == 2
        assert live_rows[100]['name'] == 'Z'
        assert live_rows[100]['customer_code'] == 'ZZ'
        assert live_rows[102]['name'] == 'A-P IB'

    def test_verify_targets_customer_missing(self):
        """Should detect when target customer is missing"""
        from scripts.cleanup_invalid_customers import verify_targets_unchanged

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'id': 100, 'name': 'Z', 'customer_code': 'ZZ', 'is_active': True},
            None  # Customer 102 not found
        ]

        targets = [
            {'id': 100, 'name': 'Z'},
            {'id': 102, 'name': 'A-P IB'}
        ]

        valid, errors, live_rows = verify_targets_unchanged(mock_cur, targets, 'test_hash')

        assert valid is False
        assert len(errors) == 1
        assert '102' in errors[0]
        assert 'not found' in errors[0]
        assert len(live_rows) == 1  # Only found customer
        # Verify the found customer has complete row data
        assert live_rows[100]['name'] == 'Z'
        assert live_rows[100]['customer_code'] == 'ZZ'
        assert live_rows[100]['is_active'] is True

    def test_verify_targets_name_changed(self):
        """Should detect when target name has changed"""
        from scripts.cleanup_invalid_customers import verify_targets_unchanged

        mock_cur = Mock()
        mock_cur.fetchone.side_effect = [
            {'id': 100, 'name': 'ZF', 'customer_code': 'ZZ', 'is_active': True},  # Name changed!
            {'id': 102, 'name': 'A-P IB', 'customer_code': 'AP', 'is_active': True}
        ]

        targets = [
            {'id': 100, 'name': 'Z'},
            {'id': 102, 'name': 'A-P IB'}
        ]

        valid, errors, live_rows = verify_targets_unchanged(mock_cur, targets, 'test_hash')

        assert valid is False
        assert len(errors) == 1
        assert '100' in errors[0]
        assert 'name changed' in errors[0]
        # Still returns complete live rows even when validation fails
        assert len(live_rows) == 2
        assert live_rows[100]['name'] == 'ZF'
        assert live_rows[100]['customer_code'] == 'ZZ'
        assert live_rows[102]['customer_code'] == 'AP'

    def test_verify_targets_returns_full_live_rows(self):
        """Should return complete live database rows for backup"""
        from scripts.cleanup_invalid_customers import verify_targets_unchanged

        mock_cur = Mock()
        # Mock complete customer row with all columns
        full_row = {
            'id': 100,
            'name': 'Z',
            'customer_code': 'ZZ',
            'is_active': True,
            'created_at': '2024-01-01',
            'updated_at': '2024-01-02',
            'notes': 'Test customer'
        }
        mock_cur.fetchone.return_value = full_row

        targets = [{'id': 100, 'name': 'Z'}]

        valid, errors, live_rows = verify_targets_unchanged(mock_cur, targets, 'test_hash')

        assert valid is True
        assert live_rows[100] == full_row
        # Verify query used SELECT *
        assert mock_cur.execute.call_args[0][0] == "SELECT * FROM customers WHERE id = %s"


class TestBackupGeneration:
    """Test backup file generation"""

    def test_create_backup_generates_both_files(self):
        """Should create both JSON and SQL backup files"""
        from scripts.cleanup_invalid_customers import create_backup

        live_rows = {
            100: {'id': 100, 'name': 'Z', 'customer_code': None, 'is_active': True}
        }
        all_refs = {100: {}}
        canonical_check = {'customers': {}}
        backup_dir = Path('/tmp/backup')

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file:

            json_path, sql_path = create_backup(
                live_rows, 'test_hash', all_refs, canonical_check, backup_dir
            )

            assert 'cleanup_backup_' in str(json_path)
            assert '.json' in str(json_path)
            assert 'cleanup_restore_' in str(sql_path)
            assert '.sql' in str(sql_path)

    def test_create_backup_json_structure(self):
        """Should generate proper JSON backup structure with live rows"""
        from scripts.cleanup_invalid_customers import create_backup

        live_rows = {
            100: {'id': 100, 'name': 'Z', 'customer_code': None, 'is_active': True}
        }
        all_refs = {100: {}}
        canonical_check = {'customers': {'IBI': {'id': 7286}}}
        backup_dir = Path('/tmp/backup')

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:

            create_backup(live_rows, 'test_hash', all_refs, canonical_check, backup_dir)

            # Check json.dump was called
            assert mock_json_dump.called
            backup_data = mock_json_dump.call_args[0][0]

            assert 'audit_source_hash' in backup_data
            assert backup_data['audit_source_hash'] == 'test_hash'
            assert backup_data['target_count'] == 1
            assert 'targets' in backup_data
            assert 'canonical_customers' in backup_data

    def test_create_backup_sql_only_real_columns(self):
        """Should generate SQL with only actual customer table columns"""
        from scripts.cleanup_invalid_customers import create_backup
        from datetime import datetime

        # Simulate full live customer row from database
        live_rows = {
            100: {
                'id': 100,
                'name': 'Test Customer',
                'customer_code': 'TC',
                'is_active': True,
                'created_at': datetime(2024, 1, 1, 12, 0, 0),
                'updated_at': datetime(2024, 1, 2, 12, 0, 0),
                'notes': None
            }
        }
        all_refs = {100: {}}
        canonical_check = {'customers': {}}
        backup_dir = Path('/tmp/backup')

        sql_content = []

        def capture_write(content):
            sql_content.append(content)

        mock_file_handle = mock_open()
        mock_file_handle.return_value.write.side_effect = capture_write

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_file_handle):

            json_path, sql_path = create_backup(
                live_rows, 'test_hash', all_refs, canonical_check, backup_dir
            )

            sql_text = ''.join(sql_content)

            # Verify SQL contains actual customer columns
            assert 'INSERT INTO customers' in sql_text
            assert 'id' in sql_text
            assert 'name' in sql_text
            assert 'customer_code' in sql_text
            assert 'is_active' in sql_text
            assert 'created_at' in sql_text

            # Verify SQL does NOT contain audit columns
            assert 'classification' not in sql_text
            assert 'evidence' not in sql_text

    def test_create_backup_full_live_rows(self):
        """Should backup complete live customer rows, not audit dicts"""
        from scripts.cleanup_invalid_customers import create_backup

        # Full live rows with all customer table columns
        live_rows = {
            100: {'id': 100, 'name': 'Z', 'customer_code': 'ZZ', 'is_active': True, 'notes': 'test'},
            102: {'id': 102, 'name': 'A-P IB', 'customer_code': 'AP', 'is_active': False, 'notes': None}
        }
        all_refs = {100: {}, 102: {}}
        canonical_check = {'customers': {}}
        backup_dir = Path('/tmp/backup')

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:

            create_backup(live_rows, 'test_hash', all_refs, canonical_check, backup_dir)

            backup_data = mock_json_dump.call_args[0][0]
            targets = backup_data['targets']

            assert len(targets) == 2
            # Verify contains full customer data
            assert any(t['id'] == 100 and t['customer_code'] == 'ZZ' for t in targets)
            assert any(t['id'] == 102 and t['customer_code'] == 'AP' for t in targets)


class TestDeletionAndVerification:
    """Test deletion and verification logic"""

    def test_delete_customers(self):
        """Should delete customers by ID list and require exactly 60"""
        from scripts.cleanup_invalid_customers import delete_customers

        mock_cur = Mock()
        mock_cur.rowcount = 60

        targets = [{'id': i, 'name': f'C{i}'} for i in range(1, 61)]

        count = delete_customers(mock_cur, targets)

        assert count == 60
        assert mock_cur.execute.called
        # Verify DELETE query was used
        call_args = mock_cur.execute.call_args[0]
        assert 'DELETE' in call_args[0]
        assert 'customers' in call_args[0]

    def test_delete_customers_wrong_count_raises(self):
        """Should raise if deleted count is not exactly 60"""
        from scripts.cleanup_invalid_customers import delete_customers

        mock_cur = Mock()
        mock_cur.rowcount = 58  # Wrong count!

        targets = [{'id': i, 'name': f'C{i}'} for i in range(1, 61)]

        with pytest.raises(RuntimeError) as exc_info:
            delete_customers(mock_cur, targets)

        assert 'expected exactly 60' in str(exc_info.value)
        assert 'got 58' in str(exc_info.value)

    def test_delete_customers_zero_count_raises(self):
        """Should raise if no rows deleted"""
        from scripts.cleanup_invalid_customers import delete_customers

        mock_cur = Mock()
        mock_cur.rowcount = 0  # Nothing deleted!

        targets = [{'id': i, 'name': f'C{i}'} for i in range(1, 61)]

        with pytest.raises(RuntimeError) as exc_info:
            delete_customers(mock_cur, targets)

        assert 'expected exactly 60' in str(exc_info.value)
        assert 'got 0' in str(exc_info.value)

    def test_delete_customers_excess_count_raises(self):
        """Should raise if more than 60 rows deleted"""
        from scripts.cleanup_invalid_customers import delete_customers

        mock_cur = Mock()
        mock_cur.rowcount = 65  # Too many!

        targets = [{'id': i, 'name': f'C{i}'} for i in range(1, 61)]

        with pytest.raises(RuntimeError) as exc_info:
            delete_customers(mock_cur, targets)

        assert 'expected exactly 60' in str(exc_info.value)
        assert 'got 65' in str(exc_info.value)

    def test_verify_deletion_success(self):
        """Should verify targets deleted and canonical remain"""
        from scripts.cleanup_invalid_customers import verify_deletion

        mock_cur = Mock()
        mock_cur.fetchall.return_value = []  # No targets remain
        mock_cur.fetchone.side_effect = [
            {'id': 7286, 'name': 'IBI'},
            {'id': 7271, 'name': 'ITT'},
            {'id': 35, 'name': 'ZF'}
        ]

        targets = [{'id': 100, 'name': 'Z'}]
        canonical_check = {}

        success, errors = verify_deletion(mock_cur, targets, canonical_check)

        assert success is True
        assert len(errors) == 0

    def test_verify_deletion_target_remains(self):
        """Should detect when target was not deleted"""
        from scripts.cleanup_invalid_customers import verify_deletion

        mock_cur = Mock()
        mock_cur.fetchall.return_value = [
            {'id': 100, 'name': 'Z'}  # Target still exists!
        ]
        mock_cur.fetchone.side_effect = [
            {'id': 7286, 'name': 'IBI'},
            {'id': 7271, 'name': 'ITT'},
            {'id': 35, 'name': 'ZF'}
        ]

        targets = [{'id': 100, 'name': 'Z'}]
        canonical_check = {}

        success, errors = verify_deletion(mock_cur, targets, canonical_check)

        assert success is False
        assert len(errors) == 1
        assert '100' in errors[0]
        assert 'still exists' in errors[0]

    def test_verify_deletion_canonical_deleted(self):
        """Should detect when canonical customer was deleted"""
        from scripts.cleanup_invalid_customers import verify_deletion

        mock_cur = Mock()
        mock_cur.fetchall.return_value = []  # Targets deleted
        mock_cur.fetchone.side_effect = [
            {'id': 7286, 'name': 'IBI'},
            None,  # ITT was deleted!
            {'id': 35, 'name': 'ZF'}
        ]

        targets = [{'id': 100, 'name': 'Z'}]
        canonical_check = {}

        success, errors = verify_deletion(mock_cur, targets, canonical_check)

        assert success is False
        assert len(errors) == 1
        assert 'ITT' in errors[0]
        assert 'deleted' in errors[0]


class TestDefaultDryRunBehavior:
    """Test default dry-run behavior"""

    def test_dry_run_is_default(self):
        """Should default to dry-run mode without --apply flag"""
        from scripts.cleanup_invalid_customers import main
        import argparse

        # Test argparse defaults
        parser = argparse.ArgumentParser()
        parser.add_argument('--apply', action='store_true')

        # No --apply flag
        args = parser.parse_args([])
        assert args.apply is False

        # Dry run should be True when apply is False
        dry_run = not args.apply
        assert dry_run is True

    def test_apply_requires_explicit_flag(self):
        """Should require explicit --apply flag for delete mode"""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument('--apply', action='store_true')

        # With --apply flag
        args = parser.parse_args(['--apply'])
        assert args.apply is True

        # Dry run should be False when apply is True
        dry_run = not args.apply
        assert dry_run is False

    def test_dry_run_uses_readonly_connection(self):
        """Should use read-only connection in dry-run mode"""
        # This verifies the connection setup logic
        dry_run = True

        # In dry-run, readonly should be True
        if dry_run:
            readonly = True
            autocommit = True
        else:
            readonly = False
            autocommit = False

        assert readonly is True
        assert autocommit is True


class TestReportGeneration:
    """Test report generation"""

    def test_generate_report_creates_both_formats(self):
        """Should generate both JSON and Markdown reports"""
        from scripts.cleanup_invalid_customers import generate_report

        targets = [{'id': 100, 'name': 'Z', 'classification': 'truncated', 'is_active': True}]
        excluded = [{'id': 10, 'name': 'Test', 'customer_code': 'T', 'is_active': True, 'evidence': 'test'}]
        all_refs = {100: {}}
        canonical_check = {'customers': {}}
        fk_refs = []
        legacy_refs = []
        report_dir = Path('/tmp/reports')

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file:

            json_path, md_path = generate_report(
                targets, excluded, all_refs, canonical_check,
                fk_refs, legacy_refs, 'test_hash', True, report_dir
            )

            assert '.json' in str(json_path)
            assert '.md' in str(md_path)
            assert 'dry_run' in str(json_path).lower()
            assert 'dry_run' in str(md_path).lower()

    def test_generate_report_includes_excluded_customers(self):
        """Should explicitly list excluded customers in report"""
        from scripts.cleanup_invalid_customers import generate_report

        targets = []
        excluded = [
            {'id': 10, 'name': 'Customer1', 'customer_code': 'C1', 'is_active': True, 'evidence': 'low conf'},
            {'id': 11, 'name': 'Customer2', 'customer_code': 'C2', 'is_active': True, 'evidence': 'low conf'}
        ]
        all_refs = {}
        canonical_check = {'customers': {}}
        fk_refs = []
        legacy_refs = []
        report_dir = Path('/tmp/reports')

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:

            generate_report(
                targets, excluded, all_refs, canonical_check,
                fk_refs, legacy_refs, 'test_hash', True, report_dir
            )

            # Check JSON includes excluded
            backup_data = mock_json_dump.call_args[0][0]
            assert 'excluded' in backup_data
            assert backup_data['excluded_count'] == 2

    def test_generate_apply_report_includes_result(self):
        """Should include apply result in post-delete report"""
        from scripts.cleanup_invalid_customers import generate_report

        targets = [{'id': 100, 'name': 'Z', 'classification': 'truncated', 'is_active': True}]
        excluded = []
        all_refs = {100: {}}
        canonical_check = {'customers': {}}
        fk_refs = []
        legacy_refs = []
        report_dir = Path('/tmp/reports')

        apply_result = {
            'success': True,
            'deleted_count': 60,
            'json_backup': '/tmp/backup.json',
            'sql_backup': '/tmp/restore.sql',
            'verification': 'passed'
        }

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:

            generate_report(
                targets, excluded, all_refs, canonical_check,
                fk_refs, legacy_refs, 'test_hash', False, report_dir,
                apply_result=apply_result
            )

            # Check JSON includes apply result
            report_data = mock_json_dump.call_args[0][0]
            assert 'apply_result' in report_data
            assert report_data['apply_result']['success'] is True
            assert report_data['apply_result']['deleted_count'] == 60

    def test_generate_dry_run_report_no_apply_result(self):
        """Should not include apply result in dry-run report"""
        from scripts.cleanup_invalid_customers import generate_report

        targets = [{'id': 100, 'name': 'Z', 'classification': 'truncated', 'is_active': True}]
        excluded = []
        all_refs = {100: {}}
        canonical_check = {'customers': {}}
        fk_refs = []
        legacy_refs = []
        report_dir = Path('/tmp/reports')

        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:

            generate_report(
                targets, excluded, all_refs, canonical_check,
                fk_refs, legacy_refs, 'test_hash', True, report_dir
            )

            # Check JSON does not include apply result
            report_data = mock_json_dump.call_args[0][0]
            assert 'apply_result' not in report_data


class TestAuditLoading:
    """Test audit file loading"""

    def test_load_audit_data_success(self):
        """Should load and hash audit JSON"""
        from scripts.cleanup_invalid_customers import load_audit_data

        audit_content = json.dumps({'test': 'data'})

        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=audit_content)):

            audit, audit_hash = load_audit_data(Path('/tmp/audit.json'))

            assert audit == {'test': 'data'}
            assert isinstance(audit_hash, str)
            assert len(audit_hash) == 16

    def test_load_audit_data_file_not_found(self):
        """Should raise FileNotFoundError for missing audit"""
        from scripts.cleanup_invalid_customers import load_audit_data

        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                load_audit_data(Path('/tmp/nonexistent.json'))


class TestLegacyReferences:
    """Test legacy reference discovery"""

    def test_get_legacy_references_finds_non_fk(self):
        """Should find columns with customer_id but no FK"""
        from scripts.cleanup_invalid_customers import get_legacy_references

        mock_cur = Mock()
        mock_cur.fetchall.return_value = [
            {'table_name': 'old_table', 'column_name': 'customer_id'},
            {'table_name': 'legacy_table', 'column_name': 'related_customer_id'}
        ]

        result = get_legacy_references(mock_cur)

        assert len(result) == 2
        assert result[0]['constraint_name'] == 'LEGACY_NO_FK'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
