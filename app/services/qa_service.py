"""
app/services/qa_service.py
===========================
品质与审计专项服务 — 常规首件放行 + 强行特赦（EMERGENCY_RELEASE）

核心职责
--------
1. release_first_piece()   — 常规首件放行，更新工单 qa_status = PASSED
2. emergency_release()      — 强行特赦：无视原状态解锁报工限制，同事务写入 qa_audit_logs

技术守则（.cursorrules §4）
---------------------------
- 严禁 ORM，必须使用原生 psycopg2
- 所有 INSERT/UPDATE 必须显式 conn.commit()
- 敏感逻辑严禁放在前端

目录归属：app/services/
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import datetime

from app.models.constants import QA_ACTION_FIRST_PIECE, QA_ACTION_EMERGENCY
from app.services.db_service import DB_CONFIG


# ============================================================================
# §8.1 常规首件放行
# ============================================================================

def approve_first_piece(work_order_id: int, inspector_id: int) -> dict:
    """
    常规首件合格，解除工单报工锁定。

    执行链路：
      1. 校验工单存在
      2. 校验当前未放行（防止重复放行）
      3. UPDATE work_orders SET first_piece_passed_at = NOW(), first_piece_passed_by = inspector_id
      4. INSERT qa_audit_logs（记录常规放行动作）
      5. conn.commit()

    参数
    ----
    work_order_id : int  工单 ID
    inspector_id  : int  检验员用户 ID（来自 session）

    返回
    ----
    {
        "code": 0/1,
        "message": str,
        "data": {
            "work_order_id": int,
            "released_at": datetime,
        }
    }
    """
    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 校验工单存在 ────────────────────────────────
            cur.execute("""
                SELECT id, order_status,
                       first_piece_passed_at,
                       is_first_piece_required
                FROM work_orders
                WHERE id = %s
                FOR UPDATE;
            """, (work_order_id,))
            wo = cur.fetchone()
            if not wo:
                return {"code": 1, "message": f"工单 #{work_order_id} 不存在", "data": None}

            # ── 2. 防止重复放行 ───────────────────────────────
            if wo.get("first_piece_passed_at"):
                return {
                    "code": 1,
                    "message": f"工单 #{work_order_id} 已完成首件放行（{wo['first_piece_passed_at']}），禁止重复操作",
                    "data": None,
                }

            # ── 3. 更新工单首件状态 ────────────────────────────
            cur.execute("""
                UPDATE work_orders
                SET first_piece_passed_at = %s,
                    first_piece_passed_by = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (now, inspector_id, now, work_order_id))

            # ── 4. 写入 QA 审计日志 ──────────────────────────
            cur.execute("""
                INSERT INTO qa_audit_logs
                    (work_order_id, operator_id, action_type, reason, created_at)
                VALUES (%s, %s, %s, %s, %s);
            """, (
                work_order_id,
                inspector_id,
                QA_ACTION_FIRST_PIECE,
                "常规首件放行",
                now,
            ))

            conn.commit()

    return {
        "code": 0,
        "message": f"工单 #{work_order_id} 首件放行成功",
        "data": {
            "work_order_id": work_order_id,
            "released_at": now.isoformat(),
        },
    }


# ============================================================================
# §8.1 强行特赦放行（Emergency Release）
# ============================================================================

def emergency_release(
    work_order_id: int,
    machine_id: int | None,
    admin_id: int,
    reason: str,
) -> dict:
    """
    强行特赦逻辑（EMERGENCY_RELEASE）。

    业务场景：首件检验未完成或品质存疑，但因紧急交期等特殊原因，
    由管理员（如 admin）强行解锁报工限制。

    执行链路（单事务）：
      1. 校验工单存在
      2. 强制 SET first_piece_passed_at = NOW()（绕过常规状态校验）
      3. INSERT qa_audit_logs（记录特赦动作，含原因）
      4. conn.commit()

    注意
    ----
    - 不校验 is_first_piece_required — 特赦逻辑可作用于任何工单
    - reason 字段必须记录，审计黑匣子不留白
    - 此操作不修改工单状态（order_status），仅解除首件卡控

    参数
    ----
    work_order_id : int        工单 ID
    machine_id    : int | None 关联机台 ID（可选，用于日志说明）
    admin_id      : int        操作管理员 ID（必须）
    reason        : str        特赦原因（必须，不能为空）

    返回
    ----
    {
        "code": 0/1,
        "message": str,
        "data": {
            "work_order_id": int,
            "released_at": datetime,
            "audit_log_id": int,
        }
    }
    """
    if not reason or not reason.strip():
        return {"code": 1, "message": "特赦原因（reason）不能为空", "data": None}

    if not admin_id:
        return {"code": 1, "message": "操作管理员 ID（admin_id）不能为空", "data": None}

    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 校验工单存在 ────────────────────────────────
            cur.execute("""
                SELECT id, order_status, part_id
                FROM work_orders
                WHERE id = %s
                FOR UPDATE;
            """, (work_order_id,))
            wo = cur.fetchone()
            if not wo:
                return {"code": 1, "message": f"工单 #{work_order_id} 不存在", "data": None}

            # ── 2. 强制解锁首件限制 ─────────────────────────────
            cur.execute("""
                UPDATE work_orders
                SET first_piece_passed_at = %s,
                    first_piece_passed_by = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (now, admin_id, now, work_order_id))

            # ── 3. 写入 QA 审计黑匣子（必须记录原因）──────────
            cur.execute("""
                INSERT INTO qa_audit_logs
                    (work_order_id, machine_id, operator_id,
                     action_type, reason, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                work_order_id,
                machine_id,
                admin_id,
                QA_ACTION_EMERGENCY,
                reason.strip(),
                now,
            ))
            audit_id = cur.fetchone()["id"]

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"工单 #{work_order_id} 已强制特赦放行。"
            f"原因：{reason.strip()}"
        ),
        "data": {
            "work_order_id": work_order_id,
            "released_at": now.isoformat(),
            "audit_log_id": audit_id,
        },
    }


# ============================================================================
# 辅助查询：读取 QA 审计记录（支持溯源）
# ============================================================================

def get_qa_audit_logs(
    work_order_id: int | None = None,
    action_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    读取 QA 审计记录（黑匣子查询接口）。

    参数
    ----
    work_order_id : int | None  按工单过滤
    action_type   : str | None  按动作类型过滤（如 EMERGENCY_RELEASE）
    limit         : int         返回条数上限，默认 50

    返回
    ----
    list[dict]，每条含：id, work_order_id, machine_id, operator_id,
                         action_type, reason, created_at
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            sql = """
                SELECT qal.*,
                       u.username AS operator_name
                FROM qa_audit_logs qal
                LEFT JOIN users u ON u.id = qal.operator_id
            """
            params = []
            conditions = []
            if work_order_id is not None:
                conditions.append("qal.work_order_id = %s")
                params.append(work_order_id)
            if action_type is not None:
                conditions.append("qal.action_type = %s")
                params.append(action_type)

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            sql += " ORDER BY qal.created_at DESC LIMIT %s;"
            params.append(limit)

            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
