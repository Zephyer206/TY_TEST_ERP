"""Customer code synchronization service."""

from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import logging

from app.models.customer import Customer

logger = logging.getLogger(__name__)


class CustomerCodeSyncService:
    """Service to sync customer codes from '客户名称代号' sheet."""

    async def sync_customer_codes(
        self,
        db: AsyncSession,
        customer_code_sheet_data: List[Dict[str, str]]
    ) -> Tuple[int, int, List[str]]:
        """Sync customer codes from Excel sheet to customers table.

        Args:
            db: Database session
            customer_code_sheet_data: List of dicts with keys:
                - 'customer_name': Customer name
                - 'customer_code': Customer code (A, AA, BG, etc.)

        Returns:
            Tuple of (updated_count, skipped_count, error_messages)
        """
        updated_count = 0
        skipped_count = 0
        errors = []

        # Build mapping from sheet
        code_mapping = {}
        for row in customer_code_sheet_data:
            name = row.get('customer_name', '').strip()
            code = row.get('customer_code', '').strip()

            if not name or not code:
                continue

            # Check for duplicate codes
            if code in code_mapping.values():
                existing_name = [k for k, v in code_mapping.items() if v == code][0]
                errors.append(
                    f"重复的客户代号: {code} 用于 {existing_name} 和 {name}"
                )
                continue

            code_mapping[name] = code

        logger.info(f"Loaded {len(code_mapping)} customer codes from sheet")

        # Query all customers
        result = await db.execute(select(Customer))
        customers = result.scalars().all()

        # Update customer codes
        for customer in customers:
            # Try exact name match first
            code = code_mapping.get(customer.name)

            # Try short_name match if exists
            if not code and customer.short_name:
                code = code_mapping.get(customer.short_name)

            # Try fuzzy match (contains)
            if not code:
                for sheet_name, sheet_code in code_mapping.items():
                    if sheet_name in customer.name or customer.name in sheet_name:
                        code = sheet_code
                        logger.info(
                            f"Fuzzy match: '{customer.name}' matched with '{sheet_name}'"
                        )
                        break

            if code:
                # Check if customer already has this code
                if customer.customer_code == code:
                    skipped_count += 1
                    logger.debug(f"Customer {customer.name} already has code {code}")
                    continue

                # Update customer code
                customer.customer_code = code
                updated_count += 1
                logger.info(
                    f"Updated customer {customer.name}: customer_code = {code}"
                )
            else:
                errors.append(
                    f"未找到客户代号: {customer.name} (ID: {customer.id})"
                )

        # Commit changes
        await db.commit()

        logger.info(
            f"Customer code sync completed: {updated_count} updated, "
            f"{skipped_count} skipped, {len(errors)} errors"
        )

        return updated_count, skipped_count, errors

    def parse_customer_code_sheet(
        self,
        sheet_rows: List[List]
    ) -> List[Dict[str, str]]:
        """Parse customer code sheet data.

        Expected format:
        - First row or first few rows may contain headers
        - Data rows contain: [customer_name, customer_code, ...]

        Args:
            sheet_rows: List of rows from Excel sheet

        Returns:
            List of dicts with 'customer_name' and 'customer_code'
        """
        data = []
        header_found = False

        for row in sheet_rows:
            if not row or len(row) < 2:
                continue

            # Skip empty rows
            if not row[0] or not row[1]:
                continue

            # Convert to strings
            cell0 = str(row[0]).strip()
            cell1 = str(row[1]).strip()

            # Skip header rows
            if not header_found:
                if '客户名称' in cell0 or '代号' in cell1 or 'Customer' in cell0:
                    header_found = True
                    continue

            # Parse data row
            data.append({
                'customer_name': cell0,
                'customer_code': cell1,
            })

        return data

    async def validate_customer_codes(
        self,
        db: AsyncSession
    ) -> List[str]:
        """Validate customer codes in database.

        Returns:
            List of validation errors/warnings
        """
        errors = []

        # Query all customers
        result = await db.execute(select(Customer))
        customers = result.scalars().all()

        # Check for missing customer codes
        missing_codes = [
            c for c in customers if not c.customer_code and c.is_active
        ]
        if missing_codes:
            errors.append(
                f"{len(missing_codes)} 个活跃客户缺少客户代号: "
                f"{', '.join(c.name for c in missing_codes[:5])}"
                + ("..." if len(missing_codes) > 5 else "")
            )

        # Check for duplicate customer codes
        code_counts = {}
        for customer in customers:
            if customer.customer_code:
                code_counts[customer.customer_code] = code_counts.get(
                    customer.customer_code, 0
                ) + 1

        duplicates = {code: count for code, count in code_counts.items() if count > 1}
        if duplicates:
            errors.append(
                f"发现重复的客户代号: {', '.join(f'{code}(x{count})' for code, count in duplicates.items())}"
            )

        return errors
