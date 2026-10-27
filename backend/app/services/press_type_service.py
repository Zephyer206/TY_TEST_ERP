"""One classification of installed presses for inquiries and scheduling."""

from math import isfinite

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.machine import Machine


class PressTypeOption(BaseModel):
    key: str
    label: str
    tonnage: float | None
    is_dual_axis: bool
    machine_count: int = 0


def classify_press(machine: Machine) -> PressTypeOption:
    model = (machine.machine_type or "").strip()
    # Legacy '(双)' without 料架 means a dual-axis press. A dual feeder
    # alone does not change the press's axis type; explicit 双轴 takes priority.
    dual_axis = "双轴" in model or ("双" in model and "料架" not in model)
    tonnage = machine.tonnage
    tonnage = float(tonnage) if tonnage is not None else None
    if tonnage is not None and (not isfinite(tonnage) or tonnage <= 0):
        tonnage = None
    value = f"{tonnage:g}" if tonnage is not None else "unknown"
    label = f"{value}T" if tonnage is not None else "未标注吨位"
    return PressTypeOption(
        key=f"{value}-{'dual-axis' if dual_axis else 'standard'}",
        label=f"{label} 双轴" if dual_axis else label,
        tonnage=tonnage,
        is_dual_axis=dual_axis,
    )


def group_press_types(machines: list[Machine]) -> list[PressTypeOption]:
    groups: dict[str, PressTypeOption] = {}
    for machine in machines:
        option = classify_press(machine)
        if option.tonnage is None or not option.tonnage.is_integer() or option.tonnage > 2147483647:
            continue
        group = groups.setdefault(option.key, option)
        group.machine_count += 1
    for option in groups.values():
        # A sole dual-axis type (e.g. 300T or 400T) needs only one tonnage
        # choice. Qualify 双轴 only where it distinguishes two installed types.
        if option.is_dual_axis and f"{option.tonnage:g}-standard" not in groups:
            option.label = f"{option.tonnage:g}T"
    return sorted(groups.values(), key=lambda option: (option.tonnage, option.is_dual_axis))


async def list_installed_press_types(db: AsyncSession) -> list[PressTypeOption]:
    machines = (await db.execute(select(Machine).where(Machine.is_deleted == False))).scalars().all()
    return group_press_types(machines)
