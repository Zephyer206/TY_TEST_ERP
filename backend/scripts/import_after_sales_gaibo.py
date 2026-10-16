"""Copy legacy FMG installation kits into the customer-first gaibo archive.

The command is intentionally explicit about the customer workspace. It is
idempotent for package numbers and reports rows that cannot be mapped without
guessing. It does not delete or modify legacy records.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_db_context  # noqa: E402
from app.models.after_sales import AfterSalesInstallationKit  # noqa: E402
from app.models.gaibo import (  # noqa: E402
    GaiboChangeLog,
    GaiboCustomerWorkspace,
    GaiboDocumentStatus,
    GaiboInstallationPackage,
    GaiboPackageItem,
)
from app.services.after_sales_document_events import parse_legacy_status_event  # noqa: E402


LEGACY_DOCUMENT_FIELDS = (
    ("drawing_status", "drawing"),
    ("sample_status", "sample"),
    ("ppap_status", "ppap"),
)


def legacy_price_evidence(kit: AfterSalesInstallationKit) -> dict[str, object]:
    """Retain the Excel price comparison without replacing the editable price.

    ``price`` remains the FCA TIANYUE Plant Price+TTOP value chosen for the
    gaibo record. The FMG comparison is import evidence only: it drives the
    red mismatch marker and keeps the original Excel distinction auditable.
    """
    legacy_source = kit.source_data or {}
    fca_price = legacy_source.get("tianyue_plant_price")
    if fca_price is None and kit.price is not None:
        fca_price = str(kit.price)
    def decimal_or_none(value: object | None) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value)).quantize(Decimal("0.0001"))
        except (InvalidOperation, ValueError):
            return None

    fca_decimal = decimal_or_none(fca_price)
    fmg_price = legacy_source.get("fmg_price")
    fmg_decimal = decimal_or_none(fmg_price)

    return {
        "fca_tianyue_plant_price_ttop_usd": fca_price,
        "fmg_price_usd": fmg_price,
        "source_difference": legacy_source.get("difference"),
        # Only two parseable source prices can establish a discrepancy.  The
        # legacy flag is evidence, not the business rule for the new archive.
        "price_mismatch": bool(
            fca_decimal is not None and fmg_decimal is not None and fca_decimal != fmg_decimal
        ),
    }


def normalize_legacy_document_status(raw_value: str | None) -> str:
    """Map Excel wording to the controlled status enum without inventing dates.

    The source workbook contains yearless date fragments. They stay in the
    document remark/source data; only an explicit conclusion becomes ``ok``.
    """
    raw = (raw_value or "").strip()
    if not raw:
        return "not_started"
    lowered = raw.casefold().replace("_", " ").replace("-", " ")
    if any(token in lowered for token in ("not ok", "not pass", "rejected", "failed", "不通过")):
        return "not_ok"
    if any(token in lowered for token in ("n/a", "not applicable", "不适用")):
        return "not_applicable"
    # Submission and estimate wording means work is moving, not approved.
    if any(token in lowered for token in ("send date", "sent date", "re sent", "resend", "submitted", "estimated", "预计")):
        return "in_progress"
    if any(token in lowered for token in (" ok", "ok", "approved", "approval", "通过")):
        return "ok"
    return "in_progress"


def legacy_document_payload(kit: AfterSalesInstallationKit, source_field: str, document_type: str) -> dict[str, Any]:
    raw = (getattr(kit, source_field) or "").strip() or None
    source_data = {
        "legacy_import": "after_sales_gaibo_v2",
        "legacy_kit_id": kit.id,
        "legacy_field": source_field,
        "legacy_raw_status": raw,
        "date_precision": "source_text_only_year_missing" if raw and ":" in raw else "not_applicable",
        "source_file_name": kit.source_file_name,
        "source_sheet": kit.source_sheet,
        "source_row": kit.source_row,
        "status_events": parse_legacy_status_event(raw, document_type),
    }
    return {
        "document_type": document_type,
        "status": normalize_legacy_document_status(raw),
        "submitted_at": None,
        "concluded_at": None,
        "remark": f"Excel 原始状态：{raw}" if raw else "Excel 未填写状态，待人工确认",
        "source_data": source_data,
    }


async def sync_legacy_documents(
    db,
    *,
    package: GaiboInstallationPackage,
    kit: AfterSalesInstallationKit,
    dry_run: bool,
    report: dict[str, object],
) -> None:
    """Create/update only importer-owned package documents.

    A later user edit has no ``legacy_import`` marker and is therefore never
    overwritten by a repeat import.
    """
    for source_field, document_type in LEGACY_DOCUMENT_FIELDS:
        payload = legacy_document_payload(kit, source_field, document_type)
        if dry_run:
            report["documents_created"] = int(report.get("documents_created", 0)) + 1
            continue
        document = await db.scalar(
            select(GaiboDocumentStatus).where(
                GaiboDocumentStatus.package_id == package.id,
                GaiboDocumentStatus.document_type == document_type,
            )
        )
        if document is None:
            db.add(GaiboDocumentStatus(package_id=package.id, **payload))
            report["documents_created"] = int(report.get("documents_created", 0)) + 1
        elif (document.source_data or {}).get("legacy_import"):
            previous_source = dict(document.source_data or {})
            incoming_source = dict(payload.get("source_data") or {})
            previous_events = previous_source.get("status_events") if isinstance(previous_source.get("status_events"), list) else []
            incoming_events = incoming_source.get("status_events") if isinstance(incoming_source.get("status_events"), list) else []
            merged_events = list(previous_events)
            for event in incoming_events:
                if event not in merged_events:
                    merged_events.append(event)
            incoming_source["status_events"] = merged_events
            payload["source_data"] = incoming_source
            changed = any(getattr(document, field) != value for field, value in payload.items())
            if changed:
                for field, value in payload.items():
                    setattr(document, field, value)
                report["documents_updated"] = int(report.get("documents_updated", 0)) + 1
            else:
                report["documents_existing"] = int(report.get("documents_existing", 0)) + 1
        else:
            report["documents_existing"] = int(report.get("documents_existing", 0)) + 1


async def sync_legacy_history(
    db,
    *,
    workspace_id: int,
    package: GaiboInstallationPackage,
    kit: AfterSalesInstallationKit,
    dry_run: bool,
    report: dict[str, object],
) -> None:
    """Copy legacy audit rows once, retaining their original timestamps."""
    if dry_run:
        report["history_created"] = int(report.get("history_created", 0)) + len(kit.change_logs)
        return
    existing_rows = (
        await db.scalars(
            select(GaiboChangeLog).where(
                GaiboChangeLog.workspace_id == workspace_id,
                GaiboChangeLog.entity_type == "package",
                GaiboChangeLog.entity_id == package.id,
            )
        )
    ).all()
    existing_ids = {
        str((row.change_data or {}).get("legacy_change_log_id"))
        for row in existing_rows
        if (row.change_data or {}).get("legacy_change_log_id") is not None
    }
    for legacy_row in kit.change_logs:
        if str(legacy_row.id) in existing_ids:
            report["history_existing"] = int(report.get("history_existing", 0)) + 1
            continue
        db.add(
            GaiboChangeLog(
                workspace_id=workspace_id,
                entity_type="package",
                entity_id=package.id,
                action=f"legacy_{legacy_row.action}",
                changed_fields=legacy_row.changed_fields or [],
                change_data={
                    "legacy_change_log_id": legacy_row.id,
                    "legacy_action": legacy_row.action,
                    "legacy_change_data": legacy_row.change_data or {},
                    "legacy_source_file_name": legacy_row.source_file_name,
                },
                summary=legacy_row.summary,
                actor_user_id=legacy_row.actor_user_id,
                created_at=legacy_row.created_at,
            )
        )
        report["history_created"] = int(report.get("history_created", 0)) + 1


async def import_workspace(customer_id: int, slug: str, display_name: str, dry_run: bool) -> dict[str, object]:
    report: dict[str, object] = {
        "workspace": {"customer_id": customer_id, "slug": slug, "display_name": display_name},
        "packages_created": 0,
        "packages_existing": 0,
        "items_created": 0,
        "documents_created": 0,
        "documents_updated": 0,
        "documents_existing": 0,
        "history_created": 0,
        "history_existing": 0,
        "package_source_evidence_updated": 0,
        "unresolved": [],
    }
    unresolved: list[dict[str, object]] = report["unresolved"]  # type: ignore[assignment]
    async with get_db_context() as db:
        workspace = await db.scalar(select(GaiboCustomerWorkspace).where(GaiboCustomerWorkspace.slug == slug))
        if workspace is None:
            if dry_run:
                workspace = GaiboCustomerWorkspace(customer_id=customer_id, slug=slug, display_name=display_name)
            else:
                workspace = GaiboCustomerWorkspace(customer_id=customer_id, slug=slug, display_name=display_name)
                db.add(workspace)
                await db.flush()

        result = await db.execute(
            select(AfterSalesInstallationKit)
            .where(AfterSalesInstallationKit.is_active.is_(True))
            .options(selectinload(AfterSalesInstallationKit.components))
            .options(selectinload(AfterSalesInstallationKit.change_logs))
            .order_by(AfterSalesInstallationKit.source_item_no.asc().nullslast())
        )
        for kit in result.scalars():
            package = await db.scalar(
                select(GaiboInstallationPackage).where(
                    GaiboInstallationPackage.workspace_id == workspace.id,
                    GaiboInstallationPackage.package_number == kit.fmg_code,
                )
            )
            if package is None:
                package = GaiboInstallationPackage(
                    workspace_id=workspace.id,
                    package_number=kit.fmg_code,
                    name=kit.description,
                    price=kit.price,
                    currency=kit.currency,
                    remark=kit.remark,
                    source_data={
                        "legacy_kit_id": kit.id,
                        "source_file_name": kit.source_file_name,
                        "source_sheet": kit.source_sheet,
                        "source_row": kit.source_row,
                        "legacy_pricing": legacy_price_evidence(kit),
                    },
                )
                if not dry_run:
                    db.add(package)
                    await db.flush()
                report["packages_created"] = int(report["packages_created"]) + 1
            else:
                report["packages_existing"] = int(report["packages_existing"]) + 1
                source_data = dict(package.source_data or {})
                pricing = legacy_price_evidence(kit)
                if source_data.get("legacy_pricing") != pricing:
                    # Import evidence is not a business edit. Preserve the timestamp
                    # shown in the working list so operators do not see a false update.
                    business_updated_at = package.updated_at
                    source_data["legacy_pricing"] = pricing
                    if not dry_run:
                        package.source_data = source_data
                        package.updated_at = business_updated_at
                    report["package_source_evidence_updated"] = int(report["package_source_evidence_updated"]) + 1

            await sync_legacy_documents(
                db,
                package=package,
                kit=kit,
                dry_run=dry_run,
                report=report,
            )
            await sync_legacy_history(
                db,
                workspace_id=workspace.id or 0,
                package=package,
                kit=kit,
                dry_run=dry_run,
                report=report,
            )

            by_kind: dict[str, dict[int, object]] = defaultdict(dict)
            for component in kit.components:
                by_kind[component.source_kind][component.sequence] = component
            for sequence in sorted(set(by_kind["ibi"]) | set(by_kind["internal"])):
                ibi = by_kind["ibi"].get(sequence)
                internal = by_kind["internal"].get(sequence)
                if internal is None or not getattr(internal, "raw_text", None):
                    unresolved.append({"fmg_code": kit.fmg_code, "sequence": sequence, "reason": "IBI/internal composition cannot be paired"})
                    continue
                if dry_run:
                    report["items_created"] = int(report["items_created"]) + 1
                    continue
                existing_item = await db.scalar(
                    select(GaiboPackageItem).where(
                        GaiboPackageItem.package_id == package.id,
                        GaiboPackageItem.sequence == sequence,
                    )
                )
                if existing_item is None:
                    db.add(
                        GaiboPackageItem(
                            package_id=package.id,
                            ibi=ibi.raw_text if ibi is not None and getattr(ibi, "raw_text", None) else None,
                            tianyue_internal_composition=internal.raw_text,
                            quantity=(
                                (ibi.quantity if ibi is not None else None)
                                or internal.quantity
                                or Decimal("1")
                            ),
                            sequence=sequence,
                            match_state=(
                                "unlinked"
                                if ibi is not None and getattr(ibi, "raw_text", None)
                                else "missing_ibi"
                            ),
                            unlinked_customer_part_number=(
                                ibi.part_number
                                if ibi is not None and getattr(ibi, "raw_text", None)
                                else None
                            ),
                        )
                    )
                    report["items_created"] = int(report["items_created"]) + 1
        if dry_run:
            await db.rollback()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customer-id", required=True, type=int)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(import_workspace(args.customer_id, args.slug, args.display_name, args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
