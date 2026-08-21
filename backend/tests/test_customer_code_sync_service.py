"""Tests for customer code sync service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.customer_code_sync_service import CustomerCodeSyncService


class TestCustomerCodeSyncService:
    """Test customer code synchronization."""

    def setup_method(self):
        self.service = CustomerCodeSyncService()

    def test_parse_customer_code_sheet(self):
        """Test parsing customer code sheet."""
        sheet_rows = [
            ['客户名称', '代号'],
            ['ZF公司', 'ZF'],
            ['IBI公司', 'IBI'],
            ['ITT公司', 'ITT'],
            ['', ''],  # Empty row should be skipped
        ]

        data = self.service.parse_customer_code_sheet(sheet_rows)

        assert len(data) == 3
        assert data[0] == {'customer_name': 'ZF公司', 'customer_code': 'ZF'}
        assert data[1] == {'customer_name': 'IBI公司', 'customer_code': 'IBI'}
        assert data[2] == {'customer_name': 'ITT公司', 'customer_code': 'ITT'}

    def test_parse_customer_code_sheet_without_header(self):
        """Test parsing when sheet starts directly with data."""
        sheet_rows = [
            ['ZF公司', 'ZF'],
            ['IBI公司', 'IBI'],
        ]

        data = self.service.parse_customer_code_sheet(sheet_rows)

        assert len(data) == 2
        assert data[0]['customer_name'] == 'ZF公司'

    @pytest.mark.asyncio
    async def test_sync_customer_codes(self, db: AsyncSession):
        """Test customer code synchronization.

        Note: This requires a test database with customers table.
        """
        # This is a placeholder - actual test would need database setup
        pass

    @pytest.mark.asyncio
    async def test_validate_customer_codes(self, db: AsyncSession):
        """Test customer code validation.

        Note: This requires a test database with customers table.
        """
        # This is a placeholder - actual test would need database setup
        pass
