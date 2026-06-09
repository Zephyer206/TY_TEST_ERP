"""
app/services/prod_service_sessions.py
====================================
生产会话状态机 — 连续模专用 + 简易模事后直报

核心职责
--------
1. start_session()             — 连续模工人扫码起机（含 Prototype）
2. close_session()            — 连续模会话结账下料
3. force_takeover_session()   — 强制接班（含 PROTOTYPING 会话）
4. report_simple_production()   — 简易模组长下班直报（无起机，不碰机台状态）

会话双轨逻辑（已确认版）
----------------------
- 连续模（Continuous）：工人开机 → 扫材料码 → 报工结账 → 机台 IDLE，累加 wip_pcs，扣料
- 简易模（Simple）：组长下班时直报 → 直接写 CLOSED 会话 → 累加 wip_pcs，扣料（不碰机台）
- 打样（Prototype）：机台 PROTOTYPING → 填入即生效 → 机台 IDLE，不扣料，不入 wip_pcs

技术守则（.cursorrules §4 + §8.1）
-----------------------------------
- 严禁 ORM，必须使用原生 psycopg2
- 所有 INSERT/UPDATE 必须显式 conn.commit()
- 会话状态变更通过本文件管理，不允许裸 UPDATE status

目录归属：app/services/
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import datetime

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "124.222.29.229",
    "port": "5432",
}


# ============================================================================
# 会话状态枚举
# ============================================================================

SESSION_RUNNING             = "RUNNING"
SESSION_PENDING_REPORT      = "PENDING_REPORT"
SESSION_CLOSED              = "CLOSED"
SESSION_ABNORMAL_TERMINATED = "ABNORMAL_TERMINATED"


# ============================================================================
# 会话类型枚举
# ============================================================================

SESSION_TYPE_CONTINUOUS = "Continuous"
SESSION_TYPE_SIMPLE     = "Simple"
SESSION_TYPE_PROTOTYPE  = "Prototype"


# ============================================================================
# 机台状态枚举
# ============================================================================

EQ_STATUS_IDLE         = "IDLE"
EQ_STATUS_RUNNING      = "RUNNING"
EQ_STATUS_PROTOTYPING  = "PROTOTYPING"


# ============================================================================
# §8.1 开启会话（连续模 + 打样专用，简易模禁止调用）
# ============================================================================

def start_session(
    machine_id: int,
    material_qr_uid: str | None,
    operator_id: int | None,
    is_prototype: bool = False,
    work_order_id: int | None = None,
) -> dict:
    """
    开启连续模会话，或连续模打样会话。

    ⚠ 警告：本接口为连续模专用。
    简易模（Simple Die）请勿调用此函数，使用 report_simple_production() 直报接口。

    会话类型分流
    -----------
    - is_prototype=True  → 'Prototype'（打样），不扫码材料，机台 PROTOTYPING
    - is_prototype=False → 'Continuous'（连续模），工人扫码材料，机台 RUNNING

    防呆规则
    --------
    - 机台有 PENDING_REPORT 未结会话 → 拦截
    - 机台有 RUNNING 会话 → 拦截
    - 机台有 PROTOTYPING 会话 → 拦截（防止重复打样开机）

    参数
    ----
    machine_id      : int         机台 ID
    material_qr_uid : str | None  原料批次二维码（Prototype 不扫码）
    operator_id     : int | None  操作工 ID
    is_prototype    : bool        True = 打样（连续模打样）
    work_order_id   : int | None  绑定工单 ID（自动推进工单状态为 RUNNING）

    返回
    ----
    {"code": 0/1, "message": str,
     "data": {"session_id": int, "machine_id": int, "session_type": str,
              "status": str, "start_time": str}}
    """
    now = datetime.datetime.now()

    if is_prototype:
        session_type = SESSION_TYPE_PROTOTYPE
        eq_next_status = EQ_STATUS_PROTOTYPING
    else:
        session_type = SESSION_TYPE_CONTINUOUS
        eq_next_status = EQ_STATUS_RUNNING

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 校验机台存在 ──────────────────────────────
            cur.execute("""
                SELECT id, current_status, equipment_code
                FROM equipments
                WHERE id = %s;
            """, (machine_id,))
            eq = cur.fetchone()
            if not eq:
                return {"code": 1, "message": f"机台 #{machine_id} 不存在", "data": None}

            # ── 2. 防呆：PENDING_REPORT 未结会话 ─────────────
            cur.execute("""
                SELECT id, session_type, operator_id
                FROM production_sessions
                WHERE machine_id = %s
                  AND status = %s
                FOR UPDATE;
            """, (machine_id, SESSION_PENDING_REPORT))
            pending = cur.fetchone()
            if pending:
                return {
                    "code": 1,
                    "message": (
                        f"机台 #{machine_id} 有未结会话（#{pending['id']}，"
                        f"状态 PENDING_REPORT），请先结账后再开启新会话"
                    ),
                    "data": None,
                }

            # ── 3. 防呆：RUNNING 未结会话 ──────────────────
            cur.execute("""
                SELECT id, session_type
                FROM production_sessions
                WHERE machine_id = %s
                  AND status = %s;
            """, (machine_id, SESSION_RUNNING))
            running = cur.fetchone()
            if running:
                return {
                    "code": 1,
                    "message": (
                        f"机台 #{machine_id} 已存在 RUNNING 会话（#{running['id']}，"
                        f"{running['session_type']}），不可重复开启"
                    ),
                    "data": None,
                }

            # ── 4. 防呆：PROTOTYPING 未结会话 ───────────────
            cur.execute("""
                SELECT id
                FROM production_sessions
                WHERE machine_id = %s
                  AND session_type = %s
                  AND status = %s;
            """, (machine_id, SESSION_TYPE_PROTOTYPE, SESSION_RUNNING))
            if cur.fetchone():
                return {
                    "code": 1,
                    "message": f"机台 #{machine_id} 已存在 PROTOTYPING 会话，不可重复开启",
                    "data": None,
                }

            # ── 5. 写入会话 ────────────────────────────────
            cur.execute("""
                INSERT INTO production_sessions
                    (machine_id, work_order_id, operator_id, material_qr_uid,
                     session_type, status, start_time,
                     reported_qty, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
                RETURNING id, machine_id, session_type, status, start_time;
            """, (
                machine_id,
                work_order_id,
                operator_id,
                material_qr_uid if session_type != SESSION_TYPE_PROTOTYPE else None,
                session_type,
                SESSION_RUNNING,
                now,
                now,
                now,
            ))
            row = cur.fetchone()

            # ── 5b. 绑定工单：推进工单状态为 RUNNING ─────────
            if work_order_id:
                cur.execute("""
                    UPDATE work_orders
                    SET order_status = 'RUNNING',
                        equipment_id = %s,
                        updated_at   = %s
                    WHERE id = %s
                      AND order_status IN ('PENDING', 'SCHEDULED')
                    RETURNING id;
                """, (machine_id, now, work_order_id))

            # ── 6. 更新机台状态 ─────────────────────────────
            cur.execute("""
                UPDATE equipments
                SET current_status = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (eq_next_status, now, machine_id))

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"会话开启成功（#{row['id']}，{session_type}），"
            f"机台 #{machine_id} 设为 {eq_next_status}"
        ),
        "data": {
            "session_id":    row["id"],
            "machine_id":   row["machine_id"],
            "session_type": row["session_type"],
            "status":      row["status"],
            "start_time":   row["start_time"].isoformat() if row["start_time"] else None,
        },
    }


# ============================================================================
# §8.1 结账会话（连续模专用）
# ============================================================================

def close_session(
    session_id: int,
    reported_qty: int,
    work_order_id: int | None = None,
) -> dict:
    """
    结账连续模会话（.cursorrules §8.1）。

    ⚠ 警告：本接口为连续模专用。
    简易模请勿调用此函数，使用 report_simple_production() 直报接口。

    执行链路（单事务）：
      1. 读取 RUNNING 会话（FOR UPDATE）
      2. 原料扣减（按 material_qr_uid）
      3. work_orders.wip_pcs += reported_qty
      4. production_sessions.status → CLOSED
      5. 机台 → IDLE
      6. conn.commit()

    参数
    ----
    session_id    : int         会话 ID
    reported_qty  : int         产出件数（必须 >= 0）
    work_order_id : int | None  工单 ID（用于料耗溯源，可空）

    返回
    ----
    {"code": 0/1, "message": str,
     "data": {"session_id": int, "session_type": str,
              "wip_added": int, "material_deducted_kg": float}}
    """
    if reported_qty < 0:
        return {"code": 1, "message": "产出件数不能为负数", "data": None}

    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 读取会话（乐观锁）────────────────────────
            cur.execute("""
                SELECT ps.id, ps.machine_id, ps.work_order_id,
                       ps.material_qr_uid, ps.operator_id,
                       ps.session_type, ps.status
                FROM production_sessions ps
                WHERE ps.id = %s
                FOR UPDATE;
            """, (session_id,))
            session = cur.fetchone()
            if not session:
                return {"code": 1, "message": f"会话 #{session_id} 不存在", "data": None}
            if session["status"] != SESSION_RUNNING:
                return {
                    "code": 1,
                    "message": f"会话状态为【{session['status']}】，仅 RUNNING 会话可结账",
                    "data": None,
                }

            # ── 2. 简易模禁止走此接口（防护性校验）────────────
            if session["session_type"] == SESSION_TYPE_SIMPLE:
                return {
                    "code": 1,
                    "message": "简易模请使用 report_simple_production() 直报接口，禁止调用 close_session()",
                    "data": None,
                }

            session_type = session["session_type"]
            is_prototype = session_type == SESSION_TYPE_PROTOTYPE

            # ── 3. 读取工单参数（用于料耗）──────────────────
            wo_id = work_order_id or session.get("work_order_id")
            wo_part_id = 0
            wo_mold_id = None
            if wo_id:
                cur.execute("""
                    SELECT id, part_id, mold_id
                    FROM work_orders
                    WHERE id = %s
                    FOR UPDATE;
                """, (wo_id,))
                wo = cur.fetchone()
                if wo:
                    wo_part_id = int(wo["part_id"] or 0)
                    wo_mold_id = wo["mold_id"]

            # ── 4. 原料扣减（Prototype 不扣料）─────────────
            mat_deducted_kg = 0.0
            if not is_prototype and session["material_qr_uid"] and reported_qty > 0:
                mat_deducted_kg = _deduct_material_by_qr_uid(
                    cur, session["material_qr_uid"],
                    reported_qty, wo_id, wo_part_id, wo_mold_id, now,
                )

            # ── 5. wip_pcs 累加（Prototype 不入 wip）────────
            wip_added = 0
            if not is_prototype and wo_id:
                wip_added = reported_qty
                cur.execute("""
                    UPDATE work_orders
                    SET wip_pcs = wip_pcs + %s,
                        updated_at = %s
                    WHERE id = %s;
                """, (wip_added, now, wo_id))

            # ── 6. 会话 CLOSED ─────────────────────────────
            cur.execute("""
                UPDATE production_sessions
                SET status       = %s,
                    end_time    = %s,
                    reported_qty = %s,
                    updated_at  = %s
                WHERE id = %s;
            """, (SESSION_CLOSED, now, reported_qty, now, session_id))

            # ── 7. 机台 → IDLE ─────────────────────────────
            cur.execute("""
                UPDATE equipments
                SET current_status = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (EQ_STATUS_IDLE, now, session["machine_id"]))

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"会话 #{session_id}（{session_type}）结账成功。"
            + (f"产出 {reported_qty} 件 → 待检 +{wip_added}" if not is_prototype else "打样不计料耗，不入待检")
            + (f"（原料扣减 {mat_deducted_kg:.4f} kg）" if mat_deducted_kg > 0 else "")
        ),
        "data": {
            "session_id":            session_id,
            "session_type":        session_type,
            "wip_added":           wip_added,
            "material_deducted_kg": mat_deducted_kg,
        },
    }


# ============================================================================
# §8.1 简易模直报（组长下班事后录入，不碰机台状态）
# ============================================================================

def report_simple_production(
    machine_id: int,
    material_batch_id: int,
    work_order_id: int,
    qty: int,
    leader_id: int | None = None,
) -> dict:
    """
    简易模组长下班直报（.cursorrules §8.1 简易模专项）。

    ⚠ 核心特征：无需起机，不改机台状态，不扫材料码。

    执行链路（单事务）：
      1. 校验工单存在，读取 part_id / mold_id
      2. 读取 material_batches（按主键 id），拿到 qr_uid 用于扣重
      3. INSERT production_sessions
         （session_type='Simple', status='CLOSED', reported_qty=qty）
      4. 原料扣减（按 material_batch_id 主键查 qr_uid 再扣重）
      5. work_orders.wip_pcs += qty
      6. conn.commit()

    不触碰：
      - equipments.current_status（机台状态保持不变）
      - 机台 RUNNING / IDLE 等任何状态

    参数
    ----
    machine_id       : int  机台 ID（仅作记录用，不改机台状态）
    material_batch_id : int  材料批次主键 ID（用于查 qr_uid 扣重）
    work_order_id    : int  工单 ID（必须，溯源用）
    qty             : int  产出件数（必须 >= 0）
    leader_id       : int | None 组长用户 ID（来自 session）

    返回
    ----
    {"code": 0/1, "message": str,
     "data": {"session_id": int, "qty": int, "wip_added": int,
              "material_deducted_kg": float}}
    """
    if qty < 0:
        return {"code": 1, "message": "产出件数不能为负数", "data": None}

    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 校验工单存在 ─────────────────────────────
            cur.execute("""
                SELECT id, part_id, mold_id, order_status, wip_pcs
                FROM work_orders
                WHERE id = %s
                FOR UPDATE;
            """, (work_order_id,))
            wo = cur.fetchone()
            if not wo:
                return {"code": 1, "message": f"工单 #{work_order_id} 不存在", "data": None}

            wo_part_id = int(wo["part_id"] or 0)
            wo_mold_id = wo["mold_id"]

            # ── 2. 按主键读取材料批次（获取 qr_uid）───────────
            cur.execute("""
                SELECT id, qr_uid, current_weight
                FROM material_batches
                WHERE id = %s;
            """, (material_batch_id,))
            mat_row = cur.fetchone()
            if not mat_row:
                return {"code": 1, "message": f"材料批次 #{material_batch_id} 不存在", "data": None}

            qr_uid = mat_row["qr_uid"]

            # ── 3. 原料扣减（同一事务内）────────────────────
            mat_deducted_kg = 0.0
            if qr_uid and qty > 0:
                mat_deducted_kg = _deduct_material_by_qr_uid(
                    cur, qr_uid, qty, work_order_id,
                    wo_part_id, wo_mold_id, now,
                )

            # ── 4. 写入会话（直接 CLOSED，无需起机）──────────
            cur.execute("""
                INSERT INTO production_sessions
                    (machine_id, work_order_id, operator_id,
                     material_qr_uid, session_type, status,
                     start_time, end_time, reported_qty,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                machine_id,
                work_order_id,
                leader_id,
                qr_uid,
                SESSION_TYPE_SIMPLE,
                SESSION_CLOSED,
                now,     # start_time = now（组长下班时间视为起止时刻）
                now,     # end_time = now（直报，一口价完成）
                qty,
                now,
                now,
            ))
            session_id = int(cur.fetchone()["id"])

            # ── 5. wip_pcs 累加 ────────────────────────────
            cur.execute("""
                UPDATE work_orders
                SET wip_pcs = wip_pcs + %s,
                    updated_at = %s
                WHERE id = %s;
            """, (qty, now, work_order_id))

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"简易模直报成功：工单 #{work_order_id}，产出 {qty} 件 → 待检 +{qty}。"
            + (f"（原料扣减 {mat_deducted_kg:.4f} kg）" if mat_deducted_kg > 0 else "")
        ),
        "data": {
            "session_id":            session_id,
            "qty":                  qty,
            "wip_added":            qty,
            "material_deducted_kg": mat_deducted_kg,
        },
    }


# ============================================================================
# §8.1 原料扣减辅助函数（按 qr_uid）
# ============================================================================

def _deduct_material_by_qr_uid(
    cur,
    qr_uid: str,
    reported_qty: int,
    wo_id: int | None,
    wo_part_id: int,
    wo_mold_id: int | None,
    now: datetime.datetime,
) -> float:
    """
    原料扣减辅助函数（在同一数据库事务中调用，使用传入的 cursor）。

    原料扣减量 = strokes × per_stroke_kg
    其中 strokes = reported_qty / cavity_count

    注意：此函数在 close_session 和 report_simple_production 事务内部被调用，
          使用传入的 cursor（不自己创建连接）。
    """
    from app.services.prod_service import get_stroke_consumption_rate

    if not qr_uid:
        return 0.0

    per_stroke_kg = 0.0
    cavity_count = 1
    if wo_part_id > 0:
        per_stroke_kg, cavity_count = get_stroke_consumption_rate(
            part_id=wo_part_id,
            mold_id=wo_mold_id,
        )

    if per_stroke_kg <= 0:
        return 0.0

    strokes = reported_qty // cavity_count if cavity_count > 0 else reported_qty
    consumed_kg = round(per_stroke_kg * strokes, 6)
    if consumed_kg <= 0:
        return 0.0

    # 原子扣减
    cur.execute("""
        SELECT current_weight FROM material_batches
        WHERE qr_uid = %s
        FOR UPDATE;
    """, (qr_uid,))
    row = cur.fetchone()
    if not row:
        return 0.0

    prev_weight = float(row[0] or 0)
    new_weight = max(0.0, prev_weight - consumed_kg)

    cur.execute("""
        UPDATE material_batches
        SET current_weight = %s,
            lifecycle_status = CASE WHEN %s <= 0 THEN 'DEPLETED' ELSE lifecycle_status END,
            updated_at = %s
        WHERE qr_uid = %s;
    """, (new_weight, new_weight, now, qr_uid))

    # 记录流水
    cur.execute("""
        INSERT INTO material_transactions
            (qr_uid, transaction_type, weight_change, current_balance,
             related_work_order_id, created_at)
        VALUES (%s, 'CONSUME', %s, %s, %s, %s);
    """, (qr_uid, -consumed_kg, new_weight, wo_id, now))

    return consumed_kg


# ============================================================================
# §8.1 强制接班（将旧会话 ABNORMAL_TERMINATED，含 PROTOTYPING）
# ============================================================================

def force_takeover_session(
    machine_id: int,
    new_operator_id: int,
) -> dict:
    """
    强制接班逻辑。

    将机台上所有活跃会话（含 PROTOTYPING）标记为 ABNORMAL_TERMINATED，
    并开启新会话（Continuous）。

    场景：换班、工人紧急离岗、主管临时指派。

    参数
    ----
    machine_id      : int  机台 ID
    new_operator_id : int  新接班人用户 ID

    返回
    ----
    {"code": 0/1, "message": str,
     "data": {"terminated_session_ids": list[int],
              "new_session_id": int}}
    """
    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 找该机台所有活跃会话（含 PROTOTYPING）─────
            cur.execute("""
                SELECT id, session_type, status
                FROM production_sessions
                WHERE machine_id = %s
                  AND status IN (%s, %s)
                FOR UPDATE;
            """, (machine_id, SESSION_RUNNING, SESSION_PENDING_REPORT))
            active = cur.fetchall()

            terminated_ids = []
            for s in active:
                terminated_ids.append(int(s["id"]))
                cur.execute("""
                    UPDATE production_sessions
                    SET status   = %s,
                        end_time = %s,
                        updated_at = %s
                    WHERE id = %s;
                """, (SESSION_ABNORMAL_TERMINATED, now, now, s["id"]))

            # ── 2. 开启新 Continuous 会话 ─────────────────
            cur.execute("""
                INSERT INTO production_sessions
                    (machine_id, operator_id, material_qr_uid,
                     session_type, status, start_time,
                     reported_qty, created_at, updated_at)
                VALUES (%s, %s, NULL, %s, %s, %s, 0, %s, %s)
                RETURNING id, session_type, status, start_time;
            """, (
                machine_id,
                new_operator_id,
                SESSION_TYPE_CONTINUOUS,
                SESSION_RUNNING,
                now,
                now,
                now,
            ))
            new_session = cur.fetchone()

            # ── 3. 机台 → RUNNING ──────────────────────────
            cur.execute("""
                UPDATE equipments
                SET current_status = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (EQ_STATUS_RUNNING, now, machine_id))

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"强制接班完成。"
            + (f"旧会话 {terminated_ids} 已标记为 ABNORMAL_TERMINATED。" if terminated_ids else "")
            + f"新会话 #{new_session['id']}（Continuous）已开启（operator=#{new_operator_id}）"
        ),
        "data": {
            "terminated_session_ids": terminated_ids,
            "new_session_id": new_session["id"],
        },
    }


def force_takeover(
    machine_id: int,
    new_operator_id: int,
) -> dict:
    """
    接班防呆 — 将机台旧会话强制 ABNORMAL_TERMINATED（.cursorrules §8.1）。

    执行链路（单事务）：
      1. 找到机台上 PENDING_REPORT / RUNNING 的旧会话
      2. 批量 UPDATE → ABNORMAL_TERMINATED（含 end_time）
      3. 开启新 Continuous 会话
      4. 机台状态 → RUNNING
      5. conn.commit()
    """
    return force_takeover_session(machine_id, new_operator_id)


# ============================================================================
# 辅助查询
# ============================================================================

def get_session_by_machine(machine_id: int) -> list[dict]:
    """查询某机台最近 20 条会话。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ps.*,
                       u.username AS operator_name,
                       wo.order_no AS work_order_no
                FROM production_sessions ps
                LEFT JOIN users u ON u.id = ps.operator_id
                LEFT JOIN work_orders wo ON wo.id = ps.work_order_id
                WHERE ps.machine_id = %s
                ORDER BY ps.created_at DESC
                LIMIT 20;
            """, (machine_id,))
            return [dict(r) for r in cur.fetchall()]


def get_active_session_by_machine(machine_id: int) -> dict | None:
    """查询某机台当前活跃会话（RUNNING 或 PENDING_REPORT）。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ps.*,
                       u.username AS operator_name
                FROM production_sessions ps
                LEFT JOIN users u ON u.id = ps.operator_id
                WHERE ps.machine_id = %s
                  AND ps.status IN (%s, %s)
                ORDER BY ps.created_at DESC
                LIMIT 1;
            """, (machine_id, SESSION_RUNNING, SESSION_PENDING_REPORT))
            row = cur.fetchone()
            return dict(row) if row else None
