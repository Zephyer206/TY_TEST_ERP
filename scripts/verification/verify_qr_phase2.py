"""Sanitized Phase 2 evidence: QR smoke, isolated test results and read-only DB.

Does not migrate the business database, change accounts, or read/print secrets.
Run after the disposable browser server and pytest fixtures have shut down.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from scripts.verification.inspect_qr_phase0 import inspect_api_contracts, inspect_qr_helpers


async def database():
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool,
                                 connect_args={"timeout": 10, "command_timeout": 20})
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            result = {"transaction_read_only": await connection.scalar(text("SHOW transaction_read_only")),
                      "migration_versions": list((await connection.execute(text(
                          "SELECT version_num FROM alembic_version ORDER BY version_num"))).scalars()),
                      "new_domain_tables_present": await connection.scalar(text(
                          "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                          "AND table_name IN ('product_boxes','product_qr_pool_items','qr_capability_grants')")),
                      "legacy_qr_enum_label_count": await connection.scalar(text(
                          "SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid "
                          "WHERE t.typname IN ('scantype','scanoperation')")),
                      "remaining_temporary_database_count": await connection.scalar(text(
                          "SELECT count(*) FROM pg_database WHERE datname ~ '^qrtmp_[a-f0-9]{32}$'")),
                      "auth_disabled": settings.AUTH_DISABLED, "business_writes": 0}
            result["status"] = "PASS" if (result["transaction_read_only"] == "on"
                and result["migration_versions"] == ["20261020_ppap"]
                and result["new_domain_tables_present"] == 0
                and result["legacy_qr_enum_label_count"] == 9) else "INCOMPLETE"
            result["temporary_database_cleanup"] = {
                "status": "PASS" if result["remaining_temporary_database_count"] == 0 else "INCOMPLETE",
                "policy": "Only delete with the original creation name/OID proof; do not infer ownership from a prefix",
                "unowned_residue_deleted": False}
            return result
    except Exception as error:
        return {"status": "INCOMPLETE", "error_type": type(error).__name__, "business_writes": 0}
    finally:
        await engine.dispose()


def tests():
    latest = {}
    runs = []
    for report in ("qr-phase2-tests.xml", "qr-phase2-api-final.xml"):
        cases = list(ET.parse(ROOT / "runtime" / report).getroot().iter("testcase"))
        runs.append({"report": report, "total": len(cases),
                     "failures": sum(case.find("failure") is not None or case.find("error") is not None for case in cases)})
        for case in cases:
            latest[(case.get("classname"), case.get("name"))] = case
    cases = list(latest.values())
    failed = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    return {"total": len(cases), "failures": failed, "skipped": skipped, "runs": runs,
            "status": "PASS" if cases and failed == skipped == 0 else "INCOMPLETE"}


async def main():
    helpers = inspect_qr_helpers()
    api = await inspect_api_contracts([])
    proof = ROOT / "specs/002-material-qr-traceability/phase2-browser.png"
    result = {"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "scope": "backend pool/print/bind and actual client wrapper; product UI/physical printing pending",
              "pytest": tests(), "legacy_helpers": helpers, "legacy_invalid_api_checks": api["checks"],
              "business_database": await database(),
              "browser": {"session": "ChatGPT in-app browser (IAB), browser id 2, tab 2",
                  "url": "http://127.0.0.1:18123/acceptance", "status": "PASS", "checks_passed": 7,
                  "evidence": "phase2-browser.png", "sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
                  "record_type": "observed browser run recorded with screenshot; this evidence script does not operate a browser",
                  "product_pages": "NOT_RUN", "system_print_dialog": "NOT_RUN", "physical_label_scan": "NOT_RUN",
                  "authentication": "synthetic users, real JWT, owned disposable database"},
              "active_new_endpoints": 9, "planned_new_endpoints": 31,
              "business_migration_applied": False, "real_account_grants_changed": False}
    output = ROOT / "specs/002-material-qr-traceability/phase2-evidence.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if (result["pytest"]["status"] == result["business_database"]["status"] == "PASS"
        and all(check["status"] == "PASS" for check in helpers + api["checks"])) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
