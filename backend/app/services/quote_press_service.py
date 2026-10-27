"""Expose and synchronize engineering press data without changing quote prices."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException

from app.models.customer_inquiry import CustomerInquiry
from app.models.quote_group import QuoteGroup, QuoteGroupItem

LOCKED_QUOTE_GROUP_STATUSES = {"已提交审批", "已审批", "已定点"}


def press_metadata(snapshot: dict | None, tonnage: int | None = None) -> dict:
    """Old tonnage-only snapshots stay manual; never guess the axis type."""
    snapshot = snapshot or {}
    key = snapshot.get("pressTypeKey") or None
    source = snapshot.get("pressTonnageSource")
    if source not in ("type", "manual"):
        source = "type" if key else "manual" if tonnage is not None else None
    dual_axis = snapshot.get("pressIsDualAxis")
    if not isinstance(dual_axis, bool):
        dual_axis = key.endswith("-dual-axis") if isinstance(key, str) else None
    label = str(snapshot.get("pressTypeLabel") or "").strip() or None
    if source == "manual":
        key, dual_axis = None, None
        label = f"{tonnage}T" if tonnage is not None else None
    elif label is None and tonnage is not None:
        label = f"{tonnage}T{' 双轴' if dual_axis else ''}"
    return {
        "press_type_key": key,
        "press_type_label": label,
        "press_is_dual_axis": dual_axis,
        "press_tonnage_source": source,
    }


def _source_part_numbers(source: dict) -> set[str]:
    numbers = {str(source.get("customerPartNo") or "").strip()}
    if source.get("isLeftRightPair"):
        numbers.add(str(source.get("customerPartNo2") or "").strip())
    return numbers - {""}


def _match_source(item: QuoteGroupItem, sources: list[dict]) -> dict:
    part_no = (item.customer_part_no or "").strip()
    snapshot_key = (item.technical_snapshot or {}).get("key")
    matches = [source for source in sources if part_no and part_no in _source_part_numbers(source)]
    if snapshot_key:
        keyed = [source for source in matches if source.get("key") == snapshot_key]
        if len(keyed) == 1:
            return keyed[0]
    if len(matches) == 1:
        return matches[0]
    # A stable technical key can match unnamed parts, but never an altered part number.
    if not part_no and snapshot_key:
        matches = [source for source in sources if source.get("key") == snapshot_key]
        if len(matches) == 1:
            return matches[0]
    raise HTTPException(409, detail=f"零件 {part_no or item.sequence} 无法唯一对应技术评审资料，请核对客户件号")


def sync_quote_presses(group: QuoteGroup, inquiry: CustomerInquiry) -> int:
    if group.status in LOCKED_QUOTE_GROUP_STATUSES:
        raise HTTPException(409, detail="报价已锁定，保留原技术审核快照")
    if inquiry.technical_review != "已完成":
        raise HTTPException(409, detail="询价尚未通过技术评审，不能同步冲床资料")
    changes = []
    for item in group.items:
        source = _match_source(item, inquiry.technical_data or [])
        try:
            value = Decimal(str(source.get("pressTonnage") or "0"))
        except InvalidOperation:
            value = Decimal("NaN")
        if not value.is_finite() or value <= 0 or value != value.to_integral_value() or value > 2147483647:
            raise HTTPException(409, detail=f"零件 {item.customer_part_no or item.sequence} 缺少有效冲床吨位，请先补充技术评审资料")
        tonnage = int(value)
        metadata = press_metadata(source, tonnage)
        snapshot = dict(item.technical_snapshot or {})
        snapshot.update(
            pressTonnage=str(tonnage),
            pressTonnageSource=metadata["press_tonnage_source"],
            pressTypeKey=metadata["press_type_key"],
            pressTypeLabel=metadata["press_type_label"],
            pressIsDualAxis=metadata["press_is_dual_axis"],
            pressMachineId=None,
            pressMachineLabel="",
        )
        changes.append((item, tonnage, snapshot))
    # Validate all matches first; an ambiguous later part must not partially update the group.
    changed = 0
    for item, tonnage, snapshot in changes:
        if item.press_tonnage != tonnage or item.technical_snapshot != snapshot:
            item.press_tonnage, item.technical_snapshot = tonnage, snapshot
            changed += 1
    if changed:
        group.updated_at = datetime.utcnow()
    return changed
