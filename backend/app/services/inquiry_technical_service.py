"""Resolve inquiry press selections into trustworthy engineering snapshots."""

from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.machine import Machine
from app.services.press_type_service import classify_press, list_installed_press_types


def _tonnage(value, index: int) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        number = Decimal("NaN")
    # Quotation items store press tonnage as an integer.
    if not number.is_finite() or number <= 0 or number > 2147483647 or number != number.to_integral_value():
        raise HTTPException(422, detail=f"零件 {index}：冲床吨位必须为正整数")
    return str(int(number))


async def resolve_inquiry_presses(
    db: AsyncSession, items: list[dict], *, completing: bool = False
) -> list[dict]:
    resolved = []
    catalog = None
    for index, original in enumerate(items, 1):
        item = dict(original)
        machine_id = item.get("pressMachineId")
        value = item.get("pressTonnage")
        type_key = item.get("pressTypeKey")
        # Convert the previous machine-based picker without retaining an assignment.
        source = item.get("pressTonnageSource")
        if source is None:
            source = "type" if type_key else "machine" if machine_id is not None else "manual" if value not in (None, "") else "type"
        if source == "machine" and machine_id is not None:
            if isinstance(machine_id, bool) or not isinstance(machine_id, int) or machine_id <= 0:
                raise HTTPException(422, detail=f"零件 {index}：冲床编号无效")
            machine = await db.get(Machine, machine_id)
            if machine is None or machine.is_deleted:
                raise HTTPException(422, detail=f"零件 {index}：所选冲床已不存在，请重新选择")
            type_key = classify_press(machine).key
            source = "type"
        elif source == "machine":
            source = "type"
        if source not in ("type", "manual"):
            raise HTTPException(422, detail=f"零件 {index}：请选择冲床类型或手动填写吨位")
        item["pressTonnageSource"] = source
        # Deprecated identity fields are cleared for older clients, not used as a binding.
        item.update(pressMachineId=None, pressMachineLabel="")
        if source == "type" and type_key:
            if not isinstance(type_key, str):
                raise HTTPException(422, detail=f"零件 {index}：冲床类型无效")
            if catalog is None:
                catalog = {option.key: option for option in await list_installed_press_types(db)}
            option = catalog.get(type_key)
            if option is None:
                raise HTTPException(422, detail=f"零件 {index}：所选冲床类型已不可用，请重新选择")
            item.update(
                pressTypeKey=option.key, pressTypeLabel=option.label,
                pressIsDualAxis=option.is_dual_axis, pressTonnage=_tonnage(option.tonnage, index),
            )
        elif source == "type":
            if value not in (None, ""):
                raise HTTPException(422, detail=f"零件 {index}：请选择现有冲床类型，特殊情况请切换手动填写")
            item.update(pressTypeKey=None, pressTypeLabel="", pressIsDualAxis=None, pressTonnage="")
        else:
            item.update(
                pressTypeKey=None, pressTypeLabel="", pressIsDualAxis=None,
                pressTonnage=_tonnage(value, index) if value not in (None, "") else "",
            )
        has_part = any(str(item.get(field) or "").strip() for field in ("partName", "customerPartNo", "customerPartNo2"))
        if completing and has_part and not item["pressTonnage"]:
            raise HTTPException(422, detail=f"零件 {index}：请选择冲床类型，特殊情况请手动填写吨位")
        resolved.append(item)
    return resolved
