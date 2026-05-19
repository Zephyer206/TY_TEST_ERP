"""
app/models/constants.py
======================
全系统业务常量 — 按领域分组。

使用规则
--------
所有 services 在导入状态枚举时，必须从本文件引入，
禁止在各自文件内重复定义相同常量值。

状态值定义（§8 / §2.3 / §4 状态机）
"""

# ============================================================================
# 机台维保流（state_machine.py 对应枚举 + 本文件数值保证唯一）
# ============================================================================
# 规则定义：running -> pending_check -> repairing -> running/offline
EQ_STATUS_IDLE          = "IDLE"
EQ_STATUS_RUNNING       = "RUNNING"
EQ_STATUS_PENDING_CHECK = "PENDING_CHECK"
EQ_STATUS_REPAIRING     = "REPAIRING"
EQ_STATUS_OFFLINE       = "OFFLINE"
EQ_STATUS_PROTOTYPING   = "PROTOTYPING"

# 报工熔断集合（.cursorrules §8 刚性卡控）
# 非 RUNNING/PROTOTYPING/IDLE 态均禁止报工写入
EQ_LOCKED_STATES = {
    EQ_STATUS_REPAIRING,
    EQ_STATUS_PENDING_CHECK,
    EQ_STATUS_OFFLINE,
}

# 机台两扫制动作标签（与 state_machine.py 同步）
EQ_ACTION_APPLY_REPAIR         = "apply_repair"
EQ_ACTION_TECH_INTERVENE       = "tech_intervene"
EQ_ACTION_COMPLETE_ONLINE      = "complete_repair_online"
EQ_ACTION_CONFIRM_MOLD_OFFLINE = "confirm_mold_offline"
EQ_ACTION_FORCE_RESET          = "force_reset"


# ============================================================================
# 模具生命周期
# ============================================================================
MOLD_STATUS_AVAILABLE   = "AVAILABLE"
MOLD_STATUS_IN_USE       = "IN_USE"
MOLD_STATUS_MAINTENANCE  = "MAINTENANCE"
MOLD_STATUS_CONVERTED    = "CONVERTED"
MOLD_STATUS_SCRAPPED      = "SCRAPPED"


# ============================================================================
# 工单生命周期
# ============================================================================
WO_PENDING   = "PENDING"
WO_SCHEDULED = "SCHEDULED"
WO_RUNNING   = "RUNNING"
WO_PAUSED    = "PAUSED"
WO_COMPLETED = "COMPLETED"


# ============================================================================
# 维修双轨模式（§8.2）
# ============================================================================
REPAIR_MODE_MACHINE          = "MACHINE_REPAIR"
REPAIR_MODE_MOLD_DISMOUNTED  = "MOLD_DISMOUNTED"
REPAIR_MODE_MOLD_ON_MACHINE  = "MOLD_ON_MACHINE"


# ============================================================================
# 零件生命周期（quotes.approval_status）
# ============================================================================
QUOTE_STATUS_DRAFT        = "DRAFT"
QUOTE_STATUS_PENDING_BOSS = "PENDING_BOSS"
QUOTE_STATUS_APPROVED     = "APPROVED"
QUOTE_STATUS_REJECTED     = "REJECTED"

# 零件生命周期（parts.part_status）
PART_STATUS_DRAFT             = "DRAFT"
PART_STATUS_SAMPLING          = "SAMPLING"
PART_STATUS_MASS_PROD        = "MASS_PRODUCTION"
PART_STATUS_OBSOLETE         = "OBSOLETE"
PART_STATUS_WAITING_APPROVAL  = "WAITING_FOR_APPROVAL"


# ============================================================================
# 原料批次生命周期
# ============================================================================
MAT_BATCH_AVAILABLE = "AVAILABLE"
MAT_BATCH_IN_USE    = "IN_USE"
MAT_BATCH_CONSUMED  = "CONSUMED"
MAT_BATCH_DEPLETED  = "DEPLETED"
MAT_BATCH_SCRAPPED  = "SCRAPPED"


# ============================================================================
# 发货单状态
# ============================================================================
DN_STATUS_DRAFT     = "DRAFT"
DN_STATUS_SHIPPED   = "SHIPPED"
DN_STATUS_DELIVERED = "DELIVERED"
DN_STATUS_CANCELLED = "CANCELLED"


# ============================================================================
# 质检结果
# ============================================================================
QA_RESULT_PASSED = "PASSED"
QA_RESULT_FAILED = "FAILED"
QA_RESULT_PENDING = "PENDING"


# ============================================================================
# QA 审计动作类型（qa_audit_logs.action_type）
# ============================================================================
QA_ACTION_FIRST_PIECE   = "first_piece_release"
QA_ACTION_EMERGENCY    = "emergency_release"


# ============================================================================
# 生产会话状态（production_sessions.status）
# ============================================================================
SESSION_RUNNING             = "RUNNING"
SESSION_PENDING_REPORT      = "PENDING_REPORT"
SESSION_CLOSED              = "CLOSED"
SESSION_ABNORMAL_TERMINATED = "ABNORMAL_TERMINATED"


# ============================================================================
# 生产会话类型（production_sessions.session_type）
# ============================================================================
SESSION_TYPE_CONTINUOUS = "Continuous"
SESSION_TYPE_SIMPLE     = "Simple"
SESSION_TYPE_PROTOTYPE  = "Prototype"


