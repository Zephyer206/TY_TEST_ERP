"""Read-only, sanitized evidence for the material/product-box QR Phase 0 audit.

Run from the repository root. Existing connection settings are consumed internally;
URLs, credentials, user identities and raw exception messages are never emitted.
This script performs no migrations, application writes or external notifications.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "specs/002-material-qr-traceability/phase0-evidence.json"
sys.path.insert(0, str(ROOT / "backend"))

TABLES = (
    "alembic_version", "users", "material_batches", "material_batch_children",
    "batch_transactions", "qr_scan_logs", "machines", "production_plans",
    "plan_machine_assignments", "production_sessions", "process_flow_cards",
    "product_qr_pool_items", "product_boxes", "product_flow_events",
    "product_box_relations", "coil_spec_exceptions", "product_conversion_records",
    "notification_outbox",
)


def normalize_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def metadata_value(value):
    """Normalize PostgreSQL catalog text, including SQL_ASCII byte results."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {metadata_value(key): metadata_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [metadata_value(item) for item in value]
    return value


def inspect_sources() -> dict:
    routes = []
    hashes = {}
    for domain in ("warehouse", "machines", "production", "qr"):
        path = ROOT / "backend/app/api" / f"{domain}.py"
        raw = path.read_bytes()
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(raw).hexdigest()
        tree = ast.parse(raw.decode("utf-8-sig"))
        prefix = ""
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if getattr(node.value.func, "id", "") == "APIRouter":
                    prefix = next((ast.literal_eval(k.value) for k in node.value.keywords
                                   if k.arg == "prefix"), "")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                        and getattr(decorator.func.value, "id", "") == "router"
                        and decorator.args and isinstance(decorator.args[0], ast.Constant)):
                    continue
                route_path = prefix + decorator.args[0].value
                if domain != "qr" and not any(token in route_path for token in (
                    "material-batches", "/scans", "generate-qr", "/scan", "process-flow-cards",
                    "verify-material", "sessions/start", "sessions/{session_id}/close",
                )):
                    continue
                minimum_levels = []
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "require_role":
                        minimum_levels.extend(ast.literal_eval(k.value) for k in call.keywords
                                              if k.arg == "min_level" and isinstance(k.value, ast.Constant))
                routes.append({"method": decorator.func.attr.upper(), "path": route_path,
                               "source": path.relative_to(ROOT).as_posix(), "line": node.lineno,
                               "minimum_levels": minimum_levels})
    registry = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import {apiRegistry} from './shared/api/registry.js'; "
         "console.log(JSON.stringify(Object.values(apiRegistry)));"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    entries = json.loads(registry.stdout)
    for route in routes:
        route["registry_keys"] = [entry["key"] for entry in entries
                                  if entry["method"] == route["method"]
                                  and normalize_path(entry["path"]) == normalize_path(route["path"])]
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    directory = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    revisions = {revision.revision for revision in directory.walk_revisions()}
    return {"routes": routes, "source_sha256": hashes,
            "migration_heads": directory.get_heads(), "migration_bases": directory.get_bases(),
            "revision_count": len(revisions), "known_revisions": sorted(revisions)}


def inspect_qr_helpers() -> list[dict]:
    from PIL import Image
    from app.services import qr_service as qr
    checks = []

    def check(name, operation):
        try:
            operation()
            checks.append({"name": name, "status": "PASS"})
        except Exception as error:
            checks.append({"name": name, "status": "FAIL", "error_type": type(error).__name__})

    def round_trip(prefix, payload):
        parsed = qr.parse_qr_content(payload)
        assert parsed and parsed["prefix"] == prefix and parsed["entity_id"] == 42

    check("material_payload_round_trip", lambda: round_trip("MAT", qr.generate_material_batch_qr(42)))
    check("machine_payload_round_trip", lambda: round_trip("MCN", qr.generate_machine_qr(42, "AUDIT-MACHINE")))
    check("process_flow_payload_round_trip", lambda: round_trip("PFC", qr.generate_process_flow_qr(42, "AUDIT-CARD")))

    def assert_invalid():
        assert qr.parse_qr_content("invalid") is None
        assert qr.get_prefix_type("UNKNOWN") is None

    check("invalid_format_and_unknown_prefix", assert_invalid)

    def assert_png():
        data = qr.generate_qr_base64("MAT:42:20261012")
        assert data.startswith("data:image/png;base64,")
        with Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))) as img:
            assert img.format == "PNG" and img.size == (300, 300)

    check("printable_png_300px", assert_png)
    return checks


async def inspect_api_contracts(routes: list[dict]) -> dict:
    """Exercise real ASGI routes without a live login, DB writes or startup hooks.

    Only invalid input branches are called. Authentication is deliberately
    replaced and therefore this is not an authentication acceptance test.
    """
    from types import SimpleNamespace
    from httpx import ASGITransport, AsyncClient
    from app.api.deps import get_current_user
    from app.database import get_db
    from app.main import app

    async def actor():
        return SimpleNamespace(id=0, role_level=1, dept="test")

    async def no_database():
        yield None

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = actor
    app.dependency_overrides[get_db] = no_database
    checks = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://phase0") as client:
            for name, params in (
                ("invalid_qr_format", {"code": "invalid"}),
                ("unknown_qr_prefix", {"code": "UNKNOWN:42:20261012"}),
                ("manual_lookup_requires_type", {"code": "AUDIT", "manual": "true"}),
            ):
                response = await client.get("/api/v1/qr/lookup", params=params)
                body = response.json()
                checks.append({"name": name, "status": "PASS" if response.status_code == 200
                               and body.get("found") is False and body.get("error") else "FAIL",
                               "http_status": response.status_code})
            health = await client.get("/health")
            schema = app.openapi()
            missing = [route for route in routes if route["method"].lower() not in
                       schema.get("paths", {}).get("/api/v1" + route["path"], {})]
            return {"checks": checks, "health_status": health.status_code,
                    "source_routes_missing_from_openapi": missing,
                    "mode": "in-process ASGI, synthetic actor, no DB, no lifespan",
                    "authentication_acceptance": "NOT_RUN", "live_browser_acceptance": "NOT_RUN"}
    except Exception as error:
        return {"status": "INCOMPLETE", "error_type": type(error).__name__, "checks": checks}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


async def inspect_database(known_revisions: list[str]) -> dict:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from app.core.config import settings
    db_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool,
                                    connect_args={"timeout": 10, "command_timeout": 20})
    try:
        async with db_engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                readonly = metadata_value((await connection.execute(text("SHOW transaction_read_only"))).scalar_one())
                columns = [metadata_value(dict(row)) for row in (await connection.execute(text(
                    "SELECT table_name, column_name, data_type, is_nullable "
                    "FROM information_schema.columns WHERE table_schema='public' "
                    "AND table_name = ANY(:tables) ORDER BY table_name, ordinal_position"
                ), {"tables": list(TABLES)})).mappings().all()]
                existing = {row["table_name"] for row in columns}
                versions = []
                if "alembic_version" in existing:
                    versions = metadata_value(list((await connection.execute(text(
                        "SELECT version_num FROM alembic_version ORDER BY version_num"
                    ))).scalars()))
                counts = {}
                for table in TABLES:
                    if table in existing and table != "users":
                        counts[table] = (await connection.execute(text(
                            f'SELECT count(*) FROM "{table}"'
                        ))).scalar_one()
                roles = []
                if "users" in existing:
                    user_columns = {row["column_name"] for row in columns if row["table_name"] == "users"}
                    if {"dept", "role_level"}.issubset(user_columns):
                        roles = [metadata_value(dict(row)) for row in (await connection.execute(text(
                            "SELECT dept, role_level, count(*) AS user_count FROM users "
                            "GROUP BY dept, role_level ORDER BY dept, role_level"
                        ))).mappings().all()]
                indexes = [metadata_value(dict(row)) for row in (await connection.execute(text(
                    "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname='public' "
                    "AND tablename = ANY(:tables) ORDER BY tablename, indexname"
                ), {"tables": list(TABLES)})).mappings().all()]
                constraints = [metadata_value(dict(row)) for row in (await connection.execute(text(
                    "SELECT c.relname AS table_name, con.conname AS constraint_name, "
                    "con.contype AS constraint_type, pg_get_constraintdef(con.oid) AS definition "
                    "FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
                    "AND c.relname = ANY(:tables) ORDER BY c.relname, con.conname"
                ), {"tables": list(TABLES)})).mappings().all()]
                return {"status": "PASS", "transaction_read_only": readonly,
                        "migration_versions": versions,
                        "unknown_migration_versions": [v for v in versions if v not in known_revisions],
                        "columns": [dict(row) for row in columns], "row_counts": counts,
                        "role_groups": roles, "indexes": indexes, "constraints": constraints,
                        "missing_tables": [table for table in TABLES if table not in existing],
                        "runtime_auth_disabled": settings.AUTH_DISABLED}
    except Exception as error:
        return {"status": "INCOMPLETE", "error_type": type(error).__name__}
    finally:
        await db_engine.dispose()


def main() -> None:
    result = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "scope": "Phase 0 baseline only", "business_writes": 0}
    try:
        result["source"] = inspect_sources()
    except Exception as error:
        result["source"] = {"status": "INCOMPLETE", "error_type": type(error).__name__}
    try:
        result["helper_checks"] = inspect_qr_helpers()
    except Exception as error:
        result["helper_checks"] = [{"status": "INCOMPLETE", "error_type": type(error).__name__}]
    try:
        result["database"] = asyncio.run(inspect_database(result["source"].get("known_revisions", [])))
    except Exception as error:
        result["database"] = {"status": "INCOMPLETE", "error_type": type(error).__name__}
    try:
        result["api_contracts"] = asyncio.run(inspect_api_contracts(result["source"].get("routes", [])))
    except Exception as error:
        result["api_contracts"] = {"status": "INCOMPLETE", "error_type": type(error).__name__}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "route_count": len(result["source"].get("routes", [])),
                      "helper_checks": result["helper_checks"],
                      "database_status": result["database"]["status"],
                      "api_checks": result["api_contracts"].get("checks", []),
                      "migration_heads": result["source"].get("migration_heads", []),
                      "migration_versions": result["database"].get("migration_versions", [])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
