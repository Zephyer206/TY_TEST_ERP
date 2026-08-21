"""Read-only comparison report for legacy FMG and gaibo after-sales archives."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_db_context  # noqa: E402
from app.models.after_sales import AfterSalesInstallationKit, AfterSalesKitComponent  # noqa: E402
from app.models.gaibo import (  # noqa: E402
    GaiboChangeLog,
    GaiboDocumentStatus,
    GaiboInstallationPackage,
    GaiboPackageItem,
)


async def build_report() -> dict[str, object]:
    async with get_db_context() as db:
        legacy_count = await db.scalar(
            select(func.count()).select_from(AfterSalesInstallationKit).where(AfterSalesInstallationKit.is_active.is_(True))
        ) or 0
        legacy_components = await db.scalar(
            select(func.count()).select_from(AfterSalesKitComponent)
        ) or 0
        legacy_core_missing = await db.scalar(
            select(func.count()).select_from(AfterSalesInstallationKit).where(
                AfterSalesInstallationKit.is_active.is_(True),
                (AfterSalesInstallationKit.ibi_spec.is_(None) | (func.trim(AfterSalesInstallationKit.ibi_spec) == ""))
                | (AfterSalesInstallationKit.internal_kit_spec.is_(None) | (func.trim(AfterSalesInstallationKit.internal_kit_spec) == "")),
            )
        ) or 0
        gaibo_packages = await db.scalar(
            select(func.count()).select_from(GaiboInstallationPackage).where(GaiboInstallationPackage.is_active.is_(True))
        ) or 0
        gaibo_items = await db.scalar(select(func.count()).select_from(GaiboPackageItem)) or 0
        gaibo_unlinked = await db.scalar(
            select(func.count()).select_from(GaiboPackageItem).where(GaiboPackageItem.match_state == "unlinked")
        ) or 0
        document_rows = (
            await db.execute(select(GaiboDocumentStatus.status, GaiboDocumentStatus.document_type))
        ).all()
        document_status_counts = Counter(row.status for row in document_rows)
        document_type_counts = Counter(row.document_type for row in document_rows)
        package_document_counts = (
            await db.execute(
                select(GaiboDocumentStatus.package_id, func.count())
                .where(GaiboDocumentStatus.package_id.is_not(None))
                .group_by(GaiboDocumentStatus.package_id)
            )
        ).all()
        packages_with_all_documents = sum(1 for _, count in package_document_counts if count >= 3)
        packages_missing_documents = max(int(gaibo_packages) - packages_with_all_documents, 0)
        history_rows = (await db.scalars(select(GaiboChangeLog))).all()
        legacy_history = sum(
            1 for row in history_rows if (row.change_data or {}).get("legacy_change_log_id") is not None
        )
    return {
        "legacy_active_installation_kits": legacy_count,
        "legacy_component_rows": legacy_components,
        "legacy_rows_missing_ibi_or_internal_composition": legacy_core_missing,
        "gaibo_active_packages": gaibo_packages,
        "gaibo_package_items": gaibo_items,
        "gaibo_unlinked_items": gaibo_unlinked,
        "gaibo_document_status_rows": len(document_rows),
        "gaibo_document_status_counts": dict(sorted(document_status_counts.items())),
        "gaibo_document_type_counts": dict(sorted(document_type_counts.items())),
        "gaibo_packages_missing_document_rows": packages_missing_documents,
        "gaibo_change_history_rows": len(history_rows),
        "gaibo_legacy_history_rows": legacy_history,
        "comparison_status": "needs_review" if legacy_core_missing else "ready_for_mapping_review",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    report = asyncio.run(build_report())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
