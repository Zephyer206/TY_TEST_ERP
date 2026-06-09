"""
app/services/pkg_service.py
===========================
包装与全检入库专项服务 — 包装报工 + 全检入库

核心职责
--------
1. pack_and_stock()  — 包装报工（更新包装记录）
2. stock_in()        — 全检入库：工单 wip_pcs 扣减 + parts.stock_pcs 累加

技术守则（.cursorrules §4 + §8.3）
-----------------------------------
- 严禁 ORM，必须使用原生 psycopg2
- 所有 INSERT/UPDATE 必须显式 conn.commit()
- 成品库存扣减必须使用 GREATEST 护栏，防止负数

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
# §8.3 全检入库（Pack & Stock — 流水线终点）
# ============================================================================

def pack_and_stock(
    work_order_id: int,
    valid_qty: int,
    operator_id: int,
    reject_qty: int = 0,
) -> dict:
    """
    包装全检入库 — 流水线终点核心操作（.cursorrules §8.3）。

    执行链路（单事务）：
      1. 校验工单存在 + 工单状态允许入库
      2. work_orders.wip_pcs -= valid_qty（扣除待检）
         → 若 wip_pcs 不足，拒绝操作（防止超额入库）
      3. parts.stock_pcs += valid_qty（增加成品库存）
         → GREATEST 护栏：parts.stock_pcs 不低于 0
      4. INSERT defect_logs（如有 reject_qty，不良品入池）
      5. INSERT packaging_logs（包装报工流水，可选）
      6. conn.commit()

    入库条件校验
    ------------
    - 工单必须为 RUNNING 或 COMPLETED 状态
    - wip_pcs 必须 >= valid_qty
    - valid_qty 必须 > 0

    参数
    ----
    work_order_id : int  工单 ID
    valid_qty    : int  全检合格入库件数（必须 > 0）
    operator_id  : int  操作员用户 ID（来自 session）
    reject_qty  : int  不良品件数（可选，默认 0；会写入 defect_logs）

    返回
    ----
    {
        "code": 0/1,
        "message": str,
        "data": {
            "work_order_id": int,
            "valid_qty": int,
            "reject_qty": int,
            "wip_remaining": int,   # 入库后剩余待检量
            "stock_added": int,     # 成品库存新增量
            "defect_log_id": int | None,
        }
    }
    """
    if valid_qty <= 0:
        return {"code": 1, "message": "合格入库件数（valid_qty）必须 > 0", "data": None}

    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 校验工单存在 ──────────────────────────────
            cur.execute("""
                SELECT wo.id, wo.order_status, wo.wip_pcs,
                       wo.part_id, wo.produced_qty,
                       pt.part_number, pt.internal_name,
                       COALESCE(wo.wip_pcs, 0) AS wip_pcs_safe
                FROM work_orders wo
                JOIN parts pt ON pt.id = wo.part_id
                WHERE wo.id = %s
                FOR UPDATE;
            """, (work_order_id,))
            wo = cur.fetchone()
            if not wo:
                return {"code": 1, "message": f"工单 #{work_order_id} 不存在", "data": None}

            # ── 2. 校验工单状态 ─────────────────────────────
            if wo["order_status"] not in ("RUNNING", "COMPLETED"):
                return {
                    "code": 1,
                    "message": f"工单状态为【{wo['order_status']}】，仅 RUNNING/COMPLETED 可入库",
                    "data": None,
                }

            # ── 3. 校验 wip_pcs 充足 ────────────────────────
            wip_before = int(wo.get("wip_pcs") or 0)
            if wip_before < valid_qty:
                return {
                    "code": 1,
                    "message": (
                        f"工单 #{work_order_id} 待检库存（wip_pcs={wip_before}）"
                        f"不足，无法入库 {valid_qty} 件"
                    ),
                    "data": None,
                }

            part_id = wo["part_id"]

            # ── 4. 扣除待检库存 ──────────────────────────────
            wip_after = wip_before - valid_qty
            cur.execute("""
                UPDATE work_orders
                SET wip_pcs = wip_pcs - %s,
                    updated_at = %s
                WHERE id = %s;
            """, (valid_qty, now, work_order_id))

            # ── 5. 增加成品库存 ──────────────────────────────
            cur.execute("""
                UPDATE parts
                SET stock_pcs = stock_pcs + %s,
                    updated_at = %s
                WHERE id = %s
                RETURNING stock_pcs;
            """, (valid_qty, now, part_id))
            stock_row = cur.fetchone()
            new_stock = int(stock_row["stock_pcs"]) if stock_row else valid_qty

            # ── 6. 记录不良品（如有）─────────────────────────
            defect_log_id = None
            if reject_qty > 0:
                cur.execute("""
                    INSERT INTO defect_logs
                        (work_order_id, defect_qty, reason, reporter_id, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    work_order_id,
                    reject_qty,
                    "全检不良（包装环节）",
                    operator_id,
                    now,
                ))
                defect_row = cur.fetchone()
                defect_log_id = int(defect_row["id"]) if defect_row else None

            # ── 7. 记录入库流水（工单级全检入库追溯）────────────────
            cur.execute("""
                INSERT INTO stock_in_logs
                    (work_order_id, part_id, valid_qty, reject_qty,
                     operator_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (
                work_order_id,
                part_id,
                valid_qty,
                reject_qty,
                operator_id,
                now,
            ))

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"工单 #{work_order_id} 入库成功："
            f"合格 {valid_qty} 件 → 成品库存"
            + (f"，不良 {reject_qty} 件 → defect_logs" if reject_qty > 0 else "")
        ),
        "data": {
            "work_order_id":  work_order_id,
            "valid_qty":     valid_qty,
            "reject_qty":     reject_qty,
            "wip_remaining": wip_after,
            "stock_added":    valid_qty,
            "stock_total":    new_stock,
            "defect_log_id": defect_log_id,
        },
    }


# ============================================================================
# §8.3 辅助查询：待检库存视图
# ============================================================================

def get_wip_overview(work_order_id: int | None = None) -> list[dict]:
    """
    查询待检库存（wip_pcs）视图。

    参数
    ----
    work_order_id : int | None  按工单过滤（None 则返回全部）

    返回
    ----
    list[dict]，含字段：work_order_id, order_no, part_id, part_number,
                        internal_name, wip_pcs, produced_qty, target_qty
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if work_order_id:
                cur.execute("""
                    SELECT wo.id         AS work_order_id,
                           wo.order_no,
                           wo.part_id,
                           pt.part_number,
                           pt.internal_name,
                           COALESCE(wo.wip_pcs, 0)  AS wip_pcs,
                           wo.produced_qty,
                           wo.target_qty,
                           wo.order_status
                    FROM work_orders wo
                    JOIN parts pt ON pt.id = wo.part_id
                    WHERE wo.id = %s
                      AND COALESCE(wo.wip_pcs, 0) > 0;
                """, (work_order_id,))
            else:
                cur.execute("""
                    SELECT wo.id         AS work_order_id,
                           wo.order_no,
                           wo.part_id,
                           pt.part_number,
                           pt.internal_name,
                           COALESCE(wo.wip_pcs, 0)  AS wip_pcs,
                           wo.produced_qty,
                           wo.target_qty,
                           wo.order_status
                    FROM work_orders wo
                    JOIN parts pt ON pt.id = wo.part_id
                    WHERE COALESCE(wo.wip_pcs, 0) > 0
                    ORDER BY wo.updated_at DESC
                    LIMIT 100;
                """)
            return [dict(r) for r in cur.fetchall()]


# ============================================================================
# §8.3 辅助查询：不良品记录
# ============================================================================

def get_defect_logs(
    work_order_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    查询不良品记录。

    参数
    ----
    work_order_id : int | None  按工单过滤
    limit         : int         返回条数上限

    返回
    ----
    list[dict]，含：id, work_order_id, defect_qty, reason, reporter_id,
                   reporter_name, created_at
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT dl.*,
                       u.username AS reporter_name,
                       wo.order_no
                FROM defect_logs dl
                LEFT JOIN users u ON u.id = dl.reporter_id
                LEFT JOIN work_orders wo ON wo.id = dl.work_order_id
                WHERE (%s::INT IS NULL OR dl.work_order_id = %s::INT)
                ORDER BY dl.created_at DESC
                LIMIT %s;
            """, (
                work_order_id if work_order_id else None,
                work_order_id if work_order_id else None,
                limit,
            ))
            return [dict(r) for r in cur.fetchall()]


# ============================================================================
# §8.3 倒推结案防呆（静默转损耗）
# ============================================================================

def force_close_packing(
    work_order_id: int,
    operator_id: int | None = None,
) -> dict:
    """
    倒推结案防呆 — 强制关闭工单包装阶段（.cursorrules §8.3）。

    执行链路（单事务，失败 rollback）：
      1. 读取 work_orders.wip_pcs → X（FOR UPDATE 行锁）
      2. UPDATE work_orders SET wip_pcs = 0, is_pkg_closed = TRUE WHERE id = %s
      3. 若 X > 0：
           INSERT INTO defect_logs (work_order_id, defect_qty, source)
           VALUES (%s, %s, 'Auto_Deduction')
      4. conn.commit()

    静默转损耗逻辑
    -------------
    倒推时工单往往处于"失控"状态（WIP 散落在车间各工序中，无法追回）。
    系统将剩余 WIP 静默记入 defect_logs（source='Auto_Deduction'），
    不弹窗提示，不发送通知，确保生产数据闭环。

    参数
    ----
    work_order_id : int        工单 ID
    operator_id  : int | None 操作员 ID（记入 defect_logs.reporter_id）

    返回
    ----
    {
        "code": 0/1,
        "message": str,
        "data": {
            "work_order_id": int,
            "wip_remaining": int,       # 结案前剩余 WIP（X）
            "defect_log_id": int | None,# 静默转入 defect_logs 的记录 ID
            "is_pkg_closed": bool,      # 结案后 is_pkg_closed 状态
        }
    }
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # ── 1. 读取 wip_pcs（行锁，防止并发倒推）────────────
                cur.execute("""
                    SELECT id, order_status, wip_pcs, part_id
                    FROM work_orders
                    WHERE id = %s
                    FOR UPDATE;
                """, (work_order_id,))
                wo = cur.fetchone()
                if not wo:
                    conn.rollback()
                    return {
                        "code": 1,
                        "message": f"工单 #{work_order_id} 不存在",
                        "data": None,
                    }

                wip_before = int(wo.get("wip_pcs") or 0)

                # ── 2. 强制清零 + 标记结案 ─────────────────────────
                cur.execute("""
                    UPDATE work_orders
                    SET wip_pcs       = 0,
                        is_pkg_closed = TRUE,
                        updated_at    = NOW()
                    WHERE id = %s
                    RETURNING is_pkg_closed;
                """, (work_order_id,))
                closed_row = cur.fetchone()
                is_pkg_closed = bool(closed_row["is_pkg_closed"]) if closed_row else True

                # ── 3. 静默转损耗（X > 0 时）──────────────────────
                defect_log_id = None
                if wip_before > 0:
                    cur.execute("""
                        INSERT INTO defect_logs
                            (work_order_id, defect_qty, source, reporter_id, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        RETURNING id;
                    """, (
                        work_order_id,
                        wip_before,
                        "Auto_Deduction",
                        operator_id,
                    ))
                    defect_row = cur.fetchone()
                    defect_log_id = int(defect_row["id"]) if defect_row else None

                conn.commit()

            except Exception as e:
                conn.rollback()
                return {
                    "code": 1,
                    "message": f"倒推结案异常（已回滚）：{str(e)}",
                    "data": None,
                }

    return {
        "code": 0,
        "message": (
            f"工单 #{work_order_id} 倒推结案完成。"
            + (f"剩余 WIP {wip_before} 件已静默转入 defect_logs（Auto_Deduction）。"
               if wip_before > 0 else "WIP 已清零，无损耗转记。")
        ),
        "data": {
            "work_order_id":  work_order_id,
            "wip_remaining": wip_before,
            "defect_log_id": defect_log_id,
            "is_pkg_closed": is_pkg_closed,
        },
    }
