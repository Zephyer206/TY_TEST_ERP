"""Legacy QR inventory must remain registered, mounted and callable via one client.

Runs the actual frontend wrappers/request builder against a memory transport,
then compares all 32 frozen routes with the real application route contracts.
No database fixture, lifespan, HTTP server or external uploader is invoked.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.main import app

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def legacy_client_contract():
    node = shutil.which("node")
    assert node, "Node.js is required for the actual TypeScript wrapper contract check"
    result = subprocess.run(
        [node, str(ROOT / "scripts/verification/verify_legacy_qr_registry.mjs")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(result.stdout)


def test_legacy_qr_inventory_matches_actual_mounted_routes(legacy_client_contract):
    paths = app.openapi()["paths"]
    endpoints = legacy_client_contract["endpoints"]
    assert len(endpoints) == 32
    assert len({row["key"] for row in endpoints}) == 32
    for row in endpoints:
        operation = paths["/api/v1" + row["path"]][row["method"].lower()]
        assert operation.get("security"), row["id"]
        success = [response for code, response in operation["responses"].items() if code.startswith("2")]
        assert len(success) == 1, row["id"]
        assert success[0]["content"]["application/json"]["schema"], row["id"]


def test_legacy_post_query_parameters_remain_query_contracts(legacy_client_contract):
    """Avoid silently moving the two legacy POST query contracts into JSON bodies."""
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/machines/{machine_id}/scan": {"scan_type", "action", "fault_reason"},
        "/api/v1/production/sessions/verify-material": {"machine_id", "part_id", "material_batch_id"},
    }
    for path, query_names in expected.items():
        operation = paths[path]["post"]
        assert {parameter["name"] for parameter in operation["parameters"] if parameter["in"] == "query"} == query_names
        assert "requestBody" not in operation
    assert legacy_client_contract["extraWrapperChecks"] == 4
