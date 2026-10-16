"""Remove draft shipping orders untouched for seven days.

Use --dry-run first. Submitted, shipped, and cancelled records are never selected.
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import get_db_context  # noqa: E402
from app.services.shipping_order_service import cleanup_drafts  # noqa: E402


async def main(dry_run: bool) -> int:
    async with get_db_context() as db:
        ids = await cleanup_drafts(db, dry_run=dry_run)
    print(f"{'would remove' if dry_run else 'removed'} {len(ids)} draft shipping orders")
    if ids:
        print("ids=" + ",".join(str(item) for item in ids))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
