#!/usr/bin/env python3
"""Classify audit groups that were intentionally left undetermined.

This report does not change the display rule or database.  It groups each
undetermined source block by the exact evidence that is missing/conflicting so
the business owner can choose a policy for each category.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts" / "analysis" / "shared_mold_blocks_audit.json"
OUT_JSON = ROOT / "scripts" / "analysis" / "undetermined_mold_block_categories.json"
OUT_MD = ROOT / "scripts" / "analysis" / "undetermined_mold_block_categories.md"

CATEGORIES = {
    "MISSING_CAVITY_ONLY": {
        "label": "仅缺少穴数/一出证据",
        "question": "材料和 TWP 一致且有来源块迹象，但没有明确一出/左右证据；是否允许仅凭左右零件语义或其他规则合并共享字段？",
    },
    "MISSING_CAVITY_MATERIAL": {
        "label": "缺少穴数证据且材料缺失/不一致",
        "question": "材料字段是否以空白传播、录入遗漏还是实际不同为准？在穴数也不明确时是否禁止合并？",
    },
    "MISSING_CAVITY_TWP": {
        "label": "缺少穴数证据且 TWP 缺失/不一致",
        "question": "TWP 不一致时是否无条件拆分，还是允许按其他来源证据重新归组？",
    },
    "MISSING_CAVITY_MATERIAL_TWP": {
        "label": "缺少穴数证据且材料、TWP均缺失/不一致",
        "question": "多个关键共享字段同时不可靠；通常应保持独立，是否需要人工补充来源？",
    },
    "NO_SOURCE_ANCHOR": {
        "label": "有一出证据但没有 Excel 合并/来源锚点",
        "question": "是否接受相邻行、相同客户、相同材料/TWP和明确一出文字作为来源块，而不要求合并单元格？",
    },
    "MATERIAL_ONLY": {
        "label": "材料缺失/不一致",
        "question": "穴数/TWP和来源块证据存在，但材料不一致或缺失；材料是否必须一致才可合并？",
    },
    "MATERIAL_TWP": {
        "label": "材料与 TWP 均缺失/不一致",
        "question": "两个共享字段同时不可靠；是否直接列为独立模具/零件？",
    },
}


def category_for(reasons: list[str]) -> str:
    reason_text = "; ".join(reasons)
    has_cavity = "no explicit 一出N/左右证据" in reason_text or "cavity evidence is missing or inconsistent" in reason_text
    has_material = "material is missing or differs" in reason_text
    has_twp = "TWP/spec is missing or differs" in reason_text
    if "no shared Excel merge/source anchor" in reason_text:
        return "NO_SOURCE_ANCHOR"
    if has_cavity and has_material and has_twp:
        return "MISSING_CAVITY_MATERIAL_TWP"
    if has_cavity and has_material:
        return "MISSING_CAVITY_MATERIAL"
    if has_cavity and has_twp:
        return "MISSING_CAVITY_TWP"
    if has_cavity:
        return "MISSING_CAVITY_ONLY"
    if has_material and has_twp:
        return "MATERIAL_TWP"
    if has_material:
        return "MATERIAL_ONLY"
    return "OTHER"


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    groups = [group for group in source.get("groups", []) if group.get("classification") == "undetermined"]
    categorized: dict[str, list[dict]] = {key: [] for key in CATEGORIES}
    categorized["OTHER"] = []
    for group in groups:
        categorized[category_for(group.get("reasons", []))].append(group)

    report = {
        "source": str(SOURCE),
        "total_undetermined": len(groups),
        "categories": {
            key: {
                **CATEGORIES.get(key, {"label": "其他", "question": "需要人工确认"}),
                "count": len(items),
                "groups": items,
            }
            for key, items in categorized.items()
            if items
        },
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 无法判定模具来源块归类",
        "",
        f"来源：`{SOURCE}`",
        "",
        f"无法判定总数：**{len(groups)} 组**",
        "",
        "本报告只做证据归类，不替业务规则做最终判定。",
        "",
    ]
    for key, meta in report["categories"].items():
        lines.extend([
            f"## {key} · {meta['label']}（{meta['count']} 组）",
            "",
            f"决策问题：{meta['question']}",
            "",
        ])
        for group in meta["groups"]:
            rows = group.get("rows", [])
            lines.append(f"- `{group.get('sheet')}` 行 {rows[0] if rows else '?'}-{rows[-1] if rows else '?'}：{group.get('customer') or '客户缺失'}；原因：{'；'.join(group.get('reasons', []))}")
            for part in group.get("parts", []):
                lines.append(
                    f"  - 行 {part.get('row')}：零件 {part.get('customer_part_no') or '-'}；模具 {part.get('tooling_number') or '-'}；材料 {part.get('material') or '-'}；TWP {part.get('spec') or '-'}；穴数 {part.get('cavity') or '-'}"
                )
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"total_undetermined": len(groups), "counts": {key: len(items) for key, items in categorized.items() if items}, "json": str(OUT_JSON), "markdown": str(OUT_MD)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
