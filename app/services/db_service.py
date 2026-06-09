import re
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "124.222.29.229",
    "port": "5432"
}


# --- 用户验证 ---
def verify_user(username, password):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s AND password = %s;", (username, password))
            row = cur.fetchone()
            if row:
                row = dict(row)
                row["is_superadmin"] = bool(row.get("is_superadmin")) or (int(row.get("role_level", 1)) >= 9)
            return row


def verify_user_by_id(user_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
            row = cur.fetchone()
            if row:
                row = dict(row)
                row["is_superadmin"] = bool(row.get("is_superadmin")) or (int(row.get("role_level", 1)) >= 9)
            return row

# --- 零件管理 ---
def get_all_parts(user_role_level):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT *, internal_name AS part_name FROM parts ORDER BY id DESC;")
            return cur.fetchall()

# ============================================================================
# 模具管理
# ============================================================================

def add_die(mold_number, mold_name="", cavity_count=1, press_tonnage="", remark=""):
    """新建模具主档，mold_number 唯一，重复则跳过"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM dies WHERE mold_number = %s;", (mold_number,))
            if cur.fetchone():
                return  # 已存在，跳过
            cur.execute("""
                INSERT INTO dies (mold_number, mold_name, cavity_count, press_tonnage, remark)
                VALUES (%s, %s, %s, %s, %s)
            """, (mold_number, mold_name, cavity_count, press_tonnage, remark))
            conn.commit()

def get_all_dies():
    """返回所有模具，带已关联零件数量"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT m.*,
                       COUNT(mp.id) AS linked_part_count
                FROM dies m
                LEFT JOIN die_parts mp ON m.id = mp.die_id
                GROUP BY m.id
                ORDER BY m.id DESC;
            """)
            return cur.fetchall()

def get_die_by_id(mold_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM dies WHERE id = %s;", (mold_id,))
            return cur.fetchone()

def update_die(mold_id, mold_name=None, cavity_count=None,
                press_tonnage=None, status=None, remark=None):
    """按字段更新模具，不传参数则跳过该字段"""
    fields = []
    vals = []
    if mold_name is not None:
        fields.append("mold_name = %s"); vals.append(mold_name)
    if cavity_count is not None:
        fields.append("cavity_count = %s"); vals.append(cavity_count)
    if press_tonnage is not None:
        fields.append("press_tonnage = %s"); vals.append(press_tonnage)
    if status is not None:
        fields.append("status = %s"); vals.append(status)
    if remark is not None:
        fields.append("remark = %s"); vals.append(remark)
    if not fields:
        return
    vals.append(mold_id)
    sql = "UPDATE dies SET " + ", ".join(fields) + " WHERE id = %s"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, vals)
            conn.commit()

def delete_die(mold_id):
    """删除模具（级联删除 die_parts 关联）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dies WHERE id = %s;", (mold_id,))
            conn.commit()


# ============================================================================
# 模具-零件关联管理（多对多）
# ============================================================================

def link_die_part(die_id, part_id, product_number="", seq_order=0):
    """建立模具与零件的关联，重复关联则忽略"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM die_parts
                WHERE die_id = %s AND part_id = %s;
            """, (die_id, part_id))
            if cur.fetchone():
                return  # 已存在
            cur.execute("""
                INSERT INTO die_parts (die_id, part_id, product_number, seq_order)
                VALUES (%s, %s, %s, %s)
            """, (die_id, part_id, product_number, seq_order))
            conn.commit()

def unlink_die_part(die_id, part_id):
    """解除模具与零件的关联"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM die_parts
                WHERE die_id = %s AND part_id = %s;
            """, (die_id, part_id))
            conn.commit()

def get_dies_by_part(part_id):
    """查某零件关联了哪些模具（返回模具主档信息 + 关联元数据）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT m.*, mp.product_number, mp.seq_order
                FROM dies m
                JOIN die_parts mp ON m.id = mp.die_id
                WHERE mp.part_id = %s
                ORDER BY mp.seq_order;
            """, (part_id,))
            return cur.fetchall()

def get_parts_by_die(die_id):
    """查某模具关联了哪些零件（返回零件主档信息 + 关联元数据）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, mp.product_number, mp.seq_order
                FROM parts p
                JOIN die_parts mp ON p.id = mp.part_id
                WHERE mp.die_id = %s
                ORDER BY mp.seq_order;
            """, (die_id,))
            return cur.fetchall()


# ============================================================================
# 穴数辅助：给定零件 ID，计算含穴数的有效工序单价
# ============================================================================

def calc_effective_price(part_id, base_price):
    """
    根据零件关联的模具穴数，计算有效工序单价。
    若零件无关联模具或穴数为 0/空，默认按 1 计算（单穴模具）。
    多副模具时取最大 cavity_count（最保守估算）。
    """
    dies = get_dies_by_part(part_id)
    if not dies:
        return base_price  # 无模具信息，按原单价计
    max_cavity = max((m.get('cavity_count') or 1) for m in dies)
    if max_cavity <= 0:
        max_cavity = 1
    return round(base_price / max_cavity, 4)


# ============================================================================
# 基础增删改
# ============================================================================

def add_new_part(num, name):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO parts (part_number, internal_name) VALUES (%s, %s)", (num, name))
            conn.commit()

# --- 按 ID 获取单个零件 ---
def get_part_by_id(part_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM parts WHERE id = %s;", (part_id,))
            return cur.fetchone()


# ============================================================================
# 机台管理 (machines)
# ============================================================================

def get_all_machines():
    """返回所有机台，带当前模具/零件/操作员/当前计划信息及异常状态"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    m.id, m.machine_number, m.machine_name, m.press_tonnage,
                    m.status, m.current_mold_id, m.current_part_id,
                    m.current_operator_id, m.remark, m.active_plan_id,
                    m.fault_reason, m.fault_reported_at,
                    m.tech_arrival_time, m.diagnosing_start_time, m.mold_offline_time,
                    mo.mold_number AS current_mold_number,
                    mo.mold_name   AS current_mold_name,
                    pt.part_number AS current_part_number,
                    pt.internal_name   AS current_part_name,
                    u.real_name    AS current_operator_name,
                    pp.part_id     AS active_part_id,
                    pt2.part_number AS active_part_number,
                    pt2.internal_name   AS active_part_name,
                    pp.total_qty    AS active_plan_total_qty,
                    pp.progress_qty AS active_plan_progress_qty
                FROM machines m
                LEFT JOIN dies  mo  ON m.current_mold_id    = mo.id
                LEFT JOIN parts  pt  ON m.current_part_id    = pt.id
                LEFT JOIN users  u   ON m.current_operator_id = u.id
                LEFT JOIN production_plans pp ON m.active_plan_id = pp.id
                LEFT JOIN parts pt2 ON pp.part_id = pt2.id
                ORDER BY m.machine_number;
            """)
            return cur.fetchall()


def get_machine_by_id(machine_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT m.*,
                    mo.mold_number  AS current_mold_number,
                    pt.part_number  AS current_part_number,
                    u.real_name     AS current_operator_name,
                    pp.part_id      AS active_part_id,
                    pt2.part_number AS active_part_number,
                    pt2.internal_name   AS active_part_name,
                    pp.total_qty    AS active_plan_total_qty,
                    pp.progress_qty AS active_plan_progress_qty
                FROM machines m
                LEFT JOIN dies mo ON m.current_mold_id  = mo.id
                LEFT JOIN parts pt ON m.current_part_id  = pt.id
                LEFT JOIN users u  ON m.current_operator_id = u.id
                LEFT JOIN production_plans pp ON m.active_plan_id = pp.id
                LEFT JOIN parts pt2 ON pp.part_id = pt2.id
                WHERE m.id = %s;
            """, (machine_id,))
            return cur.fetchone()


def resolve_machine_id_by_key(key):
    """根据机台编号或名称模糊查找机台 ID。返回 int 或 None。"""
    if not key:
        return None
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM machines
                WHERE LOWER(machine_number) = LOWER(%s)
                   OR LOWER(machine_name)  = LOWER(%s)
                LIMIT 1;
            """, (key.strip(), key.strip()))
            row = cur.fetchone()
            return row[0] if row else None


def add_machine(machine_number, machine_name='', press_tonnage='',
                remark='', current_mold_id=None):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM machines WHERE machine_number = %s;", (machine_number,))
            if cur.fetchone():
                return
            cur.execute("""
                INSERT INTO machines (machine_number, machine_name, press_tonnage, remark, current_mold_id)
                VALUES (%s, %s, %s, %s, %s);
            """, (machine_number, machine_name, press_tonnage, remark, current_mold_id))
            conn.commit()


def update_machine(machine_id, machine_name=None, press_tonnage=None,
                   status=None, remark=None, current_mold_id=None,
                   current_part_id=None, current_operator_id=None,
                   fault_reason=None, clear_fault=None,
                   tech_arrival_time=None, diagnosing_start_time=None,
                   mold_offline_time=None, clear_tech_timestamps=None):
    """
    更新机台信息。
    clear_fault=True 时，清空 fault_reason 和 fault_reported_at。
    clear_tech_timestamps=True 时，清空 tech_arrival_time / diagnosing_start_time / mold_offline_time。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            kwargs = {}
            for k, v in [
                ('machine_name', machine_name),
                ('press_tonnage', press_tonnage),
                ('status', status),
                ('remark', remark),
                ('current_mold_id', current_mold_id),
                ('current_part_id', current_part_id),
                ('current_operator_id', current_operator_id),
                ('fault_reason', fault_reason),
                ('tech_arrival_time', tech_arrival_time),
                ('diagnosing_start_time', diagnosing_start_time),
                ('mold_offline_time', mold_offline_time),
            ]:
                if v is not None:
                    kwargs[k] = v
            if clear_fault:
                kwargs['fault_reason'] = ''
                kwargs['fault_reported_at'] = None
            if clear_tech_timestamps:
                kwargs['tech_arrival_time'] = None
                kwargs['diagnosing_start_time'] = None
                kwargs['mold_offline_time'] = None
            if not kwargs:
                return
            sets = ', '.join(f"{k}=%s" for k in kwargs)
            vals = list(kwargs.values()) + [machine_id]
            cur.execute(f"UPDATE machines SET {sets}, updated_at=NOW() WHERE id=%s;", vals)
            conn.commit()


def request_machine_repair(machine_id, reporter_id):
    """
    【申请修理 — V3.0 §2.1 流程锁】
    操作工发现异常 → 申请修理 → 机台状态从 running 跳转至 pending_check。
    报工锁定：pending_check / repairing / offline 均无法提交报工。

    参数
    ----
    machine_id : int   机台 ID
    reporter_id : int  申请人（操作工）用户 ID

    约束
    ----
    - 状态必须当前为 running，方可跳转 pending_check。
      pending_check / repairing / offline 状态重复申请均被拒绝。
    - 记录 fault_reported_at 时间戳（到岗时间）。
    - 严禁在业务代码中直接 UPDATE status，必须经此函数。

    返回
    ----
    (success: bool, message: str)
    """
    from app.services.state_machine import MachineStateMachine, MachineState

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 先查询当前状态
            cur.execute(
                "SELECT id, status FROM machines WHERE id = %s FOR UPDATE;",
                (machine_id,)
            )
            row = cur.fetchone()
            if not row:
                return False, f"机台 ID {machine_id} 不存在"

            current_status = row['status']
            sm = MachineStateMachine(current_status)
            ok, message, _ = sm.trigger("apply_repair", actor="prod_worker")

            if not ok:
                return False, message

            # 写入 pending_check（apply_repair 从 running → pending_check）
            cur.execute("""
                UPDATE machines
                SET status = %s,
                    fault_reported_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """, (MachineState.PENDING_CHECK.value, machine_id))
            result = cur.fetchone()
            conn.commit()
            if not result:
                return False, f"机台 ID {machine_id} 更新失败"
            return True, f"申请修理成功，机台已进入待修状态"


def start_machine_repair(machine_id, tech_id):
    """
    【维修介入 — V3.0 §2.1 介入即维修】
    技术人员扫码到场 → 状态由 pending_check 跳转至 repairing。
    记录 tech_arrival_time（到场时间）。

    参数
    ----
    machine_id : int   机台 ID
    tech_id    : int   技术人员用户 ID

    约束
    ----
    - 仅 pending_check 状态可介入（running / offline 可直接扫码入场，但
      pending_check → repairing 是标准路径）。
    - repairing 状态不可重复介入。
    - 记录 tech_arrival_time / diagnosing_start_time。

    返回
    ----
    (success: bool, message: str)
    """
    from app.services.state_machine import MachineStateMachine, MachineState

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, status FROM machines WHERE id = %s FOR UPDATE;",
                (machine_id,)
            )
            row = cur.fetchone()
            if not row:
                return False, f"机台 ID {machine_id} 不存在"

            sm = MachineStateMachine(row['status'])
            ok, message, _ = sm.trigger("tech_intervene", actor="tech")

            if not ok:
                return False, message

            cur.execute("""
                UPDATE machines
                SET status = %s,
                    tech_arrival_time = NOW(),
                    diagnosing_start_time = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """, (MachineState.REPAIRING.value, machine_id))
            result = cur.fetchone()
            conn.commit()
            if not result:
                return False, f"机台 ID {machine_id} 更新失败"
            return True, f"维修介入成功，机台已进入维修状态"


def finalize_repair_decision(machine_id, tech_id, decision):
    """
    【维修终裁 — V3.0 §2.1 二选一终审】
    技术人员做出最终裁决，必须从以下选项中选择一个：

    decision   →  状态跳转
    -------------------------------------------------
    'online_fix' → running    【在线修复完成】机台恢复正常
    'offline'    → offline     【拆模下线】模具返修，机台停机

    参数
    ----
    machine_id : int    机台 ID
    tech_id    : int    技术人员用户 ID
    decision   : str    'online_fix' | 'offline'

    约束
    ----
    - 机台当前必须处于 repairing 状态方可终裁。
    - 终裁后清空所有维修时间戳（tech_arrival_time 等）。
    - 'offline' 裁决须额外断开机台与当前生产计划的关联。

    返回
    ----
    (success: bool, message: str)
    """
    from app.services.state_machine import MachineStateMachine, MachineState

    if decision not in ("online_fix", "offline"):
        return False, f"未知裁决类型: {decision}，仅支持 'online_fix' 或 'offline'"

    action_map = {
        "online_fix": "complete_repair_online",
        "offline":    "confirm_mold_offline",
    }
    target_state_map = {
        "online_fix": MachineState.RUNNING,
        "offline":    MachineState.OFFLINE,
    }
    action = action_map[decision]
    target_state = target_state_map[decision]

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, status FROM machines WHERE id = %s FOR UPDATE;",
                (machine_id,)
            )
            row = cur.fetchone()
            if not row:
                return False, f"机台 ID {machine_id} 不存在"

            sm = MachineStateMachine(row['status'])
            ok, message, _ = sm.trigger(action, actor="tech")

            if not ok:
                return False, message

            # 更新机台状态 + 清空维修时间戳
            cur.execute("""
                UPDATE machines
                SET status = %s,
                    fault_reason = '',
                    fault_reported_at = NULL,
                    tech_arrival_time = NULL,
                    diagnosing_start_time = NULL,
                    mold_offline_time = NULL,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """, (target_state.value, machine_id))

            # 'offline' 时断开当前生产计划关联
            if decision == "offline":
                cur.execute("""
                    UPDATE plans
                    SET status = 'suspended'
                    WHERE machine_id = %s
                      AND status = 'in_progress';
                """, (machine_id,))

            result = cur.fetchone()
            conn.commit()
            if not result:
                return False, f"机台 ID {machine_id} 终裁更新失败"

            label = "在线修复完成，机台已恢复正常运行" if decision == "online_fix" \
                else "拆模下线完成，机台已停机"
            return True, label


def reset_machine_fault(machine_id, reset_by):
    """
    组长强制重置（force_reset）：将机台状态强制恢复为 'running'。
    V3.0 §2.1：组长在 pending_check / offline 状态下可强制恢复运行。

    reset_by: 重置人 ID（日志用）
    """
    from app.services.state_machine import MachineStateMachine, MachineState

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, status FROM machines WHERE id = %s FOR UPDATE;",
                (machine_id,)
            )
            row = cur.fetchone()
            if not row:
                return False, f"机台 ID {machine_id} 不存在"

            sm = MachineStateMachine(row['status'])
            ok, msg, _ = sm.trigger("force_reset", actor="prod_leader")
            if not ok:
                return False, msg

            cur.execute("""
                UPDATE machines
                SET status = %s,
                    fault_reason = '',
                    fault_reported_at = NULL,
                    tech_arrival_time = NULL,
                    diagnosing_start_time = NULL,
                    mold_offline_time = NULL,
                    updated_at = NOW()
                WHERE id = %s;
            """, (MachineState.RUNNING.value, machine_id))
            conn.commit()
            return True, "机台已强制恢复运行"


def get_machines_with_faults():
    """
    返回所有维修锁定状态的机台（pending_check / repairing / offline），
    供看板高亮使用。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT m.id, m.machine_number, m.machine_name,
                       m.status, m.fault_reason, m.fault_reported_at,
                       u.real_name AS fault_reporter_name
                FROM machines m
                LEFT JOIN users u ON m.current_operator_id = u.id
                WHERE m.status IN ('pending_check', 'repairing', 'offline')
                ORDER BY m.fault_reported_at DESC;
            """)
            return cur.fetchall()


def tech_intervene(machine_id, tech_user_id=None):
    """
    模修员工扫码介入 pending_check 机台 → 直接进入 repairing 状态。
    - 记录 tech_arrival_time（到场时间）
    - 状态置为 repairing
    仅 dept='tech' 用户（is_tech=TRUE）可调用。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE machines
                SET status = 'repairing',
                    tech_arrival_time = NOW(),
                    diagnosing_start_time = NOW(),
                    updated_at = NOW()
                WHERE id = %s AND status = 'pending_check';
            """, (machine_id,))
            conn.commit()


def tech_complete_fix(machine_id):
    """
    【在线修复完成】：机台恢复正常运行（running）。
    清空所有维修相关时间戳，故障原因保留供后续分析。
    仅在 repairing 状态下可操作。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE machines
                SET status = 'running',
                    fault_reason = '',
                    fault_reported_at = NULL,
                    tech_arrival_time = NULL,
                    diagnosing_start_time = NULL,
                    mold_offline_time = NULL,
                    updated_at = NOW()
                WHERE id = %s AND status = 'repairing';
            """, (machine_id,))
            conn.commit()


def tech_confirm_mold_offline(machine_id):
    """
    【确认拆模下线】：模具下线，机台置为 offline。
    断开该机台与当前生产计划的关联，模具返回仓库待修。
    仅在 repairing 状态下可操作。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            now = datetime.datetime.now()
            cur.execute("""
                UPDATE machines
                SET status = 'offline',
                    mold_offline_time = NOW(),
                    current_mold_id = NULL,
                    active_plan_id = NULL,
                    current_part_id = NULL,
                    updated_at = %s
                WHERE id = %s AND status = 'repairing';
            """, (now, machine_id))
            conn.commit()


def set_machine_pending_check(machine_id):
    """
    将机台标记为 pending_check（等待开发人员到场诊断）。
    由报修流程触发（如故障处理路径变更）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE machines SET status='pending_check', updated_at=NOW()
                WHERE id=%s AND status IN ('fault', 'pending_check');
            """, (machine_id,))
            conn.commit()


def get_tech_time_analytics():
    """
    看板时效分析：
    - 从'报修'到'开发扫码'的平均/最长响应时间
    - 从'到场'到'诊断完成'（修复或拆模）的平均/最长处理时间
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 报修→到场响应时间统计（有 tech_arrival_time 的记录）
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE tech_arrival_time IS NOT NULL)         AS total_intervened,
                    AVG(EXTRACT(EPOCH FROM (tech_arrival_time - fault_reported_at))) FILTER (WHERE tech_arrival_time IS NOT NULL) AS avg_response_min,
                    MAX(EXTRACT(EPOCH FROM (tech_arrival_time - fault_reported_at))) FILTER (WHERE tech_arrival_time IS NOT NULL) AS max_response_min,
                    COUNT(*) FILTER (WHERE mold_offline_time IS NOT NULL)           AS total_mold_offline,
                    AVG(EXTRACT(EPOCH FROM (mold_offline_time - tech_arrival_time))) FILTER (WHERE mold_offline_time IS NOT NULL AND tech_arrival_time IS NOT NULL) AS avg_diagnosis_min,
                    MAX(EXTRACT(EPOCH FROM (mold_offline_time - tech_arrival_time))) FILTER (WHERE mold_offline_time IS NOT NULL AND tech_arrival_time IS NOT NULL) AS max_diagnosis_min,
                    COUNT(*) FILTER (WHERE status = 'running' AND diagnosing_start_time IS NOT NULL AND mold_offline_time IS NULL) AS total_fixed
                FROM machines
                WHERE fault_reported_at IS NOT NULL;
            """)
            row = cur.fetchone()

            # 近期响应时间明细（最近 10 条）
            cur.execute("""
                SELECT
                    machine_number,
                    fault_reported_at,
                    tech_arrival_time,
                    diagnosing_start_time,
                    mold_offline_time,
                    status,
                    EXTRACT(EPOCH FROM (tech_arrival_time - fault_reported_at)) / 60 AS response_min,
                    CASE
                        WHEN mold_offline_time IS NOT NULL AND tech_arrival_time IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (mold_offline_time - tech_arrival_time)) / 60
                        WHEN status = 'running' AND diagnosing_start_time IS NOT NULL AND mold_offline_time IS NULL
                        THEN EXTRACT(EPOCH FROM (diagnosing_start_time - diagnosing_start_time)) / 60
                        ELSE NULL
                    END AS diagnosis_min
                FROM machines
                WHERE fault_reported_at IS NOT NULL
                ORDER BY fault_reported_at DESC
                LIMIT 10;
            """)
            recent = cur.fetchall()

            return {
                'stats': row,
                'recent': recent,
            }


def bind_mold_to_machine(machine_id, mold_id):
    """将模具绑定到机台"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE machines
                SET current_mold_id = %s, status = 'idle', updated_at = NOW()
                WHERE id = %s;
            """, (mold_id, machine_id))
            conn.commit()


def set_machine_active_plan(machine_id, plan_id, operator_id):
    """
    组长切换机台当前任务。

    逻辑：
    1. 将旧 plan_machines.status → 'inactive'
    2. 将新 plan_machines.status → 'active'
    3. machines.active_plan_id → 新 plan_id
    4. machines.current_part_id → 新零件 ID
    5. plan_machines 若不存在则 INSERT

    返回：(ok: bool, message: str)
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 校验 plan 存在
            cur.execute("SELECT id, part_id, status FROM production_plans WHERE id=%s;", (plan_id,))
            plan = cur.fetchone()
            if not plan:
                return False, "生产计划不存在"
            if plan[2] == 'completed':
                return False, "该计划已完成，无法切换"

            # 1. 将该机台所有旧关联置为 inactive
            cur.execute("""
                UPDATE plan_machines
                SET status = 'inactive'
                WHERE machine_id = %s;
            """, (machine_id,))

            # 2. 若关联已存在则激活，否则新建
            cur.execute("""
                SELECT 1 FROM plan_machines WHERE plan_id=%s AND machine_id=%s;
            """, (plan_id, machine_id))
            if cur.fetchone():
                cur.execute("""
                    UPDATE plan_machines
                    SET status='active', assigned_at=NOW(), assigned_by=%s
                    WHERE plan_id=%s AND machine_id=%s;
                """, (operator_id, plan_id, machine_id))
            else:
                cur.execute("""
                    INSERT INTO plan_machines (plan_id, machine_id, assigned_by, status)
                    VALUES (%s, %s, %s, 'active');
                """, (plan_id, machine_id, operator_id))

            # 3. 更新机台当前计划 + 当前零件
            cur.execute("""
                UPDATE machines
                SET active_plan_id = %s,
                    current_part_id = %s,
                    status = 'running',
                    updated_at = NOW()
                WHERE id = %s;
            """, (plan_id, plan[1], machine_id))

            conn.commit()
            return True, f"已切换至计划 #{plan_id}"


def check_machine_active_plan(machine_id, part_id):
    """
    报工前校验：零件 ID 是否与机台当前 active_plan 匹配。

    返回：(ok: bool, message: str)
      - ok=True  → 允许报工
      - ok=False → 拒绝，message 含具体原因
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.active_plan_id, pp.part_id, pp.plan_order, pp.urgency
                FROM machines m
                LEFT JOIN production_plans pp ON m.active_plan_id = pp.id
                WHERE m.id = %s;
            """, (machine_id,))
            row = cur.fetchone()
            if not row:
                return True, ""  # 无机台记录，放行

            active_plan_id, active_part_id = row[0], row[1]
            if active_plan_id is None:
                return True, ""  # 未设置活跃计划，放行

            if active_part_id != part_id:
                return False, "任务已切换，请刷新页面"
            return True, ""


# ============================================================================
# 生产计划排产 (production_plans)
# ============================================================================

def get_all_plans(filters=None, user_role_level=1):
    """
    返回生产计划列表。
    filters: {part_id, machine_id, status, urgency, keyword}
    machine_id 过滤：通过 plan_machines 关联表匹配。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
            if filters:
                if filters.get('part_id'):
                    conditions.append("pp.part_id = %s")
                    params.append(filters['part_id'])
                if filters.get('machine_id'):
                    conditions.append("""
                        EXISTS (
                            SELECT 1 FROM plan_machines pm2
                            WHERE pm2.plan_id = pp.id
                              AND pm2.machine_id = %s
                              AND pm2.status = 'active'
                        )
                    """)
                    params.append(filters['machine_id'])
                if filters.get('status'):
                    conditions.append("pp.status = %s")
                    params.append(filters['status'])
                if filters.get('urgency'):
                    conditions.append("pp.urgency = %s")
                    params.append(filters['urgency'])
                if filters.get('keyword'):
                    conditions.append("(pt.part_number ILIKE %s OR pt.internal_name ILIKE %s)")
                    kw = f"%{filters['keyword']}%"
                    params.extend([kw, kw])

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(f"""
                SELECT
                    pp.id, pp.part_id, pp.total_qty, pp.delivered_qty,
                    pp.due_date, pp.urgency, pp.plan_order,
                    pp.status, pp.remark, pp.force_order,
                    pp.assigned_at, pp.created_at,
                    pp.progress_qty,
                    pt.part_number, pt.internal_name AS part_name,
                    m.machine_number,
                    u.real_name AS assigned_by_name,
                    c.real_name AS created_by_name,
                    STRING_AGG(DISTINCT m2.machine_number, ', ')
                        FILTER (WHERE m2.machine_number IS NOT NULL)
                        AS assigned_machines,
                    COUNT(DISTINCT pm.machine_id)::INTEGER AS machine_count,
                    -- 故障机台信息
                    BOOL_OR(CASE WHEN m2.status = 'fault' THEN TRUE ELSE FALSE END) AS has_fault,
                    STRING_AGG(DISTINCT CASE WHEN m2.status = 'fault' THEN m2.machine_number || ':' || COALESCE(m2.fault_reason,'') ELSE NULL END, '; ')
                        FILTER (WHERE m2.status = 'fault')
                        AS fault_machines
                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                LEFT JOIN plan_machines pm ON pm.plan_id = pp.id AND pm.status = 'active'
                LEFT JOIN machines m2 ON pm.machine_id = m2.id
                LEFT JOIN machines m ON pp.machine_id = m.id
                LEFT JOIN users  u  ON pp.assigned_by = u.id
                LEFT JOIN users  c  ON pp.created_by = c.id
                {where}
                GROUP BY pp.id, pp.part_id, pt.part_number, pt.internal_name,
                         pp.total_qty, pp.delivered_qty, pp.due_date, pp.urgency,
                         pp.plan_order, pp.status, pp.remark, pp.force_order,
                         pp.assigned_at, pp.created_at, pp.progress_qty,
                         m.machine_number, u.real_name, c.real_name
                ORDER BY pp.force_order DESC,
                         pp.urgency = 'critical' DESC,
                         pp.urgency = 'urgent' DESC,
                         pp.plan_order ASC,
                         pp.due_date ASC;
            """, params)
            return cur.fetchall()


def get_plan_by_id(plan_id):
    """返回单个计划详情（含关联机台列表）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT pp.*,
                    pt.part_number, pt.internal_name,
                    u.real_name AS assigned_by_name,
                    c.real_name AS created_by_name
                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                LEFT JOIN users u ON pp.assigned_by = u.id
                LEFT JOIN users c ON pp.created_by = c.id
                WHERE pp.id = %s;
            """, (plan_id,))
            plan = cur.fetchone()

            if plan:
                # 查询关联机台列表
                cur.execute("""
                    SELECT m.id, m.machine_number, m.machine_name, m.status,
                           pm.assigned_at, pm.status AS link_status
                    FROM plan_machines pm
                    JOIN machines m ON pm.machine_id = m.id
                    WHERE pm.plan_id = %s
                    ORDER BY pm.status = 'active' DESC, pm.assigned_at DESC;
                """, (plan_id,))
                plan['machines'] = cur.fetchall()

            return plan


def create_plan(part_id, total_qty, due_date, urgency, created_by,
                machine_id=None, remark='', plan_order=0):
    """
    创建生产工单（刚性卡控版）。

    V3.1 §2.1 定点卡控：
      - 若零件 nomination_status 为 pending_nomination / nominated / Draft，
        严禁创建生产工单。
      - 仅 nomination_status='production_ready' 时允许。
    """
    # ── 定点卡控校验 ────────────────────────────────────────────────
    locked, msg = check_part_nomination_locked(part_id)
    if locked:
        raise PermissionError(msg)
    # ─────────────────────────────────────────────────────────────

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO production_plans
                    (part_id, total_qty, due_date, urgency,
                     machine_id, remark, plan_order, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id;
            """, (part_id, total_qty, due_date, urgency,
                  machine_id, remark, plan_order, created_by))
            new_id = cur.fetchone()[0]
            conn.commit()
            return new_id


def assign_plan_to_machine(plan_id, machine_id, assigned_by):
    """
    将机台关联到计划（通过 plan_machines 关联表）。
    一个计划可关联多个机台，同一机台同时只能关联一个活跃计划。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 查询该机台当前模具
            cur.execute("SELECT current_mold_id FROM machines WHERE id=%s;", (machine_id,))
            row = cur.fetchone()
            mold_id = row[0] if row else None

            # 将该机台的旧关联状态改为 inactive
            cur.execute("""
                UPDATE plan_machines
                SET status='inactive', assigned_at=NOW()
                WHERE machine_id=%s AND status='active'
                RETURNING id;
            """, (machine_id,))

            # 如果旧计划仅剩这一个机台关联，则标记该计划为 cancelled
            cur.execute("""
                UPDATE production_plans
                SET status='cancelled', updated_at=NOW()
                WHERE id = (
                    SELECT plan_id FROM plan_machines
                    WHERE machine_id=%s AND status='inactive'
                    AND plan_id=%s
                )
                AND status IN ('planned','in_progress')
                AND NOT EXISTS (
                    SELECT 1 FROM plan_machines
                    WHERE plan_id=%s AND status='active' AND machine_id!=%s
                )
                RETURNING id;
            """, (machine_id, plan_id, plan_id, machine_id))

            # 插入新关联
            cur.execute("""
                INSERT INTO plan_machines (plan_id, machine_id, assigned_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (plan_id, machine_id) DO UPDATE
                SET status='active', assigned_at=NOW(), assigned_by=%s;
            """, (plan_id, machine_id, assigned_by, assigned_by))

            # 更新计划状态为 in_progress
            cur.execute("""
                UPDATE production_plans
                SET status='in_progress', updated_at=NOW()
                WHERE id=%s AND status='planned';
            """, (plan_id,))

            # 更新机台状态为 running，并设置 active_plan_id
            cur.execute("""
                UPDATE machines
                SET active_plan_id = %s,
                    current_part_id = (SELECT part_id FROM production_plans WHERE id=%s),
                    status = 'running', updated_at = NOW()
                WHERE id = %s;
            """, (plan_id, plan_id, machine_id))
            conn.commit()


def update_plan_order(plan_id, new_order, updated_by=None, force=False):
    """
    调整计划排序（用于拖拽排序）。
    force=True 时（业务部 Level 5+ 强制干预），同时设置 force_order=TRUE。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if force:
                cur.execute("""
                    UPDATE production_plans
                    SET plan_order=%s, force_order=TRUE, updated_at=NOW()
                    WHERE id=%s;
                """, (new_order, plan_id))
            else:
                cur.execute("""
                    UPDATE production_plans
                    SET plan_order=%s, updated_at=NOW()
                    WHERE id=%s;
                """, (new_order, plan_id))
            conn.commit()


def cancel_plan(plan_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE production_plans SET status='cancelled', updated_at=NOW()
                WHERE id=%s;
            """, (plan_id,))
            cur.execute("""
                UPDATE plan_machines SET status='inactive'
                WHERE plan_id=%s;
            """, (plan_id,))
            cur.execute("""
                UPDATE machines SET active_plan_id=NULL, current_part_id=NULL
                WHERE active_plan_id=%s;
            """, (plan_id,))
            conn.commit()


def close_plan(plan_id, operator_id):
    """
    结案生产计划：
    1. 将 production_plans.status 改为 'closed'
    2. 将 plan_machines 全部置为 'inactive'
    3. 将关联机台的 active_plan_id / current_part_id 清空
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 获取关联机台
            cur.execute("""
                SELECT machine_id FROM plan_machines
                WHERE plan_id = %s AND status = 'active';
            """, (plan_id,))
            machine_ids = [r[0] for r in cur.fetchall()]

            # 结案计划
            cur.execute("""
                UPDATE production_plans
                SET status = 'closed', updated_at = NOW()
                WHERE id = %s;
            """, (plan_id,))

            # 取消所有机台关联
            if machine_ids:
                cur.executemany(
                    "UPDATE plan_machines SET status='inactive' WHERE plan_id=%s AND machine_id=%s;",
                    [(plan_id, mid) for mid in machine_ids]
                )
                # 清空机台的活跃任务
                cur.executemany(
                    "UPDATE machines SET active_plan_id=NULL, current_part_id=NULL WHERE id=%s;",
                    [(mid,) for mid in machine_ids]
                )

            conn.commit()
            return machine_ids


def get_plan_close_report(plan_id):
    """
    获取计划结案报告，包含超产统计。
    返回：(plan_info, production_summary, close_stats)
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 计划基本信息
            cur.execute("""
                SELECT pp.id, pp.part_id, pt.part_number, pt.internal_name AS part_name,
                       pp.total_qty, pp.progress_qty, pp.urgency, pp.due_date,
                       pp.status, pp.remark
                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                WHERE pp.id = %s;
            """, (plan_id,))
            plan = cur.fetchone()

            if not plan:
                return None, None, None

            # 产出汇总（按状态分组）
            cur.execute("""
                SELECT
                    SUM(qty_good)              AS total_output,
                    SUM(qty_bad)               AS total_scrap,
                    COUNT(*)                   AS log_count,
                    COUNT(CASE WHEN status='approved' THEN 1 END)  AS approved_count,
                    COUNT(CASE WHEN status='pending' THEN 1 END)   AS pending_count
                FROM production_logs
                WHERE plan_id = %s;
            """, (plan_id,))
            summary = dict(cur.fetchone())

            # 超产计算
            target = plan['total_qty'] or 0
            actual = plan['progress_qty'] or 0
            over_qty = max(actual - target, 0)
            over_pct = round(over_qty / target * 100, 1) if target > 0 else 0
            close_stats = {
                'target_qty':       target,
                'actual_output':     actual,
                'overproduction_qty': over_qty,
                'overproduction_pct': over_pct,
                'total_scrap':      summary['total_scrap'] or 0,
                'log_count':        summary['log_count'] or 0,
                'approved_count':   summary['approved_count'] or 0,
                'pending_count':    summary['pending_count'] or 0,
            }

            # 关联机台明细
            cur.execute("""
                SELECT m.machine_number,
                       SUM(pl.qty_good)  AS machine_output,
                       COUNT(pl.id)      AS report_count
                FROM plan_machines pm
                JOIN machines m ON pm.machine_id = m.id
                LEFT JOIN production_logs pl ON pl.plan_id = pm.plan_id AND pl.machine_id = pm.machine_id
                WHERE pm.plan_id = %s
                GROUP BY m.id, m.machine_number
                ORDER BY machine_output DESC NULLS LAST;
            """, (plan_id,))
            machine_detail = [dict(r) for r in cur.fetchall()]

            return plan, close_stats, machine_detail


def get_machine_plans(machine_id):
    """返回某机台的排产队列（通过 plan_machines 关联表，按 plan_order 排序）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT pp.*,
                    pt.part_number, pt.internal_name AS part_name,
                    mo.mold_number, mo.mold_name,
                    m.machine_number,
                    pp.progress_qty AS progress_qty,
                    COALESCE(sub.tot_good, 0)::INTEGER AS today_good
                FROM plan_machines pm
                JOIN production_plans pp ON pm.plan_id = pp.id
                JOIN parts pt ON pp.part_id = pt.id
                LEFT JOIN machines m ON pm.machine_id = m.id
                LEFT JOIN dies mo ON m.current_mold_id = mo.id
                LEFT JOIN LATERAL (
                    SELECT SUM(qty_good)::INTEGER AS tot_good
                    FROM production_logs pl
                    WHERE pl.plan_id = pp.id
                      AND pl.machine_id = %s
                      AND DATE(pl.report_time) = CURRENT_DATE
                ) sub ON TRUE
                WHERE pm.machine_id = %s
                  AND pm.status = 'active'
                  AND pp.status IN ('planned', 'in_progress')
                ORDER BY pp.force_order DESC, pp.plan_order ASC;
            """, (machine_id, machine_id))
            return cur.fetchall()


def get_active_plan_for_machine(machine_id):
    """返回某机台的当前激活计划（队列中排第一的）"""
    plans = get_machine_plans(machine_id)
    if not plans:
        return None
    # 返回 force_order 最高、plan_order 最小的
    return plans[0]


def get_progress_dashboard(date=None):
    """
    每日进度总览看板。
    date=None 时默认今日。
    返回：零件维度统计（目标/今日产出/累计产出/完成率/关联机台）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if date:
                target_date = f"'{date}'::date"
                date_filter = f"AND DATE(report_time) = '{date}'::date"
                date_col = f"'{date}'::date"
            else:
                target_date = "CURRENT_DATE"
                date_filter = "AND DATE(report_time) = CURRENT_DATE"
                date_col = "CURRENT_DATE"

            cur.execute(f"""
                SELECT
                    pp.id              AS plan_id,
                    pp.part_id,
                    pt.part_number,
                    pt.internal_name AS part_name,
                    pp.total_qty      AS target_qty,
                    pp.urgency,
                    pp.force_order,
                    pp.plan_order,
                    pp.status         AS plan_status,
                    pp.due_date,

                    -- 今日产出（所有关联机台的汇总）
                    COALESCE(sub.today_good, 0)::INTEGER  AS today_good,
                    COALESCE(sub.today_scrap, 0)::INTEGER AS today_scrap,

                    -- 累计产出（从 production_logs）
                    COALESCE(sub_all.total_all, 0)::INTEGER AS progress_qty,

                    -- 完成百分比（允许超产，不封顶）
                    CASE WHEN pp.total_qty > 0
                         THEN ROUND(
                             COALESCE(sub_all.total_all, 0)::NUMERIC
                             / pp.total_qty * 100, 1)
                         ELSE 0
                    END                AS completion_pct,

                    -- 超产数量
                    GREATEST(COALESCE(sub_all.total_all, 0)::INTEGER - pp.total_qty, 0) AS overproduction_qty,

                    -- 超产百分比
                    CASE WHEN pp.total_qty > 0
                         THEN ROUND(GREATEST(
                             COALESCE(sub_all.total_all, 0)::NUMERIC
                             / pp.total_qty * 100 - 100, 0)::NUMERIC, 1)
                         ELSE 0
                    END                AS overproduction_pct,

                    -- 关联机台列表
                    STRING_AGG(DISTINCT m.machine_number, ', ')
                        FILTER (WHERE m.machine_number IS NOT NULL)
                        AS assigned_machines,
                    COUNT(DISTINCT pm.machine_id)::INTEGER AS machine_count,

                -- 今日有效机台数（有报工的）
                    (
                        SELECT COUNT(DISTINCT machine_id)::INTEGER
                        FROM production_logs
                        WHERE plan_id = pp.id
                          AND DATE(report_time) = {date_col}
                    ) AS active_today,

                    -- 故障/异常机台数量（fault + pending_check + diagnosing 均算异常）
                    (
                        SELECT COUNT(*)::INTEGER
                        FROM plan_machines pm2
                        JOIN machines m2 ON pm2.machine_id = m2.id
                        WHERE pm2.plan_id = pp.id AND pm2.status = 'active'
                          AND m2.status IN ('fault', 'pending_check', 'repairing')
                    ) AS anomaly_count,
                    (EXISTS (
                        SELECT 1
                        FROM plan_machines pm2
                        JOIN machines m2 ON pm2.machine_id = m2.id
                        WHERE pm2.plan_id = pp.id AND pm2.status = 'active'
                          AND m2.status IN ('fault', 'pending_check', 'repairing')
                    )) AS has_anomaly

                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                LEFT JOIN plan_machines pm ON pm.plan_id = pp.id AND pm.status = 'active'
                LEFT JOIN machines m ON pm.machine_id = m.id

                -- 今日产出（所有关联机台）
                LEFT JOIN LATERAL (
                    SELECT
                        SUM(qty_good)::INTEGER  AS today_good,
                        SUM(qty_bad)::INTEGER   AS today_scrap
                    FROM production_logs
                    WHERE plan_id = pp.id
                    {date_filter}
                ) sub ON TRUE

                -- 累计产出
                LEFT JOIN LATERAL (
                    SELECT SUM(qty_good)::INTEGER AS total_all
                    FROM production_logs
                    WHERE plan_id = pp.id AND status = 'approved'
                ) sub_all ON TRUE

                WHERE pp.status IN ('planned', 'in_progress', 'completed', 'closed')
                  AND pp.total_qty > 0
                GROUP BY pp.id, pp.part_id, pt.part_number, pt.internal_name,
                         pp.total_qty, pp.urgency, pp.force_order, pp.plan_order,
                         pp.status, pp.due_date,
                         sub.today_good, sub.today_scrap, sub_all.total_all
                ORDER BY
                    pp.force_order DESC,
                    pp.urgency = 'critical' DESC,
                    pp.urgency = 'urgent' DESC,
                    pp.plan_order ASC,
                    (pp.due_date IS NOT NULL AND pp.due_date <= {target_date} + INTERVAL '3 days') DESC;
            """)
            return cur.fetchall()


def sync_plan_progress(plan_id):
    """同步计划的累计产出（从 production_logs 汇总）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE production_plans
                SET progress_qty = COALESCE(sub.tot, 0),
                    updated_at = NOW()
                FROM (
                    SELECT plan_id, SUM(qty_good)::INTEGER AS tot
                    FROM production_logs
                    WHERE plan_id = %s AND status = 'approved'
                    GROUP BY plan_id
                ) sub
                WHERE sub.plan_id = production_plans.id;
            """, (plan_id,))
            conn.commit()


# ============================================================================
# IQC 来料检验 (materials - iqc_status)
# ============================================================================

def submit_iqc(material_id, result, iqc_by, iqc_result=''):
    """
    提交 IQC 检验结果。
    result: 'qualified' | 'unqualified'
    同时更新：
      - iqc_status / iqc_result / iqc_by / iqc_at（历史兼容）
      - is_qc_confirmed：qualified → TRUE，unqualified → FALSE
      - material_status：与 result 保持一致
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            qc_flag = (result == 'qualified')
            cur.execute("""
                UPDATE materials
                SET iqc_status = %s,
                    iqc_result = %s,
                    iqc_by = %s,
                    iqc_at = NOW(),
                    material_status = %s,
                    is_qc_confirmed = %s,
                    qc_confirmed_by = %s
                WHERE id = %s;
            """, (result, iqc_result, iqc_by, result, qc_flag, iqc_by, material_id))
            conn.commit()


def get_materials_for_iqc(dept='whse'):
    """
    whse 可见：pending（橙色待检）
    qc 可见：全部 pending + 自己审核过的
    prod 可见：仅 qualified（绿色合格）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT mat.*,
                    u.real_name AS iqc_by_name,
                    (mat.original_width - mat.current_width) AS slit_width_used
                FROM materials mat
                LEFT JOIN users u ON mat.iqc_by = u.id
                ORDER BY mat.iqc_status='pending' DESC, mat.created_at DESC;
            """)
            return cur.fetchall()


def get_materials_for_iqc_incoming(status_filter=None):
    """
    品质部来料审核专用列表。
    支持双重确认状态过滤：both / whse_only / qc_only / none
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            base = """
                SELECT mat.*,
                    u1.real_name AS whse_confirmed_by_name,
                    u2.real_name AS qc_confirmed_by_name
                FROM materials mat
                LEFT JOIN users u1 ON mat.whse_confirmed_by = u1.id
                LEFT JOIN users u2 ON mat.qc_confirmed_by = u2.id
            """
            if status_filter == 'both':
                cur.execute(base + " WHERE mat.is_whse_confirmed AND mat.is_qc_confirmed ORDER BY mat.created_at DESC;")
            elif status_filter == 'whse_only':
                cur.execute(base + " WHERE mat.is_whse_confirmed AND NOT mat.is_qc_confirmed ORDER BY mat.created_at DESC;")
            elif status_filter == 'qc_only':
                cur.execute(base + " WHERE mat.is_qc_confirmed AND NOT mat.is_whse_confirmed ORDER BY mat.created_at DESC;")
            elif status_filter == 'none':
                cur.execute(base + " WHERE NOT mat.is_whse_confirmed AND NOT mat.is_qc_confirmed ORDER BY mat.created_at DESC;")
            else:
                cur.execute(base + " ORDER BY (mat.is_whse_confirmed OR mat.is_qc_confirmed) ASC, mat.created_at DESC;")
            return cur.fetchall()


def confirm_material_whse(material_id, whse_operator_id):
    """
    仓库确认原材料可用（is_whse_confirmed = TRUE）。
    whse_operator_id：确认人 ID
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE materials
                SET is_whse_confirmed = TRUE,
                    whse_confirmed_by = %s,
                    updated_at = NOW()
                WHERE id = %s;
            """, (whse_operator_id, material_id))
            conn.commit()


def get_materials_for_whse_confirmation(status_filter=None):
    """
    仓库确认页面：返回所有物料，带双重确认状态。
    支持过滤：both / whse_only / qc_only / none
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            base = """
                SELECT mat.*,
                    u1.real_name AS whse_confirmed_by_name,
                    u2.real_name AS qc_confirmed_by_name,
                    (mat.original_width - mat.current_width) AS slit_width_used
                FROM materials mat
                LEFT JOIN users u1 ON mat.whse_confirmed_by = u1.id
                LEFT JOIN users u2 ON mat.qc_confirmed_by = u2.id
            """
            if status_filter == 'both':
                cur.execute(base + " WHERE mat.is_whse_confirmed AND mat.is_qc_confirmed ORDER BY mat.is_active DESC, mat.created_at DESC;")
            elif status_filter == 'whse_only':
                cur.execute(base + " WHERE mat.is_whse_confirmed AND NOT mat.is_qc_confirmed ORDER BY mat.is_active DESC, mat.created_at DESC;")
            elif status_filter == 'qc_only':
                cur.execute(base + " WHERE mat.is_qc_confirmed AND NOT mat.is_whse_confirmed ORDER BY mat.is_active DESC, mat.created_at DESC;")
            elif status_filter == 'none':
                cur.execute(base + " WHERE NOT mat.is_whse_confirmed AND NOT mat.is_qc_confirmed ORDER BY mat.is_active DESC, mat.created_at DESC;")
            else:
                cur.execute(base + " ORDER BY mat.is_active DESC, (mat.is_whse_confirmed OR mat.is_qc_confirmed) ASC, mat.created_at DESC;")
            return cur.fetchall()


def get_machine_by_qr(qr_key):
    """通过二维码内容解析机台ID，返回机台信息"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 二维码内容格式：/machine/123 或 /m/123
            import re
            m = re.search(r'/(\d+)$', qr_key)
            if not m:
                return None
            machine_id = int(m.group(1))
            return get_machine_by_id(machine_id)


# 多穴权限：Level 9 / Level 4 / Level 2（开发）可看全部
# Level 3 及以下只能看 cavity_status = '已确认' 的记录
def _can_see_all_molds(role_level):
    return role_level in (9, 4, 2)


# ============================================================================
# 模具模块 (Tooling) - 新增
# ============================================================================

def get_all_tooling_molds(filters=None, user_role_level=1, limit=50, offset=0):
    """
    返回模具记录（支持按客户/关键词/mold_status 过滤，带分页）。
    mold_status 过滤对所有用户生效。
    Level 3/1：仅返回 cavity_status = '已确认' 的记录（多穴权限）。
    """
    sql = """
        SELECT tm.*, tc.name AS customer_name
        FROM tooling_molds tm
        LEFT JOIN tooling_customers tc ON tm.customer_id = tc.id
        WHERE 1=1
    """
    params = []
    # 多穴权限：Level 3/1 只能看已确认的记录
    if not _can_see_all_molds(user_role_level):
        sql += " AND tm.cavity_status = '已确认'"
    if filters:
        if filters.get("customer_id"):
            sql += " AND tm.customer_id = %s"
            params.append(filters["customer_id"])
        if filters.get("keyword"):
            sql += " AND (tm.mold_number ILIKE %s OR tm.customer_product_no ILIKE %s)"
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw])
        if filters.get("mold_status"):
            sql += " AND tm.mold_status = %s"
            params.append(filters["mold_status"])
    sql += " ORDER BY tm.id DESC"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def count_tooling_molds(filters=None, user_role_level=1):
    """统计符合条件的模具总数（用于分页）"""
    sql = "SELECT COUNT(*) FROM tooling_molds tm WHERE 1=1"
    params = []
    if not _can_see_all_molds(user_role_level):
        sql += " AND tm.cavity_status = '已确认'"
    if filters:
        if filters.get("customer_id"):
            sql += " AND tm.customer_id = %s"
            params.append(filters["customer_id"])
        if filters.get("keyword"):
            sql += " AND (tm.mold_number ILIKE %s OR tm.customer_product_no ILIKE %s)"
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw])
        if filters.get("mold_status"):
            sql += " AND tm.mold_status = %s"
            params.append(filters["mold_status"])
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]


def count_mold_status_all():
    """统计各 mold_status 的数量（供前端按钮显示数量）"""
    sql = "SELECT tm.mold_status, COUNT(*) AS cnt FROM tooling_molds tm GROUP BY tm.mold_status"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return {r['mold_status']: r['cnt'] for r in cur.fetchall()}


def get_cavity_review_counts(filters=None):
    """
    统计各 cavity_status 的数量（用于 Level 9/4 审核页摘要显示）。
    """
    sql = """
        SELECT tm.cavity_status, COUNT(*) AS cnt
        FROM tooling_molds tm
        WHERE 1=1
    """
    params = []
    if filters and filters.get("customer_id"):
        sql += " AND tm.customer_id = %s"
        params.append(filters["customer_id"])
    sql += " GROUP BY tm.cavity_status"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def get_all_tooling_molds_for_review(filters=None):
    """
    多穴审核专用：返回全部模具，含 cavity_status，
    供 Level 9 / Level 4 使用。
    """
    sql = """
        SELECT tm.*, tc.name AS customer_name
        FROM tooling_molds tm
        LEFT JOIN tooling_customers tc ON tm.customer_id = tc.id
        WHERE 1=1
    """
    params = []
    if filters:
        if filters.get("customer_id"):
            sql += " AND tm.customer_id = %s"
            params.append(filters["customer_id"])
        if filters.get("keyword"):
            sql += " AND (tm.mold_number ILIKE %s OR tm.customer_product_no ILIKE %s)"
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw])
        if filters.get("status"):
            sql += " AND tm.cavity_status = %s"
            params.append(filters["status"])
    sql += " ORDER BY tm.id DESC"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def update_cavity_status(mold_id, new_status):
    """更新模具的多穴审核状态"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tooling_molds SET cavity_status = %s WHERE id = %s",
                (new_status, mold_id)
            )
            conn.commit()


def get_tooling_mold_by_id(mold_id, user_role_level=1):
    """按 ID 获取单条模具记录（带权限过滤）"""
    sql = """
        SELECT tm.*, tc.name AS customer_name
        FROM tooling_molds tm
        LEFT JOIN tooling_customers tc ON tm.customer_id = tc.id
        WHERE tm.id = %s
    """
    if not _can_see_all_molds(user_role_level):
        sql += " AND tm.cavity_status = '已确认'"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (mold_id,))
            return cur.fetchone()


def get_tooling_molds_by_customer(customer_id):
    """按客户 ID 查询模具列表"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT tm.*, tc.name AS customer_name
                FROM tooling_molds tm
                LEFT JOIN tooling_customers tc ON tm.customer_id = tc.id
                WHERE tm.customer_id = %s
                ORDER BY tm.id DESC
            """, (customer_id,))
            return cur.fetchall()


def get_all_tooling_customers():
    """返回所有客户列表"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM tooling_customers ORDER BY name")
            return cur.fetchall()


def get_tooling_parts_by_mold(mold_id):
    """按模具 ID 查询关联的零件（预留 Part 表）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT tp.*, tm.mold_number
                FROM tooling_parts tp
                JOIN tooling_molds tm ON tp.mold_id = tm.id
                WHERE tp.mold_id = %s
                ORDER BY tp.id
            """, (mold_id,))
            return cur.fetchall()

# --- 按 ID 获取单个零件 ---
def get_part_by_id(part_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM parts WHERE id = %s;", (part_id,))
            row = cur.fetchone()
            return dict(row) if row else None


# --- 查询某零件的所有报工记录（双时间戳：按 actual_date 排序）---
def get_production_logs(part_id):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT pl.*, u.real_name as worker_name, u.username,
                    m.machine_number
                FROM production_logs pl
                JOIN users u ON pl.worker_id = u.id
                LEFT JOIN machines m ON pl.machine_id = m.id
                WHERE pl.part_id = %s
                ORDER BY pl.actual_date DESC, pl.report_time DESC;
            """, (part_id,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

# --- 来料质量卡控：校验原材料是否已确认可用 ---
def check_material_qualified(material_id):
    """
    校验原材料是否满足可用条件。

    可用条件：is_whse_confirmed = TRUE  OR  is_qc_confirmed = TRUE

    返回：(ok: bool, message: str)
      - ok=True  → 允许
      - ok=False → 拒绝，含原因
    """
    if material_id is None:
        return True, ""  # 未扫码，放行
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT material_number, material_name,
                       is_whse_confirmed, is_qc_confirmed
                FROM materials WHERE id = %s;
            """, (material_id,))
            row = cur.fetchone()
            if not row:
                return False, "原材料不存在"
            number, name, whse, qc = row[0], row[1], row[2], row[3]
            label = f"{number} {name}" if name else number
            if whse or qc:
                return True, ""
            return False, f"原材料【{label}】未经仓库或品质确认，禁止使用"


def resolve_material_id_by_number(material_number):
    """
    通过物料卷号解析为 ID。
    支持模糊匹配（前缀）。
    返回 (material_id, material_number) 或 (None, None)。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, material_number FROM materials
                WHERE material_number = %s
                   OR material_number LIKE %s
                ORDER BY created_at DESC LIMIT 1;
            """, (material_number, material_number + '%'))
            row = cur.fetchone()
            if row:
                return row[0], row[1]
            return None, None


# --- 员工填报产量（良品数 + 报废数 + 报废原因）---
def submit_production_log(part_id, worker_id, good_count, scrap_count,
                          scrap_reason, remark="", machine_id=None, plan_id=None,
                          material_id=None, actual_date=None):
    """
    员工报工提交。

    报工锁定（V3.0 §2.1）：
    - 若传入了 machine_id，系统校验该机台状态。
    - 仅 running 状态的机台允许报工。
    - pending_check / repairing / offline 状态均拒绝报工，返回 Exception。

    参数
    ----
    machine_id : int | None   机台 ID（可选，若有机台扫码则必须传）
    """
    if machine_id is not None:
        from app.services.state_machine import MachineStateMachine
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, status FROM machines WHERE id = %s;",
                    (machine_id,)
                )
                row = cur.fetchone()
                if row:
                    sm = MachineStateMachine(row['status'])
                    if sm.is_production_locked():
                        from app.services.state_machine import STATE_META
                        meta = STATE_META.get(sm.current_state, {})
                        label = meta.get("label", row['status'])
                        raise Exception(
                            f"机台状态为【{label}】，报工已锁定，请等待维修处理完成后再试"
                        )

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO production_logs
                    (part_id, worker_id, qty_good, qty_bad, scrap_reason,
                     status, machine_id, plan_id, material_id,
                     actual_date)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s,
                        COALESCE(%s::date, CURRENT_DATE))
            """, (part_id, worker_id, good_count, scrap_count, scrap_reason,
                  machine_id, plan_id, material_id,
                  actual_date if actual_date else None))
            conn.commit()

# --- 组长审核产量（审核后同步计划进度）---
def audit_production_log(log_id, leader_id, approved):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            status = 'approved' if approved else 'rejected'
            # 先拿到 plan_id，审核后再同步
            cur.execute("""
                UPDATE production_logs
                SET status = %s, auditor_id = %s
                WHERE id = %s
                RETURNING plan_id;
            """, (status, leader_id, log_id))
            row = cur.fetchone()
            plan_id_after = row[0] if row else None
            conn.commit()
            # 同步关联计划的累计产出
            if plan_id_after and approved:
                sync_plan_progress(plan_id_after)

# --- 组长批量审核产量（一次处理多条）---
def batch_audit_production_log(log_ids, leader_id, approved):
    """
    批量审核多条报工记录（同一批次 approve/reject）。
    log_ids: list[int]  ID列表
    approved: bool  True=通过，False=驳回
    """
    if not log_ids:
        return 0
    status = 'approved' if approved else 'rejected'
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE production_logs
                SET status = %s, auditor_id = %s
                WHERE id IN ({','.join(['%s'] * len(log_ids))})
                  AND status = 'pending'
                RETURNING plan_id;
            """, [status, leader_id] + list(log_ids))
            affected_rows = cur.fetchall()
            conn.commit()
            # 同步所有关联计划的累计产出
            if approved:
                for row in affected_rows:
                    pid = row[0]
                    if pid:
                        sync_plan_progress(pid)
            return len(affected_rows)

# ============================================================================
# 产值大屏 & 组长异常提醒
# ============================================================================

def get_daily_dashboard_stats():
    """
    计算当日全厂产值相关指标（仅统计已审核通过的记录）。
    返回: {
        total_output_value: float   今日总产值（元）
        total_scrap_loss:  float   今日报废损失（元）
        average_yield:      float   全厂平均良率（0~100）
        today_good_count:   int     今日良品总数
        today_bad_count:    int     今日报废总数
    }
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COALESCE(SUM(pl.qty_good * q.final_price), 0) AS total_output_value,
                    COALESCE(SUM(pl.qty_bad  * q.final_price), 0) AS total_scrap_loss,
                    COALESCE(SUM(pl.qty_good), 0)                 AS today_good_count,
                    COALESCE(SUM(pl.qty_bad),  0)                 AS today_bad_count
                FROM production_logs pl
                JOIN parts p ON pl.part_id = p.id
                LEFT JOIN LATERAL (
                    SELECT final_price
                    FROM quotes
                    WHERE part_id = p.id
                      AND approval_status = 'APPROVED'
                      AND final_price IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                ) q ON TRUE
                WHERE pl.status   = 'approved'
                  AND pl.qty_good > 0
                  AND DATE(pl.report_time) = CURRENT_DATE
                  AND q.final_price IS NOT NULL
                  AND q.final_price > 0;
            """)
            row = cur.fetchone()

            good = row['today_good_count'] or 0
            bad  = row['today_bad_count']  or 0
            total = good + bad
            yield_pct = round(good / total * 100, 1) if total > 0 else 100.0

            return {
                'total_output_value': round(float(row['total_output_value'] or 0), 2),
                'total_scrap_loss':  round(float(row['total_scrap_loss']  or 0), 2),
                'average_yield':     yield_pct,
                'today_good_count':   good,
                'today_bad_count':    bad,
            }


def get_today_scrap_logs():
    """
    返回今日所有有报废的报工记录（状态不限），
    含零件图号、零件名称、报工员工、良品数、报废数、报废原因。
    供组长在首页高亮警示。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    pl.id,
                    p.part_number,
                    p.internal_name,
                    u.real_name        AS worker_name,
                    pl.qty_good,
                    pl.qty_bad,
                    pl.scrap_reason,
                    pl.report_time,
                    pl.status
                FROM production_logs pl
                JOIN users u ON pl.worker_id = u.id
                JOIN parts p ON pl.part_id   = p.id
                WHERE DATE(pl.report_time) = CURRENT_DATE
                  AND pl.qty_bad > 0
                ORDER BY pl.report_time DESC
                LIMIT 100;
            """, )
            return cur.fetchall()


# --- 获取所有员工 ---
def get_all_workers():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, real_name FROM users WHERE role_level = 1;")
            return cur.fetchall()


# ============================================================================
# 报工审核（组长/组长以上）
# ============================================================================

def get_production_logs_for_audit(status_filter=None):
    """
    返回报工记录供审核，支持按状态过滤。
    status_filter: None=全部, 'pending'=待审核, 'approved'=已通过, 'rejected'=已驳回
    """
    sql = """
        SELECT
            pl.id,
            p.part_number,
            p.internal_name,
            u.real_name       AS worker_name,
            pl.qty_good,
            pl.qty_bad,
            pl.scrap_reason,
            pl.report_time,
            pl.status
        FROM production_logs pl
        JOIN users u ON pl.worker_id = u.id
        JOIN parts p ON pl.part_id   = p.id
    """
    params = []
    if status_filter:
        sql += " WHERE pl.status = %s"
        params.append(status_filter)
    sql += " ORDER BY pl.report_time DESC LIMIT 200;"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def get_production_summary():
    """
    返回报工汇总：pending / approved / rejected 数量，
    以及今日良品总数、今日报废总数。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    status,
                    COUNT(*)              AS cnt,
                    COALESCE(SUM(qty_good), 0) AS total_good,
                    COALESCE(SUM(qty_bad),  0) AS total_bad
                FROM production_logs
                GROUP BY status;
            """)
            rows = {r['status']: r for r in cur.fetchall()}

            # 今日统计
            cur.execute("""
                SELECT
                    COALESCE(SUM(qty_good), 0) AS today_good,
                    COALESCE(SUM(qty_bad),  0) AS today_bad
                FROM production_logs
                WHERE DATE(report_time) = CURRENT_DATE;
            """)
            today = cur.fetchone()

            return {
                'pending':  rows.get('pending',  {}).get('cnt', 0),
                'approved': rows.get('approved', {}).get('cnt', 0),
                'rejected': rows.get('rejected', {}).get('cnt', 0),
                'today_good': today['today_good'],
                'today_bad':  today['today_bad'],
            }


# ============================================================================
# 包装与发货
# ============================================================================

def get_part_progress(part_id):
    """
    返回某零件的累计生产/包装/发货数量（仅统计 approved 的良品）。
    用于防错校验和进度条展示。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 累计已审核良品
            cur.execute("""
                SELECT COALESCE(SUM(qty_good), 0) AS total_good
                FROM production_logs
                WHERE part_id = %s AND status = 'approved';
            """, (part_id,))
            total_good = cur.fetchone()['total_good']

            # 累计包装数
            cur.execute("""
                SELECT COALESCE(SUM(qty), 0) AS total_packaged
                FROM packaging_logs WHERE part_id = %s;
            """, (part_id,))
            total_packaged = cur.fetchone()['total_packaged']

            # 累计发货数
            cur.execute("""
                SELECT COALESCE(SUM(qty), 0) AS total_shipped
                FROM shipping_logs WHERE part_id = %s;
            """, (part_id,))
            total_shipped = cur.fetchone()['total_shipped']

            return {
                'total_good':      int(total_good),
                'total_packaged':  int(total_packaged),
                'total_shipped':   int(total_shipped),
                'packaged_remain': int(total_good) - int(total_packaged),
                'shipped_remain':  int(total_packaged) - int(total_shipped),
            }


def submit_packaging(part_id, user_id, qty):
    """
    提交包装数。防错：qty 不能超过 remaining（total_good - total_packaged）。
    """
    progress = get_part_progress(part_id)
    remaining = progress['packaged_remain']
    if qty <= 0:
        raise ValueError("包装数必须大于 0")
    if qty > remaining:
        raise ValueError(f"包装数不能超过剩余可包装数量（当前剩余：{remaining}）")
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO packaging_logs (part_id, user_id, qty)
                VALUES (%s, %s, %s);
            """, (part_id, user_id, qty))
            conn.commit()


def submit_shipping(part_id, user_id, qty):
    """
    提交发货数。防错：qty 不能超过 remaining（total_packaged - total_shipped）。
    """
    progress = get_part_progress(part_id)
    remaining = progress['shipped_remain']
    if qty <= 0:
        raise ValueError("发货数必须大于 0")
    if qty > remaining:
        raise ValueError(f"发货数不能超过剩余可发货数量（当前剩余：{remaining}）")
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO shipping_logs (part_id, user_id, qty)
                VALUES (%s, %s, %s);
            """, (part_id, user_id, qty))
            conn.commit()


def toggle_urgent(part_id, is_urgent: bool):
    """切换零件加急状态（仅老板/业务经理可调用）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE parts SET is_urgent = %s WHERE id = %s",
                (is_urgent, part_id)
            )
            conn.commit()


def get_all_urgent_parts():
    """
    返回所有加急零件（含最新进度和百分比），供老板看板展示。
    进度百分比基于 target_count（订单目标总数）计算。
    安全校验：target_count == 0 时进度为 0；百分比最大不超过 100%。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 拉出加急零件基础信息（含 target_count）
            cur.execute("""
                SELECT p.id, p.part_number, p.internal_name, p.is_urgent,
                       COALESCE(p.target_count, 0) AS target_count
                FROM parts p
                WHERE p.is_urgent = TRUE
                ORDER BY p.id DESC;
            """)
            parts = cur.fetchall()

            result = []
            for p in parts:
                prog = get_part_progress(p['id'])
                target = int(p['target_count']) if p['target_count'] else 0

                # 基于 target_count 计算三个百分比
                prod_pct = 0.0
                pack_pct = 0.0
                ship_pct = 0.0
                if target > 0:
                    prod_pct = min((prog['total_good'] / target) * 100, 100.0)
                    pack_pct = min((prog['total_packaged'] / target) * 100, 100.0)
                    ship_pct = min((prog['total_shipped'] / target) * 100, 100.0)

                prog['part_number']    = p['part_number']
                prog['part_name']      = p['internal_name']
                prog['part_id']        = p['id']
                prog['target_count']   = target
                prog['prod_pct']       = round(prod_pct, 1)
                prog['pack_pct']       = round(pack_pct, 1)
                prog['ship_pct']       = round(ship_pct, 1)
                result.append(prog)
            return result


def get_period_summary():
    """
    返回本周/本月统计数据，供老板（Lv.9）看板使用。
    生产数统计 approved 良品，包装/发货统计全量记录。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            def fetch_period_produced(since: str, until: str):
                cur.execute("""
                    SELECT COALESCE(SUM(qty_good), 0) AS produced
                    FROM production_logs
                    WHERE status = 'approved'
                      AND DATE(report_time) >= %s
                      AND DATE(report_time) <= %s;
                """, (since, until))
                return int(cur.fetchone()['produced'])

            def fetch_period_packaged(since: str, until: str):
                cur.execute("""
                    SELECT COALESCE(SUM(qty_passed), 0) AS packaged
                    FROM pkg_packaging_logs
                    WHERE DATE(packed_at) >= %s
                      AND DATE(packed_at) <= %s;
                """, (since, until))
                return int(cur.fetchone()['packaged'])

            def fetch_period_shipped(since: str, until: str):
                cur.execute("""
                    SELECT COALESCE(SUM(qty), 0) AS shipped
                    FROM pkg_shipping_logs
                    WHERE DATE(shipped_at) >= %s
                      AND DATE(shipped_at) <= %s;
                """, (since, until))
                return int(cur.fetchone()['shipped'])

            # 本周（周一 ~ 今天）
            cur.execute("""
                SELECT
                    DATE_TRUNC('week', CURRENT_DATE)::DATE                       AS week_start,
                    CURRENT_DATE                                                 AS week_end,
                    DATE_TRUNC('month', CURRENT_DATE)::DATE                      AS month_start,
                    (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month - 1 day')::DATE AS month_end;
            """)
            bounds = cur.fetchone()

            week_produced  = fetch_period_produced(str(bounds['week_start']), str(bounds['week_end']))
            week_packaged  = fetch_period_packaged(str(bounds['week_start']), str(bounds['week_end']))
            week_shipped   = fetch_period_shipped(str(bounds['week_start']), str(bounds['week_end']))

            month_produced  = fetch_period_produced(str(bounds['month_start']), str(bounds['week_end']))
            month_packaged  = fetch_period_packaged(str(bounds['month_start']), str(bounds['week_end']))
            month_shipped   = fetch_period_shipped(str(bounds['month_start']), str(bounds['week_end']))

            return {
                'week_start':      str(bounds['week_start']),
                'week_end':        str(bounds['week_end']),
                'month_start':     str(bounds['month_start']),
                'month_end':       str(bounds['month_end']),
                'week_produced':   week_produced,
                'week_packaged':   week_packaged,
                'week_shipped':    week_shipped,
                'month_produced':  month_produced,
                'month_packaged':  month_packaged,
                'month_shipped':   month_shipped,
            }


# ============================================================================
# 首页"千人千面"辅助函数
# ============================================================================

def get_my_parts(user_id):
    """
    返回指派给指定员工的所有零件（含今日已报工统计）。
    用于 Lv.1 员工首页"我的今日任务"。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.part_number, p.internal_name, p.status
                FROM assignments a
                JOIN parts p ON a.part_id = p.id
                WHERE a.worker_id = %s
                ORDER BY a.assign_date DESC, p.id DESC;
            """, (user_id,))
            parts = cur.fetchall()

            result = []
            for p in parts:
                # 今日良品数
                cur.execute("""
                    SELECT COALESCE(SUM(qty_good), 0) AS today_good
                    FROM production_logs
                    WHERE worker_id = %s AND part_id = %s
                      AND DATE(report_time) = CURRENT_DATE;
                """, (user_id, p['id']))
                today_good = int(cur.fetchone()['today_good'])

                prog = get_part_progress(p['id'])
                # 转成纯 dict，避免 Jinja2 RealDictRow 兼容性问题
                row = {
                    'id': p['id'],
                    'part_number': p['part_number'],
                    'part_name': p['internal_name'],
                    'status': p['status'],
                    'today_good': today_good,
                    'total_good': prog['total_good'],
                }
                result.append(row)
            return result


def count_pending_quotes():
    """统计当前状态为 PENDING_BOSS（待老板审核）的报价单数量"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM quotes WHERE approval_status = 'PENDING_BOSS';")
            row = cur.fetchone()
            return row[0] if row else 0


def get_pending_logs_for_dashboard():
    """
    返回待审核的报工记录（限最近 20 条），供组长首页快速审核。
    包含零件信息和报工员工姓名。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    pl.id,
                    p.part_number,
                    p.internal_name,
                    u.real_name  AS worker_name,
                    pl.qty_good,
                    pl.qty_bad,
                    pl.scrap_reason,
                    pl.report_time
                FROM production_logs pl
                JOIN users u ON pl.worker_id = u.id
                JOIN parts p ON pl.part_id   = p.id
                WHERE pl.status = 'pending'
                ORDER BY pl.report_time DESC
                LIMIT 20;
            """)
            return cur.fetchall()


def get_team_production_summary():
    """
    返回班组今日产量汇总，用于组长首页展示。
    包含：班组总良品数、待审核数、报废数、今日任务数。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 今日班组良品总数
            cur.execute("""
                SELECT COALESCE(SUM(qty_good), 0) AS team_good
                FROM production_logs
                WHERE DATE(report_time) = CURRENT_DATE;
            """)
            team_good = int(cur.fetchone()['team_good'])

            # 待审核数
            cur.execute("""
                SELECT COUNT(*) AS pending_count
                FROM production_logs
                WHERE status = 'pending' AND DATE(report_time) = CURRENT_DATE;
            """)
            pending_count = int(cur.fetchone()['pending_count'])

            # 今日报废总数
            cur.execute("""
                SELECT COALESCE(SUM(qty_bad), 0) AS team_scrap
                FROM production_logs
                WHERE DATE(report_time) = CURRENT_DATE;
            """)
            team_scrap = int(cur.fetchone()['team_scrap'])

            # 今日有报工记录的员工数
            cur.execute("""
                SELECT COUNT(DISTINCT worker_id) AS active_workers
                FROM production_logs
                WHERE DATE(report_time) = CURRENT_DATE;
            """)
            active_workers = int(cur.fetchone()['active_workers'])

            # 今日已指派零件总数
            cur.execute("""
                SELECT COUNT(*) AS assigned_count
                FROM assignments
                WHERE assign_date = CURRENT_DATE;
            """)
            assigned_count = int(cur.fetchone()['assigned_count'])

            return {
                'team_good': team_good,
                'pending_count': pending_count,
                'team_scrap': team_scrap,
                'active_workers': active_workers,
                'assigned_count': assigned_count,
            }


# ============================================================================
# 生产管理端（主管/组长）专用查询
# ============================================================================

def get_manager_dashboard_data():
    """
    返回生产管理端仪表盘所需全部数据：
      - 机台列表（含维修计时器起点时间）
      - 待产任务池（未分配或部分分配的活跃计划）
      - 今日汇总（良品/报废/待审/在线工人）
      - 吨位开工率分组（纯SQL GROUP BY）
      - 预警指标（损耗率/修模停机/尾数积压/逾期交付）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 机台列表 ──────────────────────────────────────────────
            cur.execute("""
                SELECT
                    m.id, m.machine_number, m.machine_name, m.press_tonnage,
                    m.status, m.current_mold_id, m.current_part_id,
                    m.current_operator_id, m.remark, m.active_plan_id,
                    m.fault_reason,
                    m.fault_reported_at,
                    m.tech_arrival_time,
                    m.diagnosing_start_time,
                    mo.mold_number  AS current_mold_number,
                    pt.part_number  AS current_part_number,
                    pt.internal_name AS current_part_name,
                    u.real_name     AS current_operator_name,
                    pp.part_id      AS active_part_id,
                    pt2.part_number AS active_part_number,
                    pt2.internal_name AS active_part_name,
                    pp.total_qty   AS active_plan_total_qty,
                    pp.progress_qty AS active_plan_progress_qty
                FROM machines m
                LEFT JOIN dies  mo  ON m.current_mold_id    = mo.id
                LEFT JOIN parts  pt  ON m.current_part_id    = pt.id
                LEFT JOIN users  u   ON m.current_operator_id = u.id
                LEFT JOIN production_plans pp ON m.active_plan_id = pp.id
                LEFT JOIN parts pt2 ON pp.part_id = pt2.id
                ORDER BY m.machine_number;
            """)
            machines = cur.fetchall()

            # ── 2. 维修计时器 ───────────────────────────────────────────
            repair_timers = {}
            for m in machines:
                s = str(m.get('status') or '')
                if s in ('fault', 'pending_check', 'repairing'):
                    ts = m.get('fault_reported_at') or m.get('tech_arrival_time')
                    if ts is None:
                        repair_timers[str(m.get('id'))] = None
                    elif hasattr(ts, 'isoformat'):
                        repair_timers[str(m.get('id'))] = ts.isoformat()
                    else:
                        repair_timers[str(m.get('id'))] = str(ts)

            # ── 3. 今日生产汇总（纯SQL聚合）────────────────────────────────
            cur.execute("""
                SELECT
                    COALESCE(SUM(qty_good), 0)::INTEGER    AS team_good,
                    COALESCE(SUM(qty_bad),  0)::INTEGER    AS team_scrap,
                    COUNT(DISTINCT worker_id)::INTEGER        AS active_workers
                FROM production_logs
                WHERE DATE(report_time) = CURRENT_DATE
                  AND status = 'approved';
            """)
            row_today = cur.fetchone()
            team_good       = row_today.get('team_good', 0)
            team_scrap      = row_today.get('team_scrap', 0)
            active_workers  = row_today.get('active_workers', 0)

            # 待审核数
            cur.execute("""
                SELECT COUNT(*)::INTEGER AS pending_count
                FROM production_logs
                WHERE status = 'pending'
                  AND DATE(report_time) = CURRENT_DATE;
            """)
            pending_count = cur.fetchone().get('pending_count', 0)

            # 昨日良品（用于环比）
            cur.execute("""
                SELECT COALESCE(SUM(qty_good), 0)::INTEGER AS yesterday_good
                FROM production_logs
                WHERE DATE(report_time) = CURRENT_DATE - INTERVAL '1 day'
                  AND status = 'approved';
            """)
            yesterday_good = cur.fetchone().get('yesterday_good', 0)

            yoy_pct = None
            if yesterday_good > 0:
                yoy_pct = round((team_good - yesterday_good) / yesterday_good * 100, 1)

            today_summary = {
                'team_good':      team_good,
                'yesterday':      yesterday_good,
                'yoy_pct':        yoy_pct,
                'pending_count':  pending_count,
                'team_scrap':     team_scrap,
                'active_workers': active_workers,
            }

            # ── 4. 吨位开工率（纯SQL GROUP BY，禁止Python循环）──────────────
            cur.execute("""
                SELECT
                    COALESCE(m.press_tonnage, '未知') AS tonnage,
                    COUNT(*)                                    AS total,
                    COUNT(*) FILTER (WHERE m.status = 'running')  AS running,
                    COUNT(*) FILTER (WHERE m.status = 'idle')     AS idle,
                    COUNT(*) FILTER (WHERE m.status = 'repairing') AS repairing,
                    COUNT(*) FILTER (WHERE m.status = 'fault')    AS fault,
                    COUNT(*) FILTER (WHERE m.status = 'offline')  AS offline,
                    COUNT(*) FILTER (WHERE m.status IN ('fault','repairing')) AS fault_repair
                FROM machines m
                GROUP BY m.press_tonnage
                ORDER BY
                    CASE WHEN m.press_tonnage ~ '^[0-9]+$' THEN 1 ELSE 2 END,
                    COALESCE(m.press_tonnage, 'z') ASC;
            """)
            tonnage_rows = cur.fetchall()
            # 用字典构建，按吨位 key 索引
            tonnage_groups = {}
            for row in tonnage_rows:
                key = str(row.get('tonnage') or '未知')
                tonnage_groups[key] = {
                    'total':     row.get('total', 0),
                    'running':   row.get('running', 0),
                    'idle':      row.get('idle', 0),
                    'repairing': row.get('repairing', 0),
                    'fault':     row.get('fault', 0),
                    'offline':   row.get('offline', 0),
                    'fault_repair': row.get('fault_repair', 0),
                }

            # ── 5. 预警指标（纯SQL）────────────────────────────────────────

            # 5a. 废料损耗率（本月，已审核数据）
            cur.execute("""
                SELECT
                    COALESCE(SUM(qty_bad),  0)::INTEGER  AS total_bad,
                    COALESCE(SUM(qty_good), 0)::INTEGER  AS total_good,
                    CASE WHEN (SUM(qty_good) + SUM(qty_bad)) > 0
                         THEN ROUND(
                             SUM(qty_bad)::NUMERIC
                             / NULLIF(SUM(qty_good) + SUM(qty_bad), 0)
                             * 100, 2)
                         ELSE 0.0
                    END AS scrap_rate
                FROM production_logs
                WHERE status = 'approved'
                  AND DATE_TRUNC('month', actual_date) = DATE_TRUNC('month', CURRENT_DATE);
            """)
            row_scrap = cur.fetchone()
            total_bad    = row_scrap.get('total_bad', 0)
            total_good   = row_scrap.get('total_good', 0)
            scrap_rate   = float(row_scrap.get('scrap_rate') or 0.0)
            alert_scrap  = scrap_rate > 3.5  # 阈值 3.5%

            # 5b. 修模停机数量（repairing 状态）
            cur.execute("""
                SELECT COUNT(*)::INTEGER AS repairing_count
                FROM machines
                WHERE status = 'repairing';
            """)
            repairing_count = cur.fetchone().get('repairing_count', 0)

            # 5c. 尾数库存积压（JOIN quotes 取最新 APPROVED 单价，乘以件数计算积压金额）
            cur.execute("""
                WITH latest_quote AS (
                    SELECT DISTINCT ON (q.part_id)
                        q.part_id,
                        q.final_price
                    FROM quotes q
                    WHERE q.approval_status = 'APPROVED'
                    ORDER BY q.part_id, q.updated_at DESC NULLS LAST
                )
                SELECT
                    COUNT(DISTINCT ri.id)::INTEGER                          AS remnant_items,
                    COALESCE(SUM(ri.quantity), 0)::INTEGER                 AS remnant_total_qty,
                    COALESCE(
                        SUM(ri.quantity::NUMERIC * COALESCE(lq.final_price, 0)),
                        0
                    )::NUMERIC(18,2)                                       AS remnant_value
                FROM remnant_inventory ri
                LEFT JOIN latest_quote lq ON ri.part_id = lq.part_id;
            """)
            row_remnant = cur.fetchone()
            remnant_items     = row_remnant.get('remnant_items', 0)
            remnant_total    = row_remnant.get('remnant_total_qty', 0)
            remnant_value    = float(row_remnant.get('remnant_value') or 0)

            # 5d. 逾期交付预警（复用已有函数）
            overdue_data = get_overdue_summary()

            # ── 6. 待产任务池 ─────────────────────────────────────────────
            cur.execute("""
                SELECT
                    pp.id, pp.part_id, pp.total_qty, pp.progress_qty,
                    pp.due_date, pp.urgency, pp.plan_order,
                    pp.status, pp.created_at,
                    pt.part_number, pt.internal_name
                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                WHERE pp.status IN ('planned', 'in_progress')
                ORDER BY
                    pp.urgency = 'critical' DESC,
                    pp.urgency = 'urgent' DESC,
                    pp.due_date ASC NULLS LAST,
                    pp.plan_order ASC
                LIMIT 100;
            """)
            unassigned_plans = cur.fetchall()

            cur.execute("""
                SELECT
                    pp.id, pp.part_id, pp.total_qty, pp.progress_qty,
                    pp.due_date, pp.urgency, pp.status,
                    pt.part_number, pt.internal_name,
                    pm.machine_id
                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                JOIN plan_machines pm ON pm.plan_id = pp.id AND pm.status = 'active'
                ORDER BY pp.urgency = 'critical' DESC, pp.plan_order ASC
                LIMIT 100;
            """)
            active_plans = cur.fetchall()

            # ── 汇总返回 ───────────────────────────────────────────────────
            running_count = sum(1 for m in machines if str(m.get('status') or '') == 'running')
            fault_count   = sum(1 for m in machines if str(m.get('status') or '') in ('fault', 'pending_check'))

            import datetime as _dt
            import decimal as _dec

            def _rows_to_json(rows):
                result = []
                for row in rows:
                    d = dict(row)
                    for k, v in d.items():
                        if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
                            d[k] = v.isoformat()
                        elif isinstance(v, _dec.Decimal):
                            d[k] = float(v)
                    result.append(d)
                return result

            return {
                'machines':          [dict(m) for m in machines],
                'repair_timers':      repair_timers,
                'running_count':      running_count,
                'fault_count':        fault_count,
                'today_good':         team_good,
                'unassigned_plans':   [dict(p) for p in unassigned_plans],
                'active_plans':       [dict(p) for p in active_plans],
                'today_summary':      today_summary,
                'tonnage_groups':     tonnage_groups,
                # 新增预警指标
                'kpi': {
                    'scrap_rate':       scrap_rate,
                    'scrap_rate_str':   f'{scrap_rate:.2f}%',
                    'alert_scrap':      alert_scrap,
                    'total_bad':        total_bad,
                    'total_good':       total_good,
                    'repairing_count':  repairing_count,
                    'remnant_items':    remnant_items,
                    'remnant_total':    remnant_total,
                    'remnant_value':    remnant_value,
                },
                'overdue_data':       overdue_data,
            }


def set_machine_active_plan(machine_id, plan_id, operator_id=None):
    """
    主管/组长下发任务：将 plan_id 设为机台的 active_plan_id。
    内部调用 assign_plan_to_machine，但额外处理 active_plan_id 同步。
    """
    assign_plan_to_machine(plan_id, machine_id, operator_id)


def intervene_machine(machine_id, action, fault_reason=None, remark=None):
    """
    主管/组长异常干预：
    - action='request_offline': 标记为 pending_check
    - action='fault': 标记为 fault + 记录故障原因
    - action='reset': 清除故障，恢复 running
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            now = datetime.datetime.now()
            if action == 'request_offline':
                cur.execute("""
                    UPDATE machines
                    SET status='pending_check',
                        fault_reason=%s,
                        fault_reported_at=%s,
                        updated_at=%s
                    WHERE id=%s;
                """, (fault_reason or '', now, now, machine_id))
            elif action == 'fault':
                cur.execute("""
                    UPDATE machines
                    SET status='fault',
                        fault_reason=%s,
                        fault_reported_at=%s,
                        updated_at=%s
                    WHERE id=%s;
                """, (fault_reason or '', now, now, machine_id))
            elif action == 'reset':
                cur.execute("""
                    UPDATE machines
                    SET status='running',
                        fault_reason=NULL,
                        fault_reported_at=NULL,
                        tech_arrival_time=NULL,
                        diagnosing_start_time=NULL,
                        updated_at=%s
                    WHERE id=%s;
                """, (now, machine_id))
            conn.commit()


def get_machine_repair_log(machine_id):
    """
    返回指定机台的维修日志事件序列（从旧到新）。
    数据来源：machines 表（故障报告时间、到场时间等）+ production_logs（操作员）
    """
    events = []

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 获取机台基本信息
            cur.execute("""
                SELECT
                    m.machine_number, m.machine_name, m.status,
                    m.fault_reason,
                    m.fault_reported_at,
                    m.tech_arrival_time,
                    m.diagnosing_start_time,
                    m.mold_offline_time,
                    m.current_operator_id,
                    u.real_name AS current_operator_name,
                    mo.mold_number AS current_mold_number,
                    pt.part_number AS current_part_number,
                    pt.internal_name AS current_part_name
                FROM machines m
                LEFT JOIN users u ON m.current_operator_id = u.id
                LEFT JOIN dies mo ON m.current_mold_id = mo.id
                LEFT JOIN parts pt ON m.current_part_id = pt.id
                WHERE m.id = %s;
            """, (machine_id,))
            machine = cur.fetchone()

            if not machine:
                return {'machine': None, 'events': []}

            # 获取该机台最近的生产报工记录（用于获取操作员）
            cur.execute("""
                SELECT pl.report_time, pl.qty_good, pl.qty_bad, pl.status,
                       u.real_name AS operator_name
                FROM production_logs pl
                LEFT JOIN users u ON pl.worker_id = u.id
                WHERE pl.machine_id = %s
                ORDER BY pl.report_time DESC
                LIMIT 1;
            """, (machine_id,))
            last_report = cur.fetchone()

            # 获取该机台最近的完工/报修记录（从 operation_logs）
            cur.execute("""
                SELECT ol.created_at, ol.operation_type, ol.detail,
                       u.real_name AS operator_name
                FROM operation_logs ol
                LEFT JOIN users u ON ol.operator_id = u.id
                WHERE ol.target_table = 'machines'
                  AND ol.target_id = %s
                  AND ol.operation_type IN ('fault', 'request_offline', 'tech_intervene',
                                            'tech_complete', 'force_complete', 'fault_reset')
                ORDER BY ol.created_at DESC
                LIMIT 20;
            """, (machine_id,))
            op_logs = cur.fetchall()

    if not machine:
        return {'machine': None, 'events': []}

    machine_number = machine.get('machine_number', '未知机台')

    # ── 构建事件序列 ──
    # 1. 最后一次生产报工（记录操作员在场）
    if last_report:
        t = last_report['report_time']
        events.append({
            'time': t.strftime('%m-%d %H:%M') if t else '—',
            'iso_time': t.isoformat() if t else '',
            'title': '最后报工记录',
            'desc': f"良品 {last_report['qty_good']} / 报废 {last_report['qty_bad']}（{last_report['status']}）",
            'operator': last_report['operator_name'],
            'dot_color': 'green',
        })

    # 2. 模具下线记录
    if machine.get('mold_offline_time'):
        t = machine['mold_offline_time']
        events.append({
            'time': t.strftime('%m-%d %H:%M') if t else '—',
            'iso_time': t.isoformat() if t else '',
            'title': '模具下线',
            'desc': machine.get('current_mold_number') or '—',
            'dot_color': 'gray',
        })

    # 3. 故障报告
    if machine.get('fault_reported_at'):
        t = machine['fault_reported_at']
        events.append({
            'time': t.strftime('%m-%d %H:%M') if t else '—',
            'iso_time': t.isoformat() if t else '',
            'title': '故障报告',
            'desc': machine.get('fault_reason') or '未填写原因',
            'operator': machine.get('current_operator_name') or (last_report['operator_name'] if last_report else None),
            'dot_color': 'red',
        })

    # 4. 开发人员到场
    if machine.get('tech_arrival_time'):
        t = machine['tech_arrival_time']
        events.append({
            'time': t.strftime('%m-%d %H:%M') if t else '—',
            'iso_time': t.isoformat() if t else '',
            'title': '开发人员到场',
            'desc': '维修人员已到达现场',
            'dot_color': 'blue',
        })

    # 5. 开始诊断
    if machine.get('diagnosing_start_time'):
        t = machine['diagnosing_start_time']
        events.append({
            'time': t.strftime('%m-%d %H:%M') if t else '—',
            'iso_time': t.isoformat() if t else '',
            'title': '开始诊断修理',
            'desc': machine.get('fault_reason') or '',
            'dot_color': 'blue',
        })

    # 6. 从 operation_logs 补充更多历史事件
    for log in op_logs:
        t = log['created_at']
        op_type_map = {
            'fault': ('故障', 'red'),
            'request_offline': ('申请停机', 'red'),
            'tech_intervene': ('技术介入', 'blue'),
            'tech_complete': ('修理完成', 'green'),
            'force_complete': ('强制完工', 'gray'),
            'fault_reset': ('故障重置', 'green'),
        }
        label, color = op_type_map.get(log['operation_type'], (log['operation_type'], 'gray'))
        events.append({
            'time': t.strftime('%m-%d %H:%M') if t else '—',
            'iso_time': t.isoformat() if t else '',
            'title': label,
            'desc': log['detail'] or '',
            'operator': log['operator_name'],
            'dot_color': color,
        })

    # 按时间升序排列
    def event_key(ev):
        return ev.get('iso_time', '')
    events.sort(key=event_key)

    return {
        'machine': {
            'id': machine_id,
            'machine_number': machine_number,
            'status': machine.get('status'),
            'fault_reason': machine.get('fault_reason'),
            'current_operator_name': machine.get('current_operator_name'),
            'current_mold_number': machine.get('current_mold_number'),
        },
        'events': events,
    }


def force_complete_machine(machine_id, plan_id, remark=None):
    """
    强制完工：将生产计划关闭，并清空机台关联。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            now = datetime.datetime.now()

            # 安全熔断：确认 plan 确实关联了该机台
            cur.execute("""
                SELECT 1 FROM plan_machines
                WHERE plan_id=%s AND machine_id=%s AND status='active';
            """, (plan_id, machine_id))
            if not cur.fetchone():
                raise ValueError(f"Plan {plan_id} is not active on machine {machine_id}. Aborting force-complete.")

            # 关闭生产计划
            cur.execute("""
                UPDATE production_plans
                SET status='closed', updated_at=%s
                WHERE id=%s;
            """, (now, plan_id))
            # 将该计划所有机台关联改为 inactive
            cur.execute("""
                UPDATE plan_machines
                SET status='inactive', assigned_at=%s
                WHERE plan_id=%s;
            """, (now, plan_id))
            # 清空机台 active_plan_id
            cur.execute("""
                UPDATE machines
                SET active_plan_id=NULL,
                    current_part_id=NULL,
                    status='idle',
                    updated_at=%s
                WHERE id=%s;
            """, (now, machine_id))

            # 记录操作日志
            cur.execute("""
                INSERT INTO operation_logs
                    (operator_id, operation_type, target_table, target_id, detail, created_at)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (
                None,  # operator_id (no user context here)
                'force_complete',
                'production_plans',
                plan_id,
                f"强制完工: machine_id={machine_id}, plan_id={plan_id}, remark={remark or ''}",
                now,
            ))
            conn.commit()


def get_my_assigned_parts(leader_id):
    """
    返回由指定组长指派的所有零件，供组长"任务分派区"展示。
    仅返回尚未在 assignments 中被指派给工人的零件（即待分派零件）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 查出该组长负责但尚未指派给工人的零件
            cur.execute("""
                SELECT DISTINCT p.id, p.part_number, p.internal_name AS part_name, p.status
                FROM parts p
                WHERE p.id NOT IN (
                    SELECT DISTINCT part_id FROM assignments WHERE worker_id != %s
                )
                ORDER BY p.id DESC
                LIMIT 50;
            """, (leader_id,))
            return cur.fetchall()


# ============================================================================
# 物料台账 (Materials) - 卷料/板料宽度追踪与分条管理
# ============================================================================

def add_material(material_number, original_width, material_name="",
                 material_type="卷料", scrap_threshold=0, remark="",
                 parent_id=None, thickness=0, batch_no="",
                 current_weight=0, supplier_name=""):
    """
    新增物料记录。
    - original_width : 入库初始总宽度（入库后不再变更）
    - current_width  : 初始化时等于 original_width
    - current_weight : 初始重量（kg），入库后随分条按比例扣减
    - thickness      : 厚度（mm）
    - batch_no       : 批次号
    - parent_id      : 若从大卷分条而来，指向父料 ID
    - supplier_name  : 供应商名称（IQC 来料检用）
    - status         : 新增入库的物料状态默认为 '使用中'，分条子料由 process_slitting 设为 '待领用'
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM materials WHERE material_number = %s;
            """, (material_number,))
            if cur.fetchone():
                return  # 已存在，跳过
            cur.execute("""
                INSERT INTO materials
                    (material_number, material_name, material_type,
                     original_width, current_width,
                     original_weight, current_weight,
                     scrap_threshold, remark,
                     parent_id,
                     thickness, batch_no,
                     supplier_name,
                     is_active, status, material_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, '使用中', 'pending')
            """, (material_number, material_name, material_type,
                  original_width, original_width,
                  current_weight, current_weight,    # original_weight = current_weight = 初始重量
                  scrap_threshold, remark, parent_id,
                  thickness, batch_no, supplier_name))
            conn.commit()


def get_all_materials(filters=None, limit=50, offset=0):
    """
    返回物料列表（支持关键词搜索、状态过滤，带分页）。
    自动过滤 is_active=False 的已结案物料。
    """
    sql = """
        SELECT m.*,
               p.material_number AS parent_number,
               p.material_name   AS parent_name
        FROM materials m
        LEFT JOIN materials p ON m.parent_id = p.id
        WHERE 1=1
    """
    params = []
    if filters:
        if filters.get("keyword"):
            sql += " AND (m.material_number ILIKE %s OR m.material_name ILIKE %s)"
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw])
        if filters.get("material_type"):
            sql += " AND m.material_type = %s"
            params.append(filters["material_type"])
        if filters.get("is_active") is not None:
            sql += " AND m.is_active = %s"
            params.append(filters["is_active"])
    else:
        sql += " AND m.is_active = TRUE"
    sql += " ORDER BY m.id DESC"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def count_materials(filters=None):
    """统计符合条件的物料总数"""
    sql = "SELECT COUNT(*) FROM materials m WHERE 1=1"
    params = []
    if filters:
        if filters.get("keyword"):
            sql += " AND (m.material_number ILIKE %s OR m.material_name ILIKE %s)"
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw])
        if filters.get("material_type"):
            sql += " AND m.material_type = %s"
            params.append(filters["material_type"])
        if filters.get("is_active") is not None:
            sql += " AND m.is_active = %s"
            params.append(filters["is_active"])
    else:
        sql += " AND m.is_active = TRUE"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]


def get_material_by_id(material_id):
    """按 ID 获取单条物料记录"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT m.*,
                       p.material_number AS parent_number,
                       p.material_name   AS parent_name
                FROM materials m
                LEFT JOIN materials p ON m.parent_id = p.id
                WHERE m.id = %s;
            """, (material_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_parent_materials():
    """
    返回所有未结案的大卷（可作为父料分条）。
    即 is_active=TRUE 且 current_width > 0 的物料。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, material_number, material_name,
                       current_width, original_width
                FROM materials
                WHERE is_active = TRUE AND current_width > 0
                ORDER BY id DESC;
            """)
            return cur.fetchall()


def process_slitting(parent_id, target_width, count):
    """
    核心分条逻辑（process_slitting）。

    参数：
        parent_id    : 父料 ID
        target_width : 单条目标宽度（mm）
        count        : 分条条数

    校验：
        - 总消耗宽度 = target_width * count，若超过父料 current_width 则抛异常
        - count > 0
        - 父料必须存在且 is_active=TRUE

    扣减动作：
        - 消耗重量 = (总消耗宽度 / 原current_width) * current_weight，按比例扣减
        - current_width -= total_consumed_width
        - current_weight -= consumed_weight
        - 若扣减后 current_width <= scrap_threshold，自动结案父料（归零+写日志）

    产出动作：
        - 创建 count 条子料，status = '待领用'
        - 子料自动继承父料的 material_type、thickness、batch_no
        - 子料的 original_width = current_width = target_width
        - 子料的 parent_id = parent_id
        - 子料编号格式：{父料编号}-S{序号}，例如 MAT-001-S1, MAT-001-S2

    返回：
        (成功标志, 消息, 新增的子料ID列表)

    异常：
        ValueError  业务校验失败（如宽度不足、参数错误）
    """
    if target_width <= 0:
        raise ValueError("单条宽度必须大于 0")
    if count <= 0:
        raise ValueError("分条条数必须大于 0")

    total_consumed = round(target_width * count, 4)

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 锁住父料行
            cur.execute("""
                SELECT id, current_width, current_weight, scrap_threshold,
                       material_number, material_type, thickness, batch_no, is_active
                FROM materials WHERE id = %s FOR UPDATE;
            """, (parent_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"父料 ID={parent_id} 不存在")
            (pid, cur_width, cur_weight, threshold,
             parent_num, mat_type, thickness, batch_no, is_active) = row

            if not is_active:
                raise ValueError(f"父料 {parent_num} 已结案，无法分条")

            cur_width_f  = float(cur_width)  if cur_width  is not None else 0.0
            cur_weight_f = float(cur_weight) if cur_weight is not None else 0.0

            if total_consumed > cur_width_f:
                raise ValueError(
                    f"总消耗宽度({total_consumed}mm)超过父料剩余宽度({cur_width_f}mm)，"
                    f"最多可分 {int(cur_width_f // target_width)} 条"
                )

            # 计算消耗比例并扣减重量
            if cur_width_f > 0 and cur_weight_f > 0:
                consumed_weight = round((total_consumed / cur_width_f) * cur_weight_f, 4)
            else:
                consumed_weight = 0.0

            new_width  = round(cur_width_f  - total_consumed, 2)
            new_weight = round(cur_weight_f - consumed_weight, 4)
            # 自动结案判定：剩余宽度低于报废阈值时触发
            auto_close = (new_width <= float(threshold) if threshold else False)

            # 更新父料（自动结案时将 current_weight 归零）
            if auto_close:
                cur.execute("""
                    UPDATE materials
                    SET current_width  = 0,
                        current_weight = 0,
                        is_active     = FALSE,
                        status        = '已耗尽',
                        updated_at    = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (parent_id,))
                # 写入余料报废日志
                cur.execute("""
                    INSERT INTO production_scrap
                        (material_id, material_number, scrap_type,
                         scrap_width, scrap_weight, reason)
                    VALUES (%s, %s, 'auto_close', %s, %s, %s);
                """, (
                    parent_id,
                    parent_num,
                    new_width,      # 结案时的剩余宽度（虽然已归零，但记录快照）
                    new_weight,     # 结案时的剩余重量（归零前快照）
                    f"分条触发自动结案：切出{count}条({target_width}mm/条)，"
                    f"消耗宽度{total_consumed}mm，剩余{new_width}mm低于阈值{threshold}mm",
                ))
            else:
                cur.execute("""
                    UPDATE materials
                    SET current_width  = %s,
                        current_weight = %s,
                        updated_at    = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (new_width, new_weight, parent_id))

            # 批量创建子料，编号格式：{父料编号}-S{序号}
            child_ids = []
            child_weights = []
            for i in range(count):
                seq = i + 1
                child_num = f"{parent_num}-S{seq}"
                child_weight = round(target_width / cur_width_f * cur_weight_f, 4) if cur_width_f > 0 and cur_weight_f > 0 else 0
                cur.execute("""
                    INSERT INTO materials
                        (material_number, material_name, material_type,
                         original_width, current_width,
                         original_weight, current_weight,
                         thickness, batch_no,
                         parent_id, scrap_threshold,
                         is_active, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, '待领用')
                    RETURNING id;
                """, (
                    child_num,
                    f"{parent_num}-S{seq}",
                    mat_type,
                    target_width, target_width,
                    child_weight, child_weight,
                    thickness, batch_no,
                    parent_id,
                    threshold if threshold else 0,
                ))
                child_id = cur.fetchone()[0]
                child_ids.append(child_id)
                child_weights.append(child_weight)

            # ── 溯源日志（批量分条只记一条日志，取第一条子料 ID）────────
            first_child = child_ids[0] if child_ids else None
            cur.execute("""
                INSERT INTO material_slitting_logs
                    (parent_id, child_id, operator_id, operator_name,
                     slit_width, slit_count, slit_weight,
                     parent_consumed_width, parent_remain_width,
                     parent_auto_closed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                parent_id, first_child, None, None,
                target_width, count,
                sum(child_weights),
                total_consumed,
                new_width if not auto_close else 0,
                auto_close,
            ))

            conn.commit()

            msg = (
                f"分条成功：从 {parent_num} 切出 {count} 条 "
                f"(每条 {target_width}mm)，消耗宽度 {total_consumed}mm，"
                f"消耗重量 {consumed_weight}kg。"
            )
            if auto_close:
                msg += (f" 父料剩余宽度 {new_width}mm 低于报废阈值 "
                        f"{threshold}mm，已自动结案，归零重量 "
                        f"{new_weight}kg 并记录报废日志。")
            return True, msg, child_ids


def slit_material(material_id, slit_width):
    """
    旧版分条接口（兼容保留）：
    从父料上切下一条指定宽度，创建单个子料。
    """
    try:
        ok, msg, ids = process_slitting(
            parent_id=material_id,
            target_width=slit_width,
            count=1,
        )
        return ok, msg
    except ValueError as e:
        return False, str(e)


def update_material(material_id, material_name=None, scrap_threshold=None,
                    is_active=None, remark=None):
    """
    更新物料的可编辑字段。
    注意：original_width / current_width / parent_id 不允许随意修改。
    """
    fields = []
    vals = []
    if material_name is not None:
        fields.append("material_name = %s"); vals.append(material_name)
    if scrap_threshold is not None:
        fields.append("scrap_threshold = %s"); vals.append(scrap_threshold)
    if is_active is not None:
        fields.append("is_active = %s"); vals.append(is_active)
    if remark is not None:
        fields.append("remark = %s"); vals.append(remark)
    if not fields:
        return
    fields.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(material_id)
    sql = "UPDATE materials SET " + ", ".join(fields) + " WHERE id = %s"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, vals)
            conn.commit()


def scrap_material(material_id, operator_id=None, operator_name="", reason=""):
    """
    手动清理余料：将物料强制结案，归零当前重量，并将差额记录到 production_scrap。

    参数：
        operator_id   : 操作人 ID
        operator_name : 操作人姓名（快照）
        reason        : 手动清理原因（由仓库人员填写）

    逻辑：
        1. 读取物料当前 current_width / current_weight
        2. 归零 current_width / current_weight
        3. is_active=FALSE, status='已耗尽'
        4. 写入 production_scrap 日志（scrap_type='manual_cleanup'）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, current_width, current_weight, material_number, is_active
                FROM materials WHERE id = %s FOR UPDATE;
            """, (material_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"物料 ID={material_id} 不存在")
            (mid, scrap_width, scrap_weight, mat_num, is_active) = row
            if not is_active:
                raise ValueError(f"物料 {mat_num} 已经结案，无需重复清理")

            scrap_w  = float(scrap_width)  if scrap_width  is not None else 0.0
            scrap_wt = float(scrap_weight) if scrap_weight is not None else 0.0

            # 归零并结案
            cur.execute("""
                UPDATE materials
                SET current_width  = 0,
                    current_weight = 0,
                    is_active     = FALSE,
                    status        = '已耗尽',
                    updated_at    = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (material_id,))

            # 写入报废日志
            cur.execute("""
                INSERT INTO production_scrap
                    (material_id, material_number, scrap_type,
                     scrap_width, scrap_weight, reason,
                     operator_id, operator_name)
                VALUES (%s, %s, 'manual_cleanup', %s, %s, %s, %s, %s);
            """, (
                material_id,
                mat_num,
                scrap_w,
                scrap_wt,
                reason or "手动清理余料",
                operator_id,
                operator_name,
            ))
            conn.commit()

    return True, (f"物料 {mat_num} 已手动结案，"
                  f"清零宽度 {scrap_w}mm / 重量 {scrap_wt}kg，"
                  f"已记录报废日志。")


def execute_material_slitting(parent_id, slit_width, slit_weight=None,
                               operator_id=None, operator_name="", remark=""):
    """
    精细分条接口 —— 单次从父卷分出固定宽度的子卷（精确控制重量）。

    参数：
        parent_id      : 父料 ID
        slit_width     : 子卷宽度（mm）
        slit_weight    : 子卷重量（kg），若不传则按父卷重量比例自动推算
        operator_id    : 操作人 ID（记录分条日志）
        operator_name  : 操作人姓名快照
        remark         : 备注

    逻辑：
        1. 加锁父料行（FOR UPDATE），读取 original_width / current_width / original_weight / current_weight
        2. 校验分条宽度不超过父料剩余宽度
        3. slit_weight 为 None 时，按当前剩余比例推算：weight = (slit_width / current_width) * current_weight
        4. 创建子料记录，继承父料的 material_type / thickness / batch_no / batch_no
           子料 original_weight = slit_weight（或推算值），current_weight = slit_weight
        5. 扣减父料 current_width 和 current_weight
        6. 若扣减后 current_width <= scrap_threshold，触发自动结案（同 process_slitting）
        7. 写入 material_slitting_logs（分条溯源日志）
        8. 若自动结案，同步写入 production_scrap 日志

    返回：(成功标志, 消息, 新增子料ID)
    异常：ValueError
    """
    if slit_width <= 0:
        raise ValueError("分条宽度必须大于 0")

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 锁住父料行
            cur.execute("""
                SELECT id, current_width, current_weight,
                       original_width, original_weight,
                       scrap_threshold,
                       material_number, material_type,
                       thickness, batch_no,
                       is_active
                FROM materials WHERE id = %s FOR UPDATE;
            """, (parent_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"父料 ID={parent_id} 不存在")
            (pid, cur_width, cur_weight,
             orig_width, orig_weight,
             threshold,
             parent_num, mat_type,
             thickness, batch_no,
             is_active) = row

            if not is_active:
                raise ValueError(f"父料 {parent_num} 已结案，无法分条")

            cur_width_f  = float(cur_width)  if cur_width  is not None else 0.0
            cur_weight_f = float(cur_weight) if cur_weight is not None else 0.0

            if slit_width > cur_width_f:
                raise ValueError(
                    f"分条宽度({slit_width}mm)超过父料剩余宽度({cur_width_f}mm)"
                )

            # 精确重量计算：若未指定，按剩余宽度比例推算
            if slit_weight is None:
                if cur_width_f > 0 and cur_weight_f > 0:
                    slit_weight_f = round((slit_width / cur_width_f) * cur_weight_f, 4)
                else:
                    slit_weight_f = 0.0
            else:
                slit_weight_f = float(slit_weight)

            # 母卷扣减
            new_width  = round(cur_width_f  - slit_width, 2)
            new_weight = round(cur_weight_f - slit_weight_f, 4)
            auto_close = (new_width <= float(threshold) if threshold else False)

            # 子卷编号：父料编号-S{seq}
            cur.execute("""
                SELECT COALESCE(MAX(
                    CAST(SUBSTRING(material_number FROM POSITION('S' IN material_number)+1) AS INTEGER)
                ), 0)
                FROM materials WHERE parent_id = %s;
            """, (parent_id,))
            last_seq = cur.fetchone()[0] or 0
            child_num = f"{parent_num}-S{last_seq + 1}"

            # 更新父料（自动结案时归零）
            if auto_close:
                cur.execute("""
                    UPDATE materials
                    SET current_width  = 0,
                        current_weight = 0,
                        is_active     = FALSE,
                        status        = '已耗尽',
                        updated_at    = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (parent_id,))
                # 余料报废日志
                cur.execute("""
                    INSERT INTO production_scrap
                        (material_id, material_number, scrap_type,
                         scrap_width, scrap_weight, reason,
                         operator_id, operator_name)
                    VALUES (%s, %s, 'auto_close', %s, %s, %s, %s, %s);
                """, (
                    parent_id, parent_num,
                    new_width, new_weight,
                    f"精细分条触发自动结案：切出{child_num}({slit_width}mm/{slit_weight_f}kg)，"
                    f"母卷剩余{new_width}mm低于阈值{threshold}mm",
                    operator_id, operator_name,
                ))
            else:
                cur.execute("""
                    UPDATE materials
                    SET current_width  = %s,
                        current_weight = %s,
                        updated_at    = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (new_width, new_weight, parent_id))

            # 创建子料（继承关键属性，精确记录重量）
            cur.execute("""
                INSERT INTO materials
                    (material_number, material_name, material_type,
                     original_width, current_width,
                     original_weight, current_weight,
                     thickness, batch_no,
                     parent_id, scrap_threshold,
                     is_active, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, '待领用')
                RETURNING id;
            """, (
                child_num,
                child_num,
                mat_type,
                slit_width, slit_width,          # original_width = current_width = slit_width
                slit_weight_f, slit_weight_f,    # original_weight = current_weight = slit_weight_f
                thickness, batch_no,
                parent_id,
                threshold if threshold else 0,
            ))
            child_id = cur.fetchone()[0]

            # ── 溯源日志写入 material_slitting_logs ──────────────────
            cur.execute("""
                INSERT INTO material_slitting_logs
                    (parent_id, child_id, operator_id, operator_name,
                     slit_width, slit_count, slit_weight,
                     parent_consumed_width, parent_remain_width,
                     parent_auto_closed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                parent_id, child_id,
                operator_id, operator_name,
                slit_width, 1, slit_weight_f,
                slit_width, new_width if not auto_close else 0,
                auto_close,
            ))
            slit_log_id = cur.fetchone()[0]

            conn.commit()

            msg = (
                f"精细分条成功：从 {parent_num} 分出 {child_num} "
                f"({slit_width}mm / {slit_weight_f}kg)，"
                f"母卷剩余 {new_width}mm / {new_weight}kg"
            )
            if auto_close:
                msg += (f"（剩余宽度低于阈值 {threshold}mm，已自动结案母卷）")
            return True, msg, child_id


def close_material_item(material_id, operator_id=None, operator_name="",
                        reason=""):
    """
    仓库员手动标记余料为已报废（status='scrapped'），归零剩余重量。
    与 scrap_material 的区别：
      - scrap_material：将 is_active 设为 FALSE、status='已耗尽'，用于分条余料归零
      - close_material_item：is_active 保持 TRUE，仅将 status 改为 'scrapped'，
        表示"余料保留在系统中但已无法使用"

    参数：
        material_id     : 物料 ID
        operator_id    : 操作人 ID
        operator_name  : 操作人姓名快照
        reason         : 报废原因

    返回：(成功标志, 消息)
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, current_width, current_weight,
                       material_number, is_active, status
                FROM materials WHERE id = %s FOR UPDATE;
            """, (material_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"物料 ID={material_id} 不存在")
            (mid, scrap_width, scrap_weight,
             mat_num, is_active, cur_status) = row

            scrap_w  = float(scrap_width)  if scrap_width  is not None else 0.0
            scrap_wt = float(scrap_weight) if scrap_weight is not None else 0.0

            if cur_status == 'scrapped':
                raise ValueError(f"物料 {mat_num} 已经是报废状态，无需重复操作")

            # 归零并标记为报废
            cur.execute("""
                UPDATE materials
                SET current_width  = 0,
                    current_weight = 0,
                    status         = 'scrapped',
                    updated_at     = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (material_id,))

            # 写入分条日志（type=manual_scrapped）
            cur.execute("""
                INSERT INTO material_slitting_logs
                    (parent_id, operator_id, operator_name,
                     slit_width, slit_count, slit_weight,
                     parent_consumed_width, parent_remain_width,
                     parent_auto_closed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE);
            """, (
                material_id,
                operator_id, operator_name,
                scrap_w, 1, scrap_wt,
                scrap_w, 0,
            ))

            # 同时记录生产报废日志
            cur.execute("""
                INSERT INTO production_scrap
                    (material_id, material_number, scrap_type,
                     scrap_width, scrap_weight, reason,
                     operator_id, operator_name)
                VALUES (%s, %s, 'manual_scrapped', %s, %s, %s, %s, %s);
            """, (
                material_id, mat_num,
                scrap_w, scrap_wt,
                reason or "仓库员手动标记报废",
                operator_id, operator_name,
            ))

            conn.commit()

    return True, (
        f"物料 {mat_num} 已标记为报废，"
        f"清零宽度 {scrap_w}mm / 重量 {scrap_wt}kg"
    )


def get_material_children(parent_id):
    """查询某物料的所有子料（分条产出）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM materials WHERE parent_id = %s ORDER BY id DESC;
            """, (parent_id,))
            return cur.fetchall()


def get_material_summary():
    """
    返回物料台账统计摘要：
    - 总数 / 使用中 / 已结案
    - 各 material_type 数量
    - 即将触及阈值的预警物料（current_width <= scrap_threshold 且 is_active=TRUE）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                            AS total,
                    COUNT(*) FILTER (WHERE is_active)  AS active,
                    COUNT(*) FILTER (WHERE NOT is_active) AS closed
                FROM materials;
            """)
            total_row = cur.fetchone()

            cur.execute("""
                SELECT material_type, COUNT(*) AS cnt
                FROM materials
                GROUP BY material_type
                ORDER BY cnt DESC;
            """)
            type_rows = cur.fetchall()

            cur.execute("""
                SELECT id, material_number, material_name,
                       current_width, scrap_threshold,
                       (current_width - scrap_threshold) AS remain_until_scrap
                FROM materials
                WHERE is_active = TRUE
                  AND scrap_threshold > 0
                  AND current_width <= scrap_threshold
                ORDER BY current_width ASC;
            """)
            warning_rows = cur.fetchall()

            return {
                'total':   int(total_row['total']),
                'active':  int(total_row['active']),
                'closed':  int(total_row['closed']),
                'by_type': {r['material_type']: int(r['cnt']) for r in type_rows},
                'warnings': [dict(r) for r in warning_rows],
            }


def get_scrap_logs(limit=100, offset=0):
    """
    返回余料报废日志列表（供仓库审核/统计用）。
    包含 auto_close（自动结案）和 manual_cleanup（手动清理）两种类型。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT s.*,
                       u.real_name AS operator_name
                FROM production_scrap s
                LEFT JOIN users u ON s.operator_id = u.id
                ORDER BY s.created_at DESC
                LIMIT %s OFFSET %s;
            """, (limit, offset))
            return cur.fetchall()


def count_scrap_logs():
    """统计报废日志总数"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM production_scrap;")
            return cur.fetchone()[0]


def get_scrap_summary():
    """
    返回报废统计摘要：
    - 总记录数
    - 自动结案次数 / 手动清理次数
    - 累计报废宽度 / 累计报废重量
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    scrap_type,
                    COUNT(*)                           AS cnt,
                    COALESCE(SUM(scrap_width),  0)    AS total_scrap_width,
                    COALESCE(SUM(scrap_weight), 0)    AS total_scrap_weight
                FROM production_scrap
                GROUP BY scrap_type;
            """)
            rows = {r['scrap_type']: r for r in cur.fetchall()}

            cur.execute("SELECT COUNT(*) FROM production_scrap;")
            total = int(cur.fetchone()[0])

            return {
                'total':            total,
                'auto_close': {
                    'cnt':              int(rows.get('auto_close', {}).get('cnt', 0)),
                    'total_width':      float(rows.get('auto_close', {}).get('total_scrap_width', 0)),
                    'total_weight':     float(rows.get('auto_close', {}).get('total_scrap_weight', 0)),
                },
                'manual_cleanup': {
                    'cnt':              int(rows.get('manual_cleanup', {}).get('cnt', 0)),
                    'total_width':      float(rows.get('manual_cleanup', {}).get('total_scrap_width', 0)),
                    'total_weight':     float(rows.get('manual_cleanup', {}).get('total_scrap_weight', 0)),
                },
            }


def get_material_alerts():
    """
    返回即将触及阈值的物料预警列表（用于仓库部门首页）

    条件：current_width <= scrap_threshold 且 is_active = TRUE
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    id,
                    material_number,
                    material_name,
                    material_type,
                    current_width,
                    scrap_threshold,
                    status
                FROM materials
                WHERE is_active = TRUE
                  AND current_width <= scrap_threshold
                  AND scrap_threshold > 0
                ORDER BY current_width ASC;
            """)
            return cur.fetchall()


# ============================================================================
# 仓库管理 - 入库单 (Inbound Orders)
# ============================================================================

def ensure_inbound_orders_table():
    """
    确保 inbound_orders 表存在，不存在则创建。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inbound_orders (
                    id              SERIAL PRIMARY KEY,
                    order_no        VARCHAR(64)  NOT NULL UNIQUE,
                    supplier        VARCHAR(128) DEFAULT '',
                    material_type   VARCHAR(32)  DEFAULT '卷料',
                    expected_width  NUMERIC(10,2) DEFAULT 0,
                    expected_weight NUMERIC(10,2) DEFAULT 0,
                    actual_width    NUMERIC(10,2),
                    actual_weight   NUMERIC(10,2),
                    status          VARCHAR(16)  DEFAULT 'pending',
                    approved_by     INTEGER,
                    approved_at     TIMESTAMP,
                    remark          TEXT DEFAULT '',
                    created_by      INTEGER,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()


def add_inbound_order(order_no, supplier, material_type, expected_width,
                     expected_weight, created_by, remark=''):
    """新建入库申请单"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO inbound_orders
                    (order_no, supplier, material_type, expected_width,
                     expected_weight, status, created_by, remark)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
                ON CONFLICT (order_no) DO NOTHING;
            """, (order_no, supplier, material_type, expected_width,
                  expected_weight, created_by, remark))
            conn.commit()


def get_pending_inbound_orders():
    """
    返回待审批的入库单，供主管审批。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT i.*, u.real_name AS creator_name
                FROM inbound_orders i
                LEFT JOIN users u ON i.created_by = u.id
                WHERE i.status = 'pending'
                ORDER BY i.created_at DESC;
            """)
            return cur.fetchall()


def approve_inbound_order(order_id, approved_by):
    """主管审批通过入库单"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE inbound_orders
                SET status = 'approved', approved_by = %s, approved_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'pending';
            """, (approved_by, order_id))
            conn.commit()


def reject_inbound_order(order_id, approved_by):
    """主管驳回入库单"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE inbound_orders
                SET status = 'rejected', approved_by = %s, approved_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'pending';
            """, (approved_by, order_id))
            conn.commit()


def get_inbound_summary():
    """
    返回入库统计摘要：待审数、已通过数、今日入库数。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending')  AS pending,
                    COUNT(*) FILTER (WHERE status = 'approved') AS approved,
                    COUNT(*) FILTER (
                        WHERE status = 'approved'
                          AND DATE(approved_at) = CURRENT_DATE
                    )                                            AS today_approved
                FROM inbound_orders;
            """)
            row = cur.fetchone()
            return {
                'pending': int(row[0]),
                'approved': int(row[1]),
                'today_approved': int(row[2]),
            }


# ============================================================================
# 仓库管理 - 呆滞料分析
# ============================================================================

def get_slow_moving_materials():
    """
    呆滞料分析：超过 30 天未使用（无子料分出）的活跃物料。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    m.id,
                    m.material_number,
                    m.material_name,
                    m.material_type,
                    m.original_width,
                    m.current_width,
                    m.current_weight,
                    m.created_at,
                    (CURRENT_DATE - DATE(m.created_at)) AS days_old
                FROM materials m
                WHERE m.is_active = TRUE
                  AND m.parent_id IS NULL
                  AND (CURRENT_DATE - DATE(m.created_at)) >= 30
                  AND m.current_width > 50
                  AND NOT EXISTS (
                      SELECT 1 FROM materials c WHERE c.parent_id = m.id
                  )
                ORDER BY days_old DESC, m.current_width DESC;
            """)
            return cur.fetchall()


def get_whse_inventory_overview():
    """
    返回仓库库存总览：使用中/已结案数、预警数、呆滞料数、总宽度/重量。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE is_active = TRUE)  AS active,
                    COUNT(*) FILTER (WHERE is_active = FALSE) AS closed
                FROM materials;
            """)
            row = cur.fetchone()

            cur.execute("""
                SELECT COUNT(*) FROM materials
                WHERE is_active = TRUE
                  AND scrap_threshold > 0
                  AND current_width <= scrap_threshold;
            """)
            alert_cnt = int(cur.fetchone()[0])

            cur.execute("""
                SELECT COUNT(*) FROM materials m
                WHERE m.is_active = TRUE
                  AND m.parent_id IS NULL
                  AND (CURRENT_DATE - DATE(m.created_at)) >= 30
                  AND m.current_width > 50
                  AND NOT EXISTS (SELECT 1 FROM materials c WHERE c.parent_id = m.id);
            """)
            slow_cnt = int(cur.fetchone()[0])

            cur.execute("""
                SELECT
                    COALESCE(SUM(current_width), 0)  AS total_width,
                    COALESCE(SUM(current_weight), 0) AS total_weight
                FROM materials WHERE is_active = TRUE;
            """)
            inv = cur.fetchone()

            return {
                'active':       int(row[0]),
                'closed':       int(row[1]),
                'alert':        alert_cnt,
                'slow':         slow_cnt,
                'total_width':  float(inv[0]),
                'total_weight': float(inv[1]),
            }


# ============================================================================
# 品质管理 (QC) - 质检记录
# ============================================================================

def get_qc_pass_rate_trend(days=30):
    """
    返回近 N 天每日合格率走势。
    每条记录含：date, qty_checked, qty_passed, qty_failed, pass_rate
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    DATE(checked_at)                               AS date,
                    COALESCE(SUM(qty_checked), 0)::INTEGER       AS qty_checked,
                    COALESCE(SUM(qty_passed),  0)::INTEGER       AS qty_passed,
                    COALESCE(SUM(qty_failed),  0)::INTEGER       AS qty_failed,
                    CASE
                        WHEN COALESCE(SUM(qty_checked), 0) = 0 THEN NULL
                        ELSE ROUND(
                            SUM(qty_passed)::NUMERIC
                            / SUM(qty_checked)::NUMERIC * 100, 1)
                    END                                           AS pass_rate
                FROM qc_logs
                WHERE checked_at >= CURRENT_DATE - INTERVAL '%s days'
                  AND audit_status = 'approved'
                GROUP BY DATE(checked_at)
                ORDER BY date ASC;
            """, (days,))
            rows = cur.fetchall()

            # 补充今日合格率
            total_checked = sum(r['qty_checked'] for r in rows if r['qty_checked'])
            total_passed  = sum(r['qty_passed']  for r in rows if r['qty_checked'])
            today_rate = None
            if total_checked > 0:
                today_rate = round(total_passed / total_checked * 100, 1)

            return {
                'days': rows,
                'today_pass_rate': today_rate,
            }


def get_major_qc_anomalies():
    """
    返回待审核的重大异常（is_major=TRUE 且 audit_status='pending_review'）。
    按 checked_at DESC 倒序。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    q.id,
                    q.part_id,
                    p.part_number,
                    p.internal_name,
                    q.qty_checked,
                    q.qty_passed,
                    q.qty_failed,
                    q.result,
                    q.defect_reason,
                    q.remark,
                    q.checked_at,
                    u.real_name AS operator_name
                FROM qc_logs q
                LEFT JOIN parts p ON q.part_id = p.id
                LEFT JOIN users u ON q.operator_id = u.id
                WHERE q.is_major = TRUE
                  AND q.audit_status = 'pending_review'
                ORDER BY q.checked_at DESC;
            """)
            return cur.fetchall()


def get_pending_parts_for_qc():
    """
    返回全检员待检产品列表。
    规则：近 3 天内有 approved 报工记录但尚未在 qc_logs 留档的零件。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT
                    pl.part_id,
                    pt.part_number,
                    pt.internal_name,
                    COALESCE(SUM(pl.qty_good), 0)::INTEGER AS pending_qty
                FROM production_logs pl
                JOIN parts pt ON pl.part_id = pt.id
                WHERE pl.status = 'approved'
                  AND pl.report_time >= CURRENT_DATE - INTERVAL '3 days'
                  AND NOT EXISTS (
                      SELECT 1 FROM qc_logs q
                      WHERE q.part_id = pl.part_id
                        AND DATE(q.checked_at) >= CURRENT_DATE - INTERVAL '3 days'
                  )
                GROUP BY pl.part_id, pt.part_number, pt.internal_name
                ORDER BY pending_qty DESC;
            """)
            return cur.fetchall()


def submit_qc_log(part_id, operator_id, qty_checked, qty_passed,
                   qty_failed=0, result='pass', defect_reason='',
                   remark='', is_major=False):
    """
    提交质检记录。
    - is_major: 报废率>10% 或 qty_failed>=5 视为重大异常
    - audit_status: 非重大直接 approved；重大待主管审核
    """
    if qty_failed > 0 and qty_failed >= 5:
        is_major = True
    if qty_checked > 0 and qty_failed / qty_checked > 0.10:
        is_major = True

    audit_status = 'approved' if not is_major else 'pending_review'

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO qc_logs
                    (part_id, operator_id, qty_checked, qty_passed,
                     qty_failed, result, defect_reason, remark,
                     is_major, audit_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (part_id, operator_id, qty_checked, qty_passed,
                  qty_failed, result, defect_reason, remark,
                  is_major, audit_status))
            conn.commit()


def audit_qc_log(qc_log_id, auditor_id, approved):
    """
    主管审核重大异常。
    - approved=True  → audit_status = 'approved'
    - approved=False → audit_status = 'rejected'
    """
    status = 'approved' if approved else 'rejected'
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE qc_logs
                SET audit_status = %s,
                    auditor_id   = %s,
                    audited_at   = CURRENT_TIMESTAMP
                WHERE id = %s AND is_major = TRUE;
            """, (status, auditor_id, qc_log_id))
            conn.commit()


def get_qc_summary_stats():
    """
    返回质检汇总统计：今日检验数/合格数/合格率/待审异常数。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COALESCE(SUM(qty_checked), 0)::INTEGER AS today_checked,
                    COALESCE(SUM(qty_passed),  0)::INTEGER AS today_passed,
                    COUNT(*) FILTER (
                        WHERE is_major = TRUE
                          AND audit_status = 'pending_review'
                    )::INTEGER                             AS pending_review
                FROM qc_logs
                WHERE DATE(checked_at) = CURRENT_DATE
                  AND audit_status = 'approved';
            """)
            row = cur.fetchone()
            checked = int(row[0])
            passed  = int(row[1])
            rate = round(passed / checked * 100, 1) if checked > 0 else None
            return {
                'today_checked':    checked,
                'today_passed':     passed,
                'today_pass_rate':  rate,
                'pending_review':   int(row[2]),
            }


# ============================================================================
# 品质部 (qc) - 巡检记录（样件确认、机台巡检）
# ============================================================================

def resolve_part_id_by_number(part_number):
    """根据零件编号查找零件 ID"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM parts WHERE part_number = %s LIMIT 1;",
                (part_number,))
            row = cur.fetchone()
            return int(row[0]) if row else None

def submit_inspection_log(part_id, operator_id, inspection_type,
                           result, defect_reason='', remark='',
                           is_blocked=False, blocked_reason=''):
    """
    提交巡检记录。
    inspection_type: 'first_piece'(样件/首件) | 'patrol'(机台巡检) | 'oqc'(出货检验)
    result: 'pass' | 'fail' | 'rework'
    is_blocked: True → 标记为卡控，阻止 pkg 发货
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO qc_inspection_logs
                    (part_id, operator_id, inspection_type, result,
                     defect_reason, remark, is_blocked, blocked_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (part_id, operator_id, inspection_type, result,
                  defect_reason, remark, is_blocked, blocked_reason))
            conn.commit()


def get_qc_inspection_logs(limit=50, offset=0):
    """返回巡检记录列表（主管查看）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    i.id, i.part_id, i.inspection_type, i.result,
                    i.defect_reason, i.remark, i.inspected_at,
                    i.is_blocked, i.blocked_reason, i.auditor_result, i.audited_at,
                    pt.part_number, pt.internal_name,
                    u.real_name AS operator_name,
                    a.real_name AS auditor_name
                FROM qc_inspection_logs i
                LEFT JOIN parts pt ON i.part_id = pt.id
                LEFT JOIN users  u  ON i.operator_id = u.id
                LEFT JOIN users  a  ON i.auditor_id = a.id
                ORDER BY i.inspected_at DESC
                LIMIT %s OFFSET %s;
            """, (limit, offset))
            return cur.fetchall()


def get_today_patrol_logs():
    """返回今日机台巡检记录（主管看板用）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    i.id, i.part_id, i.inspection_type, i.result,
                    i.defect_reason, i.inspected_at, i.is_blocked, i.blocked_reason,
                    pt.part_number, pt.internal_name AS part_name,
                    u.real_name AS operator_name
                FROM qc_inspection_logs i
                LEFT JOIN parts pt ON i.part_id = pt.id
                LEFT JOIN users  u  ON i.operator_id = u.id
                WHERE DATE(i.inspected_at) = CURRENT_DATE
                ORDER BY i.inspected_at DESC;
            """)
            return cur.fetchall()


def get_qc_today_summary():
    """返回品质部门今日汇总：巡检数、合格数、不合格数、合格率"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 注意：qc_inspection_logs 每行就是一条巡检记录，没有 qty_* 数字列
            # 用 COUNT 代替 SUM(qty_*)
            cur.execute("""
                SELECT
                    COUNT(*)::INTEGER                                   AS today_inspected,
                    COUNT(*) FILTER (WHERE result = 'pass')::INTEGER   AS today_passed,
                    COUNT(*) FILTER (WHERE result = 'fail')::INTEGER  AS today_failed
                FROM qc_inspection_logs
                WHERE DATE(inspected_at) = CURRENT_DATE;
            """)
            row = cur.fetchone()
            inspected = int(row[0])
            passed    = int(row[1])
            rate = round(passed / inspected * 100, 1) if inspected > 0 else None
            return {
                'today_inspected': inspected,
                'today_passed':   passed,
                'today_failed':   int(row[2]),
                'today_pass_rate': rate,
            }


def get_blocked_parts():
    """返回当前被卡控的零件列表（is_blocked=TRUE，未解除的巡检记录）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (i.part_id)
                    i.id, i.part_id, i.inspection_type, i.result,
                    i.defect_reason, i.blocked_reason, i.inspected_at,
                    pt.part_number, pt.internal_name,
                    u.real_name AS operator_name
                FROM qc_inspection_logs i
                LEFT JOIN parts pt ON i.part_id = pt.id
                LEFT JOIN users  u  ON i.operator_id = u.id
                WHERE i.is_blocked = TRUE
                ORDER BY i.part_id, i.inspected_at DESC;
            """)
            return cur.fetchall()


def unblock_part(inspection_id, auditor_id):
    """主管解除卡控"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE qc_inspection_logs
                SET is_blocked = FALSE,
                    auditor_id   = %s,
                    auditor_result = 'approved',
                    audited_at   = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (auditor_id, inspection_id))
            conn.commit()


def get_oqc_reports(status_filter=None, limit=50, offset=0):
    """返回 OQC 出货报告列表"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where = "WHERE r.status = %s" if status_filter else ""
            params = (status_filter, limit, offset) if status_filter else (limit, offset)
            cur.execute(f"""
                SELECT
                    r.id, r.part_id, r.status, r.qty_inspected,
                    r.qty_passed, r.qty_failed, r.report_no,
                    r.report_file, r.remark, r.created_at,
                    r.audited_at,
                    pt.part_number, pt.internal_name AS part_name,
                    u.real_name AS creator_name,
                    a.real_name AS auditor_name
                FROM oqc_reports r
                LEFT JOIN parts pt ON r.part_id = pt.id
                LEFT JOIN users  u  ON r.created_by = u.id
                LEFT JOIN users  a  ON r.auditor_id = a.id
                {where}
                ORDER BY r.created_at DESC
                LIMIT %s OFFSET %s;
            """, params)
            return cur.fetchall()


def count_oqc_reports(status_filter=None):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if status_filter:
                cur.execute(
                    "SELECT COUNT(*) FROM oqc_reports WHERE status = %s;",
                    (status_filter,))
            else:
                cur.execute("SELECT COUNT(*) FROM oqc_reports;")
            return int(cur.fetchone()[0])


def create_oqc_report(part_id, created_by, qty_inspected, qty_passed, qty_failed):
    """生成 OQC 报告单"""
    import datetime
    today_str = datetime.date.today().strftime('%Y%m%d')
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM oqc_reports;")
            seq = cur.fetchone()[0]
            report_no = f"OQC-{today_str}-{seq:03d}"
            cur.execute("""
                INSERT INTO oqc_reports
                    (part_id, created_by, qty_inspected, qty_passed,
                     qty_failed, report_no, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending_approve');
            """, (part_id, created_by, qty_inspected, qty_passed, qty_failed, report_no))
            conn.commit()
            return report_no


def approve_oqc_report(report_id, auditor_id):
    """主管审核通过 OQC 报告"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE oqc_reports
                SET status = 'approved',
                    auditor_id = %s,
                    audited_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'pending_approve';
            """, (auditor_id, report_id))
            conn.commit()


# ============================================================================
# 全检包装部 (pkg) - Safety Guard 核心
# ============================================================================

def check_pkg_safety_guard(part_id):
    """
    Safety Guard：校验零件是否可以进行包装/发货操作。
    规则：
    1. 该零件必须有已审核的生产报工记录 (production_logs.status='approved')
    2. 不能有未解除的 QC 巡检卡控 (qc_inspection_logs.is_blocked=TRUE)
    3. 不能有未解除的全检不合格卡控 (pkg_packaging_logs.is_blocked=TRUE)

    Returns:
        (True, "")             = 可以操作
        (False, reason)       = 被阻止，原因见 reason
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:

            # 规则1：必须有生产报工记录
            cur.execute("""
                SELECT 1 FROM production_logs
                WHERE part_id = %s AND status = 'approved'
                LIMIT 1;
            """, (part_id,))
            if not cur.fetchone():
                return False, "无生产报工记录，禁止发货"

            # 规则2：不能有未解除的巡检卡控
            cur.execute("""
                SELECT 1 FROM qc_inspection_logs
                WHERE part_id = %s AND is_blocked = TRUE
                LIMIT 1;
            """, (part_id,))
            if cur.fetchone():
                return False, "该零件被品质部巡检验异常卡控，禁止发货"

            return True, ""


def get_part_customer_alias(internal_part_id, customer_id=None):
    """
    【件号别名查询 — V3.0 §2.2 一物多码】
    根据内部件号和客户 ID 返回发货件号。

    逻辑：优先从 part_aliases 表取别名映射；若无可用映射则返回内部件号。

    参数
    ----
    internal_part_id : int   内部零件 ID
    customer_id     : int   客户 ID（可为空，为空时返回内部件号）

    返回
    ----
    str  客户件号（alias_part_number）或内部件号（part_number）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 有 customer_id 时优先取该客户的别名
            if customer_id:
                cur.execute("""
                    SELECT alias_part_number
                    FROM part_aliases
                    WHERE internal_part_id = %s
                      AND customer_id = %s
                      AND is_active = TRUE
                    LIMIT 1;
                """, (internal_part_id, customer_id))
                row = cur.fetchone()
                if row and row[0]:
                    return row[0]

            # 无 customer_id 或无映射时，取默认别名（any active customer）
            cur.execute("""
                SELECT alias_part_number
                FROM part_aliases
                WHERE internal_part_id = %s
                  AND is_active = TRUE
                ORDER BY customer_id DESC NULLS LAST
                LIMIT 1;
            """, (internal_part_id,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]

            # 无任何映射，返回内部件号
            cur.execute("SELECT part_number FROM parts WHERE id = %s LIMIT 1;", (internal_part_id,))
            row = cur.fetchone()
            return row[0] if row else str(internal_part_id)


def get_pkg_ready_inventory(customer_id=None):
    """
    返回可包装/发货的库存（含件号别名）。
    - total_good: 累计良品总数（生产报工）
    - total_packaged: 累计已包装数（pkg_packaging_logs.result='pass', is_blocked=FALSE）
    - total_shipped: 累计已发货数（pkg_shipping_logs）
    - ready_to_ship: 可发货数 = total_packaged - total_shipped
    - ready_to_pack: 可继续包装数 = total_good - total_packaged
    - customer_alias: 该客户的件号别名（无映射时为内部件号）

    customer_id: 客户 ID，用于解析件号别名
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    pl.part_id,
                    pt.part_number        AS internal_part_number,
                    pt.internal_name,
                    COALESCE(SUM(pl.qty_good), 0)::INTEGER  AS total_good,
                    COALESCE(SUM(pkg.qty_passed), 0)::INTEGER AS total_packaged,
                    COALESCE(SUM(shp.qty), 0)::INTEGER         AS total_shipped,
                    (COALESCE(SUM(pkg.qty_passed), 0)
                     - COALESCE(SUM(shp.qty), 0))::INTEGER  AS ready_to_ship,
                    (COALESCE(SUM(pl.qty_good), 0)
                     - COALESCE(SUM(pkg.qty_passed), 0))::INTEGER AS ready_to_pack
                FROM production_logs pl
                JOIN parts pt ON pl.part_id = pt.id
                LEFT JOIN pkg_packaging_logs pkg
                    ON pkg.part_id = pl.part_id
                    AND pkg.result = 'pass'
                    AND pkg.is_blocked = FALSE
                LEFT JOIN pkg_shipping_logs shp
                    ON shp.part_id = pl.part_id
                WHERE pl.status = 'approved'
                  AND pl.report_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY pl.part_id, pt.part_number, pt.internal_name
                ORDER BY (COALESCE(SUM(pkg.qty_passed), 0)
                          - COALESCE(SUM(shp.qty), 0)) DESC;
            """)
            rows = cur.fetchall()
            # 补充别名
            result = []
            for row in rows:
                alias = get_part_customer_alias(row['part_id'], customer_id)
                row['customer_alias'] = alias
                result.append(row)
            return result


def get_part_alias_map(part_ids, customer_id=None):
    """
    批量查询件号别名，返回 {part_id: alias_or_internal_number} 字典。
    用于列表页批量展示客户件号。
    """
    if not part_ids:
        return {}
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(part_ids))
            cur.execute(f"""
                SELECT pa.internal_part_id, pa.alias_part_number, pt.part_number
                FROM part_aliases pa
                JOIN parts pt ON pt.id = pa.internal_part_id
                WHERE pa.internal_part_id IN ({placeholders})
                  AND pa.is_active = TRUE
                  AND ({'%s' + (' OR pa.customer_id = %s' * (len(part_ids) - 1)) if customer_id else '1=1'});
            """, part_ids + ([customer_id] if customer_id else []))
            # 简单单 customer 场景
            cur.execute(f"""
                SELECT pa.internal_part_id, pa.alias_part_number, pt.part_number
                FROM part_aliases pa
                JOIN parts pt ON pt.id = pa.internal_part_id
                WHERE pa.internal_part_id IN ({placeholders})
                  AND pa.is_active = TRUE
            """, part_ids)
            rows = cur.fetchall()
            alias_map = {}
            for r in rows:
                alias_map[r[0]] = r[1] or r[2]
            # 补充无映射的内部件号
            mapped_ids = set(alias_map.keys())
            for pid in part_ids:
                if pid not in mapped_ids:
                    cur.execute("SELECT part_number FROM parts WHERE id = %s LIMIT 1;", (pid,))
                    rr = cur.fetchone()
                    if rr:
                        alias_map[pid] = rr[0]
            return alias_map


def check_pkg_shipping_eligibility(part_id, qty, customer_id=None):
    """
    发货 Safety Guard 升级版（V3.0 §2.2 P4 + §2.4）：
    1. 该零件必须有已审核报工
    2. 该零件无未解除的 QC 巡检卡控
    3. 该零件必须有"已包装"库存（total_packaged - total_shipped >= qty）
    4. 件号映射有效性（P4）：
       - 若该客户存在别名映射 → 正常
       - 若无映射 → 返回警告 message（允许发货，仅提示）

    customer_id: 客户 ID（可为空）
    Returns: (True, "") | (True, warning_msg) | (False, error_msg)
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 规则1：必须有生产报工记录
            cur.execute("""
                SELECT 1 FROM production_logs
                WHERE part_id = %s AND status = 'approved' LIMIT 1;
            """, (part_id,))
            if not cur.fetchone():
                return False, "无生产报工记录，禁止发货"

            # 规则2：不能有未解除的巡检卡控
            cur.execute("""
                SELECT 1 FROM qc_inspection_logs
                WHERE part_id = %s AND is_blocked = TRUE LIMIT 1;
            """, (part_id,))
            if cur.fetchone():
                return False, "该零件被品质部巡检验异常卡控，禁止发货"

            # 规则3：必须有足够的已包装库存才能发货
            cur.execute("""
                SELECT
                    COALESCE(SUM(pkg.qty_passed), 0)::INTEGER AS total_packaged,
                    COALESCE(SUM(shp.qty), 0)::INTEGER         AS total_shipped
                FROM production_logs pl
                LEFT JOIN pkg_packaging_logs pkg
                    ON pkg.part_id = pl.part_id
                    AND pkg.result = 'pass'
                    AND pkg.is_blocked = FALSE
                LEFT JOIN pkg_shipping_logs shp
                    ON shp.part_id = pl.part_id
                WHERE pl.part_id = %s AND pl.status = 'approved'
                GROUP BY pl.part_id;
            """, (part_id,))
            row = cur.fetchone()
            total_packaged = int(row[0]) if row else 0
            total_shipped  = int(row[1]) if row else 0
            available = total_packaged - total_shipped
            if available < qty:
                return False, (f"已包装库存不足：当前可发货 {available} 件，"
                              f"本次 {qty} 件，超出 {qty - available} 件")

            # 规则4：件号映射有效性（P4 警告，非阻止）
            warning_msg = None
            if customer_id:
                cur.execute("""
                    SELECT alias_part_number FROM part_aliases
                    WHERE internal_part_id = %s
                      AND customer_id = %s
                      AND is_active = TRUE
                    LIMIT 1;
                """, (part_id, customer_id))
                alias_row = cur.fetchone()
                if not alias_row:
                    # 无该客户映射 → 警告（允许发货）
                    warning_msg = (f"⚠️ 该客户（ID={customer_id}）尚无件号映射，"
                                  f"发货件号将使用内部件号，建议联系业务维护别名映射。")

            return True, warning_msg if warning_msg else ""


def check_pkg_packaging_eligibility(part_id, qty_passed):
    """
    包装防错 Guard：
    qty_passed 严禁超过该零件的"剩余可包装数"（total_good - total_packaged）
    Returns: (True, "") | (False, reason)
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COALESCE(SUM(pl.qty_good), 0)::INTEGER  AS total_good,
                    COALESCE(SUM(pkg.qty_passed), 0)::INTEGER AS total_packaged
                FROM production_logs pl
                LEFT JOIN pkg_packaging_logs pkg
                    ON pkg.part_id = pl.part_id
                    AND pkg.result = 'pass'
                    AND pkg.is_blocked = FALSE
                WHERE pl.part_id = %s AND pl.status = 'approved'
                GROUP BY pl.part_id;
            """, (part_id,))
            row = cur.fetchone()
            total_good      = int(row[0]) if row else 0
            total_packaged  = int(row[1]) if row else 0
            remaining = total_good - total_packaged
            if qty_passed > remaining:
                return False, (f"包装数超限：该零件剩余可包装 {remaining} 件，"
                              f"本次 {qty_passed} 件，超出 {qty_passed - remaining} 件")
            return True, ""


def get_pkg_today_summary():
    """返回包装部门今日汇总：已包装数、已发货数、合格率，防错日志数"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 今日包装汇总
            cur.execute("""
                SELECT
                    COALESCE(SUM(qty_checked), 0)::INTEGER AS today_checked,
                    COALESCE(SUM(qty_passed),  0)::INTEGER AS today_passed,
                    COALESCE(SUM(qty_failed),   0)::INTEGER AS today_failed
                FROM pkg_packaging_logs
                WHERE DATE(packed_at) = CURRENT_DATE
                  AND is_blocked = FALSE;
            """)
            pkg_row = cur.fetchone()

            # 今日发货汇总
            cur.execute("""
                SELECT COALESCE(SUM(qty), 0)::INTEGER
                FROM pkg_shipping_logs
                WHERE DATE(shipped_at) = CURRENT_DATE;
            """)
            ship_row = cur.fetchone()

            # 今日防错日志
            cur.execute("""
                SELECT COUNT(*)::INTEGER FROM pkg_error_logs
                WHERE DATE(created_at) = CURRENT_DATE;
            """)
            err_cnt = int(cur.fetchone()[0])

            checked = int(pkg_row[0])
            passed  = int(pkg_row[1])
            rate = round(passed / checked * 100, 1) if checked > 0 else None

            return {
                'today_checked':    checked,
                'today_passed':    passed,
                'today_failed':    int(pkg_row[2]),
                'today_pass_rate': rate,
                'today_shipped':   int(ship_row[0]),
                'today_errors':     err_cnt,
            }


def submit_packaging_log(part_id, operator_id, qty_checked, qty_passed,
                           qty_failed=0, result='pass', defect_reason='',
                           remark='', box_no='', is_blocked=False, blocked_reason='',
                           actual_date=None):
    """
    提交包装记录（全检入箱）。
    自动检查 Safety Guard：若 is_blocked=True，阻止发货。

    双时间戳（V3.1 §4）：
      - created_at：系统当前时间（数据库 DEFAULT NOW()）
      - actual_date：业务发生日期，默认当天，支持补录历史日期
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pkg_packaging_logs
                    (part_id, operator_id, qty_checked, qty_passed,
                     qty_failed, result, defect_reason, remark, box_no,
                     is_blocked, blocked_reason, actual_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        COALESCE(%s::date, CURRENT_DATE));
            """, (part_id, operator_id, qty_checked, qty_passed,
                  qty_failed, result, defect_reason, remark, box_no,
                  is_blocked, blocked_reason,
                  actual_date if actual_date else None))
            conn.commit()


def submit_shipping_log(part_id, operator_id, qty, box_no='',
                          vehicle_no='', remark='',
                          actual_date=None, customer_id=None):
    """
    提交发货记录。执行前必须通过 Safety Guard。
    V3.0 §2.4 Back-dating 支持：
    - actual_date: 业务发生日期（可追溯补录），默认当天
    - customer_id: 客户 ID（用于件号别名解析）
    """
    import datetime
    ship_date = actual_date or datetime.date.today().isoformat()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pkg_shipping_logs
                    (part_id, operator_id, qty, box_no, vehicle_no, remark,
                     shipped_at, actual_date, customer_id)
                VALUES (%s, %s, %s, %s, %s, %s,
                        %s::DATE + CURRENT_TIME, %s::DATE, %s);
            """, (part_id, operator_id, qty, box_no, vehicle_no, remark,
                  ship_date, ship_date, customer_id))
            conn.commit()


def log_pkg_error(part_id, error_type, detail, operator_id):
    """记录包装防错日志"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pkg_error_logs
                    (part_id, error_type, detail, operator_id)
                VALUES (%s, %s, %s, %s);
            """, (part_id, error_type, detail, operator_id))
            conn.commit()


def get_pkg_error_logs(limit=50):
    """返回防错日志列表"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    e.id, e.error_type, e.detail, e.created_at,
                    pt.part_number, pt.internal_name,
                    u.real_name AS operator_name
                FROM pkg_error_logs e
                LEFT JOIN parts pt ON e.part_id = pt.id
                LEFT JOIN users  u  ON e.operator_id = u.id
                ORDER BY e.created_at DESC
                LIMIT %s;
            """, (limit,))
            return cur.fetchall()


def get_pkg_blocked_parts():
    """返回当前被卡控的零件（pkg_packaging_logs.is_blocked=TRUE）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (p.part_id)
                    p.id, p.part_id, p.result, p.defect_reason,
                    p.blocked_reason, p.packed_at,
                    pt.part_number, pt.internal_name,
                    u.real_name AS operator_name
                FROM pkg_packaging_logs p
                LEFT JOIN parts pt ON p.part_id = pt.id
                LEFT JOIN users  u  ON p.operator_id = u.id
                WHERE p.is_blocked = TRUE
                ORDER BY p.part_id, p.packed_at DESC;
            """)
            return cur.fetchall()


# ==============================================================================
# 全局进度模块 — 文员录入 + 进度看板
# ==============================================================================

def get_pkg_progress_view(target_date=None, limit=200):
    """
    全局进度看板数据源。
    实时计算选定日期内每个零件的：
      - 生产总计（production_logs.status='approved', 某日）
      - 全检总计（pkg_packaging_logs, 某日, is_blocked=FALSE）
      - 发货总计（pkg_shipping_logs, 某日）
      - 待发库存（全检总计 - 发货总计）
    target_date: date object 或 date string 'YYYY-MM-DD'，默认今日
    """
    if target_date is None:
        date_str = "CURRENT_DATE"
    elif isinstance(target_date, str):
        date_str = f"DATE '{target_date}'"
    else:
        date_str = f"DATE '{target_date.isoformat()}'"

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    pt.id                 AS part_id,
                    pt.part_number,
                    pt.internal_name,
                    COALESCE(SUM(prod.qty_good), 0)::INTEGER  AS prod_total,
                    COALESCE(SUM(pkg.qty_passed), 0)::INTEGER AS pkg_total,
                    COALESCE(SUM(shp.qty), 0)::INTEGER         AS ship_total,
                    (COALESCE(SUM(pkg.qty_passed), 0)
                     - COALESCE(SUM(shp.qty), 0))::INTEGER     AS pending_ship,
                    CASE
                        WHEN COALESCE(SUM(pkg.qty_passed), 0) < COALESCE(SUM(prod.qty_good), 0)
                          AND COALESCE(SUM(prod.qty_good), 0) > 0
                        THEN 'missed'
                        WHEN (COALESCE(SUM(pkg.qty_passed), 0)
                              - COALESCE(SUM(shp.qty), 0)) > 0
                        THEN 'pending'
                        ELSE 'ok'
                    END AS alert_status
                FROM parts pt
                LEFT JOIN production_logs prod
                    ON prod.part_id = pt.id
                    AND prod.status = 'approved'
                    AND DATE(prod.report_time) = {date_str}
                LEFT JOIN pkg_packaging_logs pkg
                    ON pkg.part_id = pt.id
                    AND pkg.result = 'pass'
                    AND pkg.is_blocked = FALSE
                    AND DATE(pkg.packed_at) = {date_str}
                LEFT JOIN pkg_shipping_logs shp
                    ON shp.part_id = pt.id
                    AND DATE(shp.shipped_at) = {date_str}
                GROUP BY pt.id, pt.part_number, pt.internal_name
                HAVING COALESCE(SUM(prod.qty_good), 0) > 0
                    OR COALESCE(SUM(pkg.qty_passed), 0) > 0
                    OR COALESCE(SUM(shp.qty), 0) > 0
                ORDER BY
                    CASE
                        WHEN COALESCE(SUM(pkg.qty_passed), 0) < COALESCE(SUM(prod.qty_good), 0)
                          AND COALESCE(SUM(prod.qty_good), 0) > 0
                        THEN 1
                        WHEN (COALESCE(SUM(pkg.qty_passed), 0)
                              - COALESCE(SUM(shp.qty), 0)) > 0
                        THEN 2
                        ELSE 3
                    END,
                    pt.part_number;
            """)
            return cur.fetchall()


def get_pkg_parts_pending_inspection(target_date=None):
    """返回'已生产但当日未全检'的零件列表（今日产量 - 今日全检 > 0）。"""
    if target_date is None:
        date_str = "CURRENT_DATE"
    elif isinstance(target_date, str):
        date_str = f"DATE '{target_date}'"
    else:
        date_str = f"DATE '{target_date.isoformat()}'"

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    pt.id          AS part_id,
                    pt.part_number,
                    pt.internal_name AS part_name,
                    COALESCE(SUM(prod.qty_good), 0)::INTEGER  AS prod_total,
                    COALESCE(SUM(pkg.qty_passed), 0)::INTEGER AS pkg_total,
                    (COALESCE(SUM(prod.qty_good), 0)
                     - COALESCE(SUM(pkg.qty_passed), 0))::INTEGER AS not_inspected
                FROM parts pt
                LEFT JOIN production_logs prod
                    ON prod.part_id = pt.id
                    AND prod.status = 'approved'
                    AND DATE(prod.report_time) = {date_str}
                LEFT JOIN pkg_packaging_logs pkg
                    ON pkg.part_id = pt.id
                    AND pkg.result = 'pass'
                    AND pkg.is_blocked = FALSE
                    AND DATE(pkg.packed_at) = {date_str}
                LEFT JOIN pkg_shipping_logs shp
                    ON shp.part_id = pt.id
                    AND DATE(shp.shipped_at) = {date_str}
                GROUP BY pt.id, pt.part_number, pt.internal_name
                HAVING (COALESCE(SUM(prod.qty_good), 0)
                        - COALESCE(SUM(pkg.qty_passed), 0)) > 0
                ORDER BY not_inspected DESC;
            """)
            return cur.fetchall()


def get_pkg_reconciliation(part_id, target_date=None):
    """
    【后端对账 API — V3.0 §2.4 Back-dating + P3/P5 件号别名】

    输入：零件 ID + 业务日期
    输出：
      - production_total  : 该日期下该零件累计 approved 良品总数
      - packaging_total  : 该日期下该零件已全检合格总数
      - pending_inspection: 待全检余量 = production_total - packaging_total
      - shipped_total     : 该日期下累计发货数
      - ready_to_ship    : 可发货库存 = packaging_total - shipped_total

    逻辑：
    - 生产数：DATE(report_time) = target_date AND status='approved'
    - 全检数：DATE(actual_date) = target_date AND result='pass' AND is_blocked=FALSE
    - 发货数：DATE(actual_date) = target_date

    用于 pkg_entry.html 对账参考和后端防错校验。
    """
    if target_date is None:
        date_expr = "CURRENT_DATE"
    elif isinstance(target_date, str):
        date_expr = f"DATE '{target_date}'"
    else:
        date_expr = f"DATE '{target_date.isoformat()}'"

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    COALESCE(SUM(prod.qty_good), 0)::INTEGER AS production_total,
                    COALESCE(SUM(pkg.qty_passed), 0)::INTEGER AS packaging_total,
                    (COALESCE(SUM(prod.qty_good), 0)
                     - COALESCE(SUM(pkg.qty_passed), 0))::INTEGER AS pending_inspection,
                    COALESCE(SUM(shp.qty), 0)::INTEGER          AS shipped_total,
                    (COALESCE(SUM(pkg.qty_passed), 0)
                     - COALESCE(SUM(shp.qty), 0))::INTEGER      AS ready_to_ship
                FROM parts pt
                LEFT JOIN production_logs prod
                    ON prod.part_id = pt.id
                    AND prod.status = 'approved'
                    AND DATE(prod.report_time) = {date_expr}
                LEFT JOIN pkg_packaging_logs pkg
                    ON pkg.part_id = pt.id
                    AND pkg.result = 'pass'
                    AND pkg.is_blocked = FALSE
                    AND DATE(pkg.actual_date) = {date_expr}
                LEFT JOIN pkg_shipping_logs shp
                    ON shp.part_id = pt.id
                    AND DATE(shp.actual_date) = {date_expr}
                WHERE pt.id = %s
            """, (part_id,))
            row = cur.fetchone()
            if not row:
                return {
                    'part_id': part_id,
                    'target_date': target_date,
                    'production_total': 0,
                    'packaging_total': 0,
                    'pending_inspection': 0,
                    'shipped_total': 0,
                    'ready_to_ship': 0,
                }
            return dict(row)


def submit_pkg_entry(part_id, operator_id, date_str,
                     qty_good, qty_bad=0, bad_reason='',
                     qty_ship=0, box_no='', vehicle_no='', remark=''):
    """
    文员补录入口：一次性提交包装+发货记录。
    熔断日志：记录所有变更前后状态。
    qty_bad > 0 → is_blocked=TRUE（卡控）
    qty_ship > 0 → 校验历史可用库存
    Returns: (True, "ok") | (False, error_msg)
    """
    import datetime
    op_date = date_str or datetime.date.today().isoformat()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 历史已全检（pass 且未卡控）
            cur.execute("""
                SELECT COALESCE(SUM(qty_passed), 0)::INTEGER
                FROM pkg_packaging_logs
                WHERE part_id = %s AND result = 'pass' AND is_blocked = FALSE;
            """, (part_id,))
            hist_passed = int(cur.fetchone()[0])

            if qty_ship > 0:
                cur.execute("""
                    SELECT COALESCE(SUM(qty), 0)::INTEGER
                    FROM pkg_shipping_logs
                    WHERE part_id = %s;
                """, (part_id,))
                hist_shipped = int(cur.fetchone()[0])
                available = hist_passed - hist_shipped
                if qty_ship > available:
                    return False, (f"发货数 {qty_ship} 超出可用库存 "
                                  f"（已全检 {hist_passed} - 已发货 {hist_shipped} = "
                                  f"{available} 件）")

            is_blocked = (qty_bad > 0)
            result = 'pass' if qty_bad == 0 else 'fail'

            cur.execute("""
                INSERT INTO pkg_packaging_logs
                    (part_id, operator_id, qty_checked, qty_passed,
                     qty_failed, result, defect_reason, remark, box_no,
                     is_blocked, blocked_reason, packed_at, actual_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::DATE + CURRENT_TIME, %s::DATE);
            """, (part_id, operator_id,
                  qty_good + qty_bad, qty_good, qty_bad,
                  result, bad_reason, remark, box_no,
                  is_blocked, bad_reason if is_blocked else '',
                  op_date, op_date))

            if qty_ship > 0 and not is_blocked:
                cur.execute("""
                    INSERT INTO pkg_shipping_logs
                        (part_id, operator_id, qty, box_no, vehicle_no, remark,
                         shipped_at, actual_date)
                    VALUES (%s, %s, %s, %s, %s, %s,
                            %s::DATE + CURRENT_TIME, %s::DATE);
                """, (part_id, operator_id, qty_ship, box_no, vehicle_no, remark,
                      op_date, op_date))

            # 熔断日志：写入 pkg_error_logs 记录重要操作
            log_pkg_error(
                part_id=part_id,
                error_type='pkg_entry',
                detail=(f"文员补录:合格={qty_good},不合格={qty_bad},"
                       f"发货={qty_ship},日期={op_date},箱号={box_no}"),
                operator_id=operator_id,
            )

            conn.commit()
            return True, "ok"


def get_all_parts_for_pkg_entry():
    """返回所有零件（用于文员录入的零件选择下拉）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, part_number, internal_name AS part_name
                FROM parts
                ORDER BY part_number;
            """)
            return cur.fetchall()


def get_pkg_daily_summary(target_date=None):
    """返回指定日期的汇总：生产总数、全检总数、发货总数"""
    if target_date is None:
        date_str = "CURRENT_DATE"
    elif isinstance(target_date, str):
        date_str = f"DATE '{target_date}'"
    else:
        date_str = f"DATE '{target_date.isoformat()}'"

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT
                    COALESCE(SUM(prod.qty_good), 0)::INTEGER AS prod_total,
                    COALESCE(SUM(pkg.qty_passed), 0)::INTEGER AS pkg_total,
                    COALESCE(SUM(pkg.qty_failed), 0)::INTEGER AS pkg_failed,
                    COALESCE(SUM(shp.qty), 0)::INTEGER         AS ship_total,
                    COUNT(DISTINCT CASE WHEN pkg.qty_passed < prod.qty_good
                                         AND prod.qty_good > 0
                                    THEN prod.part_id END)::INTEGER AS missed_count
                FROM parts pt
                LEFT JOIN production_logs prod
                    ON prod.part_id = pt.id
                    AND prod.status = 'approved'
                    AND DATE(prod.report_time) = {date_str}
                LEFT JOIN pkg_packaging_logs pkg
                    ON pkg.part_id = pt.id
                    AND pkg.result = 'pass'
                    AND pkg.is_blocked = FALSE
                    AND DATE(pkg.packed_at) = {date_str}
                LEFT JOIN pkg_shipping_logs shp
                    ON shp.part_id = pt.id
                    AND DATE(shp.shipped_at) = {date_str};
            """)
            row = cur.fetchone()
            prod  = int(row[0])
            pkg   = int(row[1])
            rate  = round(pkg / prod * 100, 1) if prod > 0 else None
            return {
                'prod_total':   prod,
                'pkg_total':    pkg,
                'pkg_failed':   int(row[2]),
                'ship_total':   int(row[3]),
                'pass_rate':    rate,
                'missed_count': int(row[4]),
            }


# ══════════════════════════════════════════════════════════════════════════════
# 老板看板 (Admin Dashboard)
# ══════════════════════════════════════════════════════════════════════════════

def get_tonnage_dashboard():
    """
    纯 SQL 按吨位分桶聚合，返回结构：
    {tonnage: {total, running, repairing, offline, idle, utilization_pct, machines: [...]}}
    所有聚合均在 SQL 层完成，禁止 Python 循环。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COALESCE(m.press_tonnage::TEXT, '未知') AS tonnage,
                    COUNT(*)                                                          AS total,
                    COUNT(*) FILTER (WHERE m.status = 'running')                     AS running,
                    COUNT(*) FILTER (WHERE m.status = 'repairing')                   AS repairing,
                    COUNT(*) FILTER (WHERE m.status = 'offline')                     AS offline,
                    COUNT(*) FILTER (WHERE m.status = 'fault')                       AS fault,
                    COUNT(*) FILTER (WHERE m.status = 'pending_check')                AS pending_check,
                    COUNT(*) FILTER (WHERE m.status = 'idle')                       AS idle,
                    ROUND(
                        COUNT(*) FILTER (WHERE m.status = 'running')::NUMERIC
                        / NULLIF(COUNT(*), 0) * 100, 1
                    ) AS utilization_pct,
                    COALESCE(JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'id',          m.id,
                            'number',       m.machine_number,
                            'name',         m.machine_name,
                            'status',       m.status,
                            'part_number',  COALESCE(pt.part_number, pt2.part_number, ''),
                            'part_name',    COALESCE(pt.internal_name, pt2.internal_name, ''),
                            'operator',     COALESCE(u.real_name, '')
                        ) ORDER BY m.machine_number
                    ) FILTER (WHERE m.id IS NOT NULL), '[]') AS machines
                FROM machines m
                LEFT JOIN parts pt  ON m.current_part_id   = pt.id
                LEFT JOIN users u  ON m.current_operator_id = u.id
                LEFT JOIN production_plans pp ON m.active_plan_id = pp.id
                LEFT JOIN parts pt2 ON pp.part_id = pt2.id
                GROUP BY m.press_tonnage
                ORDER BY
                    CASE WHEN m.press_tonnage ~ '^[0-9]+$' THEN 1 ELSE 2 END,
                    COALESCE(m.press_tonnage, 'z') ASC;
            """)
            rows = cur.fetchall()

    groups = {}
    for row in rows:
        t = str(row.get('tonnage') or '未知')
        total = int(row.get('total') or 0)
        run   = int(row.get('running') or 0)
        groups[t] = {
            'total':            total,
            'running':          run,
            'repairing':        int(row.get('repairing') or 0),
            'offline':          int(row.get('offline') or 0),
            'fault':            int(row.get('fault') or 0),
            'pending_check':    int(row.get('pending_check') or 0),
            'idle':             int(row.get('idle') or 0),
            'utilization_pct':  float(row.get('utilization_pct') or 0.0),
            'machines':         row.get('machines') or [],
        }
    return groups


def get_today_output_yoy():
    """
    今日良品数 + 昨日良品数，计算同比。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN DATE(pl.report_time) = CURRENT_DATE
                        AND pl.status = 'approved' THEN pl.qty_good ELSE 0 END), 0) AS today_good,
                    COALESCE(SUM(CASE WHEN DATE(pl.report_time) = CURRENT_DATE - INTERVAL '1 day'
                        AND pl.status = 'approved' THEN pl.qty_good ELSE 0 END), 0) AS yesterday_good
                FROM production_logs pl;
            """)
            row = cur.fetchone()
            today     = int(row['today_good'] or 0)
            yesterday = int(row['yesterday_good'] or 0)
            if yesterday > 0:
                delta = round((today - yesterday) / yesterday * 100, 1)
            else:
                delta = None
            return {'today': today, 'yesterday': yesterday, 'yoy_pct': delta}


def get_factory_utilization():
    """
    全厂开工率：当前状态为 running 的机台数 / 总机台数。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'running') AS running FROM machines;")
            row = cur.fetchone()
            total   = int(row['total'] or 0)
            running = int(row['running'] or 0)
            rate    = round(running / total * 100, 1) if total > 0 else 0.0
            return {'total': total, 'running': running, 'rate': rate}


def get_overdue_summary():
    """
    按客户分组展示逾期计划：
    - 仅返回 due_date < CURRENT_DATE 且 status NOT IN ('completed','cancelled','closed') 的计划
    - 欠货量 = total_qty - delivered_qty
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COALESCE(tc.name, '未知客户') AS customer,
                    COUNT(DISTINCT pp.id)                                AS overdue_plan_count,
                    COUNT(DISTINCT pp.part_id)                           AS overdue_part_count,
                    COALESCE(SUM(GREATEST(pp.total_qty - COALESCE(pp.delivered_qty, 0), 0)), 0)::INTEGER AS backorder_qty
                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                LEFT JOIN tooling_customers tc ON pt.customer_id = tc.id
                WHERE pp.due_date < CURRENT_DATE
                  AND pp.status NOT IN ('completed', 'cancelled', 'closed')
                GROUP BY tc.name
                ORDER BY backorder_qty DESC;
            """)
            rows = cur.fetchall()

            # 拉取每个客户下的逾期零件明细
            cur.execute("""
                SELECT
                    COALESCE(tc.name, '未知客户') AS customer,
                    pp.id          AS plan_id,
                    pp.part_id,
                    pt.part_number,
                    pt.internal_name,
                    pp.total_qty,
                    COALESCE(pp.delivered_qty, 0) AS delivered_qty,
                    pp.due_date,
                    CURRENT_DATE - pp.due_date    AS overdue_days,
                    GREATEST(pp.total_qty - COALESCE(pp.delivered_qty, 0), 0)::INTEGER AS backorder_qty
                FROM production_plans pp
                JOIN parts pt ON pp.part_id = pt.id
                LEFT JOIN tooling_customers tc ON pt.customer_id = tc.id
                WHERE pp.due_date < CURRENT_DATE
                  AND pp.status NOT IN ('completed', 'cancelled', 'closed')
                ORDER BY overdue_days DESC;
            """)
            details = cur.fetchall()

            # 按客户聚合明细
            detail_map = {}
            for d in details:
                cust = d['customer']
                if cust not in detail_map:
                    detail_map[cust] = []
                detail_map[cust].append({
                    'plan_id':        d['plan_id'],
                    'part_number':    d['part_number'],
                    'part_name':     d['internal_name'],
                    'total_qty':     int(d['total_qty'] or 0),
                    'delivered_qty': int(d['delivered_qty'] or 0),
                    'backorder_qty': int(d['backorder_qty'] or 0),
                    'due_date':      str(d['due_date']) if d['due_date'] else '',
                    'overdue_days':  int(d['overdue_days'] or 0),
                })

            result = []
            for r in rows:
                cust = r['customer']
                result.append({
                    'customer':          cust,
                    'overdue_plan_count': int(r['overdue_plan_count'] or 0),
                    'overdue_part_count': int(r['overdue_part_count'] or 0),
                    'backorder_qty':     int(r['backorder_qty'] or 0),
                    'parts':             detail_map.get(cust, []),
                })
            return result


def get_boss_kpi():
    """
    本月预估产值 + 废料损耗率（总耗料重量 - 良品净重）。
    全部由原生 SQL 聚合，禁止 Python 循环累加。

    预估产值 = SUM(qty_good * 最新 APPROVED 报价单 final_price)
    废料损耗率 = (总耗料重量 - 良品净重) / 总耗料重量 * 100
      总耗料重量 = SUM(pl.qty_good * q.gross_weight)  -- gross_weight 已存入 quotes
      良品净重   = SUM(pl.qty_good * q.gross_weight * (1 - q.scrap_rate))
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 本月预估产值 + 废料损耗率：一次 CTE 完成
            cur.execute("""
                WITH latest_quote AS (
                    SELECT DISTINCT ON (q.part_id)
                        q.part_id,
                        q.final_price,
                        COALESCE(q.gross_weight, 0)                              AS gross_weight,
                        COALESCE(q.scrap_rate, 0.10)                             AS scrap_rate
                    FROM quotes q
                    WHERE q.approval_status = 'APPROVED'
                    ORDER BY q.part_id, q.updated_at DESC NULLS LAST
                )
                SELECT
                    COALESCE(SUM(pl.qty_good * lq.final_price),                   0)::NUMERIC(18,2) AS estimated_output,
                    COALESCE(SUM(pl.qty_good * lq.gross_weight),                  0)               AS total_gross_kg,
                    COALESCE(SUM(pl.qty_good * lq.gross_weight * (1 - lq.scrap_rate)), 0)          AS total_net_kg
                FROM production_logs pl
                JOIN latest_quote lq ON pl.part_id = lq.part_id
                WHERE pl.status = 'approved'
                  AND DATE_TRUNC('month', pl.report_time) = DATE_TRUNC('month', CURRENT_DATE);
            """)
            row = cur.fetchone()
            estimated_output = float(row['estimated_output'] or 0)
            total_gross      = float(row['total_gross_kg']   or 0)
            total_net        = float(row['total_net_kg']     or 0)
            scrap_kg         = round(total_gross - total_net, 2)
            scrap_rate_pct   = round((total_gross - total_net) / total_gross * 100, 2) if total_gross > 0 else 0.0

            return {
                'estimated_output': round(estimated_output, 2),
                'total_gross_kg':   round(total_gross, 2),
                'total_net_kg':     round(total_net, 2),
                'scrap_kg':         scrap_kg,
                'scrap_rate_pct':   scrap_rate_pct,
                # 高亮阈值：报废率 > 12% 视为异常
                'scrap_alert':      scrap_rate_pct > 12.0,
            }


# ==============================================================================
# 技术部管理端（主管/课长）- 数据服务
# ==============================================================================

def get_tech_manager_permission(user_id):
    """
    检查用户是否有技术部管理端访问权限。
    权限条件：dept='tech' 且 position='manager'
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, username, real_name, role_level, dept, position, is_tech
                FROM users
                WHERE id = %s
            """, (user_id,))
            user = cur.fetchone()
            if not user:
                return False, None
            
            dept = user.get('department') or user.get('dept') or ''
            position = user.get('position') or ''
            
            # 权限判定：dept='tech' 且 position='manager'，或 role_level >= 5 的 is_tech 用户
            has_permission = (
                (dept == 'tech' and position == 'manager') or
                (user.get('is_tech', False) and user.get('role_level', 0) >= 5)
            )
            return has_permission, dict(user)


def get_realtime_radar_data():
    """
    实时维修雷达：所有非 running 机台的等待/维修时长均在 SQL 层用
    EXTRACT(EPOCH ...) 计算，禁止 Python timedelta 循环。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    m.id,
                    m.machine_number,
                    m.machine_name,
                    m.status,
                    m.fault_reason,
                    m.fault_reported_at,
                    m.tech_arrival_time,
                    m.diagnosing_start_time,
                    m.tech_user_id,
                    m.current_mold_id,
                    mo.mold_number,
                    mo.mold_name,
                    u.real_name   AS tech_name,
                    u.username    AS tech_username,
                    -- 等待时长：故障上报 → 技术人员到场
                    GREATEST(0,
                        EXTRACT(EPOCH FROM (
                            COALESCE(m.tech_arrival_time, CURRENT_TIMESTAMP)
                            - COALESCE(m.fault_reported_at, CURRENT_TIMESTAMP)
                        )) / 60
                    ) AS wait_minutes,
                    -- 维修时长：到场 → 开始诊断
                    CASE
                        WHEN m.diagnosing_start_time IS NOT NULL
                             AND m.tech_arrival_time IS NOT NULL
                        THEN GREATEST(0,
                            EXTRACT(EPOCH FROM (
                                m.diagnosing_start_time - m.tech_arrival_time
                            )) / 60
                        )
                        ELSE 0
                    END AS repair_minutes
                FROM machines m
                LEFT JOIN dies mo ON m.current_mold_id = mo.id
                LEFT JOIN users  u  ON m.tech_user_id  = u.id
                WHERE m.status != 'running'
                ORDER BY
                    CASE m.status
                        WHEN 'fault'         THEN 1
                        WHEN 'pending_check' THEN 2
                        WHEN 'repairing'     THEN 3
                        WHEN 'offline'       THEN 4
                        ELSE 5
                    END,
                    m.fault_reported_at ASC NULLS LAST;
            """)
            return cur.fetchall()


def get_tech_staff_monthly_efficiency(tech_user_id=None):
    """
    获取模修师傅的月度平均维修效率。
    如果指定 tech_user_id，则返回该师傅的数据；否则返回所有模修师傅的数据。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 获取当月的第一天
            today = datetime.date.today()
            month_start = today.replace(day=1)
            
            sql = """
                SELECT 
                    u.id AS tech_id,
                    u.username,
                    u.real_name,
                    COUNT(DISTINCT m.id) AS repair_count,
                    COUNT(DISTINCT CASE WHEN m.status = 'running' THEN m.id END) AS completed_count,
                    AVG(
                        CASE 
                            WHEN m.tech_arrival_time IS NOT NULL AND m.fault_reported_at IS NOT NULL 
                            THEN EXTRACT(EPOCH FROM (m.tech_arrival_time - m.fault_reported_at)) / 60 
                        END
                    ) AS avg_response_minutes,
                    AVG(
                        CASE 
                            WHEN m.diagnosing_start_time IS NOT NULL AND m.tech_arrival_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (m.diagnosing_start_time - m.tech_arrival_time)) / 60
                        END
                    ) AS avg_repair_minutes
                FROM users u
                LEFT JOIN machines m ON u.id = m.tech_user_id
                    AND DATE(m.fault_reported_at) >= %s
                WHERE u.is_tech = TRUE
            """
            params = [month_start]
            
            if tech_user_id:
                sql += " AND u.id = %s"
                params.append(tech_user_id)
            
            sql += " GROUP BY u.id, u.username, u.real_name ORDER BY completed_count DESC"
            
            cur.execute(sql, params)
            return cur.fetchall()


def get_offline_molds_queue():
    """
    修模间任务池：获取所有已拆模（status='offline'）的模具列表。
    包含维修节点状态、等待装机时间等信息。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 查询下线记录表
            cur.execute("""
                SELECT 
                    mor.id AS record_id,
                    mor.machine_id,
                    mor.mold_number,
                    mor.mold_name,
                    mor.fault_reason,
                    mor.offline_time,
                    mor.maintenance_status,
                    mor.status_updated_at,
                    mor.assigned_tech_id,
                    mor.remark,
                    mor.completed_at,
                    m.machine_number,
                    u.real_name AS updater_name,
                    t.real_name AS tech_name
                FROM mold_offline_records mor
                LEFT JOIN machines m ON mor.machine_id = m.id
                LEFT JOIN users u ON mor.status_updated_by = u.id
                LEFT JOIN users t ON mor.assigned_tech_id = t.id
                WHERE mor.completed_at IS NULL
                ORDER BY 
                    CASE mor.maintenance_status
                        WHEN 'waiting_parts' THEN 1
                        WHEN 'major_repair' THEN 2
                        WHEN 'ready_to_install' THEN 3
                        ELSE 4
                    END,
                    mor.offline_time ASC
            """)
            records = cur.fetchall()
            
            result = []
            now = datetime.datetime.now()
            for r in records:
                # 计算下线持续时长
                offline_minutes = 0
                if r.get('offline_time'):
                    delta = now - r['offline_time']
                    offline_minutes = int(delta.total_seconds() / 60)
                
                result.append({
                    'record_id': r['record_id'],
                    'machine_id': r['machine_id'],
                    'machine_number': r['machine_number'] or '',
                    'mold_number': r['mold_number'] or '',
                    'mold_name': r['mold_name'] or '',
                    'fault_reason': r['fault_reason'] or '',
                    'offline_time': r['offline_time'],
                    'offline_minutes': offline_minutes,
                    'maintenance_status': r['maintenance_status'],
                    'status_updated_at': r['status_updated_at'],
                    'updater_name': r['updater_name'] or '',
                    'tech_name': r['tech_name'] or '',
                    'remark': r['remark'] or '',
                })
            
            # 同时查询当前状态为 offline 的机台（可能没有在 mold_offline_records 中）
            cur.execute("""
                SELECT 
                    m.id AS machine_id,
                    m.machine_number,
                    m.mold_offline_time,
                    mo.mold_number,
                    mo.mold_name,
                    m.fault_reason,
                    m.tech_user_id,
                    u.real_name AS tech_name
                FROM machines m
                LEFT JOIN dies mo ON m.current_mold_id = mo.id
                LEFT JOIN users u ON m.tech_user_id = u.id
                WHERE m.status = 'offline'
                ORDER BY m.mold_offline_time ASC
            """)
            offline_machines = cur.fetchall()
            
            for om in offline_machines:
                # 检查是否已存在于 records 中
                existing_ids = [r['record_id'] for r in result]
                
                # 计算下线时长
                offline_minutes = 0
                if om.get('mold_offline_time'):
                    delta = now - om['mold_offline_time']
                    offline_minutes = int(delta.total_seconds() / 60)
                
                result.append({
                    'record_id': 0,  # 新增记录
                    'machine_id': om['machine_id'],
                    'machine_number': om['machine_number'] or '',
                    'mold_number': om['mold_number'] or '',
                    'mold_name': om['mold_name'] or '',
                    'fault_reason': om['fault_reason'] or '',
                    'offline_time': om['mold_offline_time'],
                    'offline_minutes': offline_minutes,
                    'maintenance_status': 'offline',  # 默认状态
                    'status_updated_at': om['mold_offline_time'],
                    'updater_name': '',
                    'tech_name': om['tech_name'] or '',
                    'remark': '',
                })
            
            return result


def update_offline_mold_status(record_id, maintenance_status, updater_id, remark=''):
    """
    更新下线模具的维修节点状态。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            now = datetime.datetime.now()
            
            if record_id > 0:
                # 更新已有记录
                cur.execute("""
                    UPDATE mold_offline_records
                    SET maintenance_status = %s,
                        status_updated_at = %s,
                        status_updated_by = %s,
                        remark = %s,
                        completed_at = CASE WHEN %s = 'reinstalled' THEN %s ELSE completed_at END
                    WHERE id = %s
                """, (maintenance_status, now, updater_id, remark, 
                      maintenance_status, now, record_id))
            else:
                # 如果 record_id = 0，可能需要新增记录（从 machines 表同步）
                pass  # 暂不处理这种情况
            
            conn.commit()
            return True


def get_mold_fault_analysis(period='month'):
    """
    模具故障分析数据。
    返回：
    - top_5_troublesome_molds: Top 5 易损模具（按报修频率排序）
    - repair_duration_trend: 维修时长趋势（按天/周统计）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
        
            result = {'top_5_molds': [], 'duration_trend': []}
        
        # 确定时间范围
        today = datetime.date.today()
        if period == 'week':
            start_date = today - datetime.timedelta(days=7)
        else:  # month
            start_date = today.replace(day=1)
        
        # Top 5 易损模具
        cur.execute("""
            SELECT 
                mo.id AS mold_id,
                mo.mold_number,
                mo.mold_name,
                COUNT(m.id) AS fault_count,
                AVG(
                    CASE 
                        WHEN m.tech_arrival_time IS NOT NULL AND m.fault_reported_at IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (m.tech_arrival_time - m.fault_reported_at)) / 60 
                    END
                ) AS avg_response_minutes,
                AVG(
                    CASE 
                        WHEN m.diagnosing_start_time IS NOT NULL AND m.tech_arrival_time IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (m.diagnosing_start_time - m.tech_arrival_time)) / 60
                    END
                ) AS avg_repair_minutes
            FROM dies mo
            INNER JOIN machines m ON mo.id = m.current_mold_id
            WHERE m.fault_reported_at >= %s
            GROUP BY mo.id, mo.mold_number, mo.mold_name
            ORDER BY fault_count DESC
            LIMIT 5
        """, (start_date,))
        result['top_5_molds'] = [
            {
                'mold_id': r['mold_id'],
                'mold_number': r['mold_number'],
                'mold_name': r['mold_name'] or '',
                'fault_count': r['fault_count'] or 0,
                'avg_response_minutes': round(r['avg_response_minutes'] or 0, 1),
                'avg_repair_minutes': round(r['avg_repair_minutes'] or 0, 1),
            }
            for r in cur.fetchall()
        ]
        
        # 维修时长趋势（按天统计）
        if period == 'week':
            # 按天统计
            cur.execute("""
                SELECT 
                    DATE(m.fault_reported_at) AS stat_date,
                    COUNT(*) AS fault_count,
                    AVG(
                        CASE 
                            WHEN m.tech_arrival_time IS NOT NULL AND m.fault_reported_at IS NOT NULL 
                            THEN EXTRACT(EPOCH FROM (m.tech_arrival_time - m.fault_reported_at)) / 60 
                        END
                    ) AS avg_response_minutes,
                    AVG(
                        CASE 
                            WHEN m.diagnosing_start_time IS NOT NULL AND m.tech_arrival_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (m.diagnosing_start_time - m.tech_arrival_time)) / 60
                        END
                    ) AS avg_repair_minutes,
                    AVG(
                        CASE 
                            WHEN m.mold_offline_time IS NOT NULL AND m.fault_reported_at IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (m.mold_offline_time - m.fault_reported_at)) / 60
                        END
                    ) AS avg_downtime_minutes
                FROM machines m
                WHERE m.fault_reported_at >= %s
                GROUP BY DATE(m.fault_reported_at)
                ORDER BY stat_date ASC
            """, (start_date,))
        else:
            # 按周统计（月视图）
            cur.execute("""
                SELECT 
                    DATE_TRUNC('week', m.fault_reported_at)::date AS stat_date,
                    COUNT(*) AS fault_count,
                    AVG(
                        CASE 
                            WHEN m.tech_arrival_time IS NOT NULL AND m.fault_reported_at IS NOT NULL 
                            THEN EXTRACT(EPOCH FROM (m.tech_arrival_time - m.fault_reported_at)) / 60 
                        END
                    ) AS avg_response_minutes,
                    AVG(
                        CASE 
                            WHEN m.diagnosing_start_time IS NOT NULL AND m.tech_arrival_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (m.diagnosing_start_time - m.tech_arrival_time)) / 60
                        END
                    ) AS avg_repair_minutes,
                    AVG(
                        CASE 
                            WHEN m.mold_offline_time IS NOT NULL AND m.fault_reported_at IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (m.mold_offline_time - m.fault_reported_at)) / 60
                        END
                    ) AS avg_downtime_minutes
                FROM machines m
                WHERE m.fault_reported_at >= %s
                GROUP BY DATE_TRUNC('week', m.fault_reported_at)
                ORDER BY stat_date ASC
            """, (start_date,))
        
        result['duration_trend'] = [
            {
                'date': r['stat_date'].strftime('%m-%d') if r['stat_date'] else '',
                'fault_count': r['fault_count'] or 0,
                'avg_response_minutes': round(r['avg_response_minutes'] or 0, 1),
                'avg_repair_minutes': round(r['avg_repair_minutes'] or 0, 1),
                'avg_downtime_minutes': round(r['avg_downtime_minutes'] or 0, 1),
            }
            for r in cur.fetchall()
        ]
        
        return result


def create_offline_mold_record(machine_id, updater_id):
    """
    为下线的机台创建维修追踪记录。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            now = datetime.datetime.now()
            
            # 获取机台和模具信息
            cur.execute("""
                SELECT 
                    m.id AS machine_id,
                    m.machine_number,
                    m.fault_reason,
                    m.mold_offline_time,
                    m.tech_user_id,
                    mo.mold_number,
                    mo.mold_name
                FROM machines m
                LEFT JOIN dies mo ON m.current_mold_id = mo.id
                WHERE m.id = %s
            """, (machine_id,))
            machine = cur.fetchone()
            
            if not machine:
                return False, "机台不存在"
            
            # 检查是否已存在记录
            cur.execute("""
                SELECT id FROM mold_offline_records 
                WHERE machine_id = %s AND completed_at IS NULL
            """, (machine_id,))
            existing = cur.fetchone()
            
            if existing:
                return True, "记录已存在"
            
            # 创建新记录
            cur.execute("""
                INSERT INTO mold_offline_records 
                (machine_id, mold_number, mold_name, fault_reason, offline_time, 
                 assigned_tech_id, status_updated_by, maintenance_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'waiting_parts')
            """, (
                machine[0], machine[4], machine[5], machine[2], 
                machine[3] or now, machine[6], updater_id
            ))
            
            conn.commit()
            return True, "记录已创建"


# ==============================================================================
# 技术部"极简两扫制"维修闭环逻辑
# ==============================================================================

def resolve_mold_by_key(mold_key):
    """
    根据扫码关键字解析模具信息。
    支持：
    1. 直接模具编号（mold_number）
    2. 机台编号关联的模具（machine_number）
    3. mold_offline_records.id
    
    返回：模具记录或机台关联的模具信息
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 尝试作为 mold_offline_records.id 解析
            try:
                record_id = int(mold_key)
                cur.execute("""
                    SELECT mor.*, m.machine_number, mo.mold_number, mo.mold_name,
                           pt.part_number AS current_part_number, pt.internal_name AS current_part_name
                    FROM mold_offline_records mor
                    LEFT JOIN machines m ON mor.machine_id = m.id
                    LEFT JOIN dies mo ON m.current_mold_id = mo.id
                    LEFT JOIN parts pt ON m.current_part_id = pt.id
                    WHERE mor.id = %s
                """, (record_id,))
                record = cur.fetchone()
                if record:
                    return {'type': 'record', 'data': dict(record)}
            except (ValueError, TypeError):
                pass
            
            # 尝试作为 mold_number 解析
            cur.execute("""
                SELECT m.*, mo.mold_number, mo.mold_name,
                       pt.part_number AS current_part_number, pt.internal_name AS current_part_name
                FROM dies mo
                LEFT JOIN machines m ON m.current_mold_id = mo.id
                LEFT JOIN parts pt ON m.current_part_id = pt.id
                WHERE mo.mold_number = %s
            """, (mold_key,))
            mold = cur.fetchone()
            if mold:
                # 检查是否有未完成的下线记录
                cur.execute("""
                    SELECT id, maintenance_status, assigned_tech_id
                    FROM mold_offline_records
                    WHERE machine_id = %s AND completed_at IS NULL
                    ORDER BY id DESC LIMIT 1
                """, (mold['id'],))
                record = cur.fetchone()
                if record:
                    return {'type': 'mold_with_record', 'mold': dict(mold), 'record': dict(record)}
                return {'type': 'mold', 'mold': dict(mold)}
            
            # 尝试作为 machine_number 解析
            cur.execute("""
                SELECT m.*, mo.mold_number, mo.mold_name,
                       pt.part_number AS current_part_number, pt.internal_name AS current_part_name
                FROM machines m
                LEFT JOIN dies mo ON m.current_mold_id = mo.id
                LEFT JOIN parts pt ON m.current_part_id = pt.id
                WHERE m.machine_number = %s
            """, (mold_key,))
            machine = cur.fetchone()
            if machine:
                return {'type': 'machine', 'machine': dict(machine)}
            
            return None


def tech_twoscan_process(mold_key, tech_user_id):
    """
    技术部"两扫制"核心逻辑：
    
    规则：
    1. 若模具状态 = 'offline'（待修）：扫码后自动关联当前用户，状态→'in_repair'，记录开始时间
    2. 若模具状态 = 'in_repair'（维修中）：且为同一人扫码，状态→'ready_to_use'，记录结束时间
    
    返回：(success, message, new_status, action_type)
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            now = datetime.datetime.now()
            
            # 解析扫码内容
            resolve_result = resolve_mold_by_key(mold_key)
            if not resolve_result:
                return False, "未找到对应的模具或机台", None, None
            
            # 获取下线记录
            record_id = None
            record = None
            machine_id = None
            
            if resolve_result['type'] == 'record':
                record = resolve_result['data']
                record_id = record['id']
                machine_id = record['machine_id']
            elif resolve_result['type'] == 'mold_with_record':
                record = resolve_result['record']
                record_id = record['id']
                machine_id = resolve_result['mold']['id']
            elif resolve_result['type'] == 'mold':
                # 需要通过 mold 找到对应的 machine
                mold = resolve_result['mold']
                machine_id = mold['id']
                mold_number = mold['mold_number']
            else:
                machine_id = resolve_result['machine']['id']
            
            # 查询最新的下线记录
            if not record_id:
                cur.execute("""
                    SELECT * FROM mold_offline_records
                    WHERE machine_id = %s AND completed_at IS NULL
                    ORDER BY id DESC LIMIT 1
                """, (machine_id,))
                record_row = cur.fetchone()
                if record_row:
                    record = dict(record_row)
                    record_id = record['id']
            
            # 若没有下线记录，创建一个
            if not record_id:
                # 获取机台和模具信息
                cur.execute("""
                    SELECT m.*, mo.mold_number, mo.mold_name,
                           pt.part_number AS current_part_number, pt.internal_name AS current_part_name
                    FROM machines m
                    LEFT JOIN dies mo ON m.current_mold_id = mo.id
                    LEFT JOIN parts pt ON m.current_part_id = pt.id
                    WHERE m.id = %s
                """, (machine_id,))
                machine = cur.fetchone()
                
                if not machine:
                    return False, "机台不存在", None, None
                
                # 创建新的下线记录
                cur.execute("""
                    INSERT INTO mold_offline_records 
                    (machine_id, mold_number, mold_name, current_part_number, current_part_name,
                     fault_reason, offline_time, maintenance_status, assigned_tech_id, status_updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'offline', %s, %s)
                    RETURNING id
                """, (
                    machine_id,
                    machine['mold_number'], machine['mold_name'],
                    machine['current_part_number'], machine['current_part_name'],
                    machine['fault_reason'] or '扫码创建',
                    now, tech_user_id, tech_user_id
                ))
                record_id = cur.fetchone()[0]
                record = {'id': record_id, 'maintenance_status': 'offline', 'assigned_tech_id': tech_user_id}
                conn.commit()
            
            # ── 两扫制核心逻辑 ──
            current_status = record.get('maintenance_status')
            assigned_tech_id = record.get('assigned_tech_id')
            
            if current_status == 'offline':
                # 第一扫：offline → in_repair
                cur.execute("""
                    UPDATE mold_offline_records
                    SET maintenance_status = 'in_repair',
                        assigned_tech_id = %s,
                        repair_start_time = %s,
                        status_updated_at = %s,
                        status_updated_by = %s
                    WHERE id = %s
                """, (tech_user_id, now, now, tech_user_id, record_id))
                conn.commit()
                return True, "开始维修", 'in_repair', 'start_repair'
            
            elif current_status == 'in_repair':
                # 第二扫：in_repair → ready_to_use（仅限同一人）
                if assigned_tech_id != tech_user_id:
                    return False, f"该模具由其他师傅({assigned_tech_id})负责，请联系相关人员", current_status, 'not_owner'
                
                cur.execute("""
                    UPDATE mold_offline_records
                    SET maintenance_status = 'ready_to_use',
                        repair_end_time = %s,
                        status_updated_at = %s,
                        status_updated_by = %s
                    WHERE id = %s
                """, (now, now, tech_user_id, record_id))
                conn.commit()
                return True, "维修完成，待装机", 'ready_to_use', 'complete_repair'
            
            elif current_status == 'ready_to_use':
                # 已完成，待装机状态
                return True, "该模具已修好，待装机", current_status, 'already_done'
            
            elif current_status in ('waiting_parts', 'major_repair'):
                # 旧状态，仅更新责任人
                cur.execute("""
                    UPDATE mold_offline_records
                    SET assigned_tech_id = %s,
                        status_updated_at = %s,
                        status_updated_by = %s
                    WHERE id = %s
                """, (tech_user_id, now, tech_user_id, record_id))
                conn.commit()
                return True, f"已更新维修责任人，当前状态：{current_status}", current_status, 'update_owner'
            
            else:
                return True, f"模具状态：{current_status}", current_status, 'query_only'


def get_tech_task_pool():
    """
    获取技术部任务池：三列看板数据（待维修/维修中/已修好）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            now = datetime.datetime.now()
            
            # 通用查询
            base_query = """
                SELECT 
                    mor.id AS record_id,
                    mor.machine_id,
                    mor.mold_number,
                    mor.mold_name,
                    mor.current_part_number,
                    mor.current_part_name,
                    mor.fault_reason,
                    mor.offline_time,
                    mor.repair_start_time,
                    mor.repair_end_time,
                    mor.maintenance_status,
                    mor.status_updated_at,
                    mor.assigned_tech_id,
                    mor.remark,
                    m.machine_number,
                    u.real_name AS tech_name
                FROM mold_offline_records mor
                LEFT JOIN machines m ON mor.machine_id = m.id
                LEFT JOIN users u ON mor.assigned_tech_id = u.id
                WHERE mor.completed_at IS NULL
            """
            
            # 待维修（offline）
            cur.execute(f"""
                {base_query}
                AND mor.maintenance_status = 'offline'
                ORDER BY mor.offline_time ASC
            """)
            waiting = [dict(r) for r in cur.fetchall()]
            
            # 维修中（in_repair）
            cur.execute(f"""
                {base_query}
                AND mor.maintenance_status = 'in_repair'
                ORDER BY mor.repair_start_time ASC
            """)
            in_repair = [dict(r) for r in cur.fetchall()]
            
            # 已修好待装机（ready_to_use）
            cur.execute(f"""
                {base_query}
                AND mor.maintenance_status = 'ready_to_use'
                ORDER BY mor.repair_end_time ASC
            """)
            ready = [dict(r) for r in cur.fetchall()]
            
            # 计算时长
            for r in waiting:
                if r.get('offline_time'):
                    delta = now - r['offline_time']
                    r['wait_minutes'] = int(delta.total_seconds() / 60)
                else:
                    r['wait_minutes'] = 0
            
            for r in in_repair:
                if r.get('repair_start_time'):
                    delta = now - r['repair_start_time']
                    r['repair_minutes'] = int(delta.total_seconds() / 60)
                else:
                    r['repair_minutes'] = 0
            
            for r in ready:
                if r.get('repair_end_time'):
                    delta = now - r['repair_end_time']
                    r['ready_minutes'] = int(delta.total_seconds() / 60)
                else:
                    r['ready_minutes'] = 0
            
            return {
                'waiting': waiting,
                'in_repair': in_repair,
                'ready': ready,
                'counts': {
                    'waiting': len(waiting),
                    'in_repair': len(in_repair),
                    'ready': len(ready),
                    'total': len(waiting) + len(in_repair) + len(ready)
                }
            }


def get_tech_performance_stats():
    """
    获取技术部绩效统计：
    - 每套模具的离线总时长
    - 每个师傅的净维修工时
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            today = datetime.date.today()
            month_start = today.replace(day=1)
            
            # 模具离线总时长统计（本月）
            cur.execute("""
                SELECT 
                    mor.mold_number,
                    mor.mold_name,
                    COUNT(*) AS repair_count,
                    AVG(
                        CASE 
                            WHEN mor.repair_start_time IS NOT NULL AND mor.offline_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (mor.repair_start_time - mor.offline_time)) / 60
                        END
                    ) AS avg_wait_minutes,
                    AVG(
                        CASE 
                            WHEN mor.repair_end_time IS NOT NULL AND mor.repair_start_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (mor.repair_end_time - mor.repair_start_time)) / 60
                        END
                    ) AS avg_repair_minutes,
                    AVG(
                        CASE 
                            WHEN mor.offline_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (COALESCE(mor.repair_end_time, NOW()) - mor.offline_time)) / 60
                        END
                    ) AS avg_total_offline_minutes
                FROM mold_offline_records mor
                WHERE DATE(mor.offline_time) >= %s
                GROUP BY mor.mold_number, mor.mold_name
                ORDER BY repair_count DESC
                LIMIT 20
            """, (month_start,))
            mold_stats = [
                {
                    'mold_number': r['mold_number'],
                    'mold_name': r['mold_name'] or '',
                    'repair_count': r['repair_count'] or 0,
                    'avg_wait_minutes': round(r['avg_wait_minutes'] or 0, 1),
                    'avg_repair_minutes': round(r['avg_repair_minutes'] or 0, 1),
                    'avg_total_offline_minutes': round(r['avg_total_offline_minutes'] or 0, 1),
                }
                for r in cur.fetchall()
            ]
            
            # 师傅净维修工时统计（本月）
            cur.execute("""
                SELECT 
                    u.id AS tech_id,
                    u.username,
                    u.real_name,
                    COUNT(*) AS total_repairs,
                    COUNT(CASE WHEN mor.maintenance_status IN ('ready_to_use', 'reinstalled') THEN 1 END) AS completed_repairs,
                    SUM(
                        CASE 
                            WHEN mor.repair_end_time IS NOT NULL AND mor.repair_start_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (mor.repair_end_time - mor.repair_start_time)) / 3600
                        END
                    ) AS total_repair_hours,
                    AVG(
                        CASE 
                            WHEN mor.repair_end_time IS NOT NULL AND mor.repair_start_time IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (mor.repair_end_time - mor.repair_start_time)) / 60
                        END
                    ) AS avg_repair_minutes
                FROM mold_offline_records mor
                LEFT JOIN users u ON mor.assigned_tech_id = u.id
                WHERE mor.assigned_tech_id IS NOT NULL
                  AND DATE(mor.offline_time) >= %s
                GROUP BY u.id, u.username, u.real_name
                ORDER BY total_repair_hours DESC NULLS LAST
            """, (month_start,))
            tech_stats = [
                {
                    'tech_id': r['tech_id'],
                    'username': r['username'],
                    'real_name': r['real_name'] or r['username'],
                    'total_repairs': r['total_repairs'] or 0,
                    'completed_repairs': r['completed_repairs'] or 0,
                    'total_repair_hours': round(r['total_repair_hours'] or 0, 1),
                    'avg_repair_minutes': round(r['avg_repair_minutes'] or 0, 1),
                }
                for r in cur.fetchall()
            ]
            
            return {
                'mold_stats': mold_stats,
                'tech_stats': tech_stats,
                'period': f"{month_start.strftime('%Y-%m-%d')} 至 {today.strftime('%Y-%m-%d')}"
            }


# ══════════════════════════════════════════════════════════════════════
# 技术部待修池自动流转 + 模糊搜索
# ══════════════════════════════════════════════════════════════════════

def confirm_mold_offline_and_create_pending_record(machine_id, tech_user_id):
    """
    机台端师傅【确认拆模下线】时调用。
    自动在 mold_offline_records 创建一条 pending_offline_repair 记录，
    并返回记录 ID 与模具信息。
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 查询机台当前模具信息
            cur.execute("""
                SELECT
                    m.id AS machine_id,
                    m.machine_number,
                    m.current_mold_number,
                    m.current_mold_name,
                    m.current_part_number,
                    m.current_part_name
                FROM machines m
                WHERE m.id = %s
            """, (machine_id,))
            machine = cur.fetchone()
            if not machine:
                return False, "机台不存在"

            mold_number = machine['current_mold_number']
            mold_name = machine['current_mold_name']
            part_number = machine.get('current_part_number')
            part_name = machine.get('current_part_name')

            # 若已有同机台的 pending/offline 记录不重复创建
            cur.execute("""
                SELECT id FROM mold_offline_records
                WHERE machine_id = %s
                AND maintenance_status IN ('pending_offline_repair', 'offline', 'in_repair')
                ORDER BY id DESC LIMIT 1
            """, (machine_id,))
            existing = cur.fetchone()
            if existing:
                return True, "已存在进行中的下线记录", existing['id']

            # 创建新记录
            cur.execute("""
                INSERT INTO mold_offline_records
                    (machine_id, mold_number, mold_name,
                     current_part_number, current_part_name,
                     offline_time, maintenance_status,
                     assigned_tech_id, status_updated_by)
                VALUES
                    (%s, %s, %s, %s, %s, NOW(), 'pending_offline_repair', %s, %s)
                RETURNING id
            """, (machine_id, mold_number, mold_name,
                  part_number, part_name, tech_user_id, tech_user_id))
            record_id = cur.fetchone()['id']
            conn.commit()
            return True, "已加入待修池", record_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def get_pending_repair_pool(tech_user_id=None, search_key=''):
    """
    获取待修池列表（用于师傅端）。
    tech_user_id: 若传入则返回该师傅"正在维修"的记录置顶
    search_key :  模糊搜索 mold_number / mold_name / part_name
    返回格式: { 'current': {...} or None, 'pending': [...] }
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            has_search = search_key and len(search_key.strip()) > 0
            pattern = f"%{search_key.strip()}%"

            # ── 师傅"正在维修"的模具（置顶）─────────────────────────────
            current_repair = None
            if tech_user_id:
                cur.execute("""
                    SELECT
                        mor.id,
                        mor.machine_id,
                        mor.mold_number,
                        mor.mold_name,
                        mor.current_part_number,
                        mor.current_part_name,
                        mor.maintenance_status,
                        mor.offline_time,
                        mor.repair_start_time,
                        mor.assigned_tech_id,
                        m.machine_number,
                        u.real_name AS tech_name
                    FROM mold_offline_records mor
                    JOIN machines m ON m.id = mor.machine_id
                    LEFT JOIN users u ON u.id = mor.assigned_tech_id
                    WHERE mor.assigned_tech_id = %s
                      AND mor.maintenance_status = 'in_repair'
                    ORDER BY mor.repair_start_time DESC
                    LIMIT 1
                """, (tech_user_id,))
                row = cur.fetchone()
                if row:
                    offline_minutes = 0
                    if row['offline_time']:
                        offline_minutes = (datetime.datetime.now() - row['offline_time']).total_seconds() / 60
                    current_repair = {
                        'id': row['id'],
                        'machine_id': row['machine_id'],
                        'machine_number': row['machine_number'],
                        'mold_number': row['mold_number'] or '',
                        'mold_name': row['mold_name'] or '',
                        'current_part_number': row['current_part_number'] or '',
                        'current_part_name': row['current_part_name'] or '',
                        'status': row['maintenance_status'],
                        'offline_minutes': int(offline_minutes),
                        'repair_start_time': row['repair_start_time'],
                        'tech_name': row['tech_name'] or '',
                    }

            # ── 待修池列表 ──────────────────────────────────────────────
            if has_search:
                # 模糊匹配（ILIKE），支持 mold_number / mold_name / part_name
                cur.execute("""
                    SELECT
                        mor.id,
                        mor.machine_id,
                        mor.mold_number,
                        mor.mold_name,
                        mor.current_part_number,
                        mor.current_part_name,
                        mor.maintenance_status,
                        mor.offline_time,
                        mor.assigned_tech_id,
                        m.machine_number,
                        u.real_name AS assigned_tech_name
                    FROM mold_offline_records mor
                    JOIN machines m ON m.id = mor.machine_id
                    LEFT JOIN users u ON u.id = mor.assigned_tech_id
                    WHERE mor.maintenance_status = 'pending_offline_repair'
                      AND (
                          mor.mold_number ILIKE %s
                          OR mor.mold_name ILIKE %s
                          OR mor.current_part_name ILIKE %s
                          OR mor.current_part_number ILIKE %s
                      )
                    ORDER BY mor.offline_time ASC
                """, (pattern, pattern, pattern, pattern))
            else:
                cur.execute("""
                    SELECT
                        mor.id,
                        mor.machine_id,
                        mor.mold_number,
                        mor.mold_name,
                        mor.current_part_number,
                        mor.current_part_name,
                        mor.maintenance_status,
                        mor.offline_time,
                        mor.assigned_tech_id,
                        m.machine_number,
                        u.real_name AS assigned_tech_name
                    FROM mold_offline_records mor
                    JOIN machines m ON m.id = mor.machine_id
                    LEFT JOIN users u ON u.id = mor.assigned_tech_id
                    WHERE mor.maintenance_status = 'pending_offline_repair'
                    ORDER BY mor.offline_time ASC
                """)

            pending = []
            for r in cur.fetchall():
                offline_minutes = 0
                if r['offline_time']:
                    offline_minutes = (datetime.now() - r['offline_time']).total_seconds() / 60
                pending.append({
                    'id': r['id'],
                    'machine_id': r['machine_id'],
                    'machine_number': r['machine_number'],
                    'mold_number': r['mold_number'] or '',
                    'mold_name': r['mold_name'] or '',
                    'current_part_number': r['current_part_number'] or '',
                    'current_part_name': r['current_part_name'] or '',
                    'status': r['maintenance_status'],
                    'offline_minutes': int(offline_minutes),
                    'assigned_tech_id': r['assigned_tech_id'],
                    'assigned_tech_name': r['assigned_tech_name'] or '',
                })

            return {'current': current_repair, 'pending': pending}
    finally:
        conn.close()


def tech_start_repair(record_id, tech_user_id):
    """
    师傅从待修池选择模具并点击【开始维修】。
    限制：同一时间只能"正在维修"一套模具。
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 检查是否已有 in_repair 记录
            cur.execute("""
                SELECT id, mold_number FROM mold_offline_records
                WHERE assigned_tech_id = %s
                  AND maintenance_status = 'in_repair'
                LIMIT 1
            """, (tech_user_id,))
            existing = cur.fetchone()
            if existing:
                return False, f"您正在维修 {existing['mold_number']}，无法同时接单"

            # 验证目标记录确实存在且状态为 pending_offline_repair
            cur.execute("""
                SELECT id, mold_number, maintenance_status
                FROM mold_offline_records
                WHERE id = %s
            """, (record_id,))
            record = cur.fetchone()
            if not record:
                return False, "记录不存在"

            if record['maintenance_status'] != 'pending_offline_repair':
                return False, f"当前状态不允许开始维修（{record['maintenance_status']}）"

            # 更新状态
            cur.execute("""
                UPDATE mold_offline_records
                SET maintenance_status = 'in_repair',
                    repair_start_time = NOW(),
                    assigned_tech_id = %s,
                    status_updated_by = %s,
                    status_updated_at = NOW()
                WHERE id = %s
            """, (tech_user_id, tech_user_id, record_id))
            conn.commit()
            return True, "开始维修", record['mold_number']
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def tech_complete_repair(record_id, tech_user_id):
    """
    师傅点击【维修完成】。
    仅允许本人操作的 in_repair 记录。
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, mold_number, assigned_tech_id, maintenance_status
                FROM mold_offline_records
                WHERE id = %s
            """, (record_id,))
            record = cur.fetchone()
            if not record:
                return False, "记录不存在"

            if record['maintenance_status'] != 'in_repair':
                return False, f"当前状态不允许完成维修（{record['maintenance_status']}）"

            if record['assigned_tech_id'] != tech_user_id:
                return False, "不是您的维修任务，无法操作"

            cur.execute("""
                UPDATE mold_offline_records
                SET maintenance_status = 'ready_to_use',
                    repair_end_time = NOW(),
                    status_updated_by = %s,
                    status_updated_at = NOW()
                WHERE id = %s
            """, (tech_user_id, record_id))
            conn.commit()
            return True, "维修完成，待装机", record['mold_number']
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def tech_get_current_repairing(tech_user_id):
    """查询师傅当前正在维修的模具（若有）"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    mor.id,
                    mor.machine_id,
                    mor.mold_number,
                    mor.mold_name,
                    mor.current_part_number,
                    mor.current_part_name,
                    mor.maintenance_status,
                    mor.offline_time,
                    mor.repair_start_time,
                    m.machine_number
                FROM mold_offline_records mor
                JOIN machines m ON m.id = mor.machine_id
                WHERE mor.assigned_tech_id = %s
                  AND mor.maintenance_status = 'in_repair'
                ORDER BY mor.repair_start_time DESC
                LIMIT 1
            """, (tech_user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                'id': row['id'],
                'machine_id': row['machine_id'],
                'machine_number': row['machine_number'],
                'mold_number': row['mold_number'] or '',
                'mold_name': row['mold_name'] or '',
                'current_part_number': row['current_part_number'] or '',
                'current_part_name': row['current_part_name'] or '',
                'offline_time': row['offline_time'],
                'repair_start_time': row['repair_start_time'],
            }
    finally:
        conn.close()


# ============================================================================
# 喷涂模块 (Spraying)
# ============================================================================

def get_spraying_recipe(part_id):
    """获取零件喷涂工艺配方（含配方不存在时的默认值）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT r.*, u.real_name AS updated_by_name
                FROM spraying_recipes r
                LEFT JOIN users u ON u.id = r.updated_by
                WHERE r.part_id = %s
            """, (part_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
            return None


def get_all_spraying_recipes():
    """获取所有喷涂工艺配方（管理端列表）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT r.*,
                       pt.part_number, pt.internal_name,
                       u.real_name AS updated_by_name
                FROM spraying_recipes r
                JOIN parts pt ON pt.id = r.part_id
                LEFT JOIN users u ON u.id = r.updated_by
                ORDER BY pt.part_number
            """)
            return [dict(r) for r in cur.fetchall()]


def upsert_spraying_recipe(part_id, sand_material, sand_dosage,
                           coating_material, coating_dosage,
                           surface_type, coating_color, operator_id):
    """
    新增或更新喷涂工艺配方。
    允许未配置配方的零件存在（允许报工时 is_calculated=FALSE）。

    返回 dict：
        recipe_id      : 新建/更新的配方 ID
        is_new         : 是否为新建（首次配置）
        has_uncalc     : 是否存在未计算的报工记录
        uncalc_count   : 未计算记录数量（仅在 has_uncalc=True 时有效）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 先查是否存在
            cur.execute("SELECT id FROM spraying_recipes WHERE part_id = %s", (part_id,))
            existing = cur.fetchone()
            is_new = not bool(existing)

            cur.execute("""
                INSERT INTO spraying_recipes
                    (part_id, sand_material, sand_dosage, coating_material,
                     coating_dosage, surface_type, coating_color, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (part_id) DO UPDATE SET
                    sand_material    = EXCLUDED.sand_material,
                    sand_dosage      = EXCLUDED.sand_dosage,
                    coating_material = EXCLUDED.coating_material,
                    coating_dosage   = EXCLUDED.coating_dosage,
                    surface_type     = EXCLUDED.surface_type,
                    coating_color    = EXCLUDED.coating_color,
                    updated_at       = NOW(),
                    updated_by       = EXCLUDED.updated_by
                RETURNING id
            """, (part_id, sand_material, float(sand_dosage),
                  coating_material, float(coating_dosage),
                  surface_type, coating_color, operator_id))
            recipe_id = cur.fetchone()[0]
            conn.commit()

    # 查询是否存在未计算的报工记录（跨连接查询）
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM spraying_logs
                WHERE part_id = %s AND is_calculated = FALSE
            """, (part_id,))
            uncalc_count = cur.fetchone()[0]

    return {
        'recipe_id': recipe_id,
        'is_new': is_new,
        'has_uncalc': uncalc_count > 0,
        'uncalc_count': uncalc_count,
    }


def get_spraying_logs_by_part(part_id, limit=100):
    """获取某零件的喷涂报工记录"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT sl.*,
                       op.real_name AS operator_name,
                       mgr.real_name AS manager_name,
                       r.sand_material, r.sand_dosage,
                       r.coating_material, r.coating_dosage,
                       r.surface_type, r.coating_color
                FROM spraying_logs sl
                LEFT JOIN users op  ON op.id  = sl.operator_id
                LEFT JOIN users mgr ON mgr.id = sl.manager_id
                LEFT JOIN spraying_recipes r ON r.part_id = sl.part_id
                WHERE sl.part_id = %s
                ORDER BY sl.created_at DESC
                LIMIT %s
            """, (part_id, limit))
            return [dict(r) for r in cur.fetchall()]


def get_spraying_logs_by_date(target_date=None, limit=200):
    """按日期查询喷涂报工记录（用于管理端批量补录视图）"""
    if target_date is None:
        date_str = "CURRENT_DATE"
    elif isinstance(target_date, str):
        date_str = f"DATE '{target_date}'"
    else:
        date_str = f"DATE '{target_date.isoformat()}'"

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT sl.*,
                       pt.part_number, pt.internal_name,
                       op.real_name  AS operator_name,
                       mgr.real_name AS manager_name
                FROM spraying_logs sl
                JOIN parts pt ON pt.id = sl.part_id
                LEFT JOIN users op  ON op.id  = sl.operator_id
                LEFT JOIN users mgr ON mgr.id = sl.manager_id
                WHERE DATE(sl.actual_date) = {date_str}
                ORDER BY sl.created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]


def submit_spraying_log_worker(part_id, quantity, operator_id, actual_date=None):
    """
    员工端喷涂报工（极简模式）。
    - 仅输入产量，默认当天日期
    - is_calculated = FALSE（配方可能未配置）

    V3.1 §4 双时间戳：actual_date 为业务发生日期，默认当天。
    """
    if quantity <= 0:
        raise ValueError("Quantity must be > 0")

    import datetime as _dt
    date_val = actual_date if actual_date else _dt.date.today().isoformat()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO spraying_logs
                    (part_id, quantity, operator_id, actual_date, is_calculated)
                VALUES (%s, %s, %s, %s, FALSE)
                RETURNING id
            """, (part_id, quantity, operator_id, date_val))
            log_id = cur.fetchone()[0]

            # 更新零件工序状态
            cur.execute("""
                UPDATE parts SET spray_status = 'stamped', spray_stamped_at = NOW()
                WHERE id = %s AND (spray_status = 'pending' OR spray_status IS NULL)
            """, (part_id,))
            conn.commit()
            return log_id


def submit_spraying_log_manager(part_id, quantity, actual_date, manager_id):
    """
    管理端补录喷涂报工。
    - 按指定日期批量录入
    - is_calculated = FALSE
    """
    if quantity <= 0:
        raise ValueError("Quantity must be > 0")

    if isinstance(actual_date, str):
        date_val = actual_date
    else:
        date_val = actual_date.isoformat()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO spraying_logs
                    (part_id, quantity, manager_id, actual_date, is_calculated)
                VALUES (%s, %s, %s, %s, FALSE)
                RETURNING id
            """, (part_id, quantity, manager_id, date_val))

            log_id = cur.fetchone()[0]

            # 更新零件工序状态
            cur.execute("""
                UPDATE parts SET spray_status = 'stamped', spray_stamped_at = NOW()
                WHERE id = %s AND (spray_status = 'pending' OR spray_status IS NULL)
            """, (part_id,))
            conn.commit()
            return log_id


def sync_spraying_consumption(part_id, recipe_id=None):
    """
    追溯计算物料消耗。
    扫描 part_id 下所有 is_calculated=FALSE 的 spraying_logs，
    按最新配方参数计算喷砂/涂料消耗，并写入 spraying_material_consumption。
    计算公式：物料消耗 = 产出数量 x 单件定额

    返回 dict：
        updated_logs   : 实际更新的报工记录数
        total_sand    : 喷砂总消耗（kg）
        total_coat    : 涂料总消耗（kg）
        skipped       : 跳过的记录数（已计算或无配方）
        has_recipe    : 该零件是否有有效配方
    """
    recipe = None
    if recipe_id is None:
        recipe = get_spraying_recipe(part_id)
        if recipe is None:
            return {'updated_logs': 0, 'total_sand': 0.0,
                    'total_coat': 0.0, 'skipped': 0, 'has_recipe': False}
        recipe_id = recipe['id']
    else:
        recipe = get_spraying_recipe(part_id)
        if recipe is None:
            return {'updated_logs': 0, 'total_sand': 0.0,
                    'total_coat': 0.0, 'skipped': 0, 'has_recipe': False}

    if float(recipe['sand_dosage']) <= 0 and float(recipe['coating_dosage']) <= 0:
        return {'updated_logs': 0, 'total_sand': 0.0,
                'total_coat': 0.0, 'skipped': 0, 'has_recipe': True}

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, quantity FROM spraying_logs
                WHERE part_id = %s AND is_calculated = FALSE
                ORDER BY actual_date, created_at
            """, (part_id,))
            uncalc = cur.fetchall()
            if not uncalc:
                return {'updated_logs': 0, 'total_sand': 0.0,
                        'total_coat': 0.0, 'skipped': len(uncalc), 'has_recipe': True}

            updated = 0
            total_sand = 0.0
            total_coat = 0.0

            for row in uncalc:
                log_id = row['id']
                qty    = row['quantity']
                consumed_records = []

                if float(recipe['sand_dosage']) > 0 and recipe['sand_material']:
                    sand_qty = float(qty) * float(recipe['sand_dosage'])
                    total_sand += sand_qty
                    consumed_records.append((
                        part_id, recipe_id, log_id,
                        recipe['sand_material'], 'sand',
                        sand_qty, 0.0, sand_qty * 0.0
                    ))

                if float(recipe['coating_dosage']) > 0 and recipe['coating_material']:
                    coat_qty = float(qty) * float(recipe['coating_dosage'])
                    total_coat += coat_qty
                    consumed_records.append((
                        part_id, recipe_id, log_id,
                        recipe['coating_material'], 'coating',
                        coat_qty, 0.0, coat_qty * 0.0
                    ))

                if consumed_records:
                    cur.executemany("""
                        INSERT INTO spraying_material_consumption
                            (part_id, recipe_id, log_id, material_name,
                             material_type, consumed_qty, unit_cost, total_cost)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, consumed_records)

                cur.execute("""
                    UPDATE spraying_logs SET is_calculated = TRUE WHERE id = %s
                """, (log_id,))
                updated += 1

            conn.commit()

    return {
        'updated_logs': updated,
        'total_sand': round(total_sand, 4),
        'total_coat': round(total_coat, 4),
        'skipped': 0,
        'has_recipe': True,
    }


def recalculate_spraying_consumption(part_id):
    """
    自动化成本核算入口 —— 按最新配方重新计算指定零件的全部未计物料消耗。

    等价于 sync_spraying_consumption，但语义强调「重新核算」场景。
    返回与 sync_spraying_consumption 一致的结构。
    """
    return sync_spraying_consumption(part_id)


def get_spraying_material_summary():
    """
    物料统计看板：汇总各型号喷砂/涂料的理论累计消耗量。
    用于与仓库实际领料对账。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    material_name,
                    material_type,
                    SUM(consumed_qty)::NUMERIC(12,4) AS total_consumed,
                    COUNT(DISTINCT part_id)            AS part_count,
                    COUNT(log_id)                      AS log_count
                FROM spraying_material_consumption
                GROUP BY material_name, material_type
                ORDER BY SUM(consumed_qty) DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def get_spraying_part_summary():
    """
    零件喷涂汇总：每个零件的喷涂产出、累计消耗、配方状态。
    用于工序流转看板。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    pt.id          AS part_id,
                    pt.part_number,
                    pt.internal_name,
                    pt.spray_status,
                    pt.spray_stamped_at,
                    COALESCE(SUM(sl.quantity), 0)::INTEGER       AS spray_total,
                    COALESCE(SUM(sand.consumed_qty), 0)::NUMERIC(12,4) AS sand_consumed,
                    COALESCE(SUM(coat.consumed_qty), 0)::NUMERIC(12,4) AS coating_consumed,
                    r.sand_material, r.sand_dosage,
                    r.coating_material, r.coating_dosage,
                    r.surface_type, r.coating_color,
                    CASE WHEN r.id IS NOT NULL THEN TRUE ELSE FALSE END AS has_recipe,
                    COUNT(sl_uncalc.id)::INTEGER AS uncalc_count
                FROM parts pt
                LEFT JOIN spraying_logs sl ON sl.part_id = pt.id
                LEFT JOIN spraying_material_consumption sand
                    ON sand.part_id = pt.id AND sand.material_type = 'sand'
                LEFT JOIN spraying_material_consumption coat
                    ON coat.part_id = pt.id AND coat.material_type = 'coating'
                LEFT JOIN spraying_recipes r ON r.part_id = pt.id
                LEFT JOIN spraying_logs sl_uncalc
                    ON sl_uncalc.part_id = pt.id AND sl_uncalc.is_calculated = FALSE
                GROUP BY
                    pt.id, pt.part_number, pt.internal_name,
                    pt.spray_status, pt.spray_stamped_at,
                    r.id, r.sand_material, r.sand_dosage,
                    r.coating_material, r.coating_dosage,
                    r.surface_type, r.coating_color
                ORDER BY pt.part_number
            """)
            return [dict(r) for r in cur.fetchall()]


def get_spraying_process_kanban():
    """
    工序流转看板数据。
    状态节点：【已冲压 -> 已喷涂 -> 已全检】
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    pt.id                          AS part_id,
                    pt.part_number,
                    pt.internal_name,
                    pt.spray_status,
                    pt.spray_stamped_at,
                    CASE
                        WHEN pt.spray_status = 'shipped'   THEN 'shipped'
                        WHEN pt.spray_status = 'pkg_ready' THEN 'pkg'
                        WHEN pt.spray_status IN ('stamped','qc_passed') THEN 'sprayed'
                        ELSE 'stamped_waiting'
                    END AS current_node,
                    prod.total_prod_qty,
                    pkg.total_pkg_qty,
                    shp.total_ship_qty
                FROM parts pt
                LEFT JOIN (
                    SELECT part_id, SUM(qty_good)::INTEGER AS total_prod_qty
                    FROM production_logs
                    WHERE status = 'approved'
                    GROUP BY part_id
                ) prod ON prod.part_id = pt.id
                LEFT JOIN (
                    SELECT part_id, SUM(qty_passed)::INTEGER AS total_pkg_qty
                    FROM pkg_packaging_logs
                    WHERE result = 'pass' AND is_blocked = FALSE
                    GROUP BY part_id
                ) pkg ON pkg.part_id = pt.id
                LEFT JOIN (
                    SELECT part_id, SUM(qty)::INTEGER AS total_ship_qty
                    FROM pkg_shipping_logs
                    GROUP BY part_id
                ) shp ON shp.part_id = pt.id
                ORDER BY
                    CASE pt.spray_status
                        WHEN 'pending'   THEN 1
                        WHEN 'stamped'   THEN 2
                        WHEN 'qc_passed' THEN 3
                        WHEN 'pkg_ready' THEN 4
                        WHEN 'shipped'   THEN 5
                        ELSE 0
                    END,
                    pt.part_number
            """)
            return [dict(r) for r in cur.fetchall()]


def get_spraying_today_summary():
    """喷涂今日汇总：今日报工批次 / 总产量 / 未计算批次"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*)::INTEGER                                    AS today_batches,
                    COALESCE(SUM(quantity), 0)::INTEGER                AS today_qty,
                    COUNT(*) FILTER (WHERE is_calculated = FALSE)::INTEGER AS uncalc_batches,
                    COUNT(DISTINCT part_id)::INTEGER                     AS today_parts
                FROM spraying_logs
                WHERE DATE(actual_date) = CURRENT_DATE
            """)
            row = cur.fetchone()
            return dict(row) if row else {
                'today_batches': 0, 'today_qty': 0,
                'uncalc_batches': 0, 'today_parts': 0
            }


def get_all_parts_for_spraying():
    """获取所有零件（用于喷涂管理端下拉选择）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT pt.id, pt.part_number, pt.internal_name,
                       r.surface_type, r.coating_color
                FROM parts pt
                LEFT JOIN spraying_recipes r ON r.part_id = pt.id
                ORDER BY pt.part_number
            """)
            return [dict(r) for r in cur.fetchall()]


def get_spraying_uncalc_parts():
    """获取有待计算消耗的零件（用于【同步历史消耗】按钮）"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT pt.id AS part_id,
                       pt.part_number, pt.internal_name,
                       COUNT(sl.id) AS uncalc_count
                FROM parts pt
                JOIN spraying_logs sl ON sl.part_id = pt.id
                WHERE sl.is_calculated = FALSE
                GROUP BY pt.id, pt.part_number, pt.internal_name
                ORDER BY pt.part_number
            """)
            return [dict(r) for r in cur.fetchall()]


def batch_sync_spraying_consumption(part_id):
    """批量同步某零件的历史物料消耗，返回实际更新的记录数"""
    return sync_spraying_consumption(part_id)


def get_parts_without_recipe():
    """
    【待完善工艺列表】
    查询已有喷涂报工记录但尚未录入工艺配方的零件。
    供管理看板提醒主管配置定额参数。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT
                    pt.id          AS part_id,
                    pt.part_number,
                    pt.internal_name,
                    pt.spray_status,
                    COUNT(sl.id)  AS unrecipe_batches,
                    SUM(sl.quantity)::INTEGER AS unrecipe_total_qty,
                    MAX(sl.actual_date) AS latest_date
                FROM parts pt
                JOIN spraying_logs sl ON sl.part_id = pt.id
                LEFT JOIN spraying_recipes r ON r.part_id = pt.id
                WHERE r.id IS NULL
                GROUP BY pt.id, pt.part_number, pt.internal_name, pt.spray_status
                ORDER BY COUNT(sl.id) DESC, pt.part_number
            """)
            return [dict(r) for r in cur.fetchall()]


def get_spraying_material_balance(start_date=None, end_date=None):
    """
    【物料平衡表】
    统计指定日期范围内，各原料的理论消耗汇总。

    参数：
        start_date : 起始日期（YYYY-MM-DD），None 表示不限
        end_date   : 结束日期（YYYY-MM-DD），None 表示不限

    返回字段：
        material_name   : 原料名称
        material_type   : sand / coating
        part_count     : 使用该原料的零件种数
        log_count      : 涉及的报工记录数
        total_consumed : 理论总消耗（kg）
        part_numbers   : 涉及的零件号列表（前10个，逗号分隔）
    """
    date_filter = ""
    params = []
    if start_date:
        date_filter += " AND DATE(sl.actual_date) >= %s"
        params.append(start_date)
    if end_date:
        date_filter += " AND DATE(sl.actual_date) <= %s"
        params.append(end_date)

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    mc.material_name,
                    mc.material_type,
                    COUNT(DISTINCT mc.part_id)                  AS part_count,
                    COUNT(mc.id)                                 AS log_count,
                    SUM(mc.consumed_qty)::NUMERIC(12,4)         AS total_consumed,
                    STRING_AGG(
                        DISTINCT pt.part_number
                        ORDER BY pt.part_number
                        SEPARATOR ', '
                    ) AS part_numbers
                FROM spraying_material_consumption mc
                JOIN spraying_logs sl ON sl.id = mc.log_id
                JOIN parts pt ON pt.id = mc.part_id
                WHERE 1=1 {date_filter}
                GROUP BY mc.material_name, mc.material_type
                ORDER BY SUM(mc.consumed_qty) DESC
            """, params)
            return [dict(r) for r in cur.fetchall()]


def get_spraying_balance_by_part(part_id, start_date=None, end_date=None):
    """
    按零件维度统计：某零件的喷涂产出与物料消耗明细。
    用于零件详情页的喷涂成本追溯。
    """
    date_filter = ""
    params = [part_id]
    if start_date:
        date_filter += " AND DATE(sl.actual_date) >= %s"
        params.append(start_date)
    if end_date:
        date_filter += " AND DATE(sl.actual_date) <= %s"
        params.append(end_date)

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    pt.part_number,
                    pt.internal_name,
                    mc.material_name,
                    mc.material_type,
                    mc.consumed_qty,
                    mc.unit_cost,
                    mc.total_cost,
                    sl.quantity    AS spray_output,
                    sl.actual_date AS spray_date,
                    r.sand_dosage,
                    r.coating_dosage
                FROM spraying_material_consumption mc
                JOIN spraying_logs sl ON sl.id = mc.log_id
                JOIN parts pt ON pt.id = mc.part_id
                LEFT JOIN spraying_recipes r ON r.part_id = pt.id
                WHERE mc.part_id = %s {date_filter}
                ORDER BY sl.actual_date DESC, mc.id DESC
            """, params)
            return [dict(r) for r in cur.fetchall()]


# ═══════════════════════════════════════════════════════════════════
# 材料基准价格管理（Material Base Prices）
# ═══════════════════════════════════════════════════════════════════

def get_all_material_base_prices():
    """
    获取全部材料基准价格列表。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT material_name, default_density, default_price,
                       scrap_price, updated_at
                FROM material_base_prices
                ORDER BY material_name
            """)
            return [dict(r) for r in cur.fetchall()]


def get_material_base_prices_for_select():
    """
    返回材料列表（用于下拉选择），格式兼容 material_name 作为 value 键。
    用于 GET /api/materials 以及 part_create.html 页面加载。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT material_name, default_density, default_price,
                       scrap_price, updated_at
                FROM material_base_prices
                ORDER BY material_name
            """)
            rows = cur.fetchall()
            # 补充 id 字段（取 material_name 的哈希映射，保证非重复即可用于前端 value）
            result = []
            for i, r in enumerate(rows, start=1):
                d = dict(r)
                d['id'] = i
                result.append(d)
            return result


def get_material_base_price(material_name):
    """
    按材料牌号查询基准价格。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT material_name, default_density, default_price,
                       scrap_price, updated_at
                FROM material_base_prices
                WHERE material_name = %s
            """, (material_name,))
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_material_base_price(material_name, default_density,
                               default_price, scrap_price=None,
                               operator_id=None):
    """
    新增或更新材料基准价格。

    返回 dict：
        action      : 'created' | 'updated'
        old_price  : 更新前价格（仅 update 时有值）
        new_price  : 更新后价格
        draft_parts: 使用该材料且状态为 Draft 的零件数（>0 时前端应询问是否同步）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT default_price FROM material_base_prices
                WHERE material_name = %s
            """, (material_name,))
            old_row = cur.fetchone()
            action = 'updated' if old_row else 'created'
            old_price = float(old_row[0]) if old_row else None

            cur.execute("""
                INSERT INTO material_base_prices
                    (material_name, default_density, default_price, scrap_price, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (material_name) DO UPDATE SET
                    default_density = EXCLUDED.default_density,
                    default_price  = EXCLUDED.default_price,
                    scrap_price    = EXCLUDED.scrap_price,
                    updated_at    = NOW()
            """, (material_name, float(default_density),
                  float(default_price),
                  float(scrap_price) if scrap_price is not None else None))
            conn.commit()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM parts
                WHERE material_name = %s
            """, (material_name,))
            draft_count = cur.fetchone()[0]

    return {
        'action': action,
        'old_price': old_price,
        'new_price': float(default_price),
        'draft_parts': draft_count,
        'material_name': material_name,
    }


def delete_material_base_price(material_name):
    """
    删除材料基准价格（仅当没有零件使用该材料时才允许）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM parts WHERE material_name = %s
            """, (material_name,))
            in_use = cur.fetchone()[0]
            if in_use > 0:
                return False, f"该材料已被 {in_use} 个零件引用，无法删除"
            cur.execute("""
                DELETE FROM material_base_prices WHERE material_name = %s
            """, (material_name,))
            conn.commit()
            return True, f"材料 {material_name} 已删除"


def get_parts_using_material(material_name):
    """
    获取使用指定材料的所有零件（含 Draft 状态），用于同步弹窗列表展示。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.part_number, p.internal_name,
                       q.final_price AS current_price,
                       m.default_price AS base_price
                FROM parts p
                LEFT JOIN material_base_prices m ON m.material_name = p.material_name
                LEFT JOIN LATERAL (
                    SELECT final_price
                    FROM quotes
                    WHERE part_id = p.id
                      AND approval_status = 'APPROVED'
                      AND final_price IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                ) q ON TRUE
                WHERE p.material_name = %s
                ORDER BY p.part_number
            """, (material_name,))
            return [dict(r) for r in cur.fetchall()]


def sync_material_price_to_parts(material_name):
    """
    将指定材料的最新基准价格同步到所有零件（已废弃，prices 现在存于 quotes 表）。
    保留本函数以兼容旧调用链，但不再操作 parts 表。
    """
    return {'affected_count': 0, 'new_price': None, 'note': 'deprecated — prices now live in quotes table'}


# ==============================================================================
# 业务部双驱报价核算引擎
# ==============================================================================

def calc_part_pricing(
        thickness: float,
        width: float,
        press_stroke: float,
        material_name: str,
        cavity_count: int = 1,
        scrap_rate: float = 0.10,
        gross_weight_g: float | None = None,   # 前端已算好的毛重（g）
        net_weight_g: float | None = None,      # 前端已算好的净重（g）
        scrap_weight_g: float | None = None,   # 前端已算好的废料重（g）
        material_utilization: float = 100.0,    # 材料利用率（%），用户输入
        stamping_fee: float = 0,
        inspection_fee: float = 0,
        packaging_fee: float = 0,
        surface_fee: float = 0,
        treatment_fee: float = 0,
        profit_margin: float = 0,
        mold_cost: float = 0,                  # 模具费（元/件）
        override_unit_price: float = None,
        override_material_cost: float = None,
        override_final_price: float = None,
        machine_type: str = None):
    """
    白盒报价核算引擎（前端传 g，后端 /1000 转 kg 再算成本）。

    计算路径：
      - 若前端已传 gross_weight_g（不为 None）：直接用前端算好的重量，不再内部重算。
        材料净成本 = (gross_weight_g / 1000 * 单价) − (scrap_weight_g / 1000 * 回收价)
      - 若前端未传：降级为自动核算模式（兼容旧逻辑）。

    参数
    ----
    thickness             : 材料厚度 mm（仅作记录/展示用）
    width                : 材料宽度 mm
    press_stroke         : 冲压行程 mm（即 P）
    material_name         : 材料牌号（查 material_base_prices）
    cavity_count          : 穴数（默认 1）
    scrap_rate           : 废料率（%），前端展示用
    gross_weight_g       : 前端算好的毛重（g），若为 None 则后端自动计算
    net_weight_g         : 前端算好的净重（g），若为 None 则后端自动计算
    scrap_weight_g       : 前端算好的废料重（g），若为 None 则后端自动计算
    material_utilization  : 材料利用率（%），用户手动输入，默认 100
    stamping_fee          : 冲压费 元/件
    inspection_fee        : 全检费 元/件
    packaging_fee        : 包装运费 元/件
    surface_fee          : 表面处理费 元/件
    treatment_fee        : 处理费合计（元）
    profit_margin        : 利润率系数（如 0.20 = 加价20%）
    override_unit_price  : 人工覆盖材料单价
    override_material_cost: 人工覆盖材料净成本
    override_final_price : 人工覆盖最终总价

    返回
    ----
    dict，包含：gross_weight, material_net_cost, material_utilization,
                final_price, treatment_fee_result, override_flags, formula_display,
                density, unit_price, scrap_price, scrap_rate, machine_type, used_formula
    """
    logger.debug("[calc] ====== calc_part_pricing ENTRY ======")
    logger.debug(f"[calc] INPUT: T={thickness}, W={width}, P={press_stroke}, material={material_name!r}, cavity={cavity_count}")
    logger.debug(f"[calc] INPUT: scrap_rate={scrap_rate}, stamping_fee={stamping_fee}, inspection_fee={inspection_fee}")
    logger.debug(f"[calc] INPUT: packaging_fee={packaging_fee}, treatment_fee={treatment_fee}, profit_margin={profit_margin}")
    logger.debug(f"[calc] INPUT: override_unit_price={override_unit_price}, override_material_cost={override_material_cost}, override_final_price={override_final_price}")

    result = {
        'gross_weight': None,
        'net_weight': None,
        'scrap_weight': None,
        'material_utilization': None,
        'material_net_cost': None,
        'final_price': None,
        'scrap_rate': float(scrap_rate),
        'material_unit_price_override': override_unit_price,
        'material_net_cost_override': override_material_cost,
        'final_price_override': override_final_price,
        'override_flags': [],
        'formula_display': {},
        'density': None,
        'unit_price': None,
        'scrap_price': None,
        'machine_type': None,
        'used_formula': None,
        'error': None,
    }

    # 1. 查材料基准价
    mat = get_material_base_price(material_name)
    logger.debug(f"[calc] material lookup: material_name={material_name!r}, mat={mat}")
    if not mat:
        result['error'] = f"材料【{material_name}】未在材料参数中心注册"
        logger.error(f"[calc] ERROR: material not found - {material_name!r}")
        return result

    density = float(mat['default_density'])
    unit_price = float(mat['default_price'])
    scrap_price_val = float(mat['scrap_price']) if mat.get('scrap_price') else 0.0
    logger.debug(f"[calc] MATERIAL: density={density}, unit_price={unit_price}, scrap_price={scrap_price_val}")

    result['density'] = density
    result['unit_price'] = unit_price
    result['scrap_price'] = scrap_price_val

    # ── 重量计算：前端已算好时直接用，否则后端自动算 ─────────────────
    T = float(thickness)
    W = float(width)
    P = float(press_stroke)
    scrap_rate_val = float(scrap_rate)

    if gross_weight_g is not None:
        # 前端已算好，直接用
        gw = float(gross_weight_g)
        nw = float(net_weight_g) if net_weight_g is not None else gw
        sw = float(scrap_weight_g) if scrap_weight_g is not None else (gw - nw)
        util_pct = float(material_utilization) if material_utilization is not None else 100.0
        logger.debug(f"[calc] FRONTEND WEIGHTS: gross={gw}g, net={nw}g, scrap={sw}g, util={util_pct}%")
        result['override_flags'].append('frontend_weight_override')
    else:
        # 后端自动核算（兼容旧逻辑）
        logger.debug(f"[calc] PARSED: T={T}, W={W}, P={P}")
        if T <= 0 or W <= 0 or P <= 0:
            result['error'] = (
                f"物理参数不完整：厚度={thickness}mm，宽度={width}mm，行程={press_stroke}mm。"
                f"三者均必须 > 0 才能进行白盒核算。"
            )
            logger.error(f"[calc] ERROR: invalid T/W/P - T={T}, W={W}, P={P}")
            return result
        # 毛重 g = T × W × P × density × cavity_count ÷ 1000
        gw = T * W * P * density * cavity_count / 1000.0
        logger.debug(f"[calc] gross_weight_g = {T} × {W} × {P} × {density} × {cavity_count} / 1000 = {gw}")

        util_pct = float(material_utilization) if material_utilization is not None else 100.0
        if util_pct <= 0 or util_pct > 100:
            util_pct = 100.0
        # 净重 g = 毛重 g × (利用率 / 100)
        nw = gw * (util_pct / 100.0)
        # 废料 g = 毛重 g - 净重 g
        sw = gw - nw
        logger.debug(f"[calc] net_weight_g={nw} (util={util_pct}%), scrap_weight_g={sw}")
        result['override_flags'].append('auto_weight')

    result['gross_weight'] = round(gw, 6)
    result['net_weight'] = round(nw, 6)
    result['scrap_weight'] = round(sw, 6)
    result['material_utilization'] = round(util_pct, 2)
    result['used_formula'] = (
        f"毛重 = {T} × {W} × {P} × {density} × {cavity_count} ÷ 1000 = {gw:.6f} g"
    )
    result['formula_display']['gross_weight'] = {
        'formula': f"{T} × {W} × {P} × {density} × {cavity_count} ÷ 1000",
        'result': f"{round(gw, 6):.6f} g",
        'detail': f"厚度{T}mm × 宽度{W}mm × 行程{P}mm × 密度{density}g/cm³ × {cavity_count}腔 ÷ 1000 = {gw:.6f} g",
    }
    result['formula_display']['material_utilization'] = {
        'formula': f"材料利用率 = {util_pct}%",
        'result': f"{round(util_pct, 2):.2f}%",
        'detail': f"净重 = 毛重 × {util_pct}% = {gw:.6f} × {util_pct / 100:.4f} = {nw:.6f} g",
    }

    # ── 材料净成本（元/kg → g 换算）──────────────────────────────
    if override_material_cost is not None:
        mat_net_cost = float(override_material_cost)
        result['override_flags'].append('material_net_cost_override')
        mat_net_cost_formula = f"（人工覆盖）{mat_net_cost} 元"
        logger.debug(f"[calc] using override_material_cost={mat_net_cost}")
    else:
        unit = unit_price if override_unit_price is None else float(override_unit_price)
        # 初始材料费 = (毛重_g / 1000) × 单价
        # 废料回收费 = (废料_g / 1000) × 回收价
        # 材料净成本 = 初始材料费 − 废料回收费
        mat_net_cost = (gw / 1000.0 * unit) - (sw / 1000.0 * scrap_price_val)
        logger.debug(f"[calc] mat_net_cost = ({gw}/1000 × {unit}) - ({sw}/1000 × {scrap_price_val}) = {mat_net_cost}")
        if override_unit_price is not None:
            result['override_flags'].append('unit_price_override')
        mat_net_cost_formula = (
            f"(({gw:.6f} ÷ 1000 × {unit}) - ({sw:.6f} ÷ 1000 × {scrap_price_val}))"
            f" = {round(mat_net_cost, 4):.4f} 元"
        )

    logger.debug(f"[calc] mat_net_cost={mat_net_cost}, type={type(mat_net_cost)}")

    # ── 废料率展示（参考值，由材料利用率换算得到）─────────────────
    # 废料率 = 1 - (利用率 / 100)
    derived_scrap_rate = max(0.0, min(1.0, 1.0 - util_pct / 100.0))
    result['formula_display']['scrap_rate'] = {
        'formula': f"废料率 = 1 − (利用率 ÷ 100) = 1 − {util_pct} ÷ 100",
        'result': f"废料率 = {derived_scrap_rate:.2%}",
        'detail': (
            f"废料 {sw:.6f} g（{derived_scrap_rate:.2%}），"
            f"净重 {nw:.6f} g，材料利用率 {util_pct:.2f}%"
        ),
    }

    result['material_net_cost'] = round(mat_net_cost, 4)
    logger.debug(f"[calc] material_net_cost (rounded to 4dp) = {result['material_net_cost']}")
    result['formula_display']['material_net_cost'] = {
        'formula': mat_net_cost_formula,
        'result': f"{round(mat_net_cost, 4):.4f} 元",
        'detail': (
            f"({gw:.6f}g ÷ 1000 × {unit})"   # 毛重 × 实际单价 = 初始材料费
            f" - ({sw:.6f}g ÷ 1000 × {scrap_price_val})"   # 废料 × 回收价
            f" = {round(mat_net_cost, 4):.4f} 元"
        ),
    }

    # ── 表面处理费（前端已按工序汇总）─────────────────────────────
    treat_fee = float(treatment_fee)
    logger.debug(f"[calc] treat_fee={treat_fee}, stamping_fee={stamping_fee}, inspection_fee={inspection_fee}, packaging_fee={packaging_fee}")
    result['formula_display']['treatment_fee'] = {
        'formula': f"前端汇总处理费 = {treat_fee:.4f} 元",
        'result': f"{round(treat_fee, 4):.4f} 元",
        'detail': "（各工序处理费已在页面汇总后传入）",
    }

    # ── 最终总价 ──────────────────────────────────────────────────
    surf_fee = float(surface_fee)
    base_total = (mat_net_cost + float(stamping_fee) + float(inspection_fee) +
                  float(packaging_fee) + surf_fee + treat_fee + float(mold_cost))
    logger.debug(f"[calc] base_total = mat_net_cost({mat_net_cost}) + stamping({stamping_fee}) + inspect({inspection_fee}) + pack({packaging_fee}) + surface({surf_fee}) + treat({treat_fee}) + mold({mold_cost}) = {base_total}")
    if override_final_price is not None:
        final = float(override_final_price)
        result['override_flags'].append('final_price_override')
        final_formula = f"（人工覆盖）{final} 元"
        logger.debug(f"[calc] using override_final_price={final}")
    else:
        final = base_total * (1 + float(profit_margin) / 100.0) if profit_margin > 0 else base_total
        logger.debug(f"[calc] final = base_total({base_total}) × (1 + {profit_margin}/100%) = {final}")
        final_formula = (
            f"({round(mat_net_cost, 4)} + {stamping_fee} + {inspection_fee}"
            f" + {packaging_fee} + {surf_fee} + {treat_fee})"
            f" × (1 + {profit_margin:.1f}%)"
            f" = {round(final, 4):.4f} 元"
        )

    # 最终返回值精确 round，不在中间步骤提前截断
    result['final_price'] = round(final, 4)
    logger.debug(f"[calc] FINAL RESULT: gross_weight={result['gross_weight']}g, material_net_cost={result['material_net_cost']}, final_price={result['final_price']}")
    logger.debug("[calc] ====== calc_part_pricing EXIT ======")
    result['formula_display']['final_price'] = {
        'formula': final_formula,
        'result': f"{round(final, 4):.4f} 元",
        'detail': (
            f"材料{round(mat_net_cost, 4)} + 冲压{stamping_fee} + 全检{inspection_fee}"
            f" + 包装{packaging_fee} + 表面{surf_fee} + 处理{treat_fee}"
            f" × 加价{profit_margin:.0f}%"
        ),
    }

    result['override_flags'] = [f for f in result['override_flags'] if f]
    result['stamping_fee']   = round(float(stamping_fee), 4)
    result['inspection_fee'] = round(float(inspection_fee), 4)
    result['packaging_fee']  = round(float(packaging_fee), 4)
    result['surface_fee']    = round(float(surface_fee), 4)
    result['treatment_fee']  = round(float(treatment_fee), 4)
    result['mold_cost']      = round(float(mold_cost), 4)
    result['profit_margin']  = round(float(profit_margin), 4)
    result['machine_type']   = machine_type
    return result


# ============================================================================
# V12 双表事务：零件 + 模具 + 报价 单连接原子写入
# ============================================================================

def create_part_with_mold_and_pricing(
        part_number: str,
        internal_name: str,
        remark: str = "",
        material_name: str = "",
        pricing_mode: str = "independent",
        *,
        referenced_part_id: int = None,
        thickness: float = None,
        width: float = None,
        press_stroke: float = None,
        cavity_count: int = 1,
        material_utilization: float = 100.0,
        machine_type: str = None,
        press_tonnage: int = 0,
        stamping_fee: float = None,
        surface_fee: float = None,
        treatment_fee: float = None,
        profit_margin: float = None,
        final_price_override: float = None,
        customer_id: int = None,
        alias_part_number: str = None,
        operator_id: int = None,
        drawing_file_path: str = None,
) -> int:
    """
    单事务创建零件 + 模具 + 报价单（parts + dies + quotes 三表原子写入）。

    严格遵循 CLAUDE.md:
      - 纯 SQL（psycopg2），无 ORM
      - T/W/P 存入 dies 表（厚度 → thickness_mm, 宽度 → width_mm, 步距 → pitch_mm）
      - 显式 conn.commit() / conn.rollback()
    """
    # 路径 A（关联参考）：继承老件的 T/W/P
    if pricing_mode == 'reference':
        if not referenced_part_id:
            raise ValueError("关联参考模式必须指定 referenced_part_id")
        ref = get_part_by_id(referenced_part_id)
        if not ref:
            raise ValueError(f"被引用的零件 ID={referenced_part_id} 不存在")
        with psycopg2.connect(**DB_CONFIG) as conn_ref:
            with conn_ref.cursor(cursor_factory=RealDictCursor) as cur_ref:
                cur_ref.execute("""
                    SELECT thickness, width, press_stroke, cavity_count, machine_type
                    FROM quotes
                    WHERE part_id = %s AND approval_status = 'APPROVED'
                    ORDER BY created_at DESC LIMIT 1;
                """, (referenced_part_id,))
                ref_q = cur_ref.fetchone()
                if ref_q:
                    thickness     = thickness     or float(ref_q.get('thickness')     or 0)
                    width         = width         or float(ref_q.get('width')         or 0)
                    press_stroke  = press_stroke  or float(ref_q.get('press_stroke')  or 0)
                    cavity_count  = int(ref_q.get('cavity_count') or cavity_count or 1)
                    if not machine_type:
                        machine_type = ref_q.get('machine_type')

    conn = psycopg2.connect(**DB_CONFIG)
    new_part_id = None
    try:
        with conn.cursor() as cur:
            # ── 1. 校验件号唯一性 ────────────────────────────────────
            # 先查是否存在同名件号
            cur.execute(
                "SELECT 1 FROM parts WHERE part_number = %s LIMIT 1;",
                (part_number,))
            if cur.fetchone():
                # 同名件号存在：remark 为空则报错；remark 非空则检查 (part_number, remark) 联合唯一
                if not remark or not remark.strip():
                    raise ValueError(f"零件号【{part_number}】已存在，请填写备注以区分重复件号")
                cur.execute(
                    "SELECT 1 FROM parts WHERE part_number = %s AND remark = %s LIMIT 1;",
                    (part_number, remark))
                if cur.fetchone():
                    raise ValueError(f"零件号【{part_number}】+备注【{remark}】已存在")

            # ── 2. INSERT parts → RETURNING id ────────────────────
            cur.execute("""
                INSERT INTO parts (
                    part_number, internal_name, remark, material_name,
                    sample_judgment_status, drawing_url,
                    version, part_status,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    'V1.0', 'DRAFT',
                    NOW(), NOW()
                )
                RETURNING id;
            """, (
                part_number, internal_name, remark, material_name,
                'pending', drawing_file_path,
            ))
            new_part_id = cur.fetchone()[0]

            # ── 3. INSERT dies（Die 模具主档）─────────────────────
            mold_number = f"DIE-{part_number}"
            cur.execute(
                "SELECT 1 FROM dies WHERE mold_number = %s LIMIT 1;",
                (mold_number,))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO dies (
                        mold_number, part_id, cavity_count,
                        press_tonnage, lifecycle_status,
                        thickness_mm, width_mm, pitch_mm,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, 'AVAILABLE',
                        %s, %s, %s,
                        NOW(), NOW()
                    );
                """, (
                    mold_number, new_part_id, cavity_count,
                    str(machine_type or press_tonnage or ''),
                    thickness, width, press_stroke,
                ))

            # ── 4. INSERT part_aliases（客户别名）──────────────────
            if customer_id and alias_part_number:
                cur.execute("""
                    INSERT INTO part_aliases
                        (internal_part_id, customer_id, alias_part_number, is_active, created_at)
                    VALUES (%s, %s, %s, TRUE, NOW())
                    ON CONFLICT (internal_part_id, customer_id)
                    DO UPDATE SET alias_part_number = EXCLUDED.alias_part_number,
                                  is_active = TRUE;
                """, (new_part_id, customer_id, alias_part_number))

            # ── 5. INSERT quotes（报价台账）────────────────────────
            cur.execute(
                "SELECT COUNT(*) FROM quotes WHERE part_id = %s;",
                (new_part_id,))
            seq = (cur.fetchone()[0] or 0) + 1
            quote_serial = (
                f"Q-{part_number}-"
                f"{datetime.datetime.now().strftime('%Y%m')}"
                f"-{seq:04d}"
            )
            scrap_rate = max(0.0, min(1.0, 1.0 - (material_utilization or 100.0) / 100.0))

            # ── 5a. 查材料基准价（用于快照）──────────────────────────
            _density = 0.0
            _mat_price = 0.0
            _scrap_price = 0.0
            if material_name:
                with psycopg2.connect(**DB_CONFIG) as conn_mat:
                    with conn_mat.cursor() as cur_mat:
                        cur_mat.execute("""
                            SELECT default_density, default_price, scrap_price
                            FROM material_base_prices
                            WHERE material_name = %s;
                        """, (material_name,))
                        _row_mat = cur_mat.fetchone()
                        if _row_mat:
                            _density = float(_row_mat[0] or 0)
                            _mat_price = float(_row_mat[1] or 0)
                            _scrap_price = float(_row_mat[2] or 0)

            # ── 5b. 计算毛重和材料净成本快照 ──────────────────────
            _gw = None
            _mat_net_cost = None
            _final_price = None
            if thickness and width and press_stroke and _density > 0:
                _gw = thickness * width * press_stroke * _density * (cavity_count or 1) / 1000.0
                _util_pct = material_utilization or 100.0
                _nw = _gw * (_util_pct / 100.0)
                _sw = _gw - _nw
                _mat_net_cost = (_gw / 1000.0 * _mat_price) - (_sw / 1000.0 * _scrap_price)
                _base = (_mat_net_cost
                         + (stamping_fee or 0.0)
                         + (surface_fee or 0.0))
                _margin = profit_margin or 5.0
                _final_price = _base * (1 + _margin / 100.0) if _margin > 0 else _base

            cur.execute("""
                INSERT INTO quotes (
                    part_id, quote_serial, pricing_mode,
                    thickness, width, press_stroke, cavity_count,
                    scrap_rate, gross_weight,
                    snapshot_mat_name, snapshot_mat_price, snapshot_density, snapshot_scrap_price,
                    material_net_cost, final_price,
                    material_utilization,
                    stamping_fee, surface_fee, treatment_fee,
                    profit_margin,
                    final_price_override, override_fields,
                    approval_status,
                    submitted_by,
                    nomination_status, nomination_attachment,
                    machine_type, customer_id,
                    created_at, updated_at
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    NOW(),NOW()
                )
                RETURNING id;
            """, (
                new_part_id, quote_serial, pricing_mode,
                thickness, width, press_stroke, cavity_count,
                scrap_rate, _gw,
                material_name, _mat_price, _density, _scrap_price,
                _mat_net_cost, _final_price,
                material_utilization or 100.0,
                stamping_fee or 0.0, surface_fee or 0.0, treatment_fee or 0.0,
                profit_margin or 5.0,
                final_price_override, '[]',
                'WAITING_FOR_TECH' if pricing_mode == 'pending_tech' else 'DRAFT',
                operator_id,
                None, None,
                machine_type, customer_id,
            ))

        # ── 6. 提交事务 ───────────────────────────────────────
        conn.commit()
        logger.info(
            "零件 %s (id=%s) + 模具 %s + 报价 %s 创建成功",
            part_number, new_part_id, mold_number, quote_serial)
        return new_part_id

    except Exception:
        conn.rollback()
        logger.exception("创建零件 [%s] 失败，已回滚", part_number)
        raise
    finally:
        conn.close()


def create_part_with_pricing(
        part_number: str,
        internal_name: str,
        remark: str = "",
        material_name: str = "",
        pricing_mode: str = "independent",
        *,
        referenced_part_id: int = None,
        thickness: float = None,
        width: float = None,
        press_stroke: float = None,
        cavity_count: int = 1,
        gross_weight: float = None,
        material_unit_price_override: float = None,
        material_net_cost_override: float = None,
        final_price_override: float = None,
        stamping_fee: float = None,
        surface_fee: float = None,
        profit_margin: float = None,
        sample_judgment_status: str = 'pending',
        customer_id: int = None,
        alias_part_number: str = None,
        operator_id: int = None,
        press_tonnage: int = 0,          # V12: parts.mold_tonnage (integer 吨)
        material_utilization: float = 100.0,
        machine_type: str = None):
    """
    创建零件并自动生成第一条报价单（parts + quotes 双写）。

    拆分后职责：
      - parts：零件身份主档（part_number / internal_name / material_name / T/W/P）
      - quotes：报价单台账（所有核价/审批字段）

    pricing_mode 为 'reference' 时，继承老件的 T/W/P/cavity_count 参数。
    """
        # 关联参考：自动继承被引用的老件物理参数
    if pricing_mode == 'reference':
        if not referenced_part_id:
            raise ValueError("关联参考模式必须指定 referenced_part_id")
        ref = get_part_by_id(referenced_part_id)
        if not ref:
            raise ValueError(f"被引用的零件 ID={referenced_part_id} 不存在")
        with psycopg2.connect(**DB_CONFIG) as conn_ref:
            with conn_ref.cursor(cursor_factory=RealDictCursor) as cur_ref:
                cur_ref.execute("""
                    SELECT thickness, width, press_stroke, cavity_count
                    FROM quotes
                    WHERE part_id = %s AND approval_status = 'APPROVED'
                    ORDER BY created_at DESC LIMIT 1;
                """, (referenced_part_id,))
                ref_q = cur_ref.fetchone()
                if ref_q:
                    thickness     = thickness     or float(ref_q.get('thickness')     or 0)
                    width         = width         or float(ref_q.get('width')         or 0)
                    press_stroke  = press_stroke  or float(ref_q.get('press_stroke')  or 0)
                    cavity_count  = cavity_count  or int(ref_q.get('cavity_count')   or 1)

    # ── 写入 parts 表 ──────────────────────────────────────────────
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 允许件号重复：同名件号存在时 remark 为空则报错
            cur.execute(
                "SELECT 1 FROM parts WHERE part_number = %s LIMIT 1;",
                (part_number,))
            if cur.fetchone():
                if not remark or not remark.strip():
                    raise ValueError(f"零件号【{part_number}】已存在，请填写备注以区分重复件号")
                cur.execute(
                    "SELECT 1 FROM parts WHERE part_number = %s AND remark = %s LIMIT 1;",
                    (part_number, remark))
                if cur.fetchone():
                    raise ValueError(f"零件号【{part_number}】+备注【{remark}】已存在")

            cur.execute("""
                INSERT INTO parts (
                    part_number, internal_name, remark, material_name,
                    sample_judgment_status,
                    version, part_status,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s,
                    'V1.0', 'DRAFT',
                    NOW(), NOW()
                )
                RETURNING id;
            """, (
                part_number, internal_name, remark, material_name,
                sample_judgment_status,
            ))
            new_part_id = cur.fetchone()[0]
            conn.commit()

    # ── 写入 part_aliases（如有客户别名）─────────────────────────────
    if customer_id and alias_part_number:
        try:
            with psycopg2.connect(**DB_CONFIG) as conn2:
                with conn2.cursor() as cur2:
                    cur2.execute("""
                        INSERT INTO part_aliases
                            (internal_part_id, customer_id, alias_part_number, is_active, created_at)
                        VALUES (%s, %s, %s, TRUE, NOW())
                        ON CONFLICT (internal_part_id, customer_id)
                        DO UPDATE SET alias_part_number = EXCLUDED.alias_part_number,
                                      is_active = TRUE;
                    """, (new_part_id, customer_id, alias_part_number))
                    conn2.commit()
        except Exception:
            pass  # 别名写入失败不影响零件创建

    # ── 内联生成第一条报价单（V12：含 machine_type）────────────────
    import json as _json
    import datetime as _dt

    with psycopg2.connect(**DB_CONFIG) as conn_q:
        with conn_q.cursor() as cur_q:
            # 计数并生成流水号
            cur_q.execute(
                "SELECT COUNT(*) FROM quotes WHERE part_id = %s;",
                (new_part_id,))
            _seq = (cur_q.fetchone()[0] or 0) + 1
            quote_serial = (
                f"Q-{part_number}-{_dt.datetime.now().strftime('%Y%m')}"
                f"-{_seq:04d}"
            )

            # scrap_rate = 1 − (利用率 / 100)
            _scrap_rate = max(0.0, min(1.0, 1.0 - (material_utilization or 100.0) / 100.0))

            cur_q.execute("""
                INSERT INTO quotes (
                    part_id, quote_serial, pricing_mode,
                    thickness, width, press_stroke, cavity_count,
                    scrap_rate, gross_weight,
                    material_utilization,
                    stamping_fee, surface_fee, treatment_fee,
                    profit_margin,
                    final_price_override, override_fields,
                    approval_status,
                    submitted_by,
                    nomination_status, nomination_attachment,
                    machine_type,
                    created_at, updated_at
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    NOW(),NOW()
                )
                RETURNING id;
            """, (
                new_part_id, quote_serial, pricing_mode,
                thickness, width, press_stroke, cavity_count,
                _scrap_rate, gross_weight,
                material_utilization or 100.0,
                stamping_fee, surface_fee, 0.0,
                profit_margin,
                final_price_override, '[]',
                'DRAFT',
                operator_id,
                None, None,
                machine_type,
                None, None,
            ))
            conn_q.commit()

    return new_part_id


# ============================================================================
# 报价单台账操作（quotes 表）
# ============================================================================

def create_quote(
        part_id: int,
        pricing_mode: str = "independent",
        thickness: float = None,
        width: float = None,
        press_stroke: float = None,
        cavity_count: int = 1,
        scrap_rate: float = 0.10,
        material_utilization: float = None,
        stamping_fee: float = None,
        surface_fee: float = None,
        treatment_fee: float = None,
        profit_margin: float = None,
        final_price_override: float = None,
        override_fields: list = None,
        approval_status: str = "WAITING_FOR_TECH",
        submitted_by: int = None,
        nomination_status: str = None,
        nomination_attachment: str = None,
        operator_id: int = None,
        machine_type: str = None) -> int:
    """
    创建一条报价单记录。

    报价流水号格式：Q-{part_number}-{YYYYMM}-{4位序号}
    创建时自动抓取材料中心当前单价，写入 snapshot_mat_price。

    参数
    ----
    part_id          : 零件 ID（必须存在）
    pricing_mode     : 'independent' | 'reference'
    thickness/width/press_stroke/cavity_count/scrap_rate : 物理参数
    stamping_fee/surface_fee/treatment_fee/profit_margin  : 费用/利润
    final_price_override : 人工覆盖总价
    override_fields  : 被覆盖字段列表（JSON 数组）
    approval_status  : 'WAITING_FOR_TECH'（业务提交图纸后待开发填写参数）
                     | 'DRAFT'（技术部直接建档）
                     | 'PENDING_BOSS'（提交老板审批）
    submitted_by     : 提交人用户 ID
    operator_id      : 操作人用户 ID（用于快照记录）

    返回
    ----
    新报价单 ID (int)
    """
    override_fields = override_fields or []

    # 抓取材料当前单价（快照）
    mat_price = 0.0
    mat_name = None
    mat_density = 0.0
    scrap_mat_price = 0.0
    with psycopg2.connect(**DB_CONFIG) as conn_mat:
        with conn_mat.cursor(cursor_factory=RealDictCursor) as cur_mat:
            cur_mat.execute("""
                SELECT default_price, material_name, default_density, scrap_price
                FROM material_base_prices
                WHERE material_name = (
                    SELECT material_name FROM parts WHERE id = %s
                );
            """, (part_id,))
            row = cur_mat.fetchone()
            if row:
                mat_price = float(row.get('default_price') or 0)
                mat_name = row.get('material_name')
                mat_density = float(row.get('default_density') or 0)
                scrap_mat_price = float(row.get('scrap_price') or 0)

    # 获取 part_number 用于生成流水号
    with psycopg2.connect(**DB_CONFIG) as conn_pn:
        with conn_pn.cursor() as cur_pn:
            cur_pn.execute(
                "SELECT part_number FROM parts WHERE id = %s;",
                (part_id,))
            row_pn = cur_pn.fetchone()
            if not row_pn:
                raise ValueError(f"零件 ID={part_id} 不存在")
            part_number = row_pn[0]

    # 计数当前零件已有报价单数量，用于生成序号
    with psycopg2.connect(**DB_CONFIG) as conn_cnt:
        with conn_cnt.cursor() as cur_cnt:
            cur_cnt.execute(
                "SELECT COUNT(*) FROM quotes WHERE part_id = %s;",
                (part_id,))
            seq = (cur_cnt.fetchone()[0] or 0) + 1

    import datetime as _dt
    import json as _json
    quote_serial = (
        f"Q-{part_number}-{_dt.datetime.now().strftime('%Y%m')}"
        f"-{seq:04d}"
    )

    override_fields_json = _json.dumps(override_fields) if override_fields else '[]'

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO quotes (
                    part_id, quote_serial, pricing_mode,
                    thickness, width, press_stroke, cavity_count, scrap_rate,
                    material_utilization,
                    snapshot_mat_price, snapshot_mat_name, snapshot_density,
                    snapshot_scrap_price,
                    stamping_fee, surface_fee, treatment_fee, profit_margin,
                    final_price_override, override_fields,
                    approval_status,
                    submitted_by,
                    nomination_status, nomination_attachment,
                    machine_type,
                    created_at, updated_at
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    NOW(), NOW()
                )
                RETURNING id;
            """, (
                part_id, quote_serial, pricing_mode,
                thickness, width, press_stroke, cavity_count, scrap_rate,
                material_utilization if material_utilization is not None else 100.0,
                mat_price, mat_name, mat_density, scrap_mat_price,
                stamping_fee, surface_fee, treatment_fee, profit_margin,
                final_price_override, override_fields_json,
                approval_status,
                submitted_by,
                nomination_status, nomination_attachment,
                machine_type,
                None, None,
            ))
            new_quote_id = cur.fetchone()[0]
            conn.commit()

    return new_quote_id


def update_quote(
        quote_id: int,
        annual_usage: int = None,
        pricing_mode: str = None,
        thickness: float = None,
        width: float = None,
        press_stroke: float = None,
        cavity_count: int = None,
        scrap_rate: float = None,
        gross_weight: float = None,
        material_net_cost: float = None,
        material_name: str = None,
        snapshot_mat_name: str = None,
        snapshot_mat_price: float = None,
        snapshot_density: float = None,
        snapshot_scrap_price: float = None,
        final_price: float = None,
        stamping_fee: float = None,
        inspection_fee: float = None,
        packaging_fee: float = None,
        surface_fee: float = None,
        mold_cost: float = None,
        treatment_fee: float = None,
        profit_margin: float = None,
        final_price_override: float = None,
        unit_price_override: float = None,
        material_cost_override: float = None,
        override_fields: list = None,
        nomination_status: str = None,
        nomination_attachment: str = None,
        machine_type: str = None,
        press_tonnage: int = None,
        material_utilization: float = None,
        annual_avg: float = None,
        lifecycle_years: float = None,
        customer_id: int = None,
        mold_discount_mode: str = None,
        mold_discount_rate: float = None,
        treatment_items: list = None) -> bool:
    """
    更新报价单字段（仅 DRAFT / REJECTED 状态允许编辑）。
    """
    import json as _json

    fields = []
    vals = []

    def _add(field, val):
        fields.append(f"{field} = %s")
        vals.append(val)

    if annual_usage is not None:       _add("annual_usage", annual_usage)
    if pricing_mode is not None:       _add("pricing_mode", pricing_mode)
    if thickness is not None:          _add("thickness", thickness)
    if width is not None:              _add("width", width)
    if press_stroke is not None:       _add("press_stroke", press_stroke)
    if cavity_count is not None:        _add("cavity_count", cavity_count)
    if scrap_rate is not None:         _add("scrap_rate", scrap_rate)
    if gross_weight is not None:       _add("gross_weight", gross_weight)
    if material_net_cost is not None:  _add("material_net_cost", material_net_cost)
    if material_name is not None:       _add("material_name", material_name)
    if snapshot_mat_name is not None:  _add("snapshot_mat_name", snapshot_mat_name)
    if snapshot_mat_price is not None:  _add("snapshot_mat_price", snapshot_mat_price)
    if snapshot_density is not None:   _add("snapshot_density", snapshot_density)
    if snapshot_scrap_price is not None: _add("snapshot_scrap_price", snapshot_scrap_price)
    if final_price is not None:        _add("final_price", final_price)
    if stamping_fee is not None:       _add("stamping_fee", stamping_fee)
    if inspection_fee is not None:      _add("inspection_fee", inspection_fee)
    if packaging_fee is not None:       _add("packaging_fee", packaging_fee)
    if surface_fee is not None:         _add("surface_fee", surface_fee)
    if mold_cost is not None:           _add("mold_cost", mold_cost)
    if treatment_fee is not None:        _add("treatment_fee", treatment_fee)
    if profit_margin is not None:       _add("profit_margin", profit_margin)
    if final_price_override is not None: _add("final_price_override", final_price_override)
    if unit_price_override is not None: _add("unit_price_override", unit_price_override)
    if material_cost_override is not None: _add("material_cost_override", material_cost_override)
    if override_fields is not None:
        _add("override_fields", _json.dumps(override_fields) if override_fields else '[]')
    if nomination_status is not None:   _add("nomination_status", nomination_status)
    if nomination_attachment is not None: _add("nomination_attachment", nomination_attachment)
    if machine_type is not None:         _add("machine_type", machine_type)
    if press_tonnage is not None:        _add("press_tonnage", press_tonnage)
    if material_utilization is not None:  _add("material_utilization", material_utilization)
    if annual_avg is not None:            _add("annual_avg", annual_avg)
    if lifecycle_years is not None:       _add("lifecycle_years", lifecycle_years)
    if mold_discount_mode is not None:    _add("mold_discount_mode", mold_discount_mode)
    if mold_discount_rate is not None:    _add("mold_discount_rate", mold_discount_rate)
    if treatment_items is not None:
        _add("treatment_items", _json.dumps(treatment_items) if treatment_items else None)

    # customer_id 变更时触发图纸迁移（null -> 有值）
    _trigger_migrate = False
    if customer_id is not None:
        with psycopg2.connect(**DB_CONFIG) as _conn:
            with _conn.cursor() as _cur:
                _cur.execute("SELECT customer_id FROM quotes WHERE id = %s", (quote_id,))
                _row = _cur.fetchone()
                _old_cid = _row[0] if _row else None
                if _old_cid is None and customer_id is not None:
                    _trigger_migrate = True
        _add("customer_id", customer_id)

    if not fields:
        return True

    fields.append("updated_at = NOW()")
    vals.append(quote_id)

    sql = f"UPDATE quotes SET {', '.join(fields)} WHERE id = %s RETURNING id"

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, vals)
            row = cur.fetchone()
            conn.commit()
            # customer_id 从 null 更新为有值 → 触发图纸迁移
            if _trigger_migrate:
                migrate_drawings_for_quote(quote_id)
            return row is not None


def get_quote_by_id(quote_id: int):
    """返回单条报价单（含零件基础信息）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT q.*, p.part_number, p.internal_name, p.material_name
                FROM quotes q
                JOIN parts p ON q.part_id = p.id
                WHERE q.id = %s
                  AND q.is_deleted = FALSE;
            """, (quote_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_quotes_by_part(part_id: int):
    """返回某零件的全部报价单历史（含软删除，按时间倒序）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT q.*,
                       u1.real_name AS submitted_by_name,
                       u2.real_name AS approved_by_name,
                       u3.real_name AS nomination_confirmed_by_name
                FROM quotes q
                LEFT JOIN users u1 ON q.submitted_by = u1.id
                LEFT JOIN users u2 ON q.approved_by = u2.id
                LEFT JOIN users u3 ON q.nomination_confirmed_by = u3.id
                WHERE q.part_id = %s
                ORDER BY q.created_at DESC;
            """, (part_id,))
            return [dict(r) for r in cur.fetchall()]


def get_latest_quote_by_part(part_id: int):
    """返回某零件的最新一条未删除报价单。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT q.*,
                       p.part_number, p.internal_name, p.material_name
                FROM quotes q
                JOIN parts p ON q.part_id = p.id
                WHERE q.part_id = %s
                  AND q.is_deleted = FALSE
                ORDER BY q.created_at DESC LIMIT 1;
            """, (part_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_quote_detail_for_edit(quote_id: int):
    """
    根据 quote_id 返回报价单完整数据，供报价单编辑页使用。
    返回 dict 含: quote(报价单), part(零件主档)
    """
    import datetime as _dt

    def _serialize(val):
        if isinstance(val, (_dt.datetime, _dt.date)):
            return val.isoformat()
        if hasattr(val, '__float__'):  # Decimal 等
            return float(val)
        return val

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT q.*,
                       p.id AS part_id, p.part_number, p.internal_name,
                       p.material_name AS part_material_name, p.remark
                FROM quotes q
                JOIN parts p ON q.part_id = p.id
                WHERE q.id = %s AND q.is_deleted = FALSE;
            """, (quote_id,))
            row = cur.fetchone()
            if not row:
                return None
            row = dict(row)
            quote = {k: _serialize(v) for k, v in row.items()}
            part = {
                'id': quote.pop('part_id', None),
                'part_number': quote.pop('part_number', None),
                'internal_name': quote.pop('internal_name', None),
                'material_name': quote.pop('part_material_name', None),
                'remark': quote.pop('remark', None),
            }
            return {
                'quote': quote,
                'part': part,
            }


def _safe_path_name(s):
    """将任意字符串转为安全的文件系统路径段（去斜杠星号等）。"""
    import re
    return re.sub(r'[\\/:*?"<>|]', '_', (s or '').strip())


def migrate_drawings_for_quote(quote_id: int) -> dict:
    """
    当报价单 customer_id 发生变化时，将 _unassigned 目录下的图纸迁移到标准路径。
    迁移对象：parts.drawing_url（业务图纸）和 quotes.sdr_drawing_path（SDR 图纸）。
    返回迁移报告：{moved_files: [...], errors: [...]}
    """
    import os as _os

    _BASE = _os.path.join("static", "uploads", "drawings")
    _UNASSIGNED = _os.path.join(_BASE, "_unassigned")

    report = {'moved_files': [], 'errors': []}

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 查该报价单的 part_id 和 customer_id
            cur.execute("""
                SELECT q.part_id, q.sdr_drawing_path, p.drawing_url,
                       tc.name as customer_name, p.internal_name, p.part_number
                FROM quotes q
                JOIN parts p ON q.part_id = p.id
                LEFT JOIN tooling_customers tc ON COALESCE(q.customer_id, p.customer_id) = tc.id
                WHERE q.id = %s
            """, (quote_id,))
            row = cur.fetchone()
            if not row:
                return report

            part_id, sdr_path, drawing_url, customer_name, part_name, part_number = row

            # 生成标准路径（若无客户则返回 None，不迁移）
            if not customer_name:
                return report

            std_subdir = '/'.join([
                _safe_path_name(customer_name),
                _safe_path_name(part_name or ''),
                _safe_path_name(part_number or str(part_id)),
            ]) + '/drawings'
            std_base = _os.path.join(_BASE, std_subdir)

            # 迁移业务图纸
            if drawing_url and drawing_url.startswith('/static/uploads/drawings/_unassigned'):
                old_path = _os.path.join(_BASE, drawing_url.replace('/static/uploads/drawings/', ''))
                new_path = _os.path.join(std_base, _os.path.basename(old_path))
                if _os.path.exists(old_path):
                    try:
                        _os.makedirs(std_base, exist_ok=True)
                        _os.rename(old_path, new_path)
                        new_url = f'/static/uploads/drawings/{std_subdir}{_os.path.basename(old_path)}'
                        cur.execute("UPDATE parts SET drawing_url = %s WHERE id = %s", (new_url, part_id))
                        conn.commit()
                        report['moved_files'].append({
                            'from': drawing_url,
                            'to': new_url,
                            'type': 'drawing'
                        })
                    except OSError as e:
                        report['errors'].append(str(e))
                else:
                    report['errors'].append(f"文件不存在: {old_path}")

            # 迁移 SDR 图纸
            if sdr_path and sdr_path.startswith('/static/uploads/drawings/_unassigned'):
                old_path = _os.path.join(_BASE, sdr_path.replace('/static/uploads/drawings/', ''))
                new_path = _os.path.join(std_base, _os.path.basename(old_path))
                if _os.path.exists(old_path):
                    try:
                        _os.makedirs(std_base, exist_ok=True)
                        _os.rename(old_path, new_path)
                        new_url = f'/static/uploads/drawings/{std_subdir}{_os.path.basename(old_path)}'
                        cur.execute("UPDATE quotes SET sdr_drawing_path = %s WHERE id = %s", (new_url, quote_id))
                        conn.commit()
                        report['moved_files'].append({
                            'from': sdr_path,
                            'to': new_url,
                            'type': 'sdr'
                        })
                    except OSError as e:
                        report['errors'].append(str(e))
                else:
                    report['errors'].append(f"SDR 文件不存在: {old_path}")

    return report


def submit_quote_to_boss(quote_id: int, operator_id: int = None):
    """
    将报价单提交至 PENDING_BOSS 审核。
    状态校验：TECH_APPROVED / DRAFT / REJECTED 均可提交（业务部直接报价走 DRAFT，技术审核后走 TECH_APPROVED）。
    """
    import datetime as _dt
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quotes
                SET approval_status = 'PENDING_BOSS',
                    submitted_at    = %s,
                    submitted_by    = %s,
                    updated_at      = NOW()
                WHERE id = %s
                  AND approval_status IN ('TECH_APPROVED', 'DRAFT', 'REJECTED')
                  AND is_deleted = FALSE
                RETURNING id;
            """, (_dt.datetime.now(), operator_id, quote_id))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def tech_approve_quote(quote_id: int, operator_id: int = None) -> bool:
    """
    技术部审核通过（WAITING_FOR_TECH → TECH_APPROVED）。
    """
    import datetime as _dt
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quotes
                SET approval_status = 'TECH_APPROVED',
                    pricing_mode   = CASE WHEN pricing_mode = 'pending_tech'
                                         THEN 'independent' ELSE pricing_mode END,
                    updated_at      = NOW()
                WHERE id = %s
                  AND approval_status = 'WAITING_FOR_TECH'
                  AND is_deleted = FALSE
                RETURNING id;
            """, (quote_id,))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def tech_reject_quote(quote_id: int, rejection_reason: str,
                      operator_id: int = None) -> bool:
    """
    技术部驳回（WAITING_FOR_TECH → TECH_REJECTED）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quotes
                SET approval_status  = 'TECH_REJECTED',
                    rejection_reason = %s,
                    updated_at       = NOW()
                WHERE id = %s
                  AND approval_status = 'WAITING_FOR_TECH'
                  AND is_deleted = FALSE
                RETURNING id;
            """, (rejection_reason, quote_id))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def update_quote_tech_params(
        quote_id: int,
        thickness: float = None,
        width: float = None,
        press_stroke: float = None,
        cavity_count: int = None,
        mold_cost: float = None,
        press_tonnage: int = None,
        sdr_drawing_path: str = None,
        material_utilization: float = None,
        mold_life: int = None,
        mold_type: str = None,
        operator_id: int = None) -> bool:
    """
    开发填写技术参数：T/W/P、模具费、穴数、吨位、模具寿命、材料利用率、模具类型，以及上传SDR图纸。
    业务提交图纸后，报价单进入 WAITING_FOR_TECH 状态，开发填写参数后变为 TECH_APPROVED。
    仅 WAITING_FOR_TECH 状态可操作。
    """
    fields = []
    vals = []
    if thickness is not None:
        fields.append("thickness = %s"); vals.append(thickness)
    if width is not None:
        fields.append("width = %s"); vals.append(width)
    if press_stroke is not None:
        fields.append("press_stroke = %s"); vals.append(press_stroke)
    if cavity_count is not None:
        fields.append("cavity_count = %s"); vals.append(cavity_count)
    if mold_cost is not None:
        fields.append("mold_cost = %s"); vals.append(mold_cost)
    if press_tonnage is not None:
        fields.append("press_tonnage = %s"); vals.append(press_tonnage)
    if sdr_drawing_path is not None:
        fields.append("sdr_drawing_path = %s"); vals.append(sdr_drawing_path)
    if material_utilization is not None:
        fields.append("material_utilization = %s"); vals.append(material_utilization)
    if mold_life is not None:
        fields.append("mold_life = %s"); vals.append(mold_life)
    if mold_type is not None:
        fields.append("mold_type = %s"); vals.append(mold_type)

    if not fields:
        return False

    # 填写参数后自动变为 TECH_APPROVED
    fields.append("approval_status = %s"); vals.append("TECH_APPROVED")

    vals.append(quote_id)
    sql = f"""
        UPDATE quotes SET {', '.join(fields)}, updated_at = NOW()
        WHERE id = %s AND approval_status = 'WAITING_FOR_TECH' AND is_deleted = FALSE
        RETURNING id;
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, vals)
            row = cur.fetchone()
            conn.commit()
            return row is not None


def _to_json_serializable(obj):
    """将 Decimal 等类型转换为 JSON 可序列化类型"""
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    return obj


def get_pending_tech_quotes():
    """
    返回所有待技术审核的报价单（WAITING_FOR_TECH 状态）。
    含零件基础信息 + 提交人信息 + 图纸路径 + 材料利用率 + 模具寿命。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT q.id, q.part_id, q.quote_serial,
                       p.part_number, p.internal_name, p.material_name,
                       p.drawing_url AS business_drawing_path,
                       q.thickness, q.width, q.press_stroke,
                       q.cavity_count, q.mold_cost,
                       q.press_tonnage, q.sdr_drawing_path,
                       q.material_utilization, q.mold_life, q.mold_type,
                       q.approval_status, q.created_at,
                       u.real_name AS submitted_by_name
                FROM quotes q
                JOIN parts p ON q.part_id = p.id
                LEFT JOIN users u ON q.submitted_by = u.id
                WHERE q.approval_status = 'WAITING_FOR_TECH'
                  AND q.is_deleted = FALSE
                ORDER BY q.created_at ASC;
            """)
            rows = []
            for r in cur.fetchall():
                row = dict(r)
                for k, v in row.items():
                    row[k] = _to_json_serializable(v)
                rows.append(row)
            return rows


# ── 模具类型管理 ────────────────────────────────────────────────

def get_all_mold_types():
    """获取所有模具类型"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, code, name, sort_order FROM mold_types ORDER BY sort_order, id")
            rows = []
            for r in cur.fetchall():
                row = dict(r)
                for k, v in row.items():
                    row[k] = _to_json_serializable(v)
                rows.append(row)
            return rows


def create_mold_type(code: str, name: str, sort_order: int = 0) -> dict:
    """创建模具类型"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mold_types (code, name, sort_order)
                VALUES (%s, %s, %s)
                RETURNING id, code, name, sort_order
            """, (code, name, sort_order))
            conn.commit()
            row = cur.fetchone()
            return {"id": row[0], "code": row[1], "name": row[2], "sort_order": row[3]}


def update_mold_type(type_id: int, code: str, name: str, sort_order: int = 0) -> bool:
    """更新模具类型"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE mold_types SET code = %s, name = %s, sort_order = %s
                WHERE id = %s
            """, (code, name, sort_order, type_id))
            conn.commit()
            return cur.rowcount > 0


def delete_mold_type(type_id: int) -> bool:
    """删除模具类型"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 检查是否被 quotes 使用
            cur.execute("SELECT COUNT(*) FROM quotes WHERE mold_type = (SELECT code FROM mold_types WHERE id = %s)", (type_id,))
            if cur.fetchone()[0] > 0:
                return False  # 正在使用中，无法删除
            cur.execute("DELETE FROM mold_types WHERE id = %s", (type_id,))
            conn.commit()
            return cur.rowcount > 0


def approve_quote(quote_id: int, operator_id: int = None) -> bool:
    """
    审核通过报价单（APPROVED）。
    仅 PENDING_BOSS 状态可操作。
    """
    import datetime as _dt
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quotes
                SET approval_status = 'APPROVED',
                    approved_at     = %s,
                    approved_by     = %s,
                    updated_at      = NOW()
                WHERE id = %s
                  AND approval_status = 'PENDING_BOSS'
                  AND is_deleted = FALSE
                RETURNING id;
            """, (_dt.datetime.now(), operator_id, quote_id))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def get_pending_boss_quotes():
    """
    返回所有 PENDING_BOSS 状态的报价单（老板待审核列表）。
    包含零件信息 + 完整价格参数 + 提交人。
    """
    import datetime as _dt
    import decimal as _dec
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    q.id                          AS quote_id,
                    q.quote_serial,
                    q.approval_status,
                    q.submitted_at,
                    --
                    -- 零件基础信息
                    p.id                          AS part_id,
                    p.part_number,
                    p.internal_name,
                    p.material_name,
                    --
                    -- 物理参数
                    q.thickness,
                    q.width,
                    q.press_stroke,
                    q.cavity_count,
                    q.annual_usage,
                    q.scrap_rate,
                    --
                    -- 价格参数
                    q.gross_weight,
                    q.snapshot_mat_name,
                    q.snapshot_mat_price,
                    q.snapshot_density,
                    q.snapshot_scrap_price,
                    q.material_net_cost,
                    q.stamping_fee,
                    q.inspection_fee,
                    q.packaging_fee,
                    q.surface_fee,
                    q.treatment_fee,
                    q.profit_margin,
                    q.mold_cost,
                    q.machine_type,
                    q.final_price,
                    q.unit_price_override,
                    q.material_cost_override,
                    q.final_price_override,
                    q.override_fields,
                    q.price_snapshot,
                    --
                    -- 提交人
                    u.real_name                    AS submitted_by_name,
                    q.rejection_reason
                FROM quotes q
                JOIN parts p ON q.part_id = p.id
                LEFT JOIN users u ON q.submitted_by = u.id
                WHERE q.approval_status = 'PENDING_BOSS'
                  AND (q.is_deleted = FALSE OR q.is_deleted IS NULL)
                ORDER BY q.submitted_at ASC;
            """)
            rows = cur.fetchall()

    # 序列化 Decimal / datetime，并对缺失的 computed 字段实时补算
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
                d[k] = v.isoformat() if hasattr(v, 'isoformat') else str(v)
            elif isinstance(v, _dec.Decimal):
                d[k] = float(v)

        # 当 material_net_cost 为 NULL 但有 T/W/P 时，实时调用白盒补算
        if d.get("material_net_cost") is None and d.get("thickness") and d.get("width") and d.get("press_stroke"):
            try:
                calc_params = {
                    "thickness": float(d["thickness"]),
                    "width": float(d["width"]),
                    "press_stroke": float(d["press_stroke"]),
                    "material_name": d.get("material_name") or "",
                    "cavity_count": int(d.get("cavity_count") or 1),
                    "scrap_rate": float(d.get("scrap_rate") or 0.10),
                    "gross_weight_g": float(d["gross_weight"]) if d.get("gross_weight") else None,
                    "stamping_fee": float(d.get("stamping_fee") or 0),
                    "inspection_fee": float(d.get("inspection_fee") or 0),
                    "packaging_fee": float(d.get("packaging_fee") or 0),
                    "surface_fee": float(d.get("surface_fee") or 0),
                    "treatment_fee": float(d.get("treatment_fee") or 0),
                    "profit_margin": float(d.get("profit_margin") or 0),
                    "override_material_cost": float(d["material_cost_override"]) if d.get("material_cost_override") else None,
                    "override_final_price": float(d["final_price_override"]) if d.get("final_price_override") else None,
                    "override_unit_price": float(d["unit_price_override"]) if d.get("unit_price_override") else None,
                }
                calc = calc_part_pricing(**calc_params)
                if calc and not calc.get("error"):
                    d["gross_weight"] = calc.get("gross_weight")
                    d["snapshot_mat_name"] = d.get("snapshot_mat_name") or calc.get("material_name")
                    d["snapshot_mat_price"] = calc.get("unit_price")
                    d["snapshot_density"] = calc.get("density")
                    d["snapshot_scrap_price"] = calc.get("scrap_price")
                    d["material_net_cost"] = calc.get("material_net_cost")
                    d["final_price"] = calc.get("final_price")
                    if d.get("gross_weight") is not None and d.get("gross_weight") != d.get("gross_weight"):
                        pass  # already set above
            except Exception:
                pass  # 静默失败，保持 NULL

        result.append(d)
    return result


def boss_update_quote(quote_id: int, body: dict) -> bool:
    """
    老板快速修改报价单字段。
    仅 PENDING_BOSS 状态可操作。
    """
    fields = []
    params = []

    # T/W/P
    if body.get("thickness") is not None:
        fields.append("thickness = %s"); params.append(body["thickness"])
    if body.get("width") is not None:
        fields.append("width = %s"); params.append(body["width"])
    if body.get("press_stroke") is not None:
        fields.append("press_stroke = %s"); params.append(body["press_stroke"])
    if body.get("cavity_count") is not None:
        fields.append("cavity_count = %s"); params.append(body["cavity_count"])
    if body.get("machine_type") is not None:
        fields.append("machine_type = %s"); params.append(body["machine_type"])
    if body.get("gross_weight") is not None:
        fields.append("gross_weight = %s"); params.append(body["gross_weight"])

    if body.get("stamping_fee") is not None:
        fields.append("stamping_fee = %s")
        params.append(body["stamping_fee"])
    if body.get("inspection_fee") is not None:
        fields.append("inspection_fee = %s"); params.append(body["inspection_fee"])
    if body.get("packaging_fee") is not None:
        fields.append("packaging_fee = %s"); params.append(body["packaging_fee"])
    if body.get("surface_fee") is not None:
        fields.append("surface_fee = %s")
        params.append(body["surface_fee"])
    if body.get("treatment_fee") is not None:
        fields.append("treatment_fee = %s")
        params.append(body["treatment_fee"])
    if body.get("mold_cost") is not None:
        fields.append("mold_cost = %s"); params.append(body["mold_cost"])
    if body.get("mold_discount_mode") is not None:
        fields.append("mold_discount_mode = %s"); params.append(body["mold_discount_mode"])
    if body.get("mold_discount_rate") is not None:
        fields.append("mold_discount_rate = %s"); params.append(body["mold_discount_rate"])
    if body.get("treatment_items") is not None:
        fields.append("treatment_items = %s"); params.append(json.dumps(body["treatment_items"]))
    if body.get("profit_margin") is not None:
        fields.append("profit_margin = %s")
        params.append(body["profit_margin"])
    if body.get("unit_price_override") is not None:
        fields.append("unit_price_override = %s")
        params.append(body["unit_price_override"])
    if body.get("material_cost_override") is not None:
        fields.append("material_cost_override = %s")
        params.append(body["material_cost_override"])
    if body.get("final_price_override") is not None:
        fields.append("final_price_override = %s")
        params.append(body["final_price_override"])

    if not fields:
        return True  # 无字段更新，视为成功

    fields.append("updated_at = NOW()")
    params.append(quote_id)

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE quotes
                SET {', '.join(fields)}
                WHERE id = %s
                  AND approval_status = 'PENDING_BOSS'
                  AND (is_deleted = FALSE OR is_deleted IS NULL)
                RETURNING id;
            """, tuple(params))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def reject_quote(quote_id: int, rejection_reason: str,
                 operator_id: int = None) -> bool:
    """
    驳回报价单（REJECTED）。
    驳回后系统生成新的报价单（parent_quote_id 指向被驳回的单据）。
    返回 True 表示驳回成功，返回 False 表示状态不允许驳回。
    """
    import datetime as _dt
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 更新原单为 REJECTED
            cur.execute("""
                UPDATE quotes
                SET approval_status = 'REJECTED',
                    rejection_reason = %s,
                    updated_at      = NOW()
                WHERE id = %s
                  AND approval_status = 'PENDING_BOSS'
                  AND is_deleted = FALSE
                RETURNING id;
            """, (rejection_reason, quote_id))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def delete_quote(quote_id: int) -> bool:
    """
    级联删除报价单及关联的零件主档（含 dies / die_parts / quotes / 库存 / alias）。

    仅 DRAFT 状态允许删除，且该零件不能有 APPROVED 报价单（防止误删已执行件）。
    若零件有 PENDING_BOSS 等非 DRAFT 报价单，拒绝删除。
    返回 True 表示删除成功，False 表示不允许删除。
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # ── 1. 校验报价单状态 ─────────────────────────────────
            cur.execute("""
                SELECT id, part_id, approval_status, is_deleted
                FROM quotes
                WHERE id = %s AND (is_deleted = FALSE OR is_deleted IS NULL);
            """, (quote_id,))
            quote_row = cur.fetchone()
            if not quote_row:
                return False
            _, part_id, status, _ = quote_row
            if status != 'DRAFT':
                return False

            # ── 2. 检查零件是否存在 APPROVED/PENDING 等非 DRAFT 报价单 ─
            cur.execute("""
                SELECT 1 FROM quotes
                WHERE part_id = %s
                  AND id != %s
                  AND approval_status NOT IN ('DRAFT', 'REJECTED')
                  AND (is_deleted = FALSE OR is_deleted IS NULL)
                LIMIT 1;
            """, (part_id, quote_id))
            if cur.fetchone():
                return False

            # ── 3. 清理 machines.current_part_id（若机台正在生产该零件则置空）──
            cur.execute("""
                UPDATE machines
                SET current_part_id = NULL
                WHERE current_part_id = %s;
            """, (part_id,))

            # ── 4. 清理 machines.current_mold_id（若 dies 被当前机台占用则置空）──
            cur.execute("""
                UPDATE machines
                SET current_mold_id = NULL
                WHERE current_mold_id IN (
                    SELECT id FROM dies WHERE part_id = %s
                );
            """, (part_id,))

            # ── 4. 软删除关联 quotes（统一走 is_deleted）──────────────
            cur.execute("""
                UPDATE quotes
                SET is_deleted = TRUE
                WHERE part_id = %s;
            """, (part_id,))

            # ── 5. 物理删除关联数据（按依赖顺序）───────────────────
            # 5a. 删除客户别名
            cur.execute("DELETE FROM part_aliases WHERE internal_part_id = %s;", (part_id,))
            # 5b. 删除库存（会级联删除 finished_inventory_sf / remnant_inventory_sf）
            cur.execute("DELETE FROM finished_inventory WHERE part_id = %s;", (part_id,))
            cur.execute("DELETE FROM remnant_inventory WHERE part_id = %s;", (part_id,))
            # 5c. 删除生产报工（含 SF 表）
            cur.execute("DELETE FROM production_logs WHERE part_id = %s;", (part_id,))
            cur.execute("DELETE FROM sf_production_logs WHERE part_id = %s;", (part_id,))
            # 5d. 删除模具-零件关联（会触发 dies FK 级联删除 dies）
            cur.execute("DELETE FROM die_parts WHERE part_id = %s;", (part_id,))
            # 5e. 删除零件主档（die_parts FK 级联删除 dies）
            cur.execute("DELETE FROM parts WHERE id = %s;", (part_id,))

            conn.commit()
            return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_part_by_id(part_id: int) -> bool:
    """
    直接按零件 ID 物理删除（用于清理孤立的测试零件）。
    忽略报价单状态（不管是 APPROVED 还是软删除），强制级联删除所有关联数据。
    警告：这是危险操作，不可逆。

    删除顺序：machines 清理 → quotes → production_plans/plan_machines →
              part_aliases → 库存 → production_logs → die_parts → parts
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # ── 1. 清理机台占用 ─────────────────────────────────
            cur.execute("""
                UPDATE machines
                SET current_part_id = NULL
                WHERE current_part_id = %s;
            """, (part_id,))
            cur.execute("""
                UPDATE machines
                SET current_mold_id = NULL
                WHERE current_mold_id IN (
                    SELECT id FROM dies WHERE part_id = %s
                );
            """, (part_id,))

            # ── 2. 物理删除所有关联报价单 ───────────────────
            cur.execute("DELETE FROM quotes WHERE part_id = %s;", (part_id,))

            # ── 3. 删除生产计划及关联 ─────────────────────────
            # plan_machines 依赖 production_plans，必须先删
            cur.execute("""
                DELETE FROM plan_machines
                WHERE plan_id IN (SELECT id FROM production_plans WHERE part_id = %s);
            """, (part_id,))
            cur.execute("DELETE FROM production_plans WHERE part_id = %s;", (part_id,))

            # ── 4. 删除客户别名 ──────────────────────────────
            cur.execute("DELETE FROM part_aliases WHERE internal_part_id = %s;", (part_id,))

            # ── 5. 删除库存（级联删除 finished_inventory_sf / remnant_inventory_sf）──
            cur.execute("DELETE FROM finished_inventory WHERE part_id = %s;", (part_id,))
            cur.execute("DELETE FROM remnant_inventory WHERE part_id = %s;", (part_id,))

            # ── 6. 删除生产报工 ──────────────────────────────
            # sf_production_logs 通过 work_order_id → production_logs 间接关联零件，
            # 删除 production_logs 后，sf_production_logs 成为孤儿记录，
            # 但没有外键约束，不影响引用完整性，单独删除即可
            cur.execute("DELETE FROM production_logs WHERE part_id = %s;", (part_id,))
            cur.execute("""
                DELETE FROM sf_production_logs
                WHERE work_order_id IN (
                    SELECT id FROM production_logs WHERE part_id = %s
                );
            """, (part_id,))

            # ── 7. 删除模具-零件关联（触发 dies 级联删除）───
            cur.execute("DELETE FROM die_parts WHERE part_id = %s;", (part_id,))

            # ── 8. 物理删除零件主档 ─────────────────────────
            cur.execute("DELETE FROM parts WHERE id = %s;", (part_id,))

            conn.commit()
            return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reopen_quote_as_new(quote_id: int, operator_id: int = None) -> int:
    """
    基于被驳回的报价单重新生成一条新报价单。
    自动继承父单的所有参数，状态为 DRAFT。
    """
    with psycopg2.connect(**DB_CONFIG) as conn_src:
        with conn_src.cursor(cursor_factory=RealDictCursor) as cur_src:
            cur_src.execute("SELECT * FROM quotes WHERE id = %s AND is_deleted = FALSE;", (quote_id,))
            parent = cur_src.fetchone()

    if not parent:
        raise ValueError(f"报价单 ID={quote_id} 不存在")

    parent = dict(parent)

    return create_quote(
        part_id=parent['part_id'],
        pricing_mode=parent.get('pricing_mode') or 'independent',
        thickness=parent.get('thickness'),
        width=parent.get('width'),
        press_stroke=parent.get('press_stroke'),
        cavity_count=parent.get('cavity_count') or 1,
        scrap_rate=parent.get('scrap_rate') or 0.10,
        stamping_fee=parent.get('stamping_fee'),
        surface_fee=parent.get('surface_fee'),
        treatment_fee=parent.get('treatment_fee'),
        profit_margin=parent.get('profit_margin'),
        final_price_override=parent.get('final_price_override'),
        override_fields=parent.get('override_fields') or [],
        approval_status='DRAFT',
        submitted_by=None,
        operator_id=operator_id,
    )


def unbind_reference_part(part_id: int):
    """
    样件判定不通过 → 一键解绑关联，自动转入独立新件 Path B。
    拆分后操作（作用于 quotes 表）：
      1. 将最新报价单的 pricing_mode 改为 'independent'
      2. 清除 final_price_override（触发重新白盒核算）
      3. 将 parts.sample_judgment_status 置为 'rejected'
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 报价单：解绑关联模式
            cur.execute("""
                UPDATE quotes
                SET pricing_mode        = 'independent',
                    final_price_override = NULL,
                    updated_at          = NOW()
                WHERE part_id = %s
                  AND approval_status IN ('DRAFT', 'REJECTED')
                ORDER BY created_at DESC
                LIMIT 1;
            """, (part_id,))
            affected = cur.rowcount
            conn.commit()

    # parts：更新样件判定状态
    with psycopg2.connect(**DB_CONFIG) as conn2:
        with conn2.cursor() as cur2:
            cur2.execute("""
                UPDATE parts
                SET sample_judgment_status = 'rejected',
                    updated_at = NOW()
                WHERE id = %s;
            """, (part_id,))
            conn2.commit()

    return affected


def get_parts_for_pricing_list(status_filter: str = ""):
    """
    返回所有零件供报价列表页展示。
    通过 LATERAL JOIN 取每个零件最新一条报价的 current_price、approval_status、pricing_mode。
    无报价的零件也会出现在列表中（字段为 NULL）。

    status_filter：可选，传入 'PENDING_BOSS' 等值，仅返回含匹配状态报价单的零件。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 当指定了 status_filter 时：只返回最新报价单状态 = 该状态的零件
            if status_filter:
                cur.execute(f"""
                    SELECT p.id, p.part_number, p.internal_name, p.remark, p.material_name,
                           q.thickness, q.width, q.press_stroke, q.cavity_count,
                           q.final_price   AS current_price,
                           q.approval_status,
                           q.pricing_mode
                    FROM parts p
                    INNER JOIN LATERAL (
                        SELECT thickness, width, press_stroke, cavity_count,
                               final_price, approval_status, pricing_mode
                        FROM quotes
                        WHERE part_id = p.id
                          AND approval_status = %s
                          AND is_deleted = FALSE
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) q ON TRUE
                    ORDER BY p.id DESC
                """, (status_filter,))
            else:
                cur.execute("""
                    SELECT p.id, p.part_number, p.internal_name, p.remark, p.material_name,
                           q.thickness, q.width, q.press_stroke, q.cavity_count,
                           q.final_price   AS current_price,
                           q.approval_status,
                           q.pricing_mode
                    FROM parts p
                    LEFT JOIN LATERAL (
                        SELECT thickness, width, press_stroke, cavity_count,
                               final_price, approval_status, pricing_mode
                        FROM quotes
                        WHERE part_id = p.id
                          AND is_deleted = FALSE
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) q ON TRUE
                    ORDER BY p.id DESC
                """)
            return [dict(r) for r in cur.fetchall()]


def get_all_parts_for_pricing_select(exclude_id: int = None):
    """
    返回所有可作为参考件的零件（供业务创建新件时选择参考件）。
    T/W/P 参数从最新 APPROVED 报价单获取。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT DISTINCT ON (p.id)
                       p.id, p.part_number, p.internal_name, p.material_name,
                       q.thickness, q.width, q.press_stroke, q.cavity_count,
                       q.final_price AS history_price,
                       q.pricing_mode
                FROM parts p
                JOIN quotes q ON q.part_id = p.id
                WHERE q.thickness IS NOT NULL
                  AND q.width IS NOT NULL
                  AND q.press_stroke IS NOT NULL
                  AND q.approval_status = 'APPROVED'
            """
            params = []
            if exclude_id:
                sql += " AND p.id != %s"
                params.append(exclude_id)
            sql += " ORDER BY p.id, q.created_at DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def get_part_history_price(referenced_part_id: int):
    """
    获取被引用零件的历史单价（APPROVED 报价单的 final_price）。
    拆分后：parts.current_price 已迁移至 quotes 表。
    返回 float 或 None。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT final_price
                FROM quotes
                WHERE part_id = %s
                  AND approval_status = 'APPROVED'
                  AND final_price IS NOT NULL
                ORDER BY approved_at DESC
                LIMIT 1;
            """, (referenced_part_id,))
            row = cur.fetchone()
            return float(row[0]) if row else None


def update_part_manual_override(
        part_id: int,
        override_fields: list,
        gross_weight: float = None,
        material_unit_price_override: float = None,
        material_net_cost_override: float = None,
        final_price_override: float = None,
        stamping_fee: float = None,
        surface_fee: float = None,
        profit_margin: float = None,
        operator_id: int = None):
    """
    业务员手动覆盖白盒核算结果（写入 quotes 表最新草稿）。

    拆分后：这些字段已从 parts 表迁移至 quotes 表。
    仅更新最新一条 DRAFT / REJECTED 状态的报价单。
    """
    import json as _json

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 找到该零件最新允许编辑的报价单
            cur.execute("""
                SELECT id FROM quotes
                WHERE part_id = %s
                  AND approval_status IN ('DRAFT', 'REJECTED')
                  AND is_deleted = FALSE
                ORDER BY created_at DESC LIMIT 1;
            """, (part_id,))
            row = cur.fetchone()
            if not row:
                return False
            quote_id = row[0]

            fields = ['updated_at = NOW()']
            vals = []
            _override_fields = list(override_fields) if override_fields else []

            if gross_weight is not None:
                fields.append("gross_weight = %s"); vals.append(gross_weight)
                if 'gross_weight' not in _override_fields:
                    _override_fields.append('gross_weight')
            if material_unit_price_override is not None:
                fields.append("unit_price_override = %s")
                vals.append(material_unit_price_override)
                if 'unit_price_override' not in _override_fields:
                    _override_fields.append('unit_price_override')
            if material_net_cost_override is not None:
                fields.append("material_cost_override = %s")
                vals.append(material_net_cost_override)
                if 'material_cost_override' not in _override_fields:
                    _override_fields.append('material_cost_override')
            if final_price_override is not None:
                fields.append("final_price_override = %s")
                vals.append(final_price_override)
                if 'final_price_override' not in _override_fields:
                    _override_fields.append('final_price_override')
            if stamping_fee is not None:
                fields.append("stamping_fee = %s"); vals.append(stamping_fee)
            if surface_fee is not None:
                fields.append("surface_fee = %s"); vals.append(surface_fee)
            if profit_margin is not None:
                fields.append("profit_margin = %s"); vals.append(profit_margin)
            if _override_fields:
                fields.append("override_fields = %s")
                vals.append(_json.dumps(_override_fields))

            vals.append(quote_id)
            sql = f"UPDATE quotes SET {', '.join(fields)} WHERE id = %s"
            cur.execute(sql, vals)
            conn.commit()
    return True


def update_part_twp(part_id: int, thickness: float = None,
                    width: float = None, press_stroke: float = None,
                    operator_id: int = None):
    """
    更新零件的 T/W/P 物理参数（写入最新报价单）。
    拆分后：T/W/P 从 parts 表迁移至 quotes 表。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 找到该零件最新允许编辑的报价单
            cur.execute("""
                SELECT id FROM quotes
                WHERE part_id = %s AND approval_status IN ('DRAFT', 'REJECTED')
                ORDER BY created_at DESC LIMIT 1;
            """, (part_id,))
            row = cur.fetchone()
            if not row:
                return False
            quote_id = row[0]

            fields = ["updated_at = NOW()"]
            vals = []
            if thickness is not None:
                fields.append("thickness = %s"); vals.append(thickness)
            if width is not None:
                fields.append("width = %s"); vals.append(width)
            if press_stroke is not None:
                fields.append("press_stroke = %s"); vals.append(press_stroke)
            if not fields or len(fields) == 1:
                return True
            vals.append(quote_id)
            sql = f"UPDATE quotes SET {', '.join(fields)} WHERE id = %s RETURNING id"
            cur.execute(sql, vals)
            conn.commit()
            row2 = cur.fetchone()
            return row2 is not None


def update_part_sample_judgment(part_id: int, status: str, operator_id: int = None):
    """
    更新样件判定结果：pending | approved | rejected
    """
    valid = ('pending', 'approved', 'rejected')
    if status not in valid:
        raise ValueError(f"无效判定状态：{status}")
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE parts
                SET sample_judgment_status = %s,
                    updated_at = NOW()
                WHERE id = %s;
            """, (status, part_id))
            conn.commit()
    return True


# ============================================================================
# 定点 (Nomination) 卡控体系
# V3.1 §2.1 定点流程：报价后 → pending_nomination → nominated → production_ready
# ============================================================================

def check_part_nomination_locked(part_id: int) -> tuple[bool, str]:
    """
    定点卡控校验（刚性约束）。

    检查零件是否处于"禁止下达量产指令"的状态。

    允许创建生产工单/采购单的状态：'production_ready'
    禁止创建的状态：
      - 'pending_nomination'  报价完成，待定点
      - 'nominated'           已定点，待确认（严禁跳过确认直接量产）
      - None / 'Draft'        价格尚未确认（样件判定中）
      - (无 nomination_status 字段的旧数据)   视为 Draft，等同禁止

    参数
    ----
    part_id : int

    返回
    ----
    (locked: bool, message: str)
      - locked=True  → 禁止，卡控消息
      - locked=False → 允许量产
    """
    part = get_part_by_id(part_id)
    if not part:
        return True, f"零件 ID={part_id} 不存在"

    status = part.get('nomination_status')
    part_number = part.get('part_number', f'ID={part_id}')

    # 明确允许量产的状态
    if status == 'production_ready':
        return False, ""

    # 禁止量产的所有状态
    if status in ('pending_nomination', 'nominated'):
        return True, (
            f"零件【{part_number}】尚未完成客户定点（当前状态：{status}），"
            f"严禁下达量产指令。"
        )

    # 无 nomination_status 字段（旧数据）或状态为空
    # 价格未确认 / 样件判定中 → 同样禁止
    if not status:
        sample_status = part.get('sample_judgment_status', 'pending')
        # 通过 quotes 表判断价格是否已锁定（替代已删除的 parts.price_status）
        has_approved_quote = False
        with psycopg2.connect(**DB_CONFIG) as conn_q:
            with conn_q.cursor() as cur_q:
                cur_q.execute("""
                    SELECT 1 FROM quotes
                    WHERE part_id = %s
                      AND approval_status = 'APPROVED'
                      AND final_price IS NOT NULL
                    LIMIT 1
                """, (part_id,))
                has_approved_quote = cur_q.fetchone() is not None
        if not has_approved_quote or sample_status == 'pending':
            return True, (
                f"零件【{part_number}】尚未完成定点确认"
                f"（报价单未 APPROVED，"
                f"样件判定：{sample_status}），严禁下达量产指令。"
            )

    # 其他未知状态 → 放行（兼容未来新状态扩展）
    return False, ""


def confirm_nomination(
        part_id: int,
        operator_id: int,
        attachment_filenames: list = None,
        price_snapshot: dict = None,
        mold_number: str = None,
        mold_type: str = None,
        press_tonnage: str = None,
        ppap_no: str = None):
    """
    定点终裁确认接口（V7.1：定点后写入 parts 模具字段）。

    V3.1 §2.1 Nomination 定点流程：
      1. 业务上传定点凭证（PDF/图片）
      2. 系统执行"价格快照"（price_snapshot），切断与 material_base_prices 的联动
      3. 报价单状态 → production_ready
      4. 定点模具基础信息同步写入 parts 表（mold_number/mold_type/press_tonnage/ppap_no）

    定点后数据流向：quotes → parts（模具字段）+ tooling_molds（模具台账基础）

    参数
    ----
    part_id            : int       零件 ID
    operator_id        : int       确认人（业务主管 / admin）
    attachment_filenames: list[str] 定点凭证文件名列表
    price_snapshot     : dict      可选，手动传入快照数据；None=自动构建
    mold_number        : str       模具编号（定点后填写）
    mold_type          : str       模具类型（级进模/单工程/传递模）
    press_tonnage      : str       冲压吨位，如 200T
    ppap_no            : str       PPAP 编号

    返回
    ----
    dict，含 keys: ok, message, snapshot, quote_id
    """
    import json as _json
    import datetime as _dt

    part = get_part_by_id(part_id)
    if not part:
        raise ValueError(f"零件 ID={part_id} 不存在")

    # ── 找到待定点的报价单 ──────────────────────────────────────────
    with psycopg2.connect(**DB_CONFIG) as conn_find:
        with conn_find.cursor(cursor_factory=RealDictCursor) as cur_find:
            cur_find.execute("""
                SELECT id, approval_status, nomination_status
                FROM quotes
                WHERE part_id = %s
                  AND nomination_status IN ('pending_nomination', 'nominated', NULL, '')
                   OR approval_status = 'APPROVED'
                ORDER BY created_at DESC LIMIT 1;
            """, (part_id,))
            quote_row = cur_find.fetchone()

    # 如果找不到特定报价单，取最新的 APPROVED 报价单
    if not quote_row:
        with psycopg2.connect(**DB_CONFIG) as conn_find2:
            with conn_find2.cursor(cursor_factory=RealDictCursor) as cur_find2:
                cur_find2.execute("""
                    SELECT id, approval_status, nomination_status
                    FROM quotes
                    WHERE part_id = %s
                    ORDER BY created_at DESC LIMIT 1;
                """, (part_id,))
                quote_row = cur_find2.fetchone()

    if not quote_row:
        raise ValueError(f"零件【{part.get('part_number')}】未找到任何报价单，无法定点")

    quote_id = quote_row['id']

    # ── 状态前置校验 ────────────────────────────────────────────────
    nom_status = quote_row.get('nomination_status')
    if nom_status == 'production_ready':
        raise ValueError(
            f"零件【{part.get('part_number')}】已处于量产就绪状态，无需重复确认。"
        )

    # ── 自动构建价格快照（若未传入）─────────────────────────────────
    if price_snapshot is None:
        # 从 quotes 表取最新报价参数
        with psycopg2.connect(**DB_CONFIG) as conn_q:
            with conn_q.cursor(cursor_factory=RealDictCursor) as cur_q:
                cur_q.execute("""
                    SELECT q.*, p.material_name
                    FROM quotes q JOIN parts p ON q.part_id = p.id
                    WHERE q.id = %s;
                """, (quote_id,))
                q_data = dict(cur_q.fetchone()) if cur_q.fetchone() else {}

        mat_name = q_data.get('material_name') or ''
        mat = get_material_base_price(mat_name) if mat_name else {}
        price_snapshot = {
            "unit_price":       float(mat.get('default_price') or 0),
            "scrap_price":      float(mat.get('scrap_price') or 0),
            "density":          float(mat.get('default_density') or 0),
            "stamping_fee":     float(q_data.get('stamping_fee') or 0),
            "surface_fee":      float(q_data.get('surface_fee') or 0),
            "profit_margin":    float(q_data.get('profit_margin') or 0),
            "gross_weight":     float(q_data.get('gross_weight') or 0),
            "material_net_cost":float(q_data.get('material_net_cost') or 0),
            "final_price":      float(q_data.get('final_price_override')
                                     or q_data.get('final_price') or 0),
            "material_name":    mat_name,
            "cavity_count":     int(q_data.get('cavity_count') or 1),
            "thickness":       float(q_data.get('thickness') or 0),
            "width":           float(q_data.get('width') or 0),
            "press_stroke":    float(q_data.get('press_stroke') or 0),
            "customer_product_no": q_data.get('customer_product_no') or '',
            "vehicle_model":   q_data.get('vehicle_model') or '',
            "snapshot_at":     _dt.datetime.now().isoformat(),
        }

    # ── 凭证文件路径序列化 ─────────────────────────────────────────
    attachment_str = ','.join(attachment_filenames) if attachment_filenames else None
    snapshot_json = _json.dumps(price_snapshot, ensure_ascii=False)
    confirmed_at = _dt.datetime.now()

    # ── 写入 quotes 表（定点确认）──────────────────────────────────
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE quotes SET
                    nomination_status        = 'production_ready',
                    nomination_attachment    = %s,
                    price_snapshot          = %s,
                    nomination_confirmed_at = %s,
                    nomination_confirmed_by = %s,
                    updated_at              = NOW()
                WHERE id = %s
                RETURNING id;
            """, (
                attachment_str,
                snapshot_json,
                confirmed_at,
                operator_id,
                quote_id,
            ))
            conn.commit()

    # ── 同步更新 parts 表汇总字段 ─────────────────────────────────
    # 先从 quotes 读 customer_product_no 和 vehicle_model（定点前quotes中已填）
    with psycopg2.connect(**DB_CONFIG) as conn_q2:
        with conn_q2.cursor(cursor_factory=RealDictCursor) as cur_q2:
            cur_q2.execute("""
                SELECT customer_product_no, vehicle_model
                FROM quotes WHERE id = %s;
            """, (quote_id,))
            quote_extra = dict(cur_q2.fetchone()) if cur_q2.fetchone() else {}

    with psycopg2.connect(**DB_CONFIG) as conn2:
        with conn2.cursor() as cur2:
            # parts 定点字段（原有）
            cur2.execute("""
                UPDATE parts SET
                    nomination_status        = 'production_ready',
                    nomination_attachment    = %s,
                    price_snapshot          = %s,
                    nomination_confirmed_at = %s,
                    nomination_confirmed_by = %s,
                    updated_at              = NOW()
                WHERE id = %s;
            """, (
                attachment_str,
                snapshot_json,
                confirmed_at,
                operator_id,
                part_id,
            ))
            conn2.commit()

    # ── 定点模具基础信息写入 parts（新字段，nom004 迁移后生效）─────
    _cpn = quote_extra.get('customer_product_no')
    _vm  = quote_extra.get('vehicle_model')
    try:
        with psycopg2.connect(**DB_CONFIG) as conn3:
            with conn3.cursor() as cur3:
                cur3.execute("""
                    UPDATE parts SET
                        customer_product_no = COALESCE(%s, customer_product_no),
                        vehicle_model      = COALESCE(%s, vehicle_model),
                        mold_number       = %s,
                        mold_type         = %s,
                        press_tonnage     = %s,
                        ppap_no           = %s,
                        updated_at         = NOW()
                    WHERE id = %s;
                """, (
                    _cpn,
                    _vm,
                    mold_number,
                    mold_type,
                    press_tonnage,
                    ppap_no,
                    part_id,
                ))
                conn3.commit()
    except Exception:
        # 迁移未执行时跳过，不阻塞定点流程
        pass

    return {
        "ok": True,
        "message": (
            f"定点确认完成，零件【{part.get('part_number')}】报价单(id={quote_id})"
            f"已切换为量产就绪状态。"
        ),
        "snapshot": price_snapshot,
        "nomination_status": "production_ready",
        "confirmed_at": confirmed_at.isoformat(),
        "quote_id": quote_id,
    }


def set_part_pending_nomination(part_id: int):
    """
    将项目状态推进为 pending_nomination（报价完成，等待定点确认）。
    在报价保存时由业务调用。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE parts
                SET nomination_status = 'pending_nomination',
                    updated_at = NOW()
                WHERE id = %s
                  AND (nomination_status IS NULL OR nomination_status = '');
            """, (part_id,))
            conn.commit()


# ============================================================================
# 双时间戳规范 (Dual Timestamp)
# V3.1 §4：必须区分 created_at（系统时间）与 actual_date（业务发生日期）
# ============================================================================
def get_part_nomination_info(part_id: int) -> dict:
    """
    返回零件定点信息（用于详情页展示定点进度卡）。
    """
    part = get_part_by_id(part_id)
    if not part:
        return {}

    mat = get_material_base_price(part.get('material_name', '')) if part.get('material_name') else {}

    # 优先展示价格快照（定点后），无快照则展示当前实时值
    snap = part.get('price_snapshot')
    if snap:
        display = {
            "source": "snapshot",
            "material_price": snap.get('unit_price'),
            "scrap_price": snap.get('scrap_price'),
            "density": snap.get('density'),
            "gross_weight": snap.get('gross_weight'),
            "material_net_cost": snap.get('material_net_cost'),
            "final_price": snap.get('final_price'),
            "stamping_fee": snap.get('stamping_fee'),
            "surface_fee": snap.get('surface_fee'),
            "profit_margin": snap.get('profit_margin'),
            "snapshot_at": snap.get('snapshot_at'),
        }
    else:
        display = {
            "source": "live",
            "material_price": mat.get('default_price') if mat else None,
            "scrap_price": mat.get('scrap_price') if mat else None,
            "density": mat.get('default_density') if mat else None,
            "gross_weight": part.get('gross_weight'),
            "material_net_cost": part.get('material_net_cost_override'),
            "final_price": part.get('final_price_override'),
            "stamping_fee": part.get('stamping_fee'),
            "surface_fee": part.get('surface_fee'),
            "profit_margin": part.get('profit_margin'),
            "snapshot_at": None,
        }

    return {
        "part_id": part_id,
        "part_number": part.get('part_number'),
        "nomination_status": part.get('nomination_status'),
        "sample_judgment_status": part.get('sample_judgment_status'),
        "attachment": part.get('nomination_attachment'),
        "confirmed_at": part.get('nomination_confirmed_at'),
        "confirmed_by": part.get('nomination_confirmed_by'),
        "pricing_display": display,
    }


def get_part_pricing_summary(part_id: int):
    """
    返回零件的完整报价信息（用于详情页展示含公式的报价明细）。

    拆分后：
      - part：零件主档（parts 表）
      - quote：最新报价单（quotes 表），含 APPROVED 快照
      - calc：实时白盒重算结果
      - history：全部历史报价单列表
    """
    logger.debug(f"[summary] ====== get_part_pricing_summary ENTRY part_id={part_id}")
    part = get_part_by_id(part_id)
    logger.debug(f"[summary] part=%s", part)
    if not part:
        return None

    mat = get_material_base_price(part.get('material_name')) if part.get('material_name') else None
    logger.debug(f"[summary] material mat=%s", mat)

    # 取最新报价单
    quote = get_latest_quote_by_part(part_id)
    logger.debug(f"[summary] quote=%s", quote)
    calc = None
    if quote:
        # 若有 T/W/P 参数，实时重算白盒（保留人工覆盖值）
        if quote.get('thickness') and quote.get('width') and quote.get('press_stroke'):
            calc_params = {
                'thickness': float(quote['thickness']),
                'width': float(quote['width']),
                'press_stroke': float(quote['press_stroke']),
                'material_name': part['material_name'] or '',
                'cavity_count': int(quote['cavity_count'] or 1),
                'scrap_rate': float(quote.get('scrap_rate') or 0.10),
                'material_utilization': float(quote.get('material_utilization') or 100.0),
                'stamping_fee': float(quote.get('stamping_fee') or 0),
                'inspection_fee': float(quote.get('inspection_fee') or 0),
                'packaging_fee': float(quote.get('packaging_fee') or 0),
                'surface_fee': float(quote.get('surface_fee') or 0),
                'treatment_fee': float(quote.get('treatment_fee') or 0),
                'profit_margin': float(quote.get('profit_margin') or 0),
                'override_unit_price': (
                    float(quote['unit_price_override'])
                    if quote.get('unit_price_override') else None),
                'override_material_cost': (
                    float(quote['material_cost_override'])
                    if quote.get('material_cost_override') else None),
                'override_final_price': (
                    float(quote['final_price_override'])
                    if quote.get('final_price_override') else None),
            }
            logger.debug(f"[summary] calling calc_part_pricing with params=%s", calc_params)
            try:
                calc = calc_part_pricing(**calc_params)
            except Exception as e:
                import traceback
                logger.error(f"[summary] calc_part_pricing EXCEPTION: {e}\n{traceback.format_exc()}")
                calc = {'error': str(e)}
        else:
            calc = {'error': 'T/W/P 参数未设置，无法白盒核算'}
    else:
        quote = {}
        calc = {'error': '该零件尚未创建报价单'}

    logger.debug(f"[summary] calc=%s", calc)

    # 历史报价单列表（用于详情页展示审批/驳回记录）
    history = get_quotes_by_part(part_id)

    # 将 quotes 表的 pricing_mode 注入到 part 对象，供前端模板使用
    # quotes 存的是 'reference'/'independent'，前端期望 'Associated'/'Independent'，做转换
    if part and quote:
        _pm = quote.get('pricing_mode')
        part['pricing_mode'] = 'Associated' if _pm == 'reference' else ('Independent' if _pm == 'independent' else _pm)
        part['thickness'] = quote.get('thickness')
        part['width'] = quote.get('width')
        part['press_stroke'] = quote.get('press_stroke')
        part['cavity_count'] = quote.get('cavity_count')
        part['material_utilization'] = quote.get('material_utilization')
        part['final_price_override'] = quote.get('final_price_override')
        part['gross_weight'] = quote.get('gross_weight')

    logger.debug("[summary] ====== get_part_pricing_summary EXIT")
    return {
        'part': part,
        'quote': quote,
        'material': mat,
        'calc': calc,
        'history': history,
    }


def set_part_pricing_mode(part_id: int, pricing_mode: str,
                          referenced_part_id: int = None,
                          operator_id: int = None):
    """
    设置零件的报价模式（写入最新报价单）。
    pricing_mode: 'Associated' | 'Independent'
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if pricing_mode not in ('Associated', 'Independent'):
                raise ValueError(f"不支持的报价模式: {pricing_mode}")

            # 找到最新允许编辑的报价单
            cur.execute("""
                SELECT id FROM quotes
                WHERE part_id = %s AND approval_status IN ('DRAFT', 'REJECTED')
                ORDER BY created_at DESC LIMIT 1;
            """, (part_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"零件 ID={part_id} 没有可编辑的报价单")

            new_pricing_mode = 'reference' if pricing_mode == 'Associated' else 'independent'
            cur.execute("""
                UPDATE quotes
                SET pricing_mode = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """, (new_pricing_mode, row[0]))
            if not cur.fetchone():
                raise ValueError(f"报价单 ID={row[0]} 更新失败")
            conn.commit()
    return True


# ═══════════════════════════════════════════════════════════════════════════
#  系统字典表（system_dicts）
#  字段：id, dict_type(varchar), dict_value(varchar), sort_order(int),
#        is_active(bool), created_at(timestamp)
#  用途：存储可配置的下拉选项，如零件名称、常用备注等
# ═══════════════════════════════════════════════════════════════════════════

def ensure_system_dicts_table():
    """建表语句（幂等，可重复执行），若表已存在则忽略"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_dicts (
                    id          SERIAL PRIMARY KEY,
                    dict_type   VARCHAR(64)  NOT NULL,
                    dict_value  VARCHAR(256) NOT NULL,
                    sort_order  INTEGER      DEFAULT 0,
                    is_active   BOOLEAN      DEFAULT TRUE,
                    created_at  TIMESTAMP    DEFAULT NOW(),
                    UNIQUE(dict_type, dict_value)
                );
            """)
            # 默认预置零件名称（如表中尚无数据）
            cur.execute("SELECT COUNT(*) FROM system_dicts WHERE dict_type = 'part_name'")
            if cur.fetchone()[0] == 0:
                defaults = [
                    ("part_name", "弹簧片", 1),
                    ("part_name", "报警器", 2),
                    ("part_name", "接触片", 3),
                    ("part_name", "端子",   4),
                    ("part_name", "支架",   5),
                    ("part_name", "外壳",   6),
                    ("part_name", "屏蔽罩", 7),
                    ("part_name", "垫片",   8),
                ]
                cur.executemany(
                    "INSERT INTO system_dicts (dict_type, dict_value, sort_order) "
                    "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    defaults,
                )
            conn.commit()


def get_dict_items(dict_type: str) -> list[dict]:
    """返回指定字典类型的所有激活项，按 sort_order 排序"""
    ensure_system_dicts_table()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, dict_value, sort_order
                FROM system_dicts
                WHERE dict_type = %s AND is_active = TRUE
                ORDER BY sort_order, id
            """, (dict_type,))
            return [dict(r) for r in cur.fetchall()]


def add_dict_item(dict_type: str, dict_value: str) -> dict:
    """新增字典项（dict_value 去重）"""
    ensure_system_dicts_table()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO system_dicts (dict_type, dict_value, sort_order)
                VALUES (%s, %s,
                    (SELECT COALESCE(MAX(sort_order), 0) + 1
                     FROM system_dicts WHERE dict_type = %s))
                ON CONFLICT (dict_type, dict_value)
                DO UPDATE SET is_active = TRUE, sort_order = system_dicts.sort_order
                RETURNING id, dict_value, sort_order
            """, (dict_type, dict_value, dict_type))
            row = cur.fetchone()
            conn.commit()
            return dict(row)


def delete_dict_item(dict_type: str, item_id: int) -> bool:
    """软删除（is_active=FALSE）字典项"""
    ensure_system_dicts_table()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE system_dicts
                SET is_active = FALSE
                WHERE id = %s AND dict_type = %s
                RETURNING id
            """, (item_id, dict_type))
            ok = cur.fetchone() is not None
            conn.commit()
            return ok


# ═══════════════════════════════════════════════════════════════════════════════
#  表面处理字典  treatment_dicts
#  字段：id / name / calc_mode ('manual'|'net_weight') / rate / unit / is_active / created_at
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_treatment_dicts_table():
    """幂等建表；若表已存在则忽略"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS treatment_dicts (
                    id          SERIAL PRIMARY KEY,
                    name        VARCHAR(128) NOT NULL UNIQUE,
                    calc_mode   VARCHAR(32)  NOT NULL DEFAULT 'manual',
                    rate        NUMERIC(12,6) NOT NULL DEFAULT 0,
                    unit        VARCHAR(16)  NOT NULL DEFAULT '元/件',
                    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
                    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
                )
            """)
            # ⚠️ 注意：建表后不 commit，先预置数据，再统一 commit
            # 如果建表后立即 commit，预置 INSERT 将开启新事务，
            # 但 with 块结束时若不再次 commit，该事务将隐式 rollback
            # 预置常用处理方式
            cur.execute("SELECT COUNT(*) FROM treatment_dicts")
            if cur.fetchone()[0] == 0:
                defaults = [
                    ("热处理",    "net_weight", 12.0,   "元/kg"),
                    ("电镀锌",    "net_weight",  8.5,   "元/kg"),
                    ("电镀镍",    "net_weight", 15.0,   "元/kg"),
                    ("发黑",      "manual",      0.5,   "元/件"),
                    ("喷涂",      "manual",      3.0,   "元/件"),
                    ("贴胶",      "manual",      1.5,   "元/件"),
                    ("阳极氧化",  "net_weight", 20.0,   "元/kg"),
                    ("磷化",      "net_weight",  6.0,   "元/kg"),
                ]
                cur.executemany(
                    "INSERT INTO treatment_dicts (name,calc_mode,rate,unit) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT (name) DO NOTHING",
                    defaults
                )
            # ── 建表 + 预置数据 统一提交 ───────────────────────
            # 在 with 块结束前显式 commit，确保所有操作在同一事务内
            conn.commit()


def get_all_treatments() -> list[dict]:
    """返回所有激活的处理方式列表"""
    _ensure_treatment_dicts_table()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, calc_mode, rate, unit
                FROM treatment_dicts
                WHERE is_active = TRUE
                ORDER BY id
            """)
            rows = cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if 'rate' in d and hasattr(d['rate'], '__float__'):
                    d['rate'] = float(d['rate'])
                result.append(d)
            return result

def get_treatment_by_id(treatment_id: int) -> dict | None:
    _ensure_treatment_dicts_table()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, calc_mode, rate, unit
                FROM treatment_dicts WHERE id = %s AND is_active = TRUE
            """, (treatment_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            if 'rate' in d and hasattr(d['rate'], '__float__'):
                d['rate'] = float(d['rate'])
            return d


def upsert_treatment(name: str, calc_mode: str, rate: float,
                     unit: str = "元/件") -> dict:
    """
    新增或更新处理方式（按 name 唯一键 upsert）。
    calc_mode: 'manual' | 'net_weight'
    返回数据字典，由 API 路由统一包装为 {code, message, data}。
    """
    _ensure_treatment_dicts_table()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO treatment_dicts (name, calc_mode, rate, unit)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    calc_mode = EXCLUDED.calc_mode,
                    rate      = EXCLUDED.rate,
                    unit      = EXCLUDED.unit
                RETURNING id, name, calc_mode, rate, unit
            """, (name, calc_mode, float(rate), unit))
            row = cur.fetchone()
            conn.commit()
            d = dict(row)
            if 'rate' in d and hasattr(d['rate'], '__float__'):
                d['rate'] = float(d['rate'])
            return d


def delete_treatment(treatment_id: int) -> bool:
    """软删除（is_active=FALSE）"""
    _ensure_treatment_dicts_table()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE treatment_dicts SET is_active = FALSE
                WHERE id = %s RETURNING id
            """, (treatment_id,))
            ok = cur.fetchone() is not None
            conn.commit()
            return ok


# ============================================================================
# 阶段二：打样与 PPAP 定型流  (v4_sample_molds_bom)
# ============================================================================


# ---------------------------------------------------------------------------
# 工具：中文数字 → int 转换（cavity_count 正则提取用）
# ---------------------------------------------------------------------------
CN_DIGIT_MAP = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '壹': 1, '贰': 2, '叁': 3, '肆': 4,
    '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9,
}

CN_UNIT_MAP = {
    '十': 10, '百': 100, '千': 1000,
}


def _cn_to_int(text: str) -> int | None:
    """
    将中文数字字符串转为 int。
    支持：二 → 2、三 → 3、十二 → 12、二十三 → 23。
    若无法解析返回 None。
    """
    if not text:
        return None
    text = text.strip()
    # 纯阿拉伯数字
    try:
        return int(text)
    except ValueError:
        pass

    result = 0
    temp = 0
    for ch in text:
        if ch in CN_DIGIT_MAP:
            temp += CN_DIGIT_MAP[ch]
        elif ch in CN_UNIT_MAP:
            if ch == '十':
                temp = temp or 1
            result += temp * CN_UNIT_MAP[ch]
            temp = 0
        elif ch in ('多', '几', '若干', ' '):
            continue
        else:
            return None
    result += temp
    return result if result > 0 else None


def extract_cavity_count(remarks: str = '', spec_text: str = '') -> int:
    """
    从备注 / 用料规格文本中提取"一出几"数值。

    匹配模式（按优先级）：
      1. "1出2" / "1出3"（阿拉伯数字）
      2. "一出二" / "一出一"（中文数字）
      3. "出2" / "出三"（省略"一"）

    备注文本为空且规格文本也为空时，返回默认值 1。
    提取失败（文本存在但无法匹配）时也返回 1，不阻断导入。
    """
    for src in [remarks, spec_text]:
        if not src:
            continue
        # 模式1：阿拉伯数字 "X出Y"（Y 为阿拉伯数字）
        m = re.search(r'[1一]出(\d+)', src)
        if m:
            raw = m.group(1)
            try:
                val = int(raw)
                if 1 <= val <= 20:
                    return val
            except ValueError:
                pass
        # 模式2：中文数字 "X出Y"（Y 为中文数字）
        m = re.search(r'[1一]出([零一二三四五六七八九十]+)', src)
        if m:
            val = _cn_to_int(m.group(1))
            if val and 1 <= val <= 20:
                return val
        # 模式3：省略"一"的 "出X"
        m = re.search(r'出([零一二三四五六七八九十]+)', src)
        if m:
            val = _cn_to_int(m.group(1))
            if val and 1 <= val <= 20:
                return val

    # 无法提取 → 默认 1
    return 1


def extract_mold_set_count(raw: str) -> int:
    """
    从'模数'列原始文本中提取物理模具套数。

    接受格式：1套 / 8.0 / 3 / 三套 / 三 / 12
    返回 int（最小为 1）。
    """
    if not raw:
        return 1
    raw = str(raw).strip()
    # 阿拉伯数字（含小数点）
    m = re.search(r'(\d+(?:\.\d+)?)', raw)
    if m:
        try:
            val = int(float(m.group(1)))
            return max(1, val)
        except ValueError:
            pass
    # 中文数字
    val = _cn_to_int(raw.rstrip('套件条条'))
    if val and val >= 1:
        return val
    return 1


# ---------------------------------------------------------------------------
# 业务函数
# ---------------------------------------------------------------------------

def create_sample_task(
        part_id: int,
        user_id: int,
        quote_id: int | None = None,
        sample_type: str = 'FIRST_SAMPLE',
        sample_fee: float = 0,
        remarks: str = '') -> dict:
    """
    创建打样 / PPAP 任务记录。

    V3.2 §2.4 样件物流与反馈：打样任务贯穿从首件到 PPAP 定型的全流程。

    参数
    ----
    part_id       : 零件 ID（必填）
    user_id       : 创建人 ID
    quote_id      : 采用的报价单 ID（可空）
    sample_type   : FIRST_SAMPLE | REPAIR_SAMPLE | PPAP | PILOT_SAMPLE
    sample_fee    : 打样费
    remarks       : 备注

    返回
    ----
    {"code": 0, "message": "...", "data": sample_task_id}
    或 {"code": 1, "message": "错误原因", "data": None}
    """
    valid_types = ('FIRST_SAMPLE', 'REPAIR_SAMPLE', 'PPAP', 'PILOT_SAMPLE')
    if sample_type not in valid_types:
        return {"code": 1,
                "message": f"无效样件类型：{sample_type}，可选值：{valid_types}",
                "data": None}

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sample_tasks
                    (part_id, quote_id, sample_type, sample_fee, remarks,
                     task_status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'IN_PROGRESS', NOW(), NOW())
                RETURNING id;
            """, (part_id, quote_id, sample_type, sample_fee, remarks))
            task_id = cur.fetchone()[0]
            conn.commit()
    return {
        "code": 0,
        "message": f"打样任务 #{task_id} 创建成功",
            "data": {"task_id": task_id, "task_status": "IN_PROGRESS"}
    }


def get_sample_task_by_id(task_id: int) -> dict | None:
    """
    查询打样任务详情（含三方签到状态）。

    返回 dict（含 keys: id, part_id, quote_id, sample_type, sample_fee,
    task_status, tech_sign_by, tech_sign_at, qa_sign_by, qa_sign_at,
    sales_sign_by, sales_sign_at, mass_prod_activated_by/at,
    related_mold_id, remarks, created_at）。
    未找到则返回 None。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    t.id, t.part_id, t.quote_id, t.sample_type,
                    t.sample_fee, t.proof_file_path,
                    t.tech_sign_by, t.tech_sign_at,
                    t.qa_sign_by,   t.qa_sign_at,
                    t.sales_sign_by,t.sales_sign_at,
                    t.task_status,
                    t.mass_prod_activated_by, t.mass_prod_activated_at,
                    t.related_mold_id, t.remarks,
                    t.created_at, t.updated_at,
                    p.part_number,
                    q.quote_serial
                FROM sample_tasks t
                LEFT JOIN parts  p ON p.id = t.part_id
                LEFT JOIN quotes q ON q.id = t.quote_id
                WHERE t.id = %s;
            """, (task_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def signoff_sample_task(task_id: int, dept_role: str, user_id: int) -> dict:
    """
    三方会签：技术 / 质量 / 业务部门签到。

    V3.2 §2.4：技术部到场扫码确认，样件状态分派。

    参数
    ----
    task_id    : 打样任务 ID
    dept_role  : 签到部门角色（tech | qa | sales）
    user_id    : 签到操作人 ID

    行为
    ----
    根据 dept_role 更新对应字段：
      tech  → tech_sign_by / tech_sign_at
      qa    → qa_sign_by / qa_sign_at
      sales → sales_sign_by / sales_sign_at

    若该部门已签到（pass_by 非空），本次为重复签到（幂等，不报错）。

    返回
    ----
    {"code": 0, "message": "...", "data": {"task_id": ..., "task_status": ...}}
    """
    role_map = {
        'tech':   ('tech_sign_by',   'tech_sign_at'),
        'qa':     ('qa_sign_by',     'qa_sign_at'),
        'sales':  ('sales_sign_by',   'sales_sign_at'),
    }
    if dept_role not in role_map:
        return {"code": 1,
                "message": f"无效部门角色：{dept_role}，可选值：{list(role_map.keys())}",
                "data": None}

    col_by, col_at = role_map[dept_role]

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 检查任务是否存在
            cur.execute(
                f"SELECT id, task_status, {col_by} FROM sample_tasks WHERE id = %s;",
                (task_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return {"code": 1, "message": f"打样任务 #{task_id} 不存在", "data": None}

            # 执行签到（已签到则幂等覆盖）
            cur.execute(f"""
                UPDATE sample_tasks
                SET {col_by} = %s, {col_at} = NOW(), updated_at = NOW()
                WHERE id = %s
                RETURNING id, task_status,
                          tech_sign_by, tech_sign_at,
                          qa_sign_by,   qa_sign_at,
                          sales_sign_by, sales_sign_at;
            """, (user_id, task_id))

            result = cur.fetchone()
            task_status = result[1]
            tech_signed   = result[2] is not None
            qa_signed    = result[4] is not None
            sales_signed = result[6] is not None
            all_signed   = tech_signed and qa_signed and sales_signed

            # 自动将任务状态升级为 COMPLETED（三方全部签到时）
            if all_signed and task_status == 'IN_PROGRESS':
                cur.execute("""
                    UPDATE sample_tasks
                    SET task_status = 'COMPLETED', updated_at = NOW()
                    WHERE id = %s;
                """, (task_id,))
                task_status = 'COMPLETED'

            conn.commit()

    return {
        "code": 0,
        "message": f"[{dept_role.upper()}] 签到成功",
        "data": {
            "task_id":         task_id,
            "task_status":     task_status,
            "tech_signed":     tech_signed,
            "qa_signed":      qa_signed,
            "sales_signed":    sales_signed,
            "all_signed":      all_signed,
        }
    }


def activate_mass_production(task_id: int, part_id: int, user_id: int) -> dict:
    """
    转量产激活：将零件状态推进至 MASS_PRODUCTION。

    V3.2 §2.4 样件物流与反馈 + §2.1 定点流程：
    必须三方（tech / qa / sales）全部签到方可解锁量产。

    前置校验
    --------
    1. task_id 对应记录存在
    2. 该任务 task_status 为 COMPLETED（已三方签到）
    3. parts 表中该零件当前状态允许流转
       （DRAFT → SAMPLING → MASS_PRODUCTION 链路）

    写入操作
    --------
    - UPDATE parts SET part_status = 'MASS_PRODUCTION'
    - UPDATE sample_tasks SET mass_prod_activated_by/at
    - 记录 actual_date = 业务发生日期（本次用 NOW()）

    返回
    ----
    {"code": 0, "message": "...", "data": {...}}
    {"code": 1, "message": "三方未全部确认，无法转量产", "data": None}
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 查询打样任务（三方签到情况）
            cur.execute("""
                SELECT id, part_id, task_status,
                       tech_sign_by, qa_sign_by, sales_sign_by,
                       mass_prod_activated_at
                FROM sample_tasks WHERE id = %s;
            """, (task_id,))
            task = cur.fetchone()

            if not task:
                conn.rollback()
                return {"code": 1, "message": f"打样任务 #{task_id} 不存在", "data": None}

            (t_id, t_part_id, t_status,
             tech_sb, qa_sb, sales_sb, mp_at) = task

            # 前置校验1：task_status 必须为 COMPLETED
            if t_status != 'COMPLETED':
                conn.rollback()
                return {
                    "code": 1,
                    "message": f"任务状态为 {t_status}，必须先完成三方签到（COMPLETED）才能转量产",
                    "data": None
                }

            # 前置校验2：三方全部确认（双重保险）
            if not (tech_sb and qa_sb and sales_sb):
                conn.rollback()
                return {
                    "code": 1,
                    "message": "三方未全部确认，无法转量产。技术/质量/业务签到记录缺失",
                    "data": None
                }

            # 前置校验3：parts 表中该零件当前状态
            cur.execute(
                "SELECT id, part_status FROM parts WHERE id = %s;",
                (part_id,))
            part = cur.fetchone()
            if not part:
                conn.rollback()
                return {"code": 1, "message": f"零件 #{part_id} 不存在", "data": None}

            old_status = part[1]
            # 允许流转状态：当前状态必须是 DRAFT / SAMPLING
            allowed = ('DRAFT', 'SAMPLING')
            if old_status not in allowed:
                conn.rollback()
                return {
                    "code": 1,
                    "message": f"零件当前状态为 {old_status}，仅 {allowed} 可流转至 MASS_PRODUCTION",
                    "data": None
                }

            # 前置校验4：防重复激活
            if mp_at is not None:
                conn.rollback()
                return {
                    "code": 1,
                    "message": f"零件 #{part_id} 已于 {mp_at} 转量产，禁止重复激活",
                    "data": None
                }

            # 执行转量产写入（两步原子提交）
            cur.execute("""
                UPDATE parts
                SET part_status = 'MASS_PRODUCTION',
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, part_status;
            """, (part_id,))
            part_after = cur.fetchone()

            cur.execute("""
                UPDATE sample_tasks
                SET mass_prod_activated_by = %s,
                    mass_prod_activated_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s;
            """, (user_id, task_id))

            conn.commit()

    return {
        "code": 0,
        "message": f"零件 #{part_id} 已成功转入 MASS_PRODUCTION",
        "data": {
            "part_id":        part_after[0],
            "old_status":     old_status,
            "new_status":     part_after[1],
            "task_id":       task_id,
            "activated_by":   user_id,
            "activated_at":   datetime.datetime.now().isoformat(),
        }
    }


# ---------------------------------------------------------------------------
# 历史 Excel 智能导入（dies 表）
# ---------------------------------------------------------------------------

def import_legacy_molds_from_csv(
        file_bytes: bytes,
        created_by_user_id: int | None = None
) -> dict:
    """
    解析历史 CSV，按列名映射字段，批量 Upsert 至 dies 表。

    CSV 列名规范
    -------------
    必须包含（其一即可）：
      - 本厂产品编号  → mold_number（唯一键，空行跳过）
      - 模具类型      → mold_type
      - 模数          → mold_set_count（正则提取数字）
      - 参考冲床吨位  → press_tonnage
      - 备注          → remarks（含 cavity_count 提取源）
      - 用料规格 (T*W*PH) → spec_text（含 cavity_count 提取源）

    cavity_count 提取（正则优先级）
    ------------------------------
    1. "1出2" / "一出二" / "出二" → 2
    2. 所有中文数字均通过 CN_DIGIT_MAP / _cn_to_int 映射
    3. 未匹配到任何数字 → 默认 1

    part_id 翻译
    ------------
    读取所有 mold_number，批量查询 parts 表。
    未匹配到零件号 → part_id = NULL（不阻断）

    写入策略
    --------
    使用 psycopg2.extras.execute_batch 进行批量 Upsert：

      INSERT INTO dies (mold_number, part_id, mold_type, mold_set_count,
                         cavity_count, press_tonnage, remarks,
                         lifecycle_status, created_at, updated_at)
      VALUES (...)
      ON CONFLICT (mold_number)
      DO UPDATE SET
          part_id       = EXCLUDED.part_id,
          mold_type     = EXCLUDED.mold_type,
          mold_set_count= EXCLUDED.mold_set_count,
          cavity_count  = EXCLUDED.cavity_count,
          press_tonnage = EXCLUDED.press_tonnage,
          remarks       = EXCLUDED.remarks,
          updated_at    = NOW()
      -- 注意：lifecycle_status 使用原值，不被 Excel 覆盖

    参数
    ----
    file_bytes          : CSV 文件字节流（request.file.read()）
    created_by_user_id  : 创建人（预留，当前未写入）

    返回
    ----
    {
        "code": 0,
        "message": "导入完成",
        "data": {
            "total_rows":     导入总行数（含跳过）,
            "inserted":       新增行数,
            "updated":        更新行数,
            "skipped":        跳过行数（无 mold_number）,
            "part_not_found": mold_number 在 parts 表未找到的列表,
            "errors":         解析错误列表,
        }
    }
    """
    import re as _re
    import io as _io
    import pandas as _pd
    from psycopg2.extras import execute_batch

    result = {
        "total_rows":     0,
        "inserted":       0,
        "updated":        0,
        "skipped":        0,
        "part_not_found": [],
        "errors":         [],
    }

    # ── 1. 解析 CSV ─────────────────────────────────────────────────
    try:
        df = _pd.read_csv(
            _io.BytesIO(file_bytes),
            encoding='utf-8-sig',      # 带 BOM 的 UTF-8
            skip_blank_lines=True,
            dtype=str,                  # 全局 str，避免类型推断出错
        )
        df = df.dropna(how='all').reset_index(drop=True)
    except Exception as e:
        return {"code": 1,
                "message": f"CSV 解析失败：{e}",
                "data": None}

    if df.empty:
        return {"code": 1, "message": "CSV 文件为空或无有效数据", "data": None}

    result["total_rows"] = len(df)

    # ── 2. 列名容错映射 ─────────────────────────────────────────────
    # 支持多种常见列名变体
    COL_ALIASES = {
        '本厂产品编号':   'mold_number',
        '模具编号':       'mold_number',
        '模具号':         'mold_number',
        '产品编号':       'mold_number',
        '模具类型':       'mold_type',
        '模数':           'mold_set_count',
        '参考冲床吨位':   'press_tonnage',
        '备注':           'remarks',
        '用料规格 (T*W*PH)': 'spec_text',
        '用料规格':        'spec_text',
    }

    def _normalize_col(name: str) -> str:
        return COL_ALIASES.get(str(name).strip(), str(name).strip())

    df.columns = [_normalize_col(c) for c in df.columns]

    # ── 3. 逐行提取并清洗字段 ──────────────────────────────────────
    cleaned_rows = []
    mold_numbers_for_lookup = []

    for idx, row in df.iterrows():
        raw_number = str(row.get('mold_number', '')).strip()
        if not raw_number or raw_number.lower() in ('nan', 'none', ''):
            result["skipped"] += 1
            continue

        mold_number = raw_number
        mold_numbers_for_lookup.append(mold_number)

        raw_type    = str(row.get('mold_type',     '')).strip()
        raw_set     = str(row.get('mold_set_count', '')).strip()
        raw_ton     = str(row.get('press_tonnage',  '')).strip()
        raw_remarks = str(row.get('remarks',        '')).strip()
        raw_spec    = str(row.get('spec_text',       '')).strip()

        mold_type    = raw_type    if raw_type    not in ('nan', '') else None
        press_ton    = raw_ton     if raw_ton     not in ('nan', '') else None
        set_count    = extract_mold_set_count(raw_set)
        cav_count    = extract_cavity_count(raw_remarks, raw_spec)
        remarks_text = raw_remarks if raw_remarks not in ('nan', '') else None

        cleaned_rows.append({
            'mold_number':    mold_number,
            'mold_type':      mold_type,
            'mold_set_count': set_count,
            'cavity_count':   cav_count,
            'press_tonnage':  press_ton,
            'remarks':        remarks_text,
        })

    if not cleaned_rows:
        return {
            "code": 0,
            "message": "无有效数据行（mold_number 全部为空）",
            "data": result
        }

    # ── 4. 批量查询 parts 表，翻译 mold_number → part_id ───────────
    mold_to_part: dict[str, int | None] = {}

    if mold_numbers_for_lookup:
        placeholders = ','.join(['%s'] * len(mold_numbers_for_lookup))
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT part_number, id FROM parts WHERE part_number = ANY(ARRAY[{placeholders}]::text[]);",
                    (mold_numbers_for_lookup,)
                )
                for pn, pid in cur.fetchall():
                    mold_to_part[pn] = pid

        # 记录未匹配项
        for mn in mold_numbers_for_lookup:
            if mn not in mold_to_part:
                mold_to_part[mn] = None
                result["part_not_found"].append(mn)

    # ── 5. 批量 Upsert（白名单字段，不碰 lifecycle_status）──────────
    sql = f"""
        INSERT INTO dies (
            mold_number, part_id, mold_type, mold_set_count,
            cavity_count, press_tonnage, remarks,
            lifecycle_status, created_at, updated_at
        ) VALUES (
            %(mold_number)s,
            %(part_id)s,
            %(mold_type)s,
            %(mold_set_count)s,
            %(cavity_count)s,
            %(press_tonnage)s,
            %(remarks)s,
            'AVAILABLE',
            NOW(),
            NOW()
        )
        ON CONFLICT (mold_number)
        DO UPDATE SET
            part_id       = EXCLUDED.part_id,
            mold_type     = EXCLUDED.mold_type,
            mold_set_count= EXCLUDED.mold_set_count,
            cavity_count  = EXCLUDED.cavity_count,
            press_tonnage = EXCLUDED.press_tonnage,
            remarks       = EXCLUDED.remarks,
            updated_at    = NOW()
        -- lifecycle_status 使用原值，不被 Excel 覆盖
    """

    batch = []
    for row in cleaned_rows:
        batch.append({
            'mold_number':    row['mold_number'],
            'part_id':        mold_to_part.get(row['mold_number']),
            'mold_type':      row['mold_type'],
            'mold_set_count': row['mold_set_count'],
            'cavity_count':   row['cavity_count'],
            'press_tonnage':  row['press_tonnage'],
            'remarks':        row['remarks'],
        })

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # execute_batch 分批提交（每 500 行一批，防止事务过大）
            BATCH_SIZE = 500
            for i in range(0, len(batch), BATCH_SIZE):
                chunk = batch[i:i + BATCH_SIZE]
                execute_batch(cur, sql, chunk, page_size=BATCH_SIZE)
            conn.commit()

    # 统计导入前已存在的 mold_number 数量（用于事后计算 inserted vs updated）
    mns = [r['mold_number'] for r in cleaned_rows]
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if mns:
                ph = ','.join(['%s'] * len(mns))
                cur.execute(
                    f"SELECT COUNT(*) FROM dies WHERE mold_number = ANY(ARRAY[{ph}]::text[]);",
                    (mns,))
                count_before = cur.fetchone()[0]
            else:
                count_before = 0

    sql = f"""
        INSERT INTO dies (
            mold_number, part_id, mold_type, mold_set_count,
            cavity_count, press_tonnage, remarks,
            lifecycle_status, created_at, updated_at
        ) VALUES (
            %(mold_number)s, %(part_id)s, %(mold_type)s, %(mold_set_count)s,
            %(cavity_count)s, %(press_tonnage)s, %(remarks)s,
            'AVAILABLE', NOW(), NOW()
        )
        ON CONFLICT (mold_number)
        DO UPDATE SET
            part_id        = EXCLUDED.part_id,
            mold_type      = EXCLUDED.mold_type,
            mold_set_count = EXCLUDED.mold_set_count,
            cavity_count   = EXCLUDED.cavity_count,
            press_tonnage  = EXCLUDED.press_tonnage,
            remarks        = EXCLUDED.remarks,
            updated_at     = NOW()
    """

    batch = []
    for row in cleaned_rows:
        batch.append({
            'mold_number':    row['mold_number'],
            'part_id':        mold_to_part.get(row['mold_number']),
            'mold_type':      row['mold_type'],
            'mold_set_count': row['mold_set_count'],
            'cavity_count':   row['cavity_count'],
            'press_tonnage':  row['press_tonnage'],
            'remarks':        row['remarks'],
        })

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            for i in range(0, len(batch), 500):
                execute_batch(cur, sql, batch[i:i + 500], page_size=500)
            conn.commit()

    # 导入后统计（精确计算 inserted / updated）
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            if mns:
                ph = ','.join(['%s'] * len(mns))
                cur.execute(
                    f"SELECT COUNT(*) FROM dies WHERE mold_number = ANY(ARRAY[{ph}]::text[]);",
                    (mns,))
                count_after = cur.fetchone()[0]
            else:
                count_after = 0

    result["updated"]  = count_before
    result["inserted"] = count_after - count_before

    return {
        "code": 0,
        "message": f"导入完成，共处理 {result['total_rows']} 行",
        "data": result
    }


# ============================================================================
# 阶段五：原料入库与物联赋码  (v5_material_qr_tracking)
# ============================================================================


# ---------------------------------------------------------------------------
# 工具：QR UID 生成（格式 MAT-YYMM-NNN）
# ---------------------------------------------------------------------------

def _generate_qr_uid(material_category: str = 'PROD') -> str:
    """
    生成唯一二维码 UID，格式：MAT-YYMM-NNN
    NNN 段取当天该类别最大序号 +1（不足三位左补零）。

    例：第二只钢带入库 → MAT-2605-002
    """
    import datetime as _dt
    prefix = f"MAT-{_dt.datetime.now().strftime('%y%m')}-"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(
                    (SELECT MAX((regexp_match(qr_uid, %s))[1]::INTEGER)
                     FROM material_batches
                     WHERE qr_uid LIKE %s), 0)
            """, (r'\d{3}$', f'{prefix}%'))
            max_seq = cur.fetchone()[0]
    seq = max_seq + 1
    return f"{prefix}{seq:03d}"


def _generate_qr_uid_v2() -> str:
    """
    生成唯一二维码 UID（无类别前缀变体，始终为 MAT-YYMM-NNN）。
    """
    import datetime as _dt
    prefix = f"MAT-{_dt.datetime.now().strftime('%y%m')}-"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(
                    (SELECT MAX((regexp_match(qr_uid, %s))[1]::INTEGER)
                     FROM material_batches
                     WHERE qr_uid LIKE %s), 0)
            """, (r'\d{3}$', f'{prefix}%'))
            max_seq = cur.fetchone()[0]
    seq = max_seq + 1
    return f"{prefix}{seq:03d}"


# ---------------------------------------------------------------------------
# 业务函数
# ---------------------------------------------------------------------------

def receive_material(
        material_category: str,
        material_name: str,
        initial_weight: float,
        user_id: int,
        spec: str | None = None,
        supplier_name: str | None = None,
        heat_number: str | None = None,
        cert_file_path: str | None = None,
        purchase_unit_price: float | None = None,
        unit: str = 'kg',
) -> dict:
    """
    执行原料入库（扫码入库）。

    极简入库原则：
    - 入库即 IN_STOCK，无需品质二次放行
    - 不强制录入炉批号（heat_number 可 NULL）
    - 不强制录入采购单价（purchase_unit_price 可 NULL）
    - 自动生成 QR UID（MAT-YYMM-NNN）
    - 同步 INSERT 一条 RECEIVE 流水

    参数
    ----
    material_category : PROD | AUX
    material_name    : 物料名称（必填）
    initial_weight   : 入库重量（必填，单位 kg 或 unit）
    user_id          : 入库操作人
    spec             : 规格描述
    supplier_name    : 供应商名称
    heat_number      : 炉批号（非强制）
    cert_file_path   : 质保单附件路径（非强制）
    purchase_unit_price : 采购单价（非强制）
    unit             : 计量单位（主材默认 kg，辅料可传桶/升/个）

    返回
    ----
    {"code": 0, "message": "...", "data": {"qr_uid": "...", "lifecycle_status": "IN_STOCK"}}
    """
    valid_cats = ('PROD', 'AUX')
    if material_category not in valid_cats:
        return {"code": 1,
                "message": f"无效类别：{material_category}，可选：{valid_cats}",
                "data": None}
    if initial_weight <= 0:
        return {"code": 1,
                "message": f"入库重量必须 > 0，当前：{initial_weight}",
                "data": None}

    qr_uid = _generate_qr_uid_v2()
    status = 'IN_STOCK'

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 写入批次主记录
            cur.execute("""
                INSERT INTO material_batches (
                    qr_uid, material_category, material_name, spec,
                    supplier_name, heat_number, cert_file_path,
                    purchase_unit_price, initial_weight, current_weight,
                    lifecycle_status, unit, created_by, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                );
            """, (
                qr_uid, material_category, material_name, spec,
                supplier_name, heat_number, cert_file_path,
                purchase_unit_price, initial_weight, initial_weight,
                status, unit, user_id,
            ))
            # 写入 RECEIVE 流水（入库变化量为正）
            cur.execute("""
                INSERT INTO material_transactions (
                    qr_uid, transaction_type, weight_change,
                    current_balance, operator_id, created_at
                ) VALUES (%s, 'RECEIVE', %s, %s, %s, NOW());
            """, (qr_uid, initial_weight, initial_weight, user_id))
            conn.commit()

    return {
        "code": 0,
        "message": f"原料 #{qr_uid} 入库成功，状态 IN_STOCK",
        "data": {
            "qr_uid":           qr_uid,
            "material_category": material_category,
            "material_name":    material_name,
            "initial_weight":   initial_weight,
            "current_weight":   initial_weight,
            "lifecycle_status": status,
            "unit":             unit,
        }
    }


def slit_mother_coil(
        mother_qr_uid: str,
        slit_items: list[dict],
        user_id: int,
) -> dict:
    """
    大卷分条为小卷（母子裂变溯源）。

    参数
    ----
    mother_qr_uid : 母卷二维码 UID
    slit_items    : 子卷列表，每项结构：
                    {"weight": float, "material_name": str | None,
                     "spec": str | None, "unit": str | None}
                    weight 为必填，子卷重量总和不能超过母卷 current_weight
    user_id       : 分条操作人

    行为（原子事务）
    1. 锁定母卷（SELECT FOR UPDATE），校验 current_weight >= sum(slit_weights)
    2. 遍历生成子卷 QR UID（继承母卷 metadata，weight 和 unit 各自独立）
    3. UPDATE 母卷 current_weight（扣减分条总重），记录一条 SLIT 流水（负数）
    4. 若母卷 current_weight 扣减至 <= 0，自动置 DEPLETED

    返回
    ----
    {"code": 0, "message": "...", "data": {"mother": {...}, "children": [...]}}
    {"code": 1, "message": "错误原因", "data": None}
    """
    if not slit_items:
        return {"code": 1, "message": "子卷列表为空", "data": None}

    total_slit_weight = sum(float(item.get('weight', 0)) for item in slit_items)
    if total_slit_weight <= 0:
        return {"code": 1, "message": "子卷重量总和必须 > 0", "data": None}

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 锁定母卷（FOR UPDATE 防并发分条超扣）
            cur.execute("""
                SELECT qr_uid, material_name, spec, material_category,
                       current_weight, lifecycle_status, unit
                FROM material_batches
                WHERE qr_uid = %s
                FOR UPDATE;
            """, (mother_qr_uid,))
            mother = cur.fetchone()

            if not mother:
                conn.rollback()
                return {"code": 1,
                        "message": f"母卷 #{mother_qr_uid} 不存在",
                        "data": None}

            (m_qr, m_name, m_spec, m_cat,
             m_curr, m_status, m_unit) = mother

            if m_curr < total_slit_weight:
                conn.rollback()
                return {
                    "code": 1,
                    "message": f"母卷当前余量 {m_curr} kg 不足以分条（需求 {total_slit_weight} kg）",
                    "data": None
                }

            # 生成子卷并写入
            child_records = []
            for item in slit_items:
                child_qr = _generate_qr_uid_v2()
                child_weight = float(item.get('weight', 0))
                child_name = item.get('material_name') or m_name
                child_spec = item.get('spec') or m_spec
                child_unit = item.get('unit') or m_unit

                cur.execute("""
                    INSERT INTO material_batches (
                        qr_uid, parent_qr_uid, material_category,
                        material_name, spec, initial_weight, current_weight,
                        lifecycle_status, unit, created_by, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'IN_STOCK', %s, %s, NOW(), NOW());
                """, (
                    child_qr, mother_qr_uid, m_cat,
                    child_name, child_spec, child_weight, child_weight,
                    child_unit, user_id,
                ))
                child_records.append({
                    "qr_uid":           child_qr,
                    "material_name":    child_name,
                    "spec":             child_spec,
                    "initial_weight":   child_weight,
                    "current_weight":   child_weight,
                    "lifecycle_status": 'IN_STOCK',
                    "unit":             child_unit,
                    "parent_qr_uid":    mother_qr_uid,
                })

            # 更新母卷 current_weight
            new_mother_weight = round(m_curr - total_slit_weight, 4)
            new_mother_status = 'DEPLETED' if new_mother_weight <= 0 else m_status
            cur.execute("""
                UPDATE material_batches
                SET current_weight = %s,
                    lifecycle_status = %s,
                    updated_at = NOW()
                WHERE qr_uid = %s;
            """, (new_mother_weight, new_mother_status, mother_qr_uid))

            # 记录母卷 SLIT 流水（weight_change 为负数）
            cur.execute("""
                INSERT INTO material_transactions (
                    qr_uid, transaction_type, weight_change,
                    current_balance, operator_id, created_at
                ) VALUES (%s, 'SLIT', %s, %s, %s, NOW());
            """, (mother_qr_uid, -total_slit_weight, new_mother_weight, user_id))

            conn.commit()

    return {
        "code": 0,
        "message": f"母卷 #{mother_qr_uid} 分条完成，生成 {len(child_records)} 只子卷",
        "data": {
            "mother": {
                "qr_uid":           mother_qr_uid,
                "current_weight":   new_mother_weight,
                "lifecycle_status": new_mother_status,
            },
            "children": child_records,
        }
    }


def consume_aux_material(
        qr_uid: str,
        consume_qty: float,
        user_id: int,
        related_work_order_id: int | None = None,
) -> dict:
    """
    辅料快捷领用/消耗。

    仅允许 material_category == 'AUX' 的批次调用。
    余料退库不换码，领用即消耗。

    参数
    ----
    qr_uid               : 辅料批次二维码 UID
    consume_qty          : 领用数量（按 unit 计量）
    user_id              : 操作人
    related_work_order_id: 关联工单 ID（非强制）

    行为
    ----
    1. SELECT 锁定批次，校验 material_category == 'AUX'
    2. 校验 current_weight >= consume_qty
    3. UPDATE 扣减 current_weight，若扣减后 <= 0 → lifecycle_status = 'DEPLETED'
    4. INSERT 一条 CONSUME 流水

    返回
    ----
    {"code": 0, "message": "...", "data": {"qr_uid": ..., "consumed": ..., "remaining": ...}}
    """
    if consume_qty <= 0:
        return {"code": 1,
                "message": f"领用数量必须 > 0，当前：{consume_qty}",
                "data": None}

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 锁定批次
            cur.execute("""
                SELECT qr_uid, material_category, current_weight, lifecycle_status, unit
                FROM material_batches
                WHERE qr_uid = %s
                FOR UPDATE;
            """, (qr_uid,))
            batch = cur.fetchone()

            if not batch:
                conn.rollback()
                return {"code": 1, "message": f"批次 #{qr_uid} 不存在", "data": None}

            (b_qr, b_cat, b_curr, b_status, b_unit) = batch

            # 业务校验：仅 AUX 允许此函数
            if b_cat != 'AUX':
                conn.rollback()
                return {
                    "code": 1,
                    "message": f"此函数仅限辅料（AUX）调用，批次 #{qr_uid} 类别为 {b_cat}（PROD 主材请通过 slit 或报工消耗）",
                    "data": None
                }

            # 库存校验
            if b_curr < consume_qty:
                conn.rollback()
                return {
                    "code": 1,
                    "message": f"库存不足：当前余量 {b_curr} {b_unit}，需求 {consume_qty} {b_unit}",
                    "data": None
                }

            # 扣减余量
            new_weight = round(b_curr - consume_qty, 4)
            new_status = 'DEPLETED' if new_weight <= 0 else b_status

            cur.execute("""
                UPDATE material_batches
                SET current_weight = %s,
                    lifecycle_status = %s,
                    updated_at = NOW()
                WHERE qr_uid = %s;
            """, (new_weight, new_status, qr_uid))

            # 记录 CONSUME 流水
            cur.execute("""
                INSERT INTO material_transactions (
                    qr_uid, transaction_type, weight_change,
                    current_balance, related_work_order_id, operator_id, created_at
                ) VALUES (%s, 'CONSUME', %s, %s, %s, %s, NOW());
            """, (qr_uid, -consume_qty, new_weight, related_work_order_id, user_id))
            conn.commit()

    return {
        "code": 0,
        "message": f"辅料 #{qr_uid} 领用成功",
        "data": {
            "qr_uid":           qr_uid,
            "material_category": 'AUX',
            "consumed":         consume_qty,
            "remaining":         new_weight,
            "unit":             b_unit,
            "lifecycle_status": new_status,
        }
    }


def get_material_batch(qr_uid: str) -> dict | None:
    """
    查询单个原料批次详情（含流水链摘要）。

    返回 dict（含 keys: qr_uid, material_category, material_name, spec,
    supplier_name, heat_number, initial_weight, current_weight,
    lifecycle_status, unit, created_at, transaction_count）。
    未找到则返回 None。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    mb.qr_uid, mb.parent_qr_uid, mb.material_category,
                    mb.material_name, mb.spec, mb.supplier_name,
                    mb.heat_number, mb.cert_file_path,
                    mb.purchase_unit_price,
                    mb.initial_weight, mb.current_weight,
                    mb.lifecycle_status, mb.unit,
                    mb.created_by, mb.created_at, mb.updated_at,
                    mb.lifecycle_status,
                    (SELECT COUNT(*) FROM material_transactions mt
                     WHERE mt.qr_uid = mb.qr_uid) AS transaction_count
                FROM material_batches mb
                WHERE mb.qr_uid = %s;
            """, (qr_uid,))
            row = cur.fetchone()
            return dict(row) if row else None


def list_material_batches(
        material_category: str | None = None,
        lifecycle_status: str | None = None,
        keyword: str = '',
        limit: int = 50,
        offset: int = 0,
) -> list[dict]:
    """
    分页查询原料批次列表（支持按类别/状态/关键字过滤）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = ["1=1"]
            params = []
            if material_category:
                conditions.append("mb.material_category = %s")
                params.append(material_category)
            if lifecycle_status:
                conditions.append("mb.lifecycle_status = %s")
                params.append(lifecycle_status)
            if keyword:
                conditions.append("(mb.material_name ILIKE %s OR mb.qr_uid ILIKE %s)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            where_clause = " AND ".join(conditions)
            cur.execute(f"""
                SELECT
                    mb.qr_uid, mb.parent_qr_uid, mb.material_category,
                    mb.material_name, mb.spec, mb.supplier_name,
                    mb.initial_weight, mb.current_weight,
                    mb.lifecycle_status, mb.unit,
                    mb.created_at, mb.lifecycle_status
                FROM material_batches mb
                WHERE {where_clause}
                ORDER BY mb.created_at DESC
                LIMIT %s OFFSET %s;
            """, (*params, limit, offset))
            return [dict(r) for r in cur.fetchall()]


# ============================================================================
# 阶段四 & 五：车间执行 (equipments / work_orders / sf_production_logs)
#             双轨维修 (maintenance_logs)
#             发货与 QA   (delivery_notes / delivery_items / part_customer_aliases)
# ============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# A. 机台设备台账 (equipments)
# ─────────────────────────────────────────────────────────────────────────────

def get_all_equipments():
    """返回所有机台，带当前关联的工单信息及维修熔断状态。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    e.id, e.equipment_code, e.equipment_name,
                    e.tonnage, e.current_status, e.created_at,
                    wo.id          AS active_wo_id,
                    wo.order_no    AS active_wo_no,
                    wo.part_id     AS wo_part_id,
                    pt.part_number AS wo_part_number,
                    pt.internal_name AS wo_part_name,
                    wo.target_qty  AS wo_target_qty,
                    wo.produced_qty AS wo_produced_qty,
                    wo.order_status AS wo_status,
                    wo.is_first_piece_required,
                    wo.first_piece_passed_at IS NOT NULL AS fp_passed,
                    mo.id          AS active_mold_id,
                    mo.mold_number AS active_mold_number,
                    u.real_name    AS current_operator_name,
                    ml.id          AS open_maintenance_id,
                    ml.repair_mode AS maintenance_mode,
                    ml.status       AS maintenance_status
                FROM equipments e
                LEFT JOIN work_orders wo
                    ON wo.equipment_id = e.id
                    AND wo.order_status IN ('SCHEDULED', 'RUNNING')
                LEFT JOIN parts pt ON wo.part_id = pt.id
                LEFT JOIN dies  mo ON wo.die_id = mo.id
                LEFT JOIN users  u  ON e.current_operator_id = u.id
                LEFT JOIN LATERAL (
                    SELECT id, repair_mode, status
                    FROM maintenance_logs
                    WHERE equipment_id = e.id
                      AND status = 'REPAIRING'
                    ORDER BY start_time DESC
                    LIMIT 1
                ) ml ON true
                ORDER BY e.equipment_code;
            """)
            return [dict(r) for r in cur.fetchall()]


def get_equipment_by_id(equipment_id: int) -> dict | None:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM equipments WHERE id = %s;", (equipment_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_equipment_by_code(code: str):
    """按 equipment_code 精确查找机台（用于扫码）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM equipments WHERE equipment_code = %s;",
                (code.strip(),)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_equipment(equipment_code: str, equipment_name: str = "",
                      tonnage: str = "") -> dict:
    """
    新增机台台账。
    equipment_code 重复则抛出 ValueError。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM equipments WHERE equipment_code = %s;",
                (equipment_code,)
            )
            if cur.fetchone():
                raise ValueError(f"机台编号 {equipment_code} 已存在")

            cur.execute("""
                INSERT INTO equipments (equipment_code, equipment_name, tonnage)
                VALUES (%s, %s, %s)
                RETURNING *;
            """, (equipment_code, equipment_name, tonnage))
            conn.commit()
            row = cur.fetchone()
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))


def update_equipment(equipment_id: int, **kwargs) -> None:
    """按字段更新机台，不传参数则跳过。严禁直接 UPDATE status。"""
    valid = {"equipment_name", "tonnage", "current_status",
             "current_operator_id"}
    fields = {k: v for k, v in kwargs.items() if k in valid and v is not None}
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields)
    vals = list(fields.values()) + [equipment_id]
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE equipments SET {sets} WHERE id = %s;", vals)
            conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# B. 机台状态熔断（通过状态机，禁止裸 UPDATE status）
# ─────────────────────────────────────────────────────────────────────────────

class EquipmentState(str):
    IDLE                 = "IDLE"
    RUNNING             = "RUNNING"
    EQUIP_REPAIR        = "EQUIP_REPAIR"
    MOLD_REPAIR_ON_MACHINE = "MOLD_REPAIR_ON_MACHINE"


def equipment_change_status(equipment_id: int, new_status: str,
                            actor: str = "system") -> dict:
    """
    状态熔断核心函数（替代裸 UPDATE）。

    合法的状态跳转：
      IDLE → RUNNING              (排产上线)
      RUNNING → EQUIP_REPAIR      (报修：设备故障)
      RUNNING → MOLD_REPAIR_ON_MACHINE (报修：不拆模维修)
      EQUIP_REPAIR → RUNNING      (维修完成)
      MOLD_REPAIR_ON_MACHINE → IDLE (拆模释放机台)
      MOLD_REPAIR_ON_MACHINE → RUNNING (不拆模在线修复)
      any → IDLE                  (管理强制重置)

    返回 {"code": 0/1, "message": str, "data": {...}}
    """
    # 读取当前状态
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM equipments WHERE id = %s;",
                (equipment_id,)
            )
            row = cur.fetchone()

    if not row:
        return {"code": 1, "message": f"机台 #{equipment_id} 不存在", "data": None}

    old_status = row["current_status"]
    now = datetime.datetime.now()

    # 状态跳转规则矩阵
    allowed: dict[tuple, list] = {
        ("IDLE",                  "RUNNING"):               True,
        ("RUNNING",               "EQUIP_REPAIR"):           True,
        ("RUNNING",               "MOLD_REPAIR_ON_MACHINE"): True,
        ("EQUIP_REPAIR",          "RUNNING"):                True,
        ("MOLD_REPAIR_ON_MACHINE","IDLE"):                   True,
        ("MOLD_REPAIR_ON_MACHINE","RUNNING"):                True,
        ("IDLE",                  "IDLE"):                  True,
        ("RUNNING",               "IDLE"):                   True,
        ("EQUIP_REPAIR",          "IDLE"):                   True,
    }

    key = (old_status, new_status)
    if not allowed.get(key):
        return {
            "code": 1,
            "message": f"非法跳转：状态【{old_status}】不能直接变更为【{new_status}】",
            "data": None,
        }

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE equipments
                SET current_status = %s, updated_at = %s
                WHERE id = %s;
            """, (new_status, now, equipment_id))

            # 联动：RUNNING 工单 → PAUSED（熔断时）
            if new_status in ("EQUIP_REPAIR", "MOLD_REPAIR_ON_MACHINE"):
                cur.execute("""
                    UPDATE work_orders
                    SET order_status = 'PAUSED', updated_at = %s
                    WHERE equipment_id = %s
                      AND order_status = 'RUNNING';
                """, (now, equipment_id))

            # 联动：MOLD_REPAIR_ON_MACHINE → IDLE（拆模释放）→ 工单不变，状态机另处理
            conn.commit()

    return {
        "code": 0,
        "message": f"机台状态已变更为【{new_status}】",
        "data": {
            "old_status": old_status,
            "new_status": new_status,
            "equipment_id": equipment_id,
            "actor": actor,
        },
    }


def equipment_check_production_lock(equipment_id: int) -> tuple[bool, str]:
    """
    报工前置校验：检查机台是否处于生产锁定状态。
    返回 (is_locked, status_label)
      is_locked=True  → 禁止报工
      is_locked=False → 可以报工
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_status FROM equipments WHERE id = %s;",
                (equipment_id,)
            )
            row = cur.fetchone()
            if not row:
                return True, "机台不存在"

    locked_states = {
        "EQUIP_REPAIR",
        "MOLD_REPAIR_ON_MACHINE",
    }
    status = row[0]
    if status in locked_states:
        labels = {
            "EQUIP_REPAIR": "设备维修中（熔断锁定）",
            "MOLD_REPAIR_ON_MACHINE": "模具在机维修（熔断锁定）",
        }
        return True, labels.get(status, status)
    return False, status


# ─────────────────────────────────────────────────────────────────────────────
# C. 生产工单 (work_orders)
# ─────────────────────────────────────────────────────────────────────────────

def get_all_work_orders(filters: dict = None) -> list:
    """工单列表，含零件信息及完成率。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cond, params = [], []
            if filters:
                if filters.get("part_id"):
                    cond.append("wo.part_id = %s")
                    params.append(filters["part_id"])
                if filters.get("status"):
                    cond.append("wo.order_status = %s")
                    params.append(filters["status"])
                if filters.get("priority"):
                    cond.append("wo.priority = %s")
                    params.append(filters["priority"])
                if filters.get("equipment_id"):
                    cond.append("wo.equipment_id = %s")
                    params.append(filters["equipment_id"])
            where = ("WHERE " + " AND ".join(cond)) if cond else ""

            cur.execute(f"""
                SELECT
                    wo.id, wo.order_no, wo.part_id,
                    wo.equipment_id, wo.target_qty, wo.produced_qty,
                    wo.priority, wo.order_status,
                    wo.is_first_piece_required,
                    wo.first_piece_passed_at,
                    wo.first_piece_passed_by,
                    wo.die_id,
                    wo.created_at, wo.updated_at,
                    pt.part_number, pt.internal_name,
                    e.equipment_code, e.equipment_name,
                    m.mold_number,
                    u.real_name AS created_by_name,
                    CASE WHEN wo.target_qty > 0
                         THEN ROUND(wo.produced_qty::NUMERIC / wo.target_qty * 100, 1)
                         ELSE 0
                    END AS completion_pct
                FROM work_orders wo
                JOIN parts pt ON wo.part_id = pt.id
                LEFT JOIN equipments e ON wo.equipment_id = e.id
                LEFT JOIN dies m ON wo.die_id = m.id
                LEFT JOIN users u ON wo.created_by = u.id
                {where}
                ORDER BY
                    wo.priority = 'URGENT' DESC,
                    wo.order_status = 'RUNNING' DESC,
                    wo.created_at DESC;
            """, params)
            return [dict(r) for r in cur.fetchall()]


def get_work_order_by_id(wo_id: int) -> dict | None:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT wo.*,
                       pt.part_number, pt.internal_name,
                       e.equipment_code, e.equipment_name,
                       u.real_name AS created_by_name,
                       pu.real_name AS fp_passed_by_name
                FROM work_orders wo
                JOIN parts pt ON wo.part_id = pt.id
                LEFT JOIN equipments e ON wo.equipment_id = e.id
                LEFT JOIN users u ON wo.created_by = u.id
                LEFT JOIN users pu ON wo.first_piece_passed_by = pu.id
                WHERE wo.id = %s;
            """, (wo_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_work_order_by_no(order_no: str) -> dict | None:
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM work_orders WHERE order_no = %s;",
                (order_no.strip(),)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def generate_order_no() -> str:
    """生成工单号 WO-YYMMDD-XXX（当日自增）。"""
    today = datetime.date.today().strftime("%y%m%d")
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(
                    CAST(SUBSTRING(order_no FROM 'WO-[0-9]{6}-([0-9]+)') AS INTEGER)
                ), 0) + 1
                FROM work_orders
                WHERE order_no LIKE %s;
            """, (f"WO-{today}-%",))
            seq = cur.fetchone()[0]
    return f"WO-{today}-{seq:03d}"


def create_work_order(part_id: int, target_qty: int,
                       priority: str = "NORMAL",
                       is_first_piece_required: bool = False,
                       created_by: int = None,
                       equipment_id: int = None) -> dict:
    """
    创建生产工单。

    刚性卡控（.cursorrules V3.2 §2.1 定点卡控）：
      - 零件必须有定点记录（nomination_status = 'production_ready'）
      - 目标数量 >= 1

    参数
    ----
    is_first_piece_required : 首件 QA 开关。True 时工单起量前必须放行。
    """
    if target_qty < 1:
        raise ValueError("目标数量必须 >= 1")

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 定点卡控
            cur.execute("""
                SELECT nomination_status FROM parts WHERE id = %s;
            """, (part_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"零件 #{part_id} 不存在")
            nom_status = row.get("nomination_status", "")
            if nom_status not in ("production_ready", ""):
                raise ValueError(
                    f"零件 #{part_id} 定点状态为【{nom_status}】，"
                    "必须定点完成后方可创建工单"
                )

            order_no = generate_order_no()
            cur.execute("""
                INSERT INTO work_orders
                    (order_no, part_id, equipment_id, target_qty, priority,
                     is_first_piece_required, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
            """, (order_no, part_id, equipment_id, target_qty,
                  priority, is_first_piece_required, created_by))
            conn.commit()
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


def schedule_work_order(wo_id: int, equipment_id: int,
                        actor_id: int = None) -> dict:
    """
    将工单分配到机台（SCHEDULED 态）。
    要求：工单当前为 PENDING 且机台处于 IDLE。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM work_orders WHERE id = %s;",
                (wo_id,)
            )
            wo = cur.fetchone()
            if not wo:
                return {"code": 1, "message": f"工单 #{wo_id} 不存在"}

            if wo["order_status"] != "PENDING":
                return {"code": 1,
                        "message": f"工单当前状态【{wo['order_status']}】，仅 PENDING 可排产"}

            cur.execute(
                "SELECT current_status FROM equipments WHERE id = %s;",
                (equipment_id,)
            )
            eq = cur.fetchone()
            if not eq:
                return {"code": 1, "message": f"机台 #{equipment_id} 不存在"}

            if eq["current_status"] not in ("IDLE",):
                return {
                    "code": 1,
                    "message": f"机台当前状态【{eq['current_status']}】，仅 IDLE 可接受新工单"
                }

            now = datetime.datetime.now()
            cur.execute("""
                UPDATE work_orders
                SET equipment_id = %s,
                    order_status = 'SCHEDULED',
                    updated_at = %s
                WHERE id = %s;
            """, (equipment_id, now, wo_id))

            cur.execute("""
                UPDATE equipments
                SET current_status = 'RUNNING'
                WHERE id = %s;
            """, (equipment_id,))

            conn.commit()
            return {
                "code": 0,
                "message": f"工单已分配到机台 #{equipment_id}，状态更新为【SCHEDULED】"
            }


def start_work_order(wo_id: int) -> dict:
    """
    工单从 SCHEDULED → RUNNING（操作工扫码确认上线）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE work_orders
                SET order_status = 'RUNNING', updated_at = NOW()
                WHERE id = %s AND order_status = 'SCHEDULED'
                RETURNING id;
            """, (wo_id,))
            row = cur.fetchone()
            conn.commit()
            if not row:
                return {"code": 1, "message": "工单不存在或不在待上线状态"}
            return {"code": 0, "message": "工单已上线生产"}


def approve_first_piece(wo_id: int, operator_id: int) -> dict:
    """
    首件 QA 放行。
    工单.is_first_piece_required=True 时，首次报工前必须先调用此函数放行。
    放行后写入 first_piece_passed_at / passed_by。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE work_orders
                SET first_piece_passed_at = NOW(),
                    first_piece_passed_by = %s
                WHERE id = %s
                  AND is_first_piece_required = TRUE
                  AND first_piece_passed_at IS NULL
                RETURNING id;
            """, (operator_id, wo_id))
            row = cur.fetchone()
            conn.commit()
            if not row:
                return {"code": 1,
                        "message": "工单无需首件放行或已放行"}
            return {"code": 0, "message": "首件已放行，可开始报工"}


def first_piece_check(wo_id: int) -> tuple[bool, str]:
    """
    报工前置：检查首件 QA 是否已放行。
    返回 (allowed, message)
      allowed=True  → 可报工
      allowed=False → 拒绝，含原因
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT is_first_piece_required, first_piece_passed_at
                FROM work_orders WHERE id = %s;
            """, (wo_id,))
            row = cur.fetchone()
            if not row:
                return False, f"工单 #{wo_id} 不存在"

            req, passed_at = row[0], row[1]
            if req and not passed_at:
                return False, "首件 QA 未放行，请先完成首件检验后再报工"
            return True, "通过"


def add_production_log(wo_id: int, equipment_id: int,
                       strokes: int, operator_id: int,
                       material_qr_uid: str = None) -> dict:
    """
    冲压报工（strokes × cavity_count = yield_qty）。
    核心逻辑（.cursorrules V3.2 §2.3）：
      1. 机台状态熔断校验
      2. 首件 QA 放行校验
      3. strokes → yield_qty 换算
      4. 自动扣减原料批次重量
      5. 工单 produced_qty 累加

    参数
    ----
    strokes          : 冲压次数（操作工输入）
    material_qr_uid : 原料批次码（可扫码录入，可 None）

    返回 {"code": 0/1, "message": str, "data": {yield_qty, ...}}
    """
    if strokes <= 0:
        return {"code": 1, "message": "冲压次数必须 > 0"}

    # ── 1. 机台状态熔断校验 ──────────────────────────
    locked, msg = equipment_check_production_lock(equipment_id)
    if locked:
        return {"code": 1, "message": msg}

    # ── 2. 读取工单 + 首件校验 ──────────────────────
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT wo.*, pt.part_number,
                       mo.cavity_count
                FROM work_orders wo
                JOIN parts pt ON wo.part_id = pt.id
                LEFT JOIN dies mo ON wo.die_id = mo.id
                WHERE wo.id = %s;
            """, (wo_id,))
            wo = cur.fetchone()
            if not wo:
                return {"code": 1, "message": f"工单 #{wo_id} 不存在"}
            if wo["order_status"] not in ("RUNNING", "SCHEDULED"):
                return {"code": 1,
                        "message": f"工单状态【{wo['order_status']}】，不允许报工"}

            # 首件 QA 校验
            fp_ok, fp_msg = first_piece_check(wo_id)
            if not fp_ok:
                return {"code": 1, "message": fp_msg}

            cavity_count = wo.get("cavity_count") or 1
            yield_qty = strokes * cavity_count

    # ── 3. 原料扣重 ────────────────────────────────
    if material_qr_uid:
        deduct_material_weight(material_qr_uid, strokes, conn=None)

    # ── 4. 写入报工记录 + 累加工单产出 ─────────────
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sf_production_logs
                    (work_order_id, equipment_id, strokes, yield_qty,
                     material_qr_uid, operator_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW());
            """, (wo_id, equipment_id, strokes, yield_qty,
                  material_qr_uid, operator_id))

            cur.execute("""
                UPDATE work_orders
                SET produced_qty = produced_qty + %s,
                    order_status  = CASE
                        WHEN produced_qty + %s >= target_qty THEN 'COMPLETED'
                        ELSE order_status
                    END,
                    updated_at = NOW()
                WHERE id = %s;
            """, (yield_qty, yield_qty, wo_id))

            conn.commit()

    return {
        "code": 0,
        "message": f"报工成功：{strokes} 冲次 × {cavity_count} 穴 = {yield_qty} 件",
        "data": {
            "strokes": strokes,
            "cavity_count": cavity_count,
            "yield_qty": yield_qty,
            "wo_id": wo_id,
            "equipment_id": equipment_id,
            "operator_id": operator_id,
        },
    }


def deduct_material_weight(qr_uid: str, strokes: int,
                            conn=None) -> None:
    """
    报工时自动扣减原料批次当前重量。
    每冲次固定消耗重量 = 单次原料消耗参数（kg/冲次），由 material_batches.unit 或 material_base_prices 表维护。
    此处按最简模型：strokes / 10.0 kg（实际应从工艺参数表取）。
    """
    # 默认每 10 冲消耗 1 kg（需后续对接 material_aux_unit 表的冲次消耗参数）
    deduct_kg = strokes / 10.0
    if conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE material_batches
            SET current_weight = GREATEST(0, current_weight - %s),
                updated_at = NOW()
            WHERE qr_uid = %s;
        """, (deduct_kg, qr_uid))
    else:
        with psycopg2.connect(**DB_CONFIG) as conn2:
            with conn2.cursor() as cur:
                cur.execute("""
                    UPDATE material_batches
                    SET current_weight = GREATEST(0, current_weight - %s),
                        updated_at = NOW()
                    WHERE qr_uid = %s;
                """, (deduct_kg, qr_uid))
                conn2.commit()


def get_sf_production_logs(wo_id: int = None,
                            equipment_id: int = None,
                            limit: int = 200) -> list:
    """返回冲压报工流水（支持按工单/机台过滤）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cond, params = [], []
            if wo_id:
                cond.append("sf.work_order_id = %s")
                params.append(wo_id)
            if equipment_id:
                cond.append("sf.equipment_id = %s")
                params.append(equipment_id)
            where = ("WHERE " + " AND ".join(cond)) if cond else ""

            cur.execute(f"""
                SELECT sf.*,
                       e.equipment_code,
                       wo.order_no,
                       pt.part_number,
                       u.real_name AS operator_name
                FROM sf_production_logs sf
                JOIN equipments e ON sf.equipment_id = e.id
                JOIN work_orders wo ON sf.work_order_id = wo.id
                JOIN parts pt ON wo.part_id = pt.id
                LEFT JOIN users u ON sf.operator_id = u.id
                {where}
                ORDER BY sf.created_at DESC
                LIMIT %s;
            """, (*params, limit))
            return [dict(r) for r in cur.fetchall()]


def get_work_order_summary(wo_id: int) -> dict:
    """工单汇总：总冲次、总产出、首件状态、各班次统计。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 基本信息
            cur.execute("""
                SELECT wo.*,
                       pt.part_number, pt.internal_name,
                       e.equipment_code, e.equipment_name,
                       mo.cavity_count
                FROM work_orders wo
                JOIN parts pt ON wo.part_id = pt.id
                LEFT JOIN equipments e ON wo.equipment_id = e.id
                LEFT JOIN dies mo ON wo.die_id = mo.id
                WHERE wo.id = %s;
            """, (wo_id,))
            wo = cur.fetchone()
            if not wo:
                return {}

            # 报工汇总
            cur.execute("""
                SELECT
                    COUNT(*)::INTEGER       AS total_reports,
                    COALESCE(SUM(sf.strokes), 0)::INTEGER  AS total_strokes,
                    COALESCE(SUM(sf.yield_qty), 0)::INTEGER AS total_yield,
                    MIN(sf.created_at) AS first_report_at,
                    MAX(sf.created_at) AS last_report_at
                FROM sf_production_logs sf
                WHERE sf.work_order_id = %s;
            """, (wo_id,))
            summary = cur.fetchone()

            return {**dict(wo), **dict(summary)}


# ─────────────────────────────────────────────────────────────────────────────
# D. 双轨维修日志 (maintenance_logs)
# ─────────────────────────────────────────────────────────────────────────────

def create_maintenance_log(target_type: str,
                            equipment_id: int = None,
                            mold_id: int = None,
                            repair_mode: str = None,
                            tech_id: int = None,
                            remarks: str = "") -> dict:
    """
    创建维修记录（双轨入口）。

    repair_mode 决定后续状态机行为：
      MACHINE_REPAIR        → 机台维修，EQUIP_REPAIR
      MOLD_ON_MACHINE       → 模具在机维修，MOLD_REPAIR_ON_MACHINE（不拆模）
      MOLD_DISMOUNTED       → 拆模维修，EQUIP_REPAIR（机台释放 IDLE）

    联动机台状态变更（通过 equipment_change_status）。
    """
    if target_type not in ("EQUIPMENT", "MOLD"):
        raise ValueError("target_type 必须为 EQUIPMENT 或 MOLD")
    if not equipment_id and target_type == "EQUIPMENT":
        raise ValueError("机台故障时 equipment_id 必填")

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 写入维修记录
            cur.execute("""
                INSERT INTO maintenance_logs
                    (target_type, equipment_id, mold_id,
                     repair_mode, status, tech_id, remarks)
                VALUES (%s, %s, %s, %s, 'REPAIRING', %s, %s)
                RETURNING *;
            """, (target_type, equipment_id, mold_id,
                  repair_mode, tech_id, remarks))
            log = dict(cur.fetchone())

            # 联动机台状态
            if equipment_id and repair_mode:
                if repair_mode == "MOLD_ON_MACHINE":
                    new_eq_status = "MOLD_REPAIR_ON_MACHINE"
                elif repair_mode == "MOLD_DISMOUNTED":
                    new_eq_status = "IDLE"          # 拆模释放，立即可接新工单
                else:
                    new_eq_status = "EQUIP_REPAIR"

                cur.execute("""
                    UPDATE equipments
                    SET current_status = %s, updated_at = NOW()
                    WHERE id = %s;
                """, (new_eq_status, equipment_id))

                # 联动：RUNNING 工单 → PAUSED
                if new_eq_status in ("EQUIP_REPAIR", "MOLD_REPAIR_ON_MACHINE"):
                    cur.execute("""
                        UPDATE work_orders
                        SET order_status = 'PAUSED', updated_at = NOW()
                        WHERE equipment_id = %s
                          AND order_status = 'RUNNING';
                    """, (equipment_id,))

            conn.commit()
            return log


def complete_maintenance_log(log_id: int, resolved: bool = True,
                              remarks: str = "") -> dict:
    """
    维修完成处理。

    resolved=True  → 状态更新为 RESOLVED
                     并联动恢复机台状态（EQUIP_REPAIR→RUNNING，
                     MOLD_REPAIR_ON_MACHINE→RUNNING，
                     拆模→IDLE）。
                     若工单为 PAUSED，自动恢复为 RUNNING。
    resolved=False → 状态更新为 CANCELLED（撤单）
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM maintenance_logs WHERE id = %s;",
                (log_id,)
            )
            log = cur.fetchone()
            if not log:
                return {"code": 1, "message": f"维修记录 #{log_id} 不存在"}
            if log["status"] != "REPAIRING":
                return {"code": 1,
                        "message": f"当前状态【{log['status']}】，非维修中无法完成"}

            new_status = "RESOLVED" if resolved else "CANCELLED"
            cur.execute("""
                UPDATE maintenance_logs
                SET status = %s,
                    end_time = NOW(),
                    remarks = COALESCE(%s, remarks)
                WHERE id = %s;
            """, (new_status, remarks, log_id))

            # 联动恢复机台状态
            eq_id = log["equipment_id"]
            repair_mode = log["repair_mode"]
            if eq_id and resolved:
                if repair_mode == "MOLD_DISMOUNTED":
                    # 拆模维修完成后模具归库，机台保持 IDLE
                    new_eq = "IDLE"
                else:
                    new_eq = "RUNNING"

                cur.execute("""
                    UPDATE equipments
                    SET current_status = %s, updated_at = NOW()
                    WHERE id = %s;
                """, (new_eq, eq_id))

                # 恢复 PAUSED 工单 → RUNNING
                cur.execute("""
                    UPDATE work_orders
                    SET order_status = 'RUNNING', updated_at = NOW()
                    WHERE equipment_id = %s
                      AND order_status = 'PAUSED';
                """, (eq_id,))

            conn.commit()

            msg = "维修完成" if resolved else "维修记录已撤单"
            return {
                "code": 0,
                "message": msg,
                "data": {"log_id": log_id, "status": new_status},
            }


def get_maintenance_logs(equipment_id: int = None,
                           status: str = None,
                           limit: int = 200) -> list:
    """维修日志查询。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cond, params = [], []
            if equipment_id:
                cond.append("ml.equipment_id = %s")
                params.append(equipment_id)
            if status:
                cond.append("ml.status = %s")
                params.append(status)
            where = ("WHERE " + " AND ".join(cond)) if cond else ""

            cur.execute(f"""
                SELECT ml.*,
                       e.equipment_code, e.equipment_name,
                       mo.mold_number, mo.mold_name,
                       u.real_name AS tech_name,
                       EXTRACT(EPOCH FROM (
                           COALESCE(ml.end_time, NOW()) - ml.start_time
                       )) / 60 AS repair_duration_min
                FROM maintenance_logs ml
                LEFT JOIN equipments e ON ml.equipment_id = e.id
                LEFT JOIN dies  mo ON ml.mold_id = mo.id
                LEFT JOIN users  u  ON ml.tech_id = u.id
                {where}
                ORDER BY ml.start_time DESC
                LIMIT %s;
            """, (*params, limit))
            return [dict(r) for r in cur.fetchall()]


def get_open_maintenance(equipment_id: int) -> dict | None:
    """查询指定机台当前未关闭的维修记录。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ml.*,
                       e.equipment_code,
                       u.real_name AS tech_name
                FROM maintenance_logs ml
                JOIN equipments e ON ml.equipment_id = e.id
                LEFT JOIN users u ON ml.tech_id = u.id
                WHERE ml.equipment_id = %s
                  AND ml.status = 'REPAIRING'
                ORDER BY ml.start_time DESC
                LIMIT 1;
            """, (equipment_id,))
            row = cur.fetchone()
            return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# E. 客户件号对照 (part_customer_aliases)
# ─────────────────────────────────────────────────────────────────────────────

def get_customer_alias(part_id: int, customer_name: str = None) -> dict | None:
    """查询零件的客户件号别名。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if customer_name:
                cur.execute("""
                    SELECT * FROM part_customer_aliases
                    WHERE part_id = %s AND customer_name = %s;
                """, (part_id, customer_name))
            else:
                cur.execute("""
                    SELECT * FROM part_customer_aliases
                    WHERE part_id = %s
                    ORDER BY created_at DESC LIMIT 1;
                """, (part_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_customer_alias(part_id: int, customer_name: str,
                           customer_part_no: str,
                           customer_part_name: str = "") -> dict:
    """新增或更新客户件号别名映射。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO part_customer_aliases
                    (part_id, customer_name, customer_part_no, customer_part_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (part_id, customer_name)
                DO UPDATE SET
                    customer_part_no   = EXCLUDED.customer_part_no,
                    customer_part_name = EXCLUDED.customer_part_name;
            """, (part_id, customer_name, customer_part_no, customer_part_name))
            conn.commit()
    return get_customer_alias(part_id, customer_name)


# ─────────────────────────────────────────────────────────────────────────────
# F. 发货单 (delivery_notes + delivery_items)
# ─────────────────────────────────────────────────────────────────────────────

def generate_dn_no() -> str:
    """生成发货单号 DN-YYYY-NNN。"""
    year = datetime.date.today().year
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(
                    CAST(SUBSTRING(dn_no FROM 'DN-[0-9]+-([0-9]+)') AS INTEGER)
                ), 0) + 1
                FROM delivery_notes
                WHERE dn_no LIKE %s;
            """, (f"DN-{year}-%",))
            seq = cur.fetchone()[0]
    return f"DN-{year}-{seq:03d}"


def get_all_delivery_notes(customer_name: str = None,
                             status: str = None,
                             limit: int = 200) -> list:
    """发货单列表（含汇总）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cond, params = [], []
            if customer_name:
                cond.append("dn.customer_name ILIKE %s")
                params.append(f"%{customer_name}%")
            if status:
                cond.append("dn.status = %s")
                params.append(status)
            where = ("WHERE " + " AND ".join(cond)) if cond else ""

            cur.execute(f"""
                SELECT dn.*,
                       u.real_name AS created_by_name,
                       COUNT(di.id)::INTEGER AS item_count,
                       COALESCE(SUM(di.qty), 0)::INTEGER AS total_qty
                FROM delivery_notes dn
                LEFT JOIN users u ON dn.created_by = u.id
                LEFT JOIN delivery_items di ON di.dn_id = dn.id
                {where}
                GROUP BY dn.id, u.real_name
                ORDER BY dn.shipped_at DESC
                LIMIT %s;
            """, (*params, limit))
            return [dict(r) for r in cur.fetchall()]


def get_delivery_note_detail(dn_id: int) -> dict | None:
    """发货单详情（含明细，自动翻译客户件号）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT dn.*, u.real_name AS created_by_name
                FROM delivery_notes dn
                LEFT JOIN users u ON dn.created_by = u.id
                WHERE dn.id = %s;
            """, (dn_id,))
            header = cur.fetchone()
            if not header:
                return None

            cur.execute("""
                SELECT di.*,
                       pt.part_number   AS internal_part_no,
                       pt.internal_name AS internal_name,
                       pca.customer_part_no   AS customer_part_no,
                       pca.customer_part_name AS customer_part_name
                FROM delivery_items di
                JOIN parts pt ON di.part_id = pt.id
                LEFT JOIN part_customer_aliases pca
                    ON pca.part_id = pt.id
                    AND pca.customer_name = %s
                WHERE di.dn_id = %s
                ORDER BY di.id;
            """, (header["customer_name"], dn_id))
            items = [dict(r) for r in cur.fetchall()]

            result = dict(header)
            result["items"] = items
            return result


def create_delivery_note(customer_name: str,
                           created_by: int,
                           items: list[dict],
                           notes: str = "",
                           shipped_at=None) -> dict:
    """
    创建发货单（含明细）。
    items: [{"part_id": int, "qty": int, "lot_no": str, "remark": str}, ...]

    返回 {"code": 0/1, "message": str, "data": {"dn_id": int, "dn_no": str}}
    """
    if not items:
        return {"code": 1, "message": "发货明细不能为空"}

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            dn_no = generate_dn_no()
            ship_ts = shipped_at if shipped_at else datetime.datetime.now()

            cur.execute("""
                INSERT INTO delivery_notes
                    (dn_no, customer_name, shipped_at, status, notes, created_by)
                VALUES (%s, %s, %s, 'SHIPPED', %s, %s)
                RETURNING id;
            """, (dn_no, customer_name, ship_ts, notes, created_by))
            dn_id = cur.fetchone()[0]

            for item in items:
                cur.execute("""
                    INSERT INTO delivery_items
                        (dn_id, part_id, qty, lot_no, remark)
                    VALUES (%s, %s, %s, %s, %s);
                """, (dn_id, item["part_id"], item["qty"],
                      item.get("lot_no", ""), item.get("remark", "")))

            conn.commit()

    return {
        "code": 0,
        "message": f"发货单 {dn_no} 已创建，共 {len(items)} 个明细",
        "data": {"dn_id": dn_id, "dn_no": dn_no},
    }


def cancel_delivery_note(dn_id: int, operator_id: int) -> dict:
    """取消发货单（SHIPPED → CANCELLED）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE delivery_notes
                SET status = 'CANCELLED', notes = notes || ' [已取消]'
                WHERE id = %s AND status = 'SHIPPED'
                RETURNING dn_no;
            """, (dn_id,))
            row = cur.fetchone()
            conn.commit()
            if not row:
                return {"code": 1, "message": "发货单不存在或已非待发货状态"}
            return {"code": 0, "message": f"发货单 {row[0]} 已取消"}


def get_shipping_eligibility(part_id: int, qty: int,
                               customer_name: str = None) -> tuple[bool, str]:
    """
    发货资格校验（.cursorrules V3.2 §2.4）：
      1. 零件生命周期状态必须为 MASS_PRODUCTION
      2. 可发货库存 = 累计良品 - 已发货数
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 生命周期校验
            cur.execute(
                "SELECT part_status FROM parts WHERE id = %s;",
                (part_id,)
            )
            row = cur.fetchone()
            if not row:
                return False, "零件不存在"
            if row[0] != "MASS_PRODUCTION":
                return False, f"零件状态【{row[0]}】，仅【MASS_PRODUCTION】可发货"

            # 库存校验
            cur.execute("""
                SELECT
                    COALESCE(SUM(pl.qty_good), 0)::INTEGER  AS total_good,
                    COALESCE(SUM(sh.qty), 0)::INTEGER         AS total_shipped
                FROM production_logs pl
                LEFT JOIN pkg_shipping_logs sh ON sh.part_id = pl.part_id
                WHERE pl.part_id = %s AND pl.status = 'approved';
            """, (part_id,))
            r = cur.fetchone()
            available = (r[0] or 0) - (r[1] or 0)
            if available < qty:
                return False, f"可发货库存不足：当前 {available} 件 < 本次 {qty} 件"
            return True, "可发货"


# ─────────────────────────────────────────────────────────────────────────────
# G. 客户管理（基础列表，用于发货单下拉）
# ─────────────────────────────────────────────────────────────────────────────

def get_all_customers() -> list:
    """返回所有已出现过的客户名称列表（去重）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT customer_name
                FROM part_customer_aliases
                WHERE customer_name IS NOT NULL AND customer_name != ''
                UNION
                SELECT DISTINCT customer_name
                FROM delivery_notes
                WHERE customer_name IS NOT NULL AND customer_name != ''
                ORDER BY 1;
            """)
            return [r[0] for r in cur.fetchall()]


# =============================================================================
# 库存体系（v12）
# =============================================================================

# ── 成品库 ────────────────────────────────────────────────────────────────────

def get_finished_inventory(part_id: int = None) -> list:
    """查询成品库，可按零件过滤。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if part_id:
                cur.execute("""
                    SELECT fi.*, pt.part_number, pt.internal_name
                    FROM finished_inventory fi
                    JOIN parts pt ON fi.part_id = pt.id
                    WHERE fi.part_id = %s
                    ORDER BY fi.location;
                """, (part_id,))
            else:
                cur.execute("""
                    SELECT fi.*, pt.part_number, pt.internal_name
                    FROM finished_inventory fi
                    JOIN parts pt ON fi.part_id = pt.id
                    ORDER BY pt.part_number, fi.location;
                """)
            return [dict(r) for r in cur.fetchall()]


def upsert_finished_inventory(part_id: int, quantity: int, location: str = "") -> dict:
    """成品库入库/更新（按 part_id + location 唯一键 upsert）。"""
    if quantity < 0:
        raise ValueError("库存数量不能为负数")
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    INSERT INTO finished_inventory (part_id, quantity, location, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (part_id, location)
                    DO UPDATE SET
                        quantity   = EXCLUDED.quantity,
                        updated_at = NOW()
                    RETURNING *;
                """, (part_id, quantity, location))
                conn.commit()
                row = cur.fetchone()
                return dict(row)
            except Exception:
                conn.rollback()
                raise


def adjust_finished_inventory(part_id: int, delta: int, location: str = "") -> dict:
    """成品库增减（delta 可正可负，结果不能低于 0）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    INSERT INTO finished_inventory (part_id, quantity, location, updated_at)
                    VALUES (%s, GREATEST(0, %s), %s, NOW())
                    ON CONFLICT (part_id, location)
                    DO UPDATE SET
                        quantity   = GREATEST(0, finished_inventory.quantity + EXCLUDED.quantity),
                        updated_at = NOW()
                    RETURNING *;
                """, (part_id, delta, location))
                conn.commit()
                row = cur.fetchone()
                return dict(row)
            except Exception:
                conn.rollback()
                raise


# ── 尾数库 ────────────────────────────────────────────────────────────────────

def get_remnant_inventory(part_id: int = None) -> list:
    """查询尾数库，可按零件过滤。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if part_id:
                cur.execute("""
                    SELECT ri.*, pt.part_number, pt.internal_name
                    FROM remnant_inventory ri
                    JOIN parts pt ON ri.part_id = pt.id
                    WHERE ri.part_id = %s;
                """, (part_id,))
            else:
                cur.execute("""
                    SELECT ri.*, pt.part_number, pt.internal_name
                    FROM remnant_inventory ri
                    JOIN parts pt ON ri.part_id = pt.id
                    ORDER BY pt.part_number;
                """)
            return [dict(r) for r in cur.fetchall()]


def upsert_remnant_inventory(part_id: int, quantity: int) -> dict:
    """尾数库入库/更新（按 part_id 唯一键 upsert）。"""
    if quantity < 0:
        raise ValueError("库存数量不能为负数")
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    INSERT INTO remnant_inventory (part_id, quantity, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (part_id)
                    DO UPDATE SET
                        quantity   = EXCLUDED.quantity,
                        updated_at = NOW()
                    RETURNING *;
                """, (part_id, quantity))
                conn.commit()
                row = cur.fetchone()
                return dict(row)
            except Exception:
                conn.rollback()
                raise


def adjust_remnant_inventory(part_id: int, delta: int) -> dict:
    """尾数库增减（delta 可正可负，结果不能低于 0）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute("""
                    INSERT INTO remnant_inventory (part_id, quantity, updated_at)
                    VALUES (%s, GREATEST(0, %s), NOW())
                    ON CONFLICT (part_id)
                    DO UPDATE SET
                        quantity   = GREATEST(0, remnant_inventory.quantity + EXCLUDED.quantity),
                        updated_at = NOW()
                    RETURNING *;
                """, (part_id, delta))
                conn.commit()
                row = cur.fetchone()
                return dict(row)
            except Exception:
                conn.rollback()
                raise


# ── 聚合查询 ──────────────────────────────────────────────────────────────────

def get_part_inventory_summary(part_id: int) -> dict:
    """
    返回零件的完整库存快照：
      - finished: 成品库各库位明细 + 合计
      - remnant:  尾数库数量
      - total:    finished_total + remnant
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT pt.id, pt.part_number, pt.internal_name, pt.part_status
                FROM parts pt WHERE pt.id = %s;
            """, (part_id,))
            part = cur.fetchone()
            if not part:
                return None

            cur.execute("""
                SELECT location, quantity, updated_at
                FROM finished_inventory
                WHERE part_id = %s
                ORDER BY location;
            """, (part_id,))
            finished_rows = [dict(r) for r in cur.fetchall()]
            finished_total = sum(r["quantity"] for r in finished_rows)

            cur.execute("""
                SELECT quantity, updated_at
                FROM remnant_inventory
                WHERE part_id = %s;
            """, (part_id,))
            rem_row = cur.fetchone()
            remnant_qty = rem_row["quantity"] if rem_row else 0

            return {
                "part_id":        part_id,
                "part_number":    part["part_number"],
                "internal_name":  part["internal_name"],
                "part_status":    part["part_status"],
                "finished":       finished_rows,
                "finished_total": finished_total,
                "remnant":        remnant_qty,
                "total":          finished_total + remnant_qty,
            }


# ── 模具物理参数更新（扩展 update_die 不够用时的专用函数）────────────────────

def update_die_physical_params(mold_id: int,
                                 thickness_mm: float = None,
                                 width_mm: float = None,
                                 pitch_mm: float = None) -> dict | None:
    """
    更新模具 T/W/P 物理参数，不传则跳过。

    同步规则（cursorrules V6.0 §2.3）：
      更新后自动将 T/W/P 同步回所有关联零件的 parts 表缓存字段，
      保证 parts 表尽量新鲜（仅作降级兜底，不是生产主数据源）。
    """
    fields, vals = [], []
    if thickness_mm is not None:
        fields.append("thickness_mm = %s"); vals.append(thickness_mm)
    if width_mm is not None:
        fields.append("width_mm = %s"); vals.append(width_mm)
    if pitch_mm is not None:
        fields.append("pitch_mm = %s"); vals.append(pitch_mm)
    if not fields:
        return get_die_by_id(mold_id)
    vals.append(mold_id)
    sql = "UPDATE dies SET " + ", ".join(fields) + ", updated_at = NOW() WHERE id = %s RETURNING *;"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(sql, vals)

                # 同步 T/W/P 回 parts 表缓存（die_parts 关联表）
                if thickness_mm is not None or width_mm is not None:
                    sync_fields, sync_vals = [], []
                    if thickness_mm is not None:
                        sync_fields.append("thickness = %s"); sync_vals.append(thickness_mm)
                    if width_mm is not None:
                        sync_fields.append("width = %s"); sync_vals.append(width_mm)
                    if sync_fields:
                        cur.execute(f"""
                            UPDATE parts
                            SET {', '.join(sync_fields)}, updated_at = NOW()
                            WHERE id IN (
                                SELECT part_id FROM die_parts WHERE die_id = %s
                            );
                        """, sync_vals + [mold_id])

                conn.commit()
                row = cur.fetchone()
                return dict(row) if row else None
            except Exception:
                conn.rollback()
                raise


# =============================================================================
# 零件-模具关联表（die-link）：一个零件 × 一个模具 = 一行
# 支持前端筛选器：默认本月 + 之前欠发
# =============================================================================
# 零件表（仅展示，供全员快速查询零件基础信息）
# 字段：件号、名称、原料、T、W、P、表面处理、模具号
# =============================================================================

def get_parts_for_list_view() -> list:
    """
    返回所有零件的基础信息，供全员快速查询。
    - T/W/P 优先取 APPROVED 报价的参数；若报价单中无 APPROVED，
      则取 parts 表本身的 thickness/width/press_stroke 字段。
    - 表面处理取 APPROVED 报价单的 surface_fee 字段（若为 0 视为无处理）。
    - 模具号：同一零件关联多个模具时，用逗号拼接。
    - 图纸：暂无图纸表，字段留空，后续扩展。
    - 按件号升序排列。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 先查 APPROVED 报价的参数（每个零件取最新一条）
            cur.execute("""
                SELECT DISTINCT ON (part_id)
                       part_id,
                       thickness,
                       width,
                       press_stroke,
                       surface_fee,
                       cavity_count
                FROM quotes
                WHERE approval_status = 'APPROVED'
                  AND is_deleted = FALSE
                ORDER BY part_id, updated_at DESC
            """)
            approved = {r["part_id"]: r for r in cur.fetchall()}

            # 再查所有零件关联的模具号（逗号拼接）
            cur.execute("""
                SELECT mp.part_id,
                       STRING_AGG(DISTINCT d.mold_number, ', ' ORDER BY d.mold_number) AS mold_numbers
                FROM die_parts mp
                JOIN dies d ON d.id = mp.die_id
                GROUP BY mp.part_id
            """)
            mold_map = {r["part_id"]: r["mold_numbers"] for r in cur.fetchall()}

            # 最后查所有零件基础数据
            cur.execute("""
                SELECT id, part_number, internal_name, material_name,
                       remark,
                       COALESCE(thickness, 0) AS thickness_fallback,
                       COALESCE(width, 0)      AS width_fallback,
                       COALESCE(press_stroke, 0) AS stroke_fallback
                FROM parts
                ORDER BY part_number ASC
            """)
            rows = cur.fetchall()

    result = []
    for row in rows:
        pid = row["id"]
        q = approved.get(pid, {})
        # T/W/P: 报价单优先，parts 表兜底
        thickness  = q.get("thickness")     if q.get("thickness")     is not None else row["thickness_fallback"]
        width      = q.get("width")         if q.get("width")         is not None else row["width_fallback"]
        press_stroke = q.get("press_stroke") if q.get("press_stroke") is not None else row["stroke_fallback"]
        # 表面处理：surface_fee > 0 时说明有处理
        surface_fee  = q.get("surface_fee") or 0
        surface_txt  = ("是" if surface_fee > 0 else "") if q else ""
        # 模具号
        mold_numbers = mold_map.get(pid, "")

        result.append({
            "id":           pid,
            "part_number":  row["part_number"],
            "internal_name": row["internal_name"],
            "material_name": row["material_name"],
            "remark":       row["remark"],
            "thickness":    thickness  or None,
            "width":        width      or None,
            "press_stroke": press_stroke or None,
            "surface_txt":  surface_txt,
            "mold_numbers": mold_numbers,
            "drawing":      "",   # 图纸字段，预留扩展
        })
    return result


# =============================================================================

def get_parts_with_die_link(
        part_name: str = "",
        mold_number: str = "",
        month: str = ""
) -> list:
    """
    零件-模具关联表：每个 (part_id, mold_id) 组合输出一行。

    显示字段：零件信息 / 模具信息 / 报价 / 重量 / 表面处理 / 订单与发货
    跳转支持：零件→模具详情，模具→零件列表

    参数
    ----
    part_name  : 零件编号/名称模糊搜索
    mold_number : 模具编号模糊搜索
    month       : "YYYY-MM"，空则默认本月；查询条件为 <= 该月（含欠发）
    """
    if not month:
        month = datetime.date.today().strftime("%Y-%m")

    params = []
    conditions = []

    if part_name:
        conditions.append("(p.part_number ILIKE %s OR p.internal_name ILIKE %s)")
        params.extend([f"%{part_name}%", f"%{part_name}%"])

    if mold_number:
        conditions.append("d.mold_number ILIKE %s")
        params.append(f"%{mold_number}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
        SELECT
            p.id         AS part_id,
            p.part_number,
            p.internal_name  AS part_name,
            p.material_name,
            p.part_status,

            d.id         AS mold_id,
            d.mold_number,
            d.mold_name,
            d.cavity_count   AS mold_cavities,
            d.press_tonnage  AS mold_tonnage,

            COALESCE(d.thickness_mm, p.thickness)     AS thickness,
            COALESCE(d.width_mm,    p.width)          AS width,
            COALESCE(d.pitch_mm,    p.press_stroke)   AS pitch,

            COALESCE(mat.default_density, 7.85) AS density,

            ROUND(
                (COALESCE(d.thickness_mm, p.thickness) * 1000
                 * COALESCE(d.width_mm,    p.width)     * 1000
                 * COALESCE(d.pitch_mm,    p.press_stroke) * 1e-6
                 * COALESCE(mat.default_density, 7.85)
                 * COALESCE(d.cavity_count, q.cavity_count, 1)
                )::NUMERIC, 4
            ) AS gross_weight,

            q.final_price,
            q.surface_fee,
            NULL::TEXT AS surface_type,

            COALESCE(SUM(pp.total_qty), 0)::INTEGER    AS order_qty,
            COALESCE(SUM(pp.delivered_qty), 0)::INTEGER AS shipped_qty,
            GREATEST(
                COALESCE(SUM(pp.total_qty), 0)
                - COALESCE(SUM(pp.delivered_qty), 0),
                0
            )::INTEGER                                  AS backlog_qty

        FROM die_parts mp
        JOIN parts p ON p.id = mp.part_id
        LEFT JOIN dies d ON d.id = mp.die_id
        LEFT JOIN material_base_prices mat ON mat.material_name = p.material_name
        LEFT JOIN LATERAL (
            SELECT
                q2.final_price,
                q2.surface_fee,
                q2.cavity_count
            FROM quotes q2
            WHERE q2.part_id = p.id
              AND q2.approval_status = 'APPROVED'
              AND q2.is_deleted = FALSE
            ORDER BY q2.updated_at DESC
            LIMIT 1
        ) q ON TRUE
        LEFT JOIN production_plans pp ON pp.part_id = p.id
            AND DATE_TRUNC('month', pp.due_date) <= DATE %s
        WHERE {where_clause}
        GROUP BY
            p.id, p.part_number, p.internal_name, p.material_name, p.part_status,
            p.thickness, p.width, p.press_stroke,
            d.id, d.mold_number, d.mold_name, d.cavity_count, d.press_tonnage,
            d.thickness_mm, d.width_mm, d.pitch_mm,
            mat.default_density,
            q.final_price, q.surface_fee, q.cavity_count
        ORDER BY p.id DESC, d.id DESC;
    """
    params.append(f"{month}-01")

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

def get_finished_inventory_list(customer_name: str = None) -> list:
    """
    成品库列表，JOIN 客户别名表。
    customer_name 非空时只返回该客户有别名映射的零件行。
    每个 (part_id, location) 一行，附带客户件号/件名。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if customer_name:
                cur.execute("""
                    SELECT
                        fi.id,
                        fi.part_id,
                        fi.location,
                        fi.quantity,
                        fi.updated_at,
                        pt.part_number,
                        pt.internal_name,
                        pt.part_status,
                        pca.customer_name,
                        pca.customer_part_no,
                        pca.customer_part_name
                    FROM finished_inventory fi
                    JOIN parts pt ON fi.part_id = pt.id
                    JOIN part_customer_aliases pca
                        ON pca.part_id = fi.part_id
                        AND pca.customer_name = %s
                    ORDER BY pca.customer_name, pt.part_number, fi.location;
                """, (customer_name,))
            else:
                cur.execute("""
                    SELECT
                        fi.id,
                        fi.part_id,
                        fi.location,
                        fi.quantity,
                        fi.updated_at,
                        pt.part_number,
                        pt.internal_name,
                        pt.part_status,
                        pca.customer_name,
                        pca.customer_part_no,
                        pca.customer_part_name
                    FROM finished_inventory fi
                    JOIN parts pt ON fi.part_id = pt.id
                    LEFT JOIN (
                        SELECT DISTINCT ON (part_id)
                            part_id, customer_name, customer_part_no, customer_part_name
                        FROM part_customer_aliases
                        ORDER BY part_id, created_at DESC
                    ) pca ON pca.part_id = fi.part_id
                    ORDER BY pt.part_number, fi.location;
                """)
            return [dict(r) for r in cur.fetchall()]


def get_remnant_inventory_list(customer_name: str = None) -> list:
    """
    尾数库列表，JOIN 客户别名表。
    每个 part_id 一行（尾数库无库位区分）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if customer_name:
                cur.execute("""
                    SELECT
                        ri.id,
                        ri.part_id,
                        ri.quantity,
                        ri.updated_at,
                        pt.part_number,
                        pt.internal_name,
                        pt.part_status,
                        pca.customer_name,
                        pca.customer_part_no,
                        pca.customer_part_name
                    FROM remnant_inventory ri
                    JOIN parts pt ON ri.part_id = pt.id
                    JOIN part_customer_aliases pca
                        ON pca.part_id = ri.part_id
                        AND pca.customer_name = %s
                    ORDER BY pca.customer_name, pt.part_number;
                """, (customer_name,))
            else:
                cur.execute("""
                    SELECT
                        ri.id,
                        ri.part_id,
                        ri.quantity,
                        ri.updated_at,
                        pt.part_number,
                        pt.internal_name,
                        pt.part_status,
                        pca.customer_name,
                        pca.customer_part_no,
                        pca.customer_part_name
                    FROM remnant_inventory ri
                    JOIN parts pt ON ri.part_id = pt.id
                    LEFT JOIN (
                        SELECT DISTINCT ON (part_id)
                            part_id, customer_name, customer_part_no, customer_part_name
                        FROM part_customer_aliases
                        ORDER BY part_id, created_at DESC
                    ) pca ON pca.part_id = ri.part_id
                    ORDER BY pt.part_number;
                """)
            return [dict(r) for r in cur.fetchall()]


# ============================================================================
# 价格台账（prices）
# ============================================================================

def get_or_create_price_ledger(part_id: int, customer_id: int = None) -> dict:
    """获取或创建价格台账主记录"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, part_id, customer_id, material_name,
                       net_weight, gross_weight,
                       material_unit_price, scrap_price,
                       surface_treatment, created_at, updated_at
                FROM prices
                WHERE part_id = %s AND (customer_id = %s OR (customer_id IS NULL AND %s IS NULL));
            """, (part_id, customer_id, customer_id))
            row = cur.fetchone()
            if row:
                for k, v in row.items():
                    if isinstance(v, (datetime, date)):
                        row[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        row[k] = float(v)
                return dict(row)

            cur.execute("""
                INSERT INTO prices (part_id, customer_id, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                RETURNING id, part_id, customer_id, material_name,
                          net_weight, gross_weight,
                          material_unit_price, scrap_price,
                          surface_treatment, created_at, updated_at;
            """, (part_id, customer_id))
            row = cur.fetchone()
            conn.commit()
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    row[k] = float(v)
            return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_price_ledger(part_id: int, customer_id: int = None,
                         material_name: str = None, net_weight: float = None,
                         gross_weight: float = None,
                         material_unit_price: float = None,
                         scrap_price: float = None,
                         surface_treatment: list = None) -> dict:
    """创建或更新价格台账主记录（成本要素）"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO prices (part_id, customer_id, material_name, net_weight,
                                   gross_weight, material_unit_price, scrap_price,
                                   surface_treatment, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (part_id, customer_id)
                DO UPDATE SET
                    material_name = COALESCE(EXCLUDED.material_name, prices.material_name),
                    net_weight = COALESCE(EXCLUDED.net_weight, prices.net_weight),
                    gross_weight = COALESCE(EXCLUDED.gross_weight, prices.gross_weight),
                    material_unit_price = COALESCE(EXCLUDED.material_unit_price, prices.material_unit_price),
                    scrap_price = COALESCE(EXCLUDED.scrap_price, prices.scrap_price),
                    surface_treatment = COALESCE(EXCLUDED.surface_treatment, prices.surface_treatment),
                    updated_at = NOW()
                RETURNING id, part_id, customer_id, material_name,
                           net_weight, gross_weight,
                           material_unit_price, scrap_price,
                           surface_treatment, created_at, updated_at;
            """, (part_id, customer_id,
                  material_name, net_weight,
                  gross_weight, material_unit_price, scrap_price,
                  json.dumps(surface_treatment or []) if surface_treatment is not None else None))
            row = cur.fetchone()
            conn.commit()
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    row[k] = float(v)
            return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_price_years(price_id: int):
    """获取某价格台账的所有年份记录"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT py.id, py.price_id, py.year, py.unit_price,
                       py.annual_sales, py.operator_id, py.updated_at,
                       u.real_name AS operator_name
                FROM price_years py
                LEFT JOIN users u ON py.operator_id = u.id
                WHERE py.price_id = %s
                ORDER BY py.year DESC;
            """, (price_id,))
            rows = cur.fetchall()
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, (datetime, date)):
                        row[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        row[k] = float(v)
            return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_price_year(price_id: int, year: int, unit_price: float = None,
                       annual_sales: int = None, operator_id: int = None) -> dict:
    """创建或更新某年的单价和年销量"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO price_years (price_id, year, unit_price, annual_sales, operator_id, updated_at)
                VALUES (%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (price_id, year)
                DO UPDATE SET
                    unit_price = COALESCE(EXCLUDED.unit_price, price_years.unit_price),
                    annual_sales = COALESCE(EXCLUDED.annual_sales, price_years.annual_sales),
                    operator_id = COALESCE(EXCLUDED.operator_id, price_years.operator_id),
                    updated_at = NOW()
                RETURNING id, price_id, year, unit_price, annual_sales, updated_at;
            """, (price_id, year, unit_price, annual_sales, operator_id))
            row = cur.fetchone()
            conn.commit()
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    row[k] = float(v)
            return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_annual_reductions(price_id: int):
    """获取某价格台账的所有年降规则"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ar.id, ar.price_id, ar.reduction_pct, ar.start_year,
                       ar.duration_years, ar.reason, ar.created_by, ar.created_at,
                       u.real_name AS created_by_name
                FROM annual_reductions ar
                LEFT JOIN users u ON ar.created_by = u.id
                WHERE ar.price_id = %s
                ORDER BY ar.start_year DESC;
            """, (price_id,))
            rows = cur.fetchall()
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, (datetime, date)):
                        row[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        row[k] = float(v)
            return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_annual_reduction(price_id: int, reduction_pct: float, start_year: int,
                             duration_years: int = 0, reason: str = "",
                             created_by: int = None) -> dict:
    """创建或更新年降规则（按 price_id + start_year 唯一）"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM annual_reductions WHERE price_id=%s AND start_year=%s",
                        (price_id, start_year))
            existing = cur.fetchone()
            if existing:
                cur.execute("""
                    UPDATE annual_reductions
                    SET reduction_pct=%s, duration_years=%s, reason=%s
                    WHERE id=%s;
                """, (reduction_pct, duration_years, reason, existing[0]))
            else:
                cur.execute("""
                    INSERT INTO annual_reductions
                        (price_id, reduction_pct, start_year, duration_years, reason, created_by, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,NOW());
                """, (price_id, reduction_pct, start_year, duration_years, reason, created_by))
            conn.commit()
            return {"success": True, "price_id": price_id, "reduction_pct": reduction_pct,
                    "start_year": start_year, "duration_years": duration_years}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def delete_annual_reduction(rule_id: int) -> dict:
    """删除某条年降规则"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM annual_reductions WHERE id = %s", (rule_id,))
            conn.commit()
            return {"success": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_manual_adjustments(price_id: int, limit: int = 50):
    """获取某价格台账的调价历史"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ma.id, ma.price_id, ma.adjusted_at, ma.old_price, ma.new_price,
                       ma.adjustment_type, ma.reason, ma.operator_id,
                       u.real_name AS operator_name
                FROM manual_adjustments ma
                LEFT JOIN users u ON ma.operator_id = u.id
                WHERE ma.price_id = %s
                ORDER BY ma.adjusted_at DESC
                LIMIT %s;
            """, (price_id, limit))
            rows = cur.fetchall()
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, (datetime, date)):
                        row[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        row[k] = float(v)
            return [dict(r) for r in rows]
    finally:
        conn.close()


def add_manual_adjustment(price_id: int, old_price: float, new_price: float,
                           adjustment_type: str = "manual",
                           reason: str = "", operator_id: int = None) -> dict:
    """记录一次手动调价"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO manual_adjustments
                    (price_id, adjusted_at, old_price, new_price, adjustment_type, reason, operator_id)
                VALUES (%s, NOW(), %s, %s, %s, %s, %s)
                RETURNING id, price_id, adjusted_at, old_price, new_price, adjustment_type, reason;
            """, (price_id, old_price, new_price, adjustment_type, reason, operator_id))
            row = cur.fetchone()

            current_year = datetime.now().year
            cur.execute("""
                INSERT INTO price_years (price_id, year, unit_price, operator_id, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (price_id, year)
                DO UPDATE SET unit_price = EXCLUDED.unit_price, updated_at = NOW();
            """, (price_id, current_year, new_price, operator_id))

            conn.commit()
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    row[k] = float(v)
            return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_price_ledger_full(part_id: int, customer_id: int = None) -> dict:
    """获取完整价格台账（含主记录、年份、年降、调价历史）"""
    ledger = get_or_create_price_ledger(part_id, customer_id)
    price_id = ledger['id']
    ledger['years'] = get_price_years(price_id)
    ledger['annual_reductions'] = get_annual_reductions(price_id)
    ledger['adjustments'] = get_manual_adjustments(price_id)
    return ledger


def list_price_ledgers_by_customer(customer_id: int):
    """获取某客户下所有零件的价格台账摘要"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id AS price_id, p.part_id, p.customer_id,
                       p.material_name, p.net_weight, p.gross_weight,
                       p.material_unit_price, p.scrap_price,
                       p.surface_treatment,
                       p.updated_at,
                       pt.part_number, pt.internal_name,
                       tc.name AS customer_name,
                       py.unit_price AS current_unit_price, py.year AS current_year,
                       ar.reduction_pct, ar.start_year, ar.duration_years
                FROM prices p
                JOIN parts pt ON p.part_id = pt.id
                LEFT JOIN tooling_customers tc ON p.customer_id = tc.id
                LEFT JOIN LATERAL (
                    SELECT unit_price, year FROM price_years
                    WHERE price_id = p.id
                    ORDER BY year DESC LIMIT 1
                ) py ON TRUE
                LEFT JOIN LATERAL (
                    SELECT reduction_pct, start_year, duration_years
                    FROM annual_reductions
                    WHERE price_id = p.id
                    ORDER BY start_year DESC LIMIT 1
                ) ar ON TRUE
                WHERE p.customer_id = %s
                ORDER BY pt.internal_name;
            """, (customer_id,))
            rows = cur.fetchall()
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, (datetime, date)):
                        row[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        row[k] = float(v)
            return [dict(r) for r in rows]
    finally:
        conn.close()