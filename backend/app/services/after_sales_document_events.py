"""Parse and expose the human-readable progress of after-sales documents.

The legacy FMG workbook stores several milestones in one free-text cell.  This
module keeps that original text intact while giving the UI a small, stable
event shape for list summaries and detail timelines.
"""

from __future__ import annotations

import re
from typing import Any


_DATE_RE = re.compile(r"(?<!\d)(\d{1,2}[./-]\d{1,2})(?!\d)")


def _label_for_raw(raw: str, document_type: str) -> tuple[str, str]:
    text = raw.casefold().replace("_", " ").replace("-", " ")
    if any(token in text for token in ("not ok", "not pass", "reject", "failed", "不通过", "未通过")):
        return "not_ok", "未通过"
    if any(token in text for token in ("approval date", "approved", "approval", "通过", "已通过")) or re.search(r"\bok\b", text):
        return "approved", "已通过"
    if any(token in text for token in ("re sent", "resent", "re-send")):
        return "resent", "已重发"
    if any(token in text for token in ("send date", "sent date", "submitted")):
        return "sent", "已寄出"
    if "estimated" in text or "预计" in text:
        return "estimated", "预计完成"
    return "note", {"drawing": "图纸记录", "sample": "样件记录", "ppap": "PPAP 记录"}.get(document_type, "状态记录")


def parse_legacy_status_event(raw_value: str | None, document_type: str) -> list[dict[str, Any]]:
    """Turn one legacy Excel status cell into one timeline event.

    Workbook dates are often yearless (for example ``7.10``).  Keep the
    original date text instead of guessing a year.
    """
    raw = (raw_value or "").strip()
    if not raw:
        return []
    event_type, label = _label_for_raw(raw, document_type)
    match = _DATE_RE.search(raw)
    return [{
        "event_type": event_type,
        "label": label,
        "date_text": match.group(1) if match else None,
        "raw_text": raw,
    }]


def document_events(source_data: dict[str, Any] | None, *, document_type: str, remark: str | None = None) -> list[dict[str, Any]]:
    """Return persisted events, with a safe legacy fallback for old rows."""
    data = source_data or {}
    events = data.get("status_events")
    if isinstance(events, list):
        normalized: list[dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            normalized.append({
                "event_type": str(event.get("event_type") or "note"),
                "label": str(event.get("label") or "状态记录"),
                "date_text": event.get("date_text"),
                "raw_text": str(event.get("raw_text") or ""),
            })
        if normalized:
            return normalized
    raw = data.get("legacy_raw_status")
    if not raw and remark and "Excel 原始状态：" in remark:
        raw = remark.split("Excel 原始状态：", 1)[1].strip()
    return parse_legacy_status_event(raw, document_type)


def latest_document_event(source_data: dict[str, Any] | None, *, document_type: str, remark: str | None = None) -> dict[str, Any] | None:
    events = document_events(source_data, document_type=document_type, remark=remark)
    return events[-1] if events else None


def append_status_event(source_data: dict[str, Any] | None, *, status: str, document_type: str, raw_text: str | None = None) -> dict[str, Any]:
    """Append a normalized manual status event without discarding source data."""
    data = dict(source_data or {})
    events = document_events(data, document_type=document_type)
    labels = {
        "not_started": ("not_started", "未开始"),
        "in_progress": ("in_progress", "进行中"),
        "ok": ("approved", "已通过"),
        "not_ok": ("not_ok", "未通过"),
        "not_applicable": ("not_applicable", "不适用"),
    }
    event_type, label = labels.get(status, ("status_updated", status))
    event = {"event_type": event_type, "label": label, "date_text": None, "raw_text": raw_text or "人工更新状态"}
    if not events or events[-1] != event:
        events.append(event)
    data["status_events"] = events
    return data
