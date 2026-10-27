"""Read-only checks for the current QR design and executable task coverage."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / "specs/002-material-qr-traceability"


def verify() -> dict:
    documents = {p.relative_to(FEATURE).as_posix(): p.read_text(encoding="utf-8")
                 for p in FEATURE.rglob("*.md")}
    spec, tasks = documents["spec.md"], documents["tasks.md"]
    requirements = set(re.findall(r"\*\*(FR-\d{3})\*\*", spec))
    criteria = set(re.findall(r"\*\*(SC-\d{3})\*\*", spec))
    task_lines = re.findall(r"^- \[[ xX]\] T\d{3} .+$", tasks, re.M)
    ids = [re.search(r"T\d{3}", line)[0] for line in task_lines]
    assert ids == [f"T{i:03}" for i in range(1, len(ids) + 1)], "task ID gaps/duplicates"
    assert len(task_lines) >= 50, "incomplete task breakdown"
    assert all(re.search(r"`[^`]+/[^`]+\.[a-z]+`", line) for line in task_lines), "task paths"
    for story in range(1, 9):
        assert sum(f"[US{story}]" in line for line in task_lines) >= 4, f"US{story} coverage"
    # Ignore broad release ranges: every FR/SC needs an explicit story/foundation mapping.
    explicit = "\n".join(line for line in task_lines if "～" not in line)
    missing_fr = requirements - set(re.findall(r"FR-\d{3}", explicit))
    missing_sc = criteria - set(re.findall(r"SC-\d{3}", explicit))
    assert not missing_fr and not missing_sc, f"coverage gaps: {sorted(missing_fr | missing_sc)}"
    assert len(re.findall(r"^- Q:", spec, re.M)) == 3, "accepted answers must remain three"
    assert "[NEEDS CLARIFICATION:" not in spec
    contract, registry = documents["contracts/product-box-qr.md"], documents["contracts/api-registry.md"]
    endpoint_pattern = r"^\| `(\w+\.\w+)` \| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)` \|"
    endpoints = re.findall(endpoint_pattern, contract, re.M)
    assert endpoints == re.findall(endpoint_pattern, registry, re.M), "contract/registry drift"
    assert len(endpoints) == 31 and len(set(x[0] for x in endpoints)) == 31
    assert len(set((m, p) for _, m, p in endpoints)) == 31
    checks = {
        "context_and_scope": ("context_id", "state_version", "30分钟", "production_plans.id"),
        "quantity_and_conversion": ("source_quantity_id", "conversion_version", "child_qr_payload", "actual_qty"),
        "separate_controlled_actions": ("quantity-corrections", "/advance", "/resume", "qr-admin"),
        "reliability": ("60秒", "5次", "1、5、15、30", "IDEMPOTENCY_CONFLICT", "422"),
    }
    for name, values in checks.items():
        assert all(value in contract + documents["contracts/order-routing.md"] for value in values), name
    assert "派生只读字段" in documents["data-model.md"]
    assert "binding_allowed=false" in documents["contracts/order-routing.md"]
    assert "target_qty=0" in documents["contracts/order-routing.md"]
    assert "qr_print_job_items" in documents["data-model.md"]
    assert "确认人必须为作业申请人" in documents["contracts/permissions.md"]
    assert "20261020_ppap" in documents["plan.md"]
    assert "30** | **30" in documents["tasks-material-legacy.md"]
    missing_links = []
    for name, body in documents.items():
        for link in re.findall(r"\]\(([^)]+)\)", body):
            if ":" in link or link.startswith("#"):
                continue
            if not (FEATURE / name).parent.joinpath(link.split("#")[0]).exists():
                missing_links.append((name, link))
    assert not missing_links, f"missing links: {missing_links}"
    return {"status": "PASS", "requirements": len(requirements), "success_criteria": len(criteria),
            "tasks": len(task_lines), "user_stories": 8, "endpoints": len(endpoints),
            "explicit_requirement_coverage": "100%", "accepted_business_answers": 3,
            "runtime_acceptance": "NOT_RUN", "browser_acceptance": "NOT_RUN"}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False))
