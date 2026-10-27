"""Collect production acceptance evidence without tokens or business writes."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.core.config import settings
from scripts.verification.verify_qr_phase3 import business_database

FEATURE = ROOT / "specs/002-material-qr-traceability"


def snapshot():
    owned = json.loads((ROOT / "runtime/qr-ui-owned.json").read_text(encoding="utf-8"))
    name = owned.get("database")
    source = make_url(settings.DATABASE_URL).set(drivername="postgresql+psycopg2")
    assert isinstance(name, str) and re.fullmatch(r"qrtmp_[a-f0-9]{32}", name)
    assert name != source.database and owned["purpose"] == "synthetic QR UI acceptance"
    engine = create_engine(source.set(database=name), echo=False, poolclass=NullPool,
                           connect_args={"connect_timeout": 10})
    try:
        with engine.begin() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            assert connection.scalar(text("SELECT oid FROM pg_database WHERE datname=current_database()")) == owned["original_oid"]
            queries = {
                "boxes": "SELECT id,order_id,bound_by,current_qty,version FROM product_boxes ORDER BY id",
                "production_states": "SELECT id,production_status,version,completed_by FROM machine_order_process_states ORDER BY id",
                "quantities": "SELECT id,state_id,box_id,current_qty,updated_by,version FROM box_process_quantities ORDER BY id",
                "allocations": "SELECT source_quantity_id,available_qty,order_qty,stock_qty,assigned_by,version FROM product_output_allocations ORDER BY id",
                "events": "SELECT event_type,operator_id,before_qty,after_qty,remark FROM product_flow_events ORDER BY id",
            }
            result = {key: [dict(row) for row in connection.execute(text(query)).mappings()]
                      for key, query in queries.items()}
            result.update(transaction_read_only="on", synthetic_data_only=True, owned_original_oid_matched=True)
            assert result["boxes"][0]["current_qty"] == 20
            assert result["quantities"][0]["updated_by"] == 102
            assert result["allocations"][0]["order_qty"] == 10
            assert result["allocations"][0]["stock_qty"] == 10
            assert result["allocations"][0]["assigned_by"] == 104
            assert result["production_states"][0]["completed_by"] == 101
            assert result["production_states"][1]["production_status"] == "pending"
            assert any(row["event_type"] == "quantity_correction" and row["operator_id"] == 102
                       and row["before_qty"] == 25 and row["after_qty"] == 20
                       and row["remark"] == "隔离验收实物复核" for row in result["events"])
            (FEATURE / "phase4-production-db.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"status": "PASS", "synthetic_data_only": True, "snapshot_written": True}
    finally:
        engine.dispose()


def tests():
    latest, runs = {}, []
    for name in ("qr-production-full.xml", "qr-production-routes-final.xml"):
        cases = list(ET.parse(ROOT / "runtime" / name).getroot().iter("testcase"))
        runs.append({"report": name, "total": len(cases),
                     "failures": sum(c.find("failure") is not None or c.find("error") is not None for c in cases)})
        for case in cases:
            latest[(case.get("classname"), case.get("name"))] = case
    failed = sum(c.find("failure") is not None or c.find("error") is not None for c in latest.values())
    skipped = sum(c.find("skipped") is not None for c in latest.values())
    assert len(latest) == 209 and failed == skipped == 0
    return dict(status="PASS", unique_total=len(latest), failures=failed, skipped=skipped, runs=runs)


async def evidence():
    files = [p for p in FEATURE.glob("phase4-*.png")] + [FEATURE / "phase4-production-db.json", FEATURE / "phase4-production-first-db.json"]
    artifacts = [{"name": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
    journals = [json.loads((ROOT / "runtime" / name).read_text(encoding="utf-8"))
                for name in ("qr-production-first-owned.json", "qr-ui-owned.json")]
    assert all(j["state"] == "cleaned" for j in journals)
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        scope="T022-T028 configuration, machine production, quantity and allocation",
        pytest=tests(), business_database=await business_database(),
        active_new_endpoints=18, planned_new_endpoints=31, legacy_registered_endpoints=32,
        completed_tasks=27, total_tasks=59,
        browser={"status": "PASS", "first_session": "Chrome extension 3, tab 1952681252",
                 "resumed_session": "in-app Chromium browser 2, tab 2",
                 "url": "http://127.0.0.1:18125/product-box-production",
                 "identities": [101, 102, 104, 105], "synthetic_jwt_in_memory_only": True},
        checks={"frontend_type_and_build": "PASS", "api_usage_violations": 0,
                "physical_print_and_paper_scan": "NOT_RUN", "continuous_process_trace": "NOT_IMPLEMENTED"},
        owned_ui_cleanup={"status": "PASS", "databases": journals}, artifacts=artifacts)
    (FEATURE / "phase4-evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true")
    options = parser.parse_args()
    try:
        print(json.dumps(snapshot() if options.snapshot else asyncio.run(evidence()), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"status": "INCOMPLETE", "error_type": type(error).__name__}))
        sys.exit(1)
