"""Backup and deactivate invalid customer records.

This script:
1. Backs up customers 90 and 105 with timestamp
2. Verifies they have zero business references
3. Sets is_active=false (does NOT delete)
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_context
from app.models.customer import Customer


async def verify_no_references(db: AsyncSession, customer_id: int) -> dict:
    """Verify customer has no business references."""

    # Check part_customer_aliases
    aliases = await db.execute(
        text("SELECT COUNT(*) FROM part_customer_aliases WHERE customer_id = :id"),
        {"id": customer_id}
    )
    aliases_count = aliases.scalar()

    # Check tooling_customer_links
    tooling = await db.execute(
        text("SELECT COUNT(*) FROM tooling_customer_links WHERE customer_id = :id"),
        {"id": customer_id}
    )
    tooling_count = tooling.scalar()

    # Check quotes
    quotes = await db.execute(
        text("SELECT COUNT(*) FROM quotes WHERE customer_id = :id"),
        {"id": customer_id}
    )
    quotes_count = quotes.scalar()

    # Check customer_prices (table may not exist yet)
    prices_count = 0
    try:
        # Check if table exists first
        table_check = await db.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'customer_prices')")
        )
        if table_check.scalar():
            prices = await db.execute(
                text("SELECT COUNT(*) FROM customer_prices WHERE customer_id = :id"),
                {"id": customer_id}
            )
            prices_count = prices.scalar()
    except Exception:
        pass

    return {
        "customer_id": customer_id,
        "part_customer_aliases": aliases_count,
        "tooling_customer_links": tooling_count,
        "quotes": quotes_count,
        "customer_prices": prices_count,
        "total_references": aliases_count + tooling_count + quotes_count + prices_count
    }


async def backup_customer(db: AsyncSession, customer_id: int) -> dict:
    """Backup customer data to dict."""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    return {
        "id": customer.id,
        "name": customer.name,
        "customer_code": customer.customer_code,
        "short_name": customer.short_name,
        "contact_person": customer.contact_person,
        "contact_phone": customer.contact_phone,
        "contact_email": customer.contact_email,
        "address": customer.address,
        "is_active": customer.is_active,
        "sheet_key": customer.sheet_key,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
    }


async def main():
    """Main execution."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = Path(__file__).parent / "backups" / f"customers_backup_{timestamp}.json"

    backup_file.parent.mkdir(parents=True, exist_ok=True)

    async with get_db_context() as db:
        try:
            print("=" * 60)
            print("Customer Backup and Deactivation Script")
            print("=" * 60)

            # Target customers
            target_ids = [90, 105]

            backup_data = {
                "timestamp": timestamp,
                "customers": [],
                "references_check": [],
                "operations": []
            }

            # Step 1: Backup and verify
            print("\nStep 1: Backing up and verifying customers...")
            for customer_id in target_ids:
                print(f"\nCustomer {customer_id}:")

                # Backup
                customer_data = await backup_customer(db, customer_id)
                backup_data["customers"].append(customer_data)
                print(f"  Name: {customer_data['name']}")
                print(f"  Code: {customer_data['customer_code']}")
                print(f"  Active: {customer_data['is_active']}")

                # Verify references
                refs = await verify_no_references(db, customer_id)
                backup_data["references_check"].append(refs)
                print(f"  Business references:")
                print(f"    - part_customer_aliases: {refs['part_customer_aliases']}")
                print(f"    - tooling_customer_links: {refs['tooling_customer_links']}")
                print(f"    - quotes: {refs['quotes']}")
                print(f"    - customer_prices: {refs['customer_prices']}")
                print(f"    - TOTAL: {refs['total_references']}")

                if refs['total_references'] > 0:
                    print(f"  WARNING: Customer {customer_id} has {refs['total_references']} business references!")

            # Save backup
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            print(f"\nBackup saved to: {backup_file}")

            # Step 2: Check if safe to proceed
            total_refs = sum(r['total_references'] for r in backup_data['references_check'])
            if total_refs > 0:
                print(f"\nABORTED: Found {total_refs} total business references.")
                print("Cannot proceed with deactivation.")
                return

            # Step 3: Deactivate
            print("\nStep 2: Deactivating customers...")
            print("Proceed? (y/n): ", end="")
            response = input().strip().lower()

            if response != 'y':
                print("Aborted by user.")
                return

            for customer_id in target_ids:
                customer = await db.get(Customer, customer_id)
                if customer:
                    old_active = customer.is_active
                    customer.is_active = False
                    backup_data["operations"].append({
                        "customer_id": customer_id,
                        "name": customer.name,
                        "old_is_active": old_active,
                        "new_is_active": False
                    })
                    print(f"  Customer {customer_id} ({customer.name}): is_active = False")

            await db.commit()

            # Update backup with operations
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            print("\nCustomers deactivated successfully.")
            print(f"Operations logged to: {backup_file}")

            # Step 4: Verify
            print("\nStep 3: Verifying final state...")
            for customer_id in target_ids:
                customer = await db.get(Customer, customer_id)
                print(f"  Customer {customer_id}: is_active = {customer.is_active}")

            print("\n" + "=" * 60)
            print("COMPLETED SUCCESSFULLY")
            print("=" * 60)

        except Exception as e:
            print(f"\nERROR: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
