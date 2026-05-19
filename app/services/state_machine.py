"""
机台状态机 — MachineStateMachine
================================

依据 .cursorrules V3.0 §2.1 规范实现。

状态定义
--------
running       : 机台正常运行
pending_check : 操作工已申请修理，等待技术人员到场（生产锁定）
repairing     : 技术人员到场，扫码介入，开始维修（生产锁定）
offline       : 模具已拆下，机台停止运行

跳转矩阵（按角色/操作员）
------------------------
任何状态 → running          : tech() 执行"在线修复完成"
任何状态 → pending_check     : prod_worker() 执行"申请修理"
pending_check → repairing    : tech() 扫码到场（介入即维修）
repairing → running         : tech() 执行【在线修复完成】
repairing → offline         : tech() 执行【确认拆模下线】

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
    RUNNING       = "running"
    PENDING_CHECK = "pending_check"
    REPAIRING     = "repairing"
    OFFLINE       = "offline"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Transition:
    from_state: MachineState
    to_state: MachineState
    actor: str          # 操作角色标识：'prod_worker' | 'tech'
    label: str          # 业务操作中文描述
    description: str    # 详细说明


# ---------------------------------------------------------------------------
# 跳转路径注册表
# ---------------------------------------------------------------------------

_TRANSITIONS: dict[Tuple[MachineState, str], MachineState] = {
    # --- 生产操作员 ---
    # 操作工发现异常 → 申请修理 → pending_check（任何状态均可）
    (MachineState.RUNNING,       "apply_repair"):       MachineState.PENDING_CHECK,
    (MachineState.PENDING_CHECK,  "apply_repair"):       MachineState.PENDING_CHECK,  # 重复申请无意义，保持原状态
    (MachineState.REPAIRING,      "apply_repair"):       MachineState.REPAIRING,       # 维修中不允许重复申请
    (MachineState.OFFLINE,        "apply_repair"):       MachineState.PENDING_CHECK,  # 停机状态下再次申请修理

    # --- 技术人员 ---
    # 技术人员到场扫码 → 介入即维修 → repairing
    (MachineState.PENDING_CHECK,  "tech_intervene"):     MachineState.REPAIRING,
    (MachineState.RUNNING,        "tech_intervene"):     MachineState.REPAIRING,       # 异常运行可直接扫码
    (MachineState.OFFLINE,        "tech_intervene"):     MachineState.REPAIRING,       # 停机模具可直接扫码

    # 【在线修复完成】→ running
    (MachineState.REPAIRING,      "complete_repair_online"):  MachineState.RUNNING,
    (MachineState.PENDING_CHECK,  "complete_repair_online"):  MachineState.RUNNING,       # 简单问题无需离线

    # 【确认拆模下线】→ offline
    (MachineState.REPAIRING,      "confirm_mold_offline"):    MachineState.OFFLINE,

    # --- 组长 / 开发人员重置 ---
    # 将机台强制恢复运行（overrule）
    (MachineState.PENDING_CHECK,  "force_reset"):         MachineState.RUNNING,
    (MachineState.OFFLINE,        "force_reset"):         MachineState.RUNNING,
}


# ---------------------------------------------------------------------------
# 业务描述映射（用于日志和提示）
# ---------------------------------------------------------------------------

_TRANSITION_INFO: dict[Tuple[MachineState, str], Transition] = {
    (MachineState.RUNNING,       "apply_repair"):
        Transition(MachineState.RUNNING,       MachineState.PENDING_CHECK, "prod_worker",
                   "申请修理", "操作工发起报修，机台进入待修状态"),

    (MachineState.PENDING_CHECK, "apply_repair"):
        Transition(MachineState.PENDING_CHECK, MachineState.PENDING_CHECK, "prod_worker",
                   "申请修理", "已在待修状态，重复申请无效果"),

    (MachineState.REPAIRING,     "apply_repair"):
        Transition(MachineState.REPAIRING, MachineState.REPAIRING, "prod_worker",
                   "申请修理", "维修中不允许重复申请，直接拒绝"),

    (MachineState.OFFLINE,       "apply_repair"):
        Transition(MachineState.OFFLINE, MachineState.PENDING_CHECK, "prod_worker",
                   "申请修理", "停机状态下再次申请修理，进入待修池"),

    (MachineState.PENDING_CHECK, "tech_intervene"):
        Transition(MachineState.PENDING_CHECK, MachineState.REPAIRING, "tech",
                   "技术人员到场介入", "扫码后直接进入维修状态，记录到场时间"),

    (MachineState.RUNNING,       "tech_intervene"):
        Transition(MachineState.RUNNING, MachineState.REPAIRING, "tech",
                   "技术人员到场介入", "异常运行可直接扫码到场"),

    (MachineState.OFFLINE,       "tech_intervene"):
        Transition(MachineState.OFFLINE, MachineState.REPAIRING, "tech",
                   "技术人员到场介入", "停机模具可直接扫码到场维修"),

    (MachineState.REPAIRING,     "complete_repair_online"):
        Transition(MachineState.REPAIRING, MachineState.RUNNING, "tech",
                   "在线修复完成", "维修成功，机台恢复正常运行"),

    (MachineState.PENDING_CHECK, "complete_repair_online"):
        Transition(MachineState.PENDING_CHECK, MachineState.RUNNING, "tech",
                   "在线修复完成", "简单问题无需离线，直接恢复运行"),

    (MachineState.REPAIRING,     "confirm_mold_offline"):
        Transition(MachineState.REPAIRING, MachineState.OFFLINE, "tech",
                   "确认拆模下线", "模具下线维修，机台进入停机状态"),

    (MachineState.PENDING_CHECK, "force_reset"):
        Transition(MachineState.PENDING_CHECK, MachineState.RUNNING, "prod_leader",
                   "强制重置", "组长强制将待修机台恢复运行"),

    (MachineState.OFFLINE,       "force_reset"):
        Transition(MachineState.OFFLINE, MachineState.RUNNING, "prod_leader",
                   "强制重置", "组长强制将停机机台恢复运行"),
}


# ---------------------------------------------------------------------------
# 状态元数据（供 UI 渲染和看板使用）
# ---------------------------------------------------------------------------

STATE_META: dict[MachineState, dict] = {
    MachineState.RUNNING: {
        "label":        "运行中",
        "color":        "#22c55e",   # 绿
        "bg_color":     "#dcfce7",
        "border_color": "#16a34a",
        "icon":         "▶",
        "description":  "机台正常运行中",
    },
    MachineState.PENDING_CHECK: {
        "label":        "待修理",
        "color":        "#f59e0b",   # 黄/橙
        "bg_color":     "#fef9c3",
        "border_color": "#d97706",
        "icon":         "⏳",
        "description":  "已报修，等待技术人员到场",
    },
    MachineState.REPAIRING: {
        "label":        "维修中",
        "color":        "#3b82f6",   # 蓝
        "bg_color":     "#dbeafe",
        "border_color": "#2563eb",
        "icon":         "🔧",
        "description":  "技术人员正在维修",
    },
    MachineState.OFFLINE: {
        "label":        "停机",
        "color":        "#6b7280",   # 灰
        "bg_color":     "#f3f4f6",
        "border_color": "#4b5563",
        "icon":         "⏹",
        "description":  "模具已下线，机台停止运行",
    },
}


# ---------------------------------------------------------------------------
# MachineStateMachine 类
# ---------------------------------------------------------------------------

class MachineStateMachine:
    """
    机台状态机

    使用方式（业务层必须调用此类，不得直接 UPDATE machines.status）：

        sm = MachineStateMachine(current_state="pending_check")

        # 技术人员到场
        ok, msg, next_state = sm.trigger("tech_intervene", actor="tech")
        # → (True, "技术人员到场介入", MachineState.REPAIRING)

        # 维修完成
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

    # ------------------------------------------------------------------ action mapping

    @staticmethod
    def _resolve_action(
        action: str,
        actor: str,
    ) -> str:
        """将 actor 映射到具体 action key，同时做基础校验。"""
        return action

    # ------------------------------------------------------------------ trigger

    def trigger(
        self,
        action: str,
        actor: str,
    ) -> Tuple[bool, str, Optional[MachineState]]:
        """
        触发状态跳转。

        参数
        ----
        action : str
            操作动作标识：
            - "apply_repair"            生产操作员申请修理
            - "tech_intervene"          技术人员到场介入
            - "complete_repair_online"  在线修复完成
            - "confirm_mold_offline"    确认拆模下线
            - "force_reset"             组长强制重置
        actor : str
            执行者角色："prod_worker" | "tech" | "prod_leader"

        返回
        ----
        (success: bool, message: str, next_state: MachineState | None)
        """
        key = (self.current_state, action)

        # 查找跳转目标
        next_state = _TRANSITIONS.get(key)

        if next_state is None:
            valid_actions = [
                a for (s, a) in _TRANSITIONS
                if s == self.current_state
            ]
            meta = STATE_META.get(self.current_state, {})
            label = meta.get("label", self.current_state.value)
            return (
                False,
                f"当前状态【{label}】不允许执行【{action}】。"
                f"可选操作: {valid_actions}",
                None,
            )

        # 获取业务描述
        info: Transition = _TRANSITION_INFO.get(key)
        if info:
            message = info.label
            description = info.description
        else:
            message = action
            description = ""

        # 角色权限校验（仅记录警告，不阻断，权限校验留给业务层）
        role_allowed = self._check_role(action, actor)
        if not role_allowed:
            return (
                False,
                f"角色【{actor}】无权执行【{message}】（{description}）。"
                f"允许角色: {self._allowed_roles(action)}",
                None,
            )

        # 执行跳转
        self.current_state = next_state

        return True, message, next_state

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _check_role(action: str, actor: str) -> bool:
        """简单角色白名单校验。业务层可覆盖此逻辑做更精细的权限判断。"""
        role_map: dict[str, set[str]] = {
            "apply_repair":            {"prod_worker", "prod_leader", "admin"},
            "tech_intervene":          {"tech", "admin"},
            "complete_repair_online":  {"tech", "admin"},
            "confirm_mold_offline":    {"tech", "admin"},
            "force_reset":             {"prod_leader", "admin"},
        }
        allowed = role_map.get(action, set())
        return actor in allowed or actor == "admin"

    @staticmethod
    def _allowed_roles(action: str) -> list[str]:
        role_map: dict[str, set[str]] = {
            "apply_repair":            {"prod_worker", "prod_leader", "admin"},
            "tech_intervene":          {"tech", "admin"},
            "complete_repair_online":  {"tech", "admin"},
            "confirm_mold_offline":    {"tech", "admin"},
            "force_reset":             {"prod_leader", "admin"},
        }
        return sorted(role_map.get(action, set()))

    # ------------------------------------------------------------------ queries

    def is_production_locked(self) -> bool:
        """生产锁定：pending_check / repairing / offline 均不允许报工。"""
        return self.current_state in (
            MachineState.PENDING_CHECK,
            MachineState.REPAIRING,
            MachineState.OFFLINE,
        )

    def is_under_repair(self) -> bool:
        """技术人员已介入维修。"""
        return self.current_state == MachineState.REPAIRING

    def is_running(self) -> bool:
        """正常运行，可正常报工。"""
        return self.current_state == MachineState.RUNNING

    @staticmethod
    def get_state_meta(state: str | MachineState) -> dict:
        """获取状态元数据（颜色、标签等）。"""
        if isinstance(state, str):
            state = MachineState(state)
        return STATE_META.get(state, {
            "label":        state.value if isinstance(state, MachineState) else str(state),
            "color":        "#6b7280",
            "bg_color":     "#f3f4f6",
            "border_color": "#4b5563",
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
        """返回当前状态下给定角色可执行的动作列表。"""
        return [
            action
            for (state, action) in _TRANSITIONS
            if state == self.current_state
            and MachineStateMachine._check_role(action, actor)
        ]
