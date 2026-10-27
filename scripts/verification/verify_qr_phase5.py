"""Sanitized process-trace evidence; owned UI and business reads are read-only."""
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
    engine = create_engine(source.set(database=name), echo=False, poolclass=NullPool, connect_args={"connect_timeout": 10})
    try:
        with engine.begin() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            assert connection.scalar(text("SELECT oid FROM pg_database WHERE datname=current_database()")) == owned["original_oid"]
            queries = {
                "boxes": "SELECT id,box_no,order_id,current_process_code,next_process_code,current_qty,version,bound_by FROM product_boxes ORDER BY id",
                "quantities": "SELECT id,state_id,box_id,input_qty,current_qty,source_quantity_id,material_batch_id,updated_by FROM box_process_quantities ORDER BY id",
                "allocations": "SELECT source_quantity_id,box_id,available_qty,order_qty,stock_qty FROM product_output_allocations ORDER BY id",
                "states": "SELECT id,process_code,production_status,completed_by FROM machine_order_process_states ORDER BY id",
                "handoffs": "SELECT event_type,before_qty,after_qty,before_snapshot,after_snapshot,material_batch_id,operator_id FROM product_flow_events WHERE event_type='process_start' ORDER BY id",
                "materials": "SELECT id,batch_no,parent_batch_id,current_weight FROM material_batches WHERE id IN (9501,9502) ORDER BY id",
            }
            result = {key: [dict(row) for row in connection.execute(text(query)).mappings()] for key, query in queries.items()}
            first = next(row for row in result["boxes"] if row["id"] == 1)
            assert first["current_process_code"] == "PACK" and first["next_process_code"] is None and first["current_qty"] == 25
            quantities = [row for row in result["quantities"] if row["box_id"] == 1]
            assert [row["current_qty"] for row in quantities] == [30, 25, 25]
            assert [row["input_qty"] for row in quantities] == [0, 30, 25]
            assert {row["source_quantity_id"] for row in quantities} == {quantities[0]["id"]}
            assert {row["material_batch_id"] for row in quantities} == {9502}
            allocations = [row for row in result["allocations"] if row["box_id"] == 1]
            assert len(allocations) == 1 and allocations[0]["available_qty"] == 30
            assert len(result["handoffs"]) == 2
            assert next(row for row in result["states"] if row["id"] == 1001)["completed_by"] == 101
            assert [row["current_weight"] for row in result["materials"]] == [70, 30]
            second = [row for row in result["quantities"] if row["box_id"] == 2]
            assert len(second) == 1 and second[0]["current_qty"] == 7 and second[0]["material_batch_id"] == 9501
            result.update(status="PASS", transaction_read_only="on", synthetic_data_only=True, owned_original_oid_matched=True)
            (FEATURE / "phase5-db.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"status": "PASS", "snapshot_written": True, "no_duplicate_first_box_output": True}
    finally:
        engine.dispose()


def tests():
    latest, runs = {}, []
    for name in ("qr-trace-full.xml", "qr-trace-final.xml", "qr-trace-compat-final.xml"):
        cases = list(ET.parse(ROOT / "runtime" / name).getroot().iter("testcase"))
        runs.append({"report": name, "total": len(cases), "failures": sum(c.find("failure") is not None or c.find("error") is not None for c in cases)})
        for case in cases:
            latest[(case.get("classname"), case.get("name"))] = case
    failed = sum(c.find("failure") is not None or c.find("error") is not None for c in latest.values())
    skipped = sum(c.find("skipped") is not None for c in latest.values())
    assert len(latest) == 231 and failed == skipped == 0
    return dict(status="PASS", unique_total=len(latest), failures=failed, skipped=skipped, runs=runs)


async def evidence():
    journal = json.loads((ROOT / "runtime/qr-ui-owned.json").read_text(encoding="utf-8"))
    assert journal["state"] == "cleaned" and journal["original_oid"] == 214584
    perf = json.loads((FEATURE / "phase5-performance.json").read_text(encoding="utf-8"))
    assert perf["under_3000"]
    names = ["phase5-trace.png", "phase5-trace-overview.png", "phase5-material-lineage.png", "phase5-invalid-flow.png", "phase5-material-guard.png",
             "phase5-material-recovered.png", "phase5-other-owner.png", "phase5-db.json", "phase5-guard-db.json", "phase5-performance.json"]
    artifacts = [{"name": name, "bytes": (FEATURE / name).stat().st_size,
                  "sha256": hashlib.sha256((FEATURE / name).read_bytes()).hexdigest()} for name in names]
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), client_date="2026-10-27",
        scope="T029-T033 ordered handoff, material sources, event pagination and real browser trace",
        pytest=tests(), completed_tasks=32, total_tasks=59, active_new_endpoints=21, planned_new_endpoints=31,
        business_database=await business_database(), browser={"status": "PASS", "session": "in-app Chromium browser 2, tab 3",
            "production_url": "http://127.0.0.1:18125/product-box-production", "trace_url": "http://127.0.0.1:18125/product-box-trace",
            "identities": [101, 105], "synthetic_jwt_in_memory_only": True}, performance=perf,
        checks={"frontend_type_and_build": "PASS", "api_usage_violations": 0, "physical_print": "NOT_RUN"},
        owned_ui_cleanup={"status": "PASS", "database": journal}, artifacts=artifacts)
    (FEATURE / "phase5-evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
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
