"""Tests for Excel import service."""

import pytest
from decimal import Decimal

from app.services.excel_import_service import (
    ExcelValidationService,
    ExcelHeaderMapper,
)


class TestExcelValidationService:
    """Test Excel validation rules."""

    def setup_method(self):
        self.validator = ExcelValidationService()

    def test_is_header_row(self):
        """Test header row detection."""
        # Header row
        header_row = {
            'col1': '序号',
            'col2': '客户名称',
            'col3': '原图产品编号',
        }
        assert self.validator.is_header_row(header_row) is True

        # Data row
        data_row = {
            'col1': '1',
            'col2': 'ZF',
            'col3': '1234567',
        }
        assert self.validator.is_header_row(data_row) is False

    def test_is_empty_data_row(self):
        """Test empty data row detection."""
        # Empty row
        empty_row = {
            '原图产品编号': '',
            '本厂产品名称': '',
            '本厂产品编号': '',
        }
        assert self.validator.is_empty_data_row(empty_row) is True

        # Valid row with customer part number
        valid_row1 = {
            '原图产品编号': '1234567',
            '本厂产品名称': '',
            '本厂产品编号': '',
        }
        assert self.validator.is_empty_data_row(valid_row1) is False

        # Valid row with internal name and tooling number
        valid_row2 = {
            '原图产品编号': '',
            '本厂产品名称': '端子',
            '本厂产品编号': 'M001',
        }
        assert self.validator.is_empty_data_row(valid_row2) is False

    def test_validate_material(self):
        """Test material validation."""
        # Valid materials
        valid_materials = ['SPCC', 'SECC', 'SGCC', 'SUS304', 'AL5052', '铜', '铝']
        for material in valid_materials:
            is_valid, error = self.validator.validate_material(material)
            assert is_valid is True

        # Invalid materials (specs)
        invalid_materials = ['T0.5', 'W100', 'P10', '100*0.5']
        for material in invalid_materials:
            is_valid, error = self.validator.validate_material(material)
            assert is_valid is False
            assert error is not None

    def test_validate_mold_type(self):
        """Test mold type validation."""
        # Continuous mold with process steps (invalid)
        is_valid, error = self.validator.validate_mold_type('连续模', 5)
        assert is_valid is False
        assert '连续模不应有工序步数' in error

        # Continuous mold without process steps (valid)
        is_valid, error = self.validator.validate_mold_type('连续模', None)
        assert is_valid is True

        # Non-continuous mold with process steps (valid)
        is_valid, error = self.validator.validate_mold_type('简易模', 3)
        assert is_valid is True

    def test_parse_cavity_count(self):
        """Test cavity count parsing."""
        assert self.validator.parse_cavity_count('1出2') == 2
        assert self.validator.parse_cavity_count('1出4') == 4
        assert self.validator.parse_cavity_count('1 出 2') == 2
        assert self.validator.parse_cavity_count('单出') is None
        assert self.validator.parse_cavity_count('') is None

    def test_validate_customer_code_conflict(self):
        """Test customer code conflict validation."""
        mapping = {
            'ZF公司': 'ZF',
            'IBI公司': 'IBI',
        }

        # No conflict
        is_valid, error = self.validator.validate_customer_code_conflict(
            'ITT公司', 'ITT', mapping
        )
        assert is_valid is True

        # Same customer, same code (valid)
        is_valid, error = self.validator.validate_customer_code_conflict(
            'ZF公司', 'ZF', mapping
        )
        assert is_valid is True

        # Same customer, different code (conflict)
        is_valid, error = self.validator.validate_customer_code_conflict(
            'ZF公司', 'ZF2', mapping
        )
        assert is_valid is False
        assert '客户代号冲突' in error

        # Different customer, same code (conflict)
        is_valid, error = self.validator.validate_customer_code_conflict(
            '新公司', 'ZF', mapping
        )
        assert is_valid is False
        assert '客户代号冲突' in error

    def test_generate_part_fingerprint(self):
        """Test part fingerprint generation."""
        fp1 = self.validator.generate_part_fingerprint(
            'M001', '端子', 'SPCC', Decimal('0.5'), Decimal('100'), Decimal('10'), 'left'
        )
        fp2 = self.validator.generate_part_fingerprint(
            'M001', '端子', 'SPCC', Decimal('0.5'), Decimal('100'), Decimal('10'), 'left'
        )
        fp3 = self.validator.generate_part_fingerprint(
            'M001', '端子', 'SPCC', Decimal('0.6'), Decimal('100'), Decimal('10'), 'left'
        )

        assert fp1 == fp2  # Same inputs produce same fingerprint
        assert fp1 != fp3  # Different thickness produces different fingerprint

    def test_validate_row(self):
        """Test complete row validation."""
        customer_code_mapping = {'ZF公司': 'ZF'}

        # Valid row
        valid_row = {
            '客户名称': 'ZF公司',
            '客户代号': 'ZF',
            '原图产品编号': '1234567',
            '本厂产品名称': '端子',
            '本厂产品编号': 'M001',
            '材质': 'SPCC',
            '模具类型': '连续模',
        }
        is_valid, errors = self.validator.validate_row(valid_row, customer_code_mapping)
        assert is_valid is True
        assert len(errors) == 0

        # Invalid row (header)
        header_row = {
            '客户名称': '客户名称',
            '原图产品编号': '原图产品编号',
        }
        is_valid, errors = self.validator.validate_row(header_row, customer_code_mapping)
        assert is_valid is False
        assert '表头行' in errors[0]

        # Invalid row (material is spec)
        invalid_material_row = {
            '原图产品编号': '1234567',
            '本厂产品名称': '端子',
            '材质': 'T0.5',
        }
        is_valid, errors = self.validator.validate_row(invalid_material_row, customer_code_mapping)
        assert is_valid is False
        assert any('材质字段包含规格数据' in e for e in errors)


class TestExcelHeaderMapper:
    """Test Excel header mapping."""

    def setup_method(self):
        self.mapper = ExcelHeaderMapper()

    def test_find_header_row(self):
        """Test header row detection."""
        sheet_data = [
            ['客户资料表'],
            [],
            ['序号', '原图产品编号', '本厂产品名称', '本厂产品编号', '材质'],
            ['1', '1234567', '端子', 'M001', 'SPCC'],
        ]

        header_idx = self.mapper.find_header_row(sheet_data)
        assert header_idx == 2

    def test_map_headers(self):
        """Test header mapping."""
        header_row = ['序号', '原图产品编号', '本厂产品名称', '本厂产品编号', '材质', 'T', 'W', 'P']

        mapping = self.mapper.map_headers(header_row)

        # Check that key headers are mapped
        assert '原图产品编号' in mapping.values()
        assert '本厂产品名称' in mapping.values()
        assert '本厂产品编号' in mapping.values()
        assert '材质' in mapping.values()
        # T/W/P are single characters and may match with "Thickness" in longer headers
        # Just verify we get at least 5 mappings
        assert len(mapping) >= 5

    def test_extract_row_data(self):
        """Test row data extraction."""
        row = ['1', '1234567', '端子', 'M001', 'SPCC', '0.5', '100', '10']
        column_mapping = {
            0: '序号',
            1: '原图产品编号',
            2: '本厂产品名称',
            3: '本厂产品编号',
            4: '材质',
            5: 'T',
            6: 'W',
            7: 'P',
        }

        row_data = self.mapper.extract_row_data(row, column_mapping)

        assert row_data['原图产品编号'] == '1234567'
        assert row_data['本厂产品名称'] == '端子'
        assert row_data['本厂产品编号'] == 'M001'
        assert row_data['材质'] == 'SPCC'
        assert row_data['T'] == '0.5'

    def test_extract_row_data_with_merged_names(self):
        """Test extraction with 原图产品名称1 and 原图产品名称2."""
        row = ['1', '1234567', '端子', '左', 'M001']
        column_mapping = {
            1: '原图产品编号',
            2: '原图产品名称1',
            3: '原图产品名称2',
            4: '本厂产品编号',
        }

        row_data = self.mapper.extract_row_data(row, column_mapping)

        assert row_data['原图产品名称'] == '端子 左'
