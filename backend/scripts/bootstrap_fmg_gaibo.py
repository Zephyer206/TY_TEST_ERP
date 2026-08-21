"""Create the approved FMG Mexico customer workspace and import legacy kits.

This is intentionally idempotent: it creates the customer only when absent,
reuses the gaibo workspace by slug, and delegates row mapping to the existing
non-destructive legacy importer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_db_context  # noqa: E402
from app.models.customer import Customer  # noqa: E402
from scripts.import_after_sales_gaibo import import_workspace  # noqa: E402


async def ensure_customer(name: str, dry_run: bool) -> tuple[int | None, bool]:
    async with get_db_context() as db:
        customer = await db.scalar(select(Customer).where(Customer.name == name))
        if customer is not None:
            return customer.id, False
        if dry_run:
            return None, True
        customer = Customer(name=name, short_name=name)
        db.add(customer)
        await db.flush()
        return customer.id, True


async def main_async(args: argparse.Namespace) -> dict[str, object]:
    customer_id, customer_created = await ensure_customer(args.customer_name, args.dry_run)
    if args.dry_run:
        report = await import_workspace(customer_id or 0, args.slug, args.display_name, dry_run=True)
        report["customer_name"] = args.customer_name
        report["customer_would_be_created"] = customer_created
        report["dry_run"] = True
        return report
    assert customer_id is not None
    report = await import_workspace(customer_id, args.slug, args.display_name, dry_run=False)
    report["customer_id"] = customer_id
    report["customer_created"] = customer_created
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customer-name", default="FMG 墨西哥")
    parser.add_argument("--slug", default="fmg-mexico")
    parser.add_argument("--display-name", default="FMG 墨西哥")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(main_async(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
