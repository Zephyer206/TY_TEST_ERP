"""Collect sanitized QR workspace evidence; never operates the browser.

The browser observations are recorded independently in the acceptance documents.
This script reads test XML, screenshots and owned-cleanup evidence and performs
only a read-only transaction against the configured business database.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.product_box import DOMAIN_TABLES


def tests():
    latest, runs = {}, []
    for name in ("qr-phase3-tests.xml", "qr-phase3-material-final.xml"):
        cases = list(ET.parse(ROOT / "runtime" / name).getroot().iter("testcase"))
        failures = sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
        runs.append({"report": name, "total": len(cases), "failures": failures})
        for case in cases:
            latest[(case.get("classname"), case.get("name"))] = case
    cases = list(latest.values())
    failed = sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
    skipped = sum(c.find("skipped") is not None for c in cases)
    return {"unique_total": len(cases), "failures": failed, "skipped": skipped,
            "runs": runs, "status": "PASS" if len(cases) == 128 and failed == skipped == 0 else "INCOMPLETE"}


async def business_database():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool,
                                 connect_args={"timeout": 10, "command_timeout": 20})
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            names = [table.name for table in DOMAIN_TABLES]
            statement = text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                             "AND table_name IN :names").bindparams(bindparam("names", expanding=True))
            result = {
                "transaction_read_only": await connection.scalar(text("SHOW transaction_read_only")),
                "migration_versions": list((await connection.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))).scalars()),
                "new_domain_tables_checked": len(names),
                "new_domain_tables_present": await connection.scalar(statement, {"names": names}),
                "legacy_qr_enum_label_count": await connection.scalar(text("SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid WHERE t.typname IN ('scantype','scanoperation')")),
                "remaining_temporary_database_count": await connection.scalar(text("SELECT count(*) FROM pg_database WHERE datname ~ '^qrtmp_[a-f0-9]{32}$'")),
                "auth_disabled": settings.AUTH_DISABLED, "business_writes": 0,
            }
            result["status"] = "PASS" if (result["transaction_read_only"] == "on"
                and result["migration_versions"] == ["20261020_ppap"]
                and result["new_domain_tables_checked"] == 23 and result["new_domain_tables_present"] == 0
                and result["legacy_qr_enum_label_count"] == 9) else "INCOMPLETE"
            result["historical_temporary_cleanup"] = {
                "status": "PASS" if result["remaining_temporary_database_count"] == 0 else "INCOMPLETE",
                "unowned_residue_deleted": False,
                "reason": "Historical residue has no original creation name/OID ownership proof; prefix matching is insufficient",
            }
            return result
    except Exception as error:
        return {"status": "INCOMPLETE", "error_type": type(error).__name__, "business_writes": 0}
    finally:
        await engine.dispose()


def artifacts():
    names = ("phase3-workspace.png", "phase3-print-preview.png", "phase3-material.png",
             "phase3-material-old-date.png", "phase3-material-old-date.pdf", "phase3-label-proof.pdf",
             "phase3-metadata-recovery.png", "phase3-metadata-recovery-db.json", "phase3-product-db.json", "phase3-material-db.json")
    result = []
    for name in names:
        path = ROOT / "specs/002-material-qr-traceability" / name
        data = path.read_bytes()
        result.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return result


async def main():
    journal = json.loads((ROOT / "runtime/qr-ui-owned.json").read_text(encoding="utf-8-sig"))
    evidence = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "T012 legacy registry, T014 material UI, T020 product QR workspace; T021 incomplete",
        "pytest": tests(), "business_database": await business_database(),
        "active_new_endpoints": 11, "planned_new_endpoints": 31, "legacy_registered_endpoints": 32,
        "completed_tasks": 20, "total_tasks": 59,
        "browser": {
            "session": "Chrome extension browser 3; synthetic JWT and owned disposable PostgreSQL databases",
            "material_tab": "1952680422", "material_url": "http://127.0.0.1:18125/material-qr",
            "product_url": "http://127.0.0.1:18125/product-box-qr",
            "material_ui": "PASS", "product_workspace_ui": "PASS", "metadata_error_recovery": "PASS",
            "record_type": "Independent observed browser acceptance; this script does not control a browser",
            "system_print_dialog": "NOT_RUN", "physical_print_and_scanner": "NOT_RUN",
            "full_scan_to_binding_duration": "NOT_MEASURED",
        },
        "software_printing": {"format": "A4", "labels": 500, "pages": 24, "last_page_labels": 17,
            "synthetic_confirmation_items": 500, "physical_success_inferred": False},
        "checks": {"frontend_type_check": "PASS", "frontend_build": "PASS", "api_usage_violations": 0,
            "legacy_wrapper_endpoints": 32, "extra_wrapper_checks": 4, "design_consistency": "PASS",
            "design_script_scope": "Static consistency only; its NOT_RUN runtime/browser fields do not override separately observed UI evidence"},
        "owned_ui_database_cleanup": {"state": journal["state"], "original_oid_recorded": isinstance(journal.get("original_oid"), int)},
        "lifecycle_observations": {"owned_runs": [
            {"purpose": "500-product workspace", "original_oid": 99128, "cleanup": "matched original ownership journal, exported summary, cleaned"},
            {"purpose": "material workspace", "original_oid": 150370, "cleanup": "graceful shutdown, journal cleaned"},
            {"purpose": "metadata error recovery", "original_oid": 151678, "cleanup": "graceful shutdown, journal cleaned"}],
            "dedicated_ports_stopped": [18124, 18125], "normal_ports_preserved": [8000, 5173]},
        "business_migration_applied": False, "real_account_grants_changed": False,
        "artifacts": artifacts(),
    }
    output = ROOT / "specs/002-material-qr-traceability/phase3-evidence.json"
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output.relative_to(ROOT)), "tests": evidence["pytest"],
                      "business_database": evidence["business_database"],
                      "owned_ui_cleanup": evidence["owned_ui_database_cleanup"]}, ensure_ascii=True))
    return 0 if evidence["pytest"]["status"] == evidence["business_database"]["status"] == "PASS" and journal["state"] == "cleaned" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
