"""Read-only split evidence for the exact journalled synthetic database."""
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
    source = make_url(settings.DATABASE_URL).set(drivername="postgresql+psycopg2")
    name = owned.get("database")
    assert isinstance(name, str) and re.fullmatch(r"qrtmp_[a-f0-9]{32}", name)
    assert name != source.database and owned["purpose"] == "synthetic QR UI acceptance" and owned["state"] == "active"
    engine = create_engine(source.set(database=name), echo=False, poolclass=NullPool, connect_args={"connect_timeout": 10})
    try:
        with engine.begin() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            assert connection.scalar(text("SELECT oid FROM pg_database WHERE datname=current_database()")) == owned["original_oid"]
            queries = {
                "boxes": "SELECT id,qr_pool_item_id,box_no,order_id,order_product_id,current_process_code,next_process_code,current_qty,lifecycle_status,version,bound_by FROM product_boxes ORDER BY id",
                "quantities": "SELECT id,state_id,box_id,input_qty,current_qty,source_quantity_id,material_batch_id,updated_by FROM box_process_quantities ORDER BY id",
                "allocations": "SELECT id,source_quantity_id,box_id,available_qty,order_qty,stock_qty,origin_allocation_id,version FROM product_output_allocations ORDER BY id",
                "relations": "SELECT parent_box_id,child_box_id,relation_type,source_order_id,target_order_id,quantity,order_qty,stock_qty,source_snapshot,created_by FROM product_box_relations ORDER BY id",
                "split_events": "SELECT product_box_id,event_type,before_qty,after_qty,operator_id FROM product_flow_events WHERE event_type IN ('split','cross_order_split') ORDER BY id",
                "materials": "SELECT id,parent_batch_id,current_weight FROM material_batches WHERE id IN (9501,9502) ORDER BY id",
                "pool": "SELECT id,pool_status FROM product_qr_pool_items ORDER BY id",
            }
            result = {key: [dict(row) for row in connection.execute(text(query)).mappings()] for key, query in queries.items()}
            boxes = {row["id"]: row for row in result["boxes"]}
            assert len(boxes) == 5 and [boxes[i]["current_qty"] for i in range(1, 6)] == [40, 30, 0, 20, 10]
            assert [boxes[i]["order_id"] for i in range(1, 6)] == [401, 401, 401, 403, 401]
            assert boxes[3]["lifecycle_status"] == "empty"
            assert boxes[1]["current_process_code"] == boxes[2]["current_process_code"] == "FINISH"
            assert sum(row["current_qty"] for row in result["boxes"]) == 100
            assert len(result["allocations"]) == 5 and sum(row["available_qty"] for row in result["allocations"]) == 100
            allocations = {row["box_id"]: row for row in result["allocations"]}
            for identity, allocation in allocations.items():
                assert allocation["available_qty"] == allocation["order_qty"] == boxes[identity]["current_qty"] and allocation["stock_qty"] == 0
            assert [allocations[i]["origin_allocation_id"] for i in range(1, 6)] == [None, allocations[1]["id"], allocations[1]["id"], allocations[1]["id"], allocations[3]["id"]]
            roots = [row for row in result["quantities"] if row["id"] == row["source_quantity_id"]]
            assert len(roots) == 5 and sum(row["current_qty"] for row in roots) == 100
            assert len(result["quantities"]) == 7 and {row["material_batch_id"] for row in result["quantities"]} == {9502}
            later = [row for row in result["quantities"] if row["id"] != row["source_quantity_id"]]
            assert sorted(row["input_qty"] for row in later) == [30, 40]
            assert len(result["relations"]) == 4 and len(result["split_events"]) == 8
            assert result["relations"][0]["source_snapshot"]["current_qty"] == 100
            assert [row["created_by"] for row in result["relations"]] == [103, 103, 102, 103]
            assert [row["current_weight"] for row in result["materials"]] == [70, 30]
            assert sum(row["pool_status"] == "bound" for row in result["pool"]) == 5
            cancelled = json.loads((ROOT / "runtime/qr-split-cancel.json").read_text(encoding="utf-8-sig"))
            assert len(cancelled["boxes"]) == 1 and cancelled["boxes"][0]["current_qty"] == 100
            assert cancelled["pool_items"][1]["pool_status"] == "unused"
            result.update(status="PASS", transaction_read_only="on", owned_original_oid=owned["original_oid"],
                          synthetic_data_only=True, physical_quantity=100, effective_output=100, source_order_use=80, target_order_use=20,
                          cancel_no_mutation="PASS", material_weight_unchanged="PASS")
            (FEATURE / "phase6-db.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            return {"status": "PASS", "physical_quantity": 100, "effective_output": 100, "relations": 4}
    finally:
        engine.dispose()


def tests():
    latest, runs = {}, []
    for name in ("qr-split-related.xml", "qr-split-full.xml"):
        cases = list(ET.parse(ROOT / "runtime" / name).getroot().iter("testcase"))
        runs.append({"report": name, "total": len(cases), "sha256": hashlib.sha256((ROOT / "runtime" / name).read_bytes()).hexdigest(),
                     "failures": sum(c.find("failure") is not None or c.find("error") is not None for c in cases)})
        for case in cases:
            latest[(case.get("classname"), case.get("name"))] = case
    failures = sum(c.find("failure") is not None or c.find("error") is not None for c in latest.values())
    skipped = sum(c.find("skipped") is not None for c in latest.values())
    assert len(latest) == 272 and failures == skipped == 0
    return dict(status="PASS", unique_total=len(latest), failures=failures, skipped=skipped, runs=runs)


async def evidence():
    owned = json.loads((ROOT / "runtime/qr-ui-owned.json").read_text(encoding="utf-8"))
    db = json.loads((FEATURE / "phase6-db.json").read_text(encoding="utf-8"))
    assert owned["state"] == "cleaned" and owned["original_oid"] == db["owned_original_oid"] and db["status"] == "PASS"
    names = ["phase6-split-confirm.png", "phase6-cross-confirm.png", "phase6-zero-trace.png", "phase6-zero-handoff.png",
             "phase6-source-readonly.png", "phase6-parent-child-handoff.png", "phase6-other-owner.png",
             "phase6-split-overview.png", "phase6-child-trace.png", "phase6-owner-preview.png", "phase6-db.json", "phase6-browser.json"]
    artifacts = [{"name": name, "bytes": (FEATURE / name).stat().st_size,
                  "sha256": hashlib.sha256((FEATURE / name).read_bytes()).hexdigest()} for name in names]
    checks = json.loads((ROOT / "runtime/qr-split-checks.json").read_text(encoding="utf-8"))
    assert checks["api_usage_violations"] == 0 and checks["frontend_build"] == checks["design"] == checks["diff_check"] == "PASS"
    browser = json.loads((FEATURE / "phase6-browser.json").read_text(encoding="utf-8"))
    assert browser["status"] == "PASS"
    baseline = await business_database()
    assert baseline["status"] == "PASS"
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), client_date="2026-10-27",
        scope="T034-T038 same/cross order split, quantity conservation, ancestry, zero and continued production",
        completed_tasks=37, total_tasks=59, active_new_endpoints=22, planned_new_endpoints=31,
        implementation_status="PASS", acceptance_status="PASS",
        pytest=tests(), business_database=baseline, browser=browser, checks=checks,
        owned_ui_cleanup={"status": "PASS", "database": owned}, artifacts=artifacts)
    (FEATURE / "phase6-evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true")
    options = parser.parse_args()
    try:
        result = snapshot() if options.snapshot else asyncio.run(evidence())
        print(json.dumps(result if options.snapshot else {"status": "PASS", "completed_tasks": result["completed_tasks"],
            "unique_tests": result["pytest"]["unique_total"], "browser": result["browser"]["status"],
            "owned_ui_cleanup": result["owned_ui_cleanup"]["status"], "business_database": result["business_database"]["status"],
            "historical_cleanup": result["business_database"]["historical_temporary_cleanup"]["status"]}))
    except Exception as error:
        print(json.dumps({"status": "INCOMPLETE", "error_type": type(error).__name__}))
        sys.exit(1)
