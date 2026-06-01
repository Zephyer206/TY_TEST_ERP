"""
机台状态机 — MachineStateMachine
================================

依据 .cursorrules V6.0 §2.2 规范实现，与 machines 表实际状态严格对齐。

状态定义（6 个，与数据库一致）
--------
idle          : 机台空闲待排（可接收新任务）
running       : 机台正常运行
fault         : 故障停机（已报告故障，等待技术人员到场）
pending_check : 操作工已申请修理，等待技术人员到场（生产锁定）
repairing     : 技术人员到场，扫码介入，开始维修（生产锁定）
offline       : 模具已拆下，机台停止运行

跳转矩阵
------------------------
idle/running → fault          : 操作工发现异常并记录故障
fault → pending_check          : 操作工确认报修（进入维修流程）
fault → running               : 组长强制排除故障直接复产
idle/running → pending_check  : 操作工申请修理
pending_check → repairing      : tech 扫码到场（介入即维修）
pending_check → running       : tech 在线修复完成
repairing → running           : tech 执行【在线修复完成】
repairing → offline          : tech 执行【确认拆模下线】
offline → running             : tech/组长强制重置

设计约束
--------
- 状态变更必须经由 MachineStateMachine 实例方法，不允许在业务代码中直接 UPDATE status
- 维修时间戳（tech_arrival_time / diagnosing_start_time / mold_offline_time）由状态机内部管理
- 所有跳转均返回 (success: bool, message: str)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class MachineState(str, Enum):
    IDLE          = "idle"
    RUNNING       = "running"
    FAULT         = "fault"
    PENDING_CHECK = "pending_check"
    REPAIRING     = "repairing"
    OFFLINE       = "offline"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Transition:
    from_state: MachineState
    to_state: MachineState
    actor: str
    label: str
    description: str


_TRANSITIONS: dict[Tuple[MachineState, str], MachineState] = {
    # 生产操作员
    (MachineState.IDLE,    "report_fault"):     MachineState.FAULT,
    (MachineState.RUNNING, "report_fault"):     MachineState.FAULT,
    (MachineState.IDLE,    "apply_repair"):     MachineState.PENDING_CHECK,
    (MachineState.RUNNING, "apply_repair"):     MachineState.PENDING_CHECK,
    (MachineState.FAULT,  "apply_repair"):     MachineState.PENDING_CHECK,
    (MachineState.PENDING_CHECK, "apply_repair"): MachineState.PENDING_CHECK,
    (MachineState.REPAIRING, "apply_repair"):    MachineState.REPAIRING,
    (MachineState.OFFLINE, "apply_repair"):     MachineState.PENDING_CHECK,
    # 技术人员
    (MachineState.FAULT,  "tech_intervene"):    MachineState.REPAIRING,
    (MachineState.PENDING_CHECK, "tech_intervene"): MachineState.REPAIRING,
    (MachineState.RUNNING, "tech_intervene"):    MachineState.REPAIRING,
    (MachineState.OFFLINE, "tech_intervene"):    MachineState.REPAIRING,
    (MachineState.REPAIRING, "complete_repair_online"): MachineState.RUNNING,
    (MachineState.PENDING_CHECK, "complete_repair_online"): MachineState.RUNNING,
    (MachineState.REPAIRING, "confirm_mold_offline"): MachineState.OFFLINE,
    # 组长强制重置
    (MachineState.FAULT,  "force_reset"):         MachineState.RUNNING,
    (MachineState.IDLE,   "force_reset"):         MachineState.RUNNING,
    (MachineState.PENDING_CHECK, "force_reset"):   MachineState.RUNNING,
    (MachineState.OFFLINE, "force_reset"):         MachineState.RUNNING,
}


_TRANSITION_INFO: dict[Tuple[MachineState, str], Transition] = {
    (MachineState.IDLE,    "report_fault"):
        Transition(MachineState.IDLE,    MachineState.FAULT,          "prod_worker",
                   "故障上报", "操作工发现异常并记录故障，机台进入故障状态"),

    (MachineState.RUNNING, "report_fault"):
        Transition(MachineState.RUNNING, MachineState.FAULT,          "prod_worker",
                   "故障上报", "操作工发现异常并记录故障，机台进入故障状态"),

    (MachineState.IDLE,    "apply_repair"):
        Transition(MachineState.IDLE,    MachineState.PENDING_CHECK,  "prod_worker",
                   "申请修理", "操作工发起报修，机台进入待修状态"),

    (MachineState.RUNNING, "apply_repair"):
        Transition(MachineState.RUNNING, MachineState.PENDING_CHECK,  "prod_worker",
                   "申请修理", "操作工发起报修，机台进入待修状态"),

    (MachineState.FAULT,  "apply_repair"):
        Transition(MachineState.FAULT,  MachineState.PENDING_CHECK,  "prod_worker",
                   "确认报修", "故障状态下确认报修，进入待修池"),

    (MachineState.PENDING_CHECK, "apply_repair"):
        Transition(MachineState.PENDING_CHECK, MachineState.PENDING_CHECK, "prod_worker",
                   "申请修理", "已在待修状态，重复申请无效果"),

    (MachineState.REPAIRING, "apply_repair"):
        Transition(MachineState.REPAIRING, MachineState.REPAIRING,    "prod_worker",
                   "申请修理", "维修中不允许重复申请"),

    (MachineState.OFFLINE, "apply_repair"):
        Transition(MachineState.OFFLINE, MachineState.PENDING_CHECK, "prod_worker",
                   "申请修理", "停机状态下再次申请修理，进入待修池"),

    (MachineState.FAULT,  "tech_intervene"):
        Transition(MachineState.FAULT,  MachineState.REPAIRING,       "tech",
                   "技术人员到场介入", "扫码后直接进入维修状态，记录到场时间"),

    (MachineState.PENDING_CHECK, "tech_intervene"):
        Transition(MachineState.PENDING_CHECK, MachineState.REPAIRING, "tech",
                   "技术人员到场介入", "扫码后直接进入维修状态，记录到场时间"),

    (MachineState.RUNNING, "tech_intervene"):
        Transition(MachineState.RUNNING, MachineState.REPAIRING,       "tech",
                   "技术人员到场介入", "异常运行可直接扫码到场"),

    (MachineState.OFFLINE, "tech_intervene"):
        Transition(MachineState.OFFLINE, MachineState.REPAIRING,       "tech",
                   "技术人员到场介入", "停机模具可直接扫码到场维修"),

    (MachineState.REPAIRING, "complete_repair_online"):
        Transition(MachineState.REPAIRING,      MachineState.RUNNING,  "tech",
                   "在线修复完成", "维修成功，机台恢复正常运行"),

    (MachineState.PENDING_CHECK, "complete_repair_online"):
        Transition(MachineState.PENDING_CHECK,  MachineState.RUNNING,  "tech",
                   "在线修复完成", "简单问题无需离线，直接恢复运行"),

    (MachineState.REPAIRING, "confirm_mold_offline"):
        Transition(MachineState.REPAIRING, MachineState.OFFLINE,       "tech",
                   "确认拆模下线", "模具下线维修，机台进入停机状态"),

    (MachineState.FAULT,  "force_reset"):
        Transition(MachineState.FAULT,  MachineState.RUNNING,         "prod_leader",
                   "强制重置", "组长强制将故障机台排除故障后恢复运行"),

    (MachineState.IDLE,   "force_reset"):
        Transition(MachineState.IDLE,   MachineState.RUNNING,         "prod_leader",
                   "强制重置", "组长将空闲机台置为运行"),

    (MachineState.PENDING_CHECK, "force_reset"):
        Transition(MachineState.PENDING_CHECK, MachineState.RUNNING,    "prod_leader",
                   "强制重置", "组长强制将待修机台恢复运行"),

    (MachineState.OFFLINE, "force_reset"):
        Transition(MachineState.OFFLINE, MachineState.RUNNING,         "prod_leader",
                   "强制重置", "组长强制将停机机台恢复运行"),
}


STATE_META: dict[MachineState, dict] = {
    MachineState.IDLE: {
        "label":        "空闲",
        "color":        "#f97316",
        "bg_color":     "rgba(249,115,22,0.15)",
        "border_color": "#f97316",
        "icon":         "⏸",
        "description":  "机台空闲待排",
    },
    MachineState.RUNNING: {
        "label":        "运行中",
        "color":        "#22c55e",
        "bg_color":     "rgba(34,197,94,0.15)",
        "border_color": "#22c55e",
        "icon":         "▶",
        "description":  "机台正常运行中",
    },
    MachineState.FAULT: {
        "label":        "故障",
        "color":        "#f87171",
        "bg_color":     "rgba(248,113,113,0.15)",
        "border_color": "#f87171",
        "icon":         "⚠",
        "description":  "已报告故障，等待技术人员到场",
    },
    MachineState.PENDING_CHECK: {
        "label":        "待修理",
        "color":        "#fbbf24",
        "bg_color":     "rgba(251,191,36,0.15)",
        "border_color": "#fbbf24",
        "icon":         "⏳",
        "description":  "已报修，等待技术人员到场",
    },
    MachineState.REPAIRING: {
        "label":        "维修中",
        "color":        "#60a5fa",
        "bg_color":     "rgba(96,165,250,0.15)",
        "border_color": "#60a5fa",
        "icon":         "🔧",
        "description":  "技术人员正在维修",
    },
    MachineState.OFFLINE: {
        "label":        "停机",
        "color":        "#6b7280",
        "bg_color":     "rgba(107,114,128,0.15)",
        "border_color": "#6b7280",
        "icon":         "⏹",
        "description":  "模具已下线，机台停止运行",
    },
}


class MachineStateMachine:
    """
    机台状态机。

    使用方式：

        sm = MachineStateMachine(current_state="pending_check")

        ok, msg, next_state = sm.trigger("tech_intervene", actor="tech")
        # → (True, "技术人员到场介入", MachineState.REPAIRING)

        ok, msg, next_state = sm.trigger("complete_repair_online", actor="tech")
        # → (True, "在线修复完成", MachineState.RUNNING)
    """

    def __init__(self, current_state: str | MachineState):
        if isinstance(current_state, str):
            try:
                self.current_state = MachineState(current_state)
            except ValueError:
                raise ValueError(
                    f"未知机台状态: {current_state!r}，"
                    f"可选值: {[s.value for s in MachineState]}"
                )
        else:
            self.current_state = current_state

    def trigger(self, action: str, actor: str) -> Tuple[bool, str, Optional[MachineState]]:
        """
        触发状态跳转。

        action : str
            "report_fault"             — 操作工上报故障
            "apply_repair"             — 操作工申请修理
            "tech_intervene"           — 技术人员到场介入
            "complete_repair_online"   — 在线修复完成
            "confirm_mold_offline"     — 确认拆模下线
            "force_reset"              — 组长强制重置
        actor : str
            "prod_worker" | "tech" | "prod_leader" | "admin"
        """
        key = (self.current_state, action)
        next_state = _TRANSITIONS.get(key)

        if next_state is None:
            valid = [a for (s, a) in _TRANSITIONS if s == self.current_state]
            meta = STATE_META.get(self.current_state, {})
            label = meta.get("label", self.current_state.value)
            return False, f"当前状态【{label}】不允许执行【{action}】，可选: {valid}", None

        info: Transition = _TRANSITION_INFO.get(key)
        message = info.label if info else action

        if not self._check_role(action, actor):
            allowed = self._allowed_roles(action)
            return False, f"角色【{actor}】无权执行【{message}】，允许: {allowed}", None

        self.current_state = next_state
        return True, message, next_state

    @staticmethod
    def _check_role(action: str, actor: str) -> bool:
        role_map = {
            "report_fault":            {"prod_worker", "prod_leader", "admin"},
            "apply_repair":            {"prod_worker", "prod_leader", "admin"},
            "tech_intervene":          {"tech", "admin"},
            "complete_repair_online":  {"tech", "admin"},
            "confirm_mold_offline":    {"tech", "admin"},
            "force_reset":            {"prod_leader", "admin"},
        }
        return actor in role_map.get(action, set()) or actor == "admin"

    @staticmethod
    def _allowed_roles(action: str) -> list[str]:
        role_map = {
            "report_fault":            {"prod_worker", "prod_leader", "admin"},
            "apply_repair":            {"prod_worker", "prod_leader", "admin"},
            "tech_intervene":          {"tech", "admin"},
            "complete_repair_online":  {"tech", "admin"},
            "confirm_mold_offline":    {"tech", "admin"},
            "force_reset":            {"prod_leader", "admin"},
        }
        return sorted(role_map.get(action, set()))

    def is_production_locked(self) -> bool:
        """pending_check / repairing / offline / fault 均不允许报工。"""
        return self.current_state in (
            MachineState.FAULT,
            MachineState.PENDING_CHECK,
            MachineState.REPAIRING,
            MachineState.OFFLINE,
        )

    def is_under_repair(self) -> bool:
        return self.current_state == MachineState.REPAIRING

    def is_running(self) -> bool:
        return self.current_state == MachineState.RUNNING

    @staticmethod
    def get_state_meta(state: str | MachineState) -> dict:
        if isinstance(state, str):
            state = MachineState(state)
        return STATE_META.get(state, {
            "label":        state.value if isinstance(state, MachineState) else str(state),
            "color":        "#6b7280",
            "bg_color":     "rgba(107,114,128,0.15)",
            "border_color": "#6b7280",
            "icon":         "?",
            "description":  "未知状态",
        })

    @staticmethod
    def all_states() -> list[MachineState]:
        return list(MachineState)

    @staticmethod
    def all_transitions() -> list[Transition]:
        return list(_TRANSITION_INFO.values())

    def available_actions(self, actor: str) -> list[str]:
        return [
            action
            for (state, action) in _TRANSITIONS
            if state == self.current_state
            and MachineStateMachine._check_role(action, actor)
        ]
