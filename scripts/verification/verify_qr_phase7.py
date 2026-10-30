"""Read-only evidence for state-scoped exceptions and durable in-app delivery."""
import asyncio
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

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
    source = make_url(settings.DATABASE_URL).set(drivername="postgresql+psycopg2")
    name = owned.get("database")
    assert re.fullmatch(r"qrtmp_[a-f0-9]{32}", name or "") and name != source.database
    assert owned["purpose"] == "synthetic QR UI acceptance" and owned["state"] == "active"
    engine = create_engine(source.set(database=name), echo=False, poolclass=NullPool)
    try:
        with engine.begin() as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            assert db.scalar(text("SELECT oid FROM pg_database WHERE datname=current_database()")) == owned["original_oid"]
            queries = {
                "boxes": "SELECT id,order_id,current_qty,bound_by FROM product_boxes ORDER BY id",
                "quantities": "SELECT box_id,state_id,current_qty,source_quantity_id,id,material_batch_id,updated_by FROM box_process_quantities ORDER BY id",
                "allocations": "SELECT box_id,available_qty,order_qty,stock_qty FROM product_output_allocations ORDER BY id",
                "exceptions": "SELECT id,order_id,state_id,status,resolution,expected_spec,actual_spec,confirmed_by,released_by,rechecked_material_batch_id,resume_reason FROM coil_spec_exceptions ORDER BY id",
                "groups": "SELECT exception_id,group_type,resolution_status,recipient_ids FROM exception_recipient_groups ORDER BY id",
                "deliveries": "SELECT id,exception_id,recipient_user_id,status,attempts,retry_batch,last_error FROM notification_outbox ORDER BY id",
                "tasks": "SELECT id,outbox_id,recipient_user_id FROM qr_notifications ORDER BY id",
                "attempts": "SELECT outbox_id,retry_batch,attempt_no,result,safe_error_code FROM qr_notification_attempts ORDER BY id",
                "materials": "SELECT id,current_weight FROM material_batches WHERE id IN (9501,9502,9503) ORDER BY id",
                "latencies": "SELECT extract(epoch FROM o.sent_at-e.created_at)::float AS seconds FROM notification_outbox o JOIN coil_spec_exceptions e ON e.id=o.exception_id WHERE e.order_id=401 ORDER BY o.id",
            }
            result = {key: [dict(r) for r in db.execute(text(query)).mappings()] for key, query in queries.items()}
            assert [r["current_qty"] for r in result["boxes"]] == [12, 5, 7]
            assert {r["order_id"] for r in result["boxes"]} == {401}
            assert [r["material_batch_id"] for r in result["quantities"]] == [9502, 9503, 9501]
            assert all(r["source_quantity_id"] == r["id"] and r["updated_by"] == 101 for r in result["quantities"])
            assert sum(r["available_qty"] for r in result["allocations"]) == 24
            assert all(r["available_qty"] == r["order_qty"] and r["stock_qty"] == 0 for r in result["allocations"])
            first, accepted, resumed = result["exceptions"]
            assert first["order_id"] == 402 and first["status"] == "pending_confirmation" and first["confirmed_by"] is None
            assert accepted["resolution"] == "accept_continue" and accepted["confirmed_by"] == 104
            assert resumed["resolution"] == "pause" and resumed["confirmed_by"] == resumed["released_by"] == 104
            assert resumed["rechecked_material_batch_id"] == 9501
            assert len(result["groups"]) == 6 and all(g["resolution_status"] == "resolved" for g in result["groups"])
            assert len(result["deliveries"]) == 6 and len(result["tasks"]) == 5 and len(result["attempts"]) == 15
            assert len({r["outbox_id"] for r in result["tasks"]}) == 5
            failed = [r for r in result["deliveries"] if r["status"] == "failed"]
            assert len(failed) == 1 and failed[0]["attempts"] == 5
            retried = [r for r in result["deliveries"] if r["retry_batch"] == 1]
            assert len(retried) == 1 and retried[0]["status"] == "sent" and retried[0]["attempts"] == 1
            assert len([r for r in result["attempts"] if r["outbox_id"] == retried[0]["id"]]) == 6
            assert [r["current_weight"] for r in result["materials"]] == [70, 30, 20]
            assert len(result["latencies"]) == 4 and all(0 <= r["seconds"] <= 60 for r in result["latencies"])
            assert db.scalar(text("SELECT count(*) FROM product_flow_events WHERE event_type='process_start'")) == 0
            preview = json.loads((ROOT / "runtime/qr-exceptions-preview.json").read_text(encoding="utf-8-sig"))
            guard = json.loads((ROOT / "runtime/qr-exceptions-pause-guard.json").read_text(encoding="utf-8-sig"))
            assert len(preview["exceptions"]) == 1 and preview["boxes"][0]["current_qty"] == 0
            assert sum(b["current_qty"] for b in guard["boxes"]) == 17
            result.update(status="PASS", transaction_read_only="on", owned_original_oid=owned["original_oid"],
                preview_no_mutation=True, paused_handoff_no_mutation=True, synthetic_data_only=True,
                fault_fixture="Order 402 failures replayed using the real dispatch service and a synthetic past clock; not elapsed retry time")
            (FEATURE / "phase7-db.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            return {"status": "PASS", "quantity": 24, "exceptions": 3, "durable_tasks": 5,
                    "normal_delivery_seconds": [r["seconds"] for r in result["latencies"]]}
    finally:
        engine.dispose()


async def evidence():
    owned = json.loads((ROOT / "runtime/qr-ui-owned.json").read_text(encoding="utf-8"))
    data = json.loads((FEATURE / "phase7-db.json").read_text(encoding="utf-8"))
    assert owned["state"] == "cleaned" and owned["original_oid"] == data["owned_original_oid"]
    cases = list(ET.parse(ROOT / "runtime/qr-exceptions-full.xml").getroot().iter("testcase"))
    assert len(cases) == 306 and all(c.find("failure") is None and c.find("error") is None and c.find("skipped") is None for c in cases)
    baseline = await business_database()
    assert baseline["status"] == "PASS"
    paths = sorted(FEATURE.glob("phase7-*.png")) + [FEATURE / "phase7-db.json", FEATURE / "phase7-browser.json"]
    checks = json.loads((ROOT / "runtime/qr-exceptions-checks.json").read_text(encoding="utf-8"))
    assert all(checks[k] == "PASS" for k in ("build", "api_usage", "design", "diff"))
    browser = json.loads((FEATURE / "phase7-browser.json").read_text(encoding="utf-8"))
    assert browser["status"] == "PASS" and len(browser["checks"]) == 16
    assert all(check["status"] == "PASS" for check in browser["checks"])
    for port in (18124, 18125):
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(("127.0.0.1", port)) != 0
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(), client_date="2026-10-28", completed_tasks=43,
        total_tasks=59, active_new_endpoints=28, planned_new_endpoints=31, implementation_status="PASS", acceptance_status="PASS",
        pytest={"unique_total": len(cases), "failures": 0, "skipped": 0, "report": "runtime/qr-exceptions-full.xml"},
        business_database=baseline, checks=checks, owned_ui_cleanup=owned,
        browser=browser, owned_service_ports={"18124": "STOPPED", "18125": "STOPPED"},
        artifacts=[dict(name=p.name, bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
    (FEATURE / "phase7-evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "PASS", "unique_tests": len(cases), "completed_tasks": 43, "business_database": baseline["status"]}


if __name__ == "__main__":
    try:
        print(json.dumps(snapshot() if "--snapshot" in sys.argv else asyncio.run(evidence())))
    except Exception as error:
        print(json.dumps({"status": "INCOMPLETE", "error_type": type(error).__name__}))
        raise SystemExit(1)
