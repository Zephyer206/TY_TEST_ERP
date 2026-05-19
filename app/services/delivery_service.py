"""
app/services/delivery_service.py
================================
成品发货与客户件号映射引擎（§8.3）

核心职责
--------
1. 发货明细查询：强制关联 part_customer_aliases，无别名时标记 PENDING_CONFIG
2. 发货确认：扣减 parts.stock_pcs，全事务原子操作

技术守则（§4）
--------------
- 严禁 ORM，必须原生 psycopg2
- 所有写操作必须显式 conn.commit()
- 敏感计算严禁放在前端
- 查询接口按常量文件定义的状态值过滤
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from app.models.constants import (
    DN_STATUS_SHIPPED,
    DN_STATUS_DELIVERED,
    DN_STATUS_CANCELLED,
)


# ============================================================================
# §8.3 查询：带客户件号翻译的发货明细（含别名状态感知）
# ============================================================================

def get_delivery_items(dn_id: int, customer_name: str) -> list[dict]:
    """
    发货明细（含客户件号翻译 + 别名状态感知，§8.3 核心实现）。

    别名状态枚举（alias_status）：
      ALIAS_OK        — 别名已配置，正常展示客户件号
      PENDING_CONFIG  — 无别名配置，强制标记，不得直接显示内部 ID
      INTERNAL_ONLY   — 内部件（无客户映射需求）

    参数
    ----
    dn_id         : int   发货单 ID
    customer_name : str   客户名称（用于匹配 part_customer_aliases.customer_name）

    返回
    ----
    list[dict]，每个 dict 包含：
      delivery_item_id, part_id, internal_part_no, internal_name,
      display_part_no, display_name, qty, lot_no, remark, alias_status
    """
    with psycopg2.connect(**_db_config()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    di.id                                 AS delivery_item_id,
                    di.qty,
                    di.lot_no,
                    di.remark,
                    pt.id                                 AS part_id,
                    pt.part_number                        AS internal_part_no,
                    pt.internal_name,
                    COALESCE(pca.customer_part_no, NULL) AS alias_part_no,
                    COALESCE(pca.customer_part_name, NULL) AS alias_name,
                    CASE
                        WHEN pca.id IS NOT NULL THEN 'ALIAS_OK'
                        ELSE 'PENDING_CONFIG'
                    END                                   AS alias_status
                FROM delivery_items di
                JOIN parts pt ON di.part_id = pt.id
                LEFT JOIN part_customer_aliases pca
                    ON pca.part_id = pt.id
                    AND pca.customer_name = %s
                WHERE di.dn_id = %s
                ORDER BY di.id;
            """, (customer_name, dn_id))
            rows = cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        alias_status = d.get("alias_status") or "PENDING_CONFIG"

        if alias_status == "ALIAS_OK":
            display_part_no = d.get("alias_part_no") or d.get("internal_part_no", "")
            display_name   = d.get("alias_name") or d.get("internal_name", "")
        else:
            display_part_no = None
            display_name   = None

        result.append({
            "delivery_item_id": d.get("delivery_item_id"),
            "part_id":         d.get("part_id"),
            "internal_part_no": d.get("internal_part_no", ""),
            "internal_name":   d.get("internal_name", ""),
            "display_part_no": display_part_no,
            "display_name":   display_name,
            "qty":            d.get("qty", 0),
            "lot_no":         d.get("lot_no"),
            "remark":         d.get("remark"),
            "alias_status":   alias_status,
        })

    return result


def get_delivery_note_status(dn_id: int) -> dict | None:
    """
    读取发货单主档状态（用于确认前的校验）。
    """
    with psycopg2.connect(**_db_config()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, status, customer_name, shipped_at, operator_id
                FROM delivery_notes
                WHERE id = %s;
            """, (dn_id,))
            row = cur.fetchone()
            return dict(row) if row else None


# ============================================================================
# §8.3 发货确认：原子扣库 + 状态更新
# ============================================================================

def confirm_delivery(dn_id: int, operator_id: int) -> dict:
    """
    发货确认（§8.3 完整实现）。

    执行链路：
      1. 校验发货单状态（必须为 SHIPPED）
      2. 读取发货明细，计算总扣库量
      3. 批量 UPDATE parts.stock_pcs（GREATEST 护栏）
      4. 批量 INSERT material_transactions（发货流水）
      5. UPDATE delivery_notes → DELIVERED（时间戳）
      6. 全事务统一 commit

    参数
    ----
    dn_id       : int   发货单 ID
    operator_id : int   操作人用户 ID

    返回
    ----
    {
        "code": 0/1,
        "message": str,
        "data": {
            "dn_id": int,
            "total_shipped": int,
            "items_processed": int,
        }
    }
    """
    with psycopg2.connect(**_db_config()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 校验发货单状态 ───────────────────────────
            cur.execute("""
                SELECT id, status, customer_name
                FROM delivery_notes
                WHERE id = %s
                FOR UPDATE;
            """, (dn_id,))
            dn = cur.fetchone()
            if not dn:
                return {"code": 1, "message": f"发货单 #{dn_id} 不存在", "data": None}
            if dn["status"] != DN_STATUS_SHIPPED:
                return {
                    "code": 1,
                    "message": f"发货单状态为【{dn['status']}】，仅 SHIPPED 可确认发货",
                    "data": None,
                }

            customer_name = dn.get("customer_name") or ""

            # ── 2. 读取发货明细 ───────────────────────────
            cur.execute("""
                SELECT di.id AS item_id, di.part_id, di.qty
                FROM delivery_items di
                WHERE di.dn_id = %s;
            """, (dn_id,))
            items = cur.fetchall()
            if not items:
                return {"code": 1, "message": "发货单无明细，无法发货", "data": None}

            # ── 3. 批量扣减成品库存 ───────────────────────
            total_shipped = 0
            for item in items:
                part_id = int(item["part_id"])
                qty     = int(item["qty"])

                # 护栏：stock_pcs 不得低于 0
                cur.execute("""
                    UPDATE parts
                    SET stock_pcs = GREATEST(0, stock_pcs - %s),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING stock_pcs;
                """, (qty, part_id))
                new_stock = cur.fetchone()
                total_shipped += qty

                # ── 4. 记录发货流水 ─────────────────────
                cur.execute("""
                    INSERT INTO material_transactions
                        (part_id, transaction_type, qty_change, balance_after,
                         operator_id, remarks)
                    VALUES (%s, 'SHIP_OUT', %s, %s, %s,
                            '发货确认: DN#' || %s);
                """, (
                    part_id, -qty,
                    int(new_stock["stock_pcs"]) if new_stock else 0,
                    operator_id, str(dn_id),
                ))

            # ── 5. 更新发货单状态 ───────────────────────
            cur.execute("""
                UPDATE delivery_notes
                SET status = %s,
                    delivered_at = NOW()
                WHERE id = %s;
            """, (DN_STATUS_DELIVERED, dn_id))

            conn.commit()

    return {
        "code": 0,
        "message": f"发货确认完成，共扣减 {total_shipped} 件成品库存（DN#{dn_id}）",
        "data": {
            "dn_id":            dn_id,
            "total_shipped":    total_shipped,
            "items_processed":  len(items),
        },
    }


# ============================================================================
# §8.3 辅助：发货单列表（含别名待配统计）
# ============================================================================

def get_delivery_notes_with_alias_status(
    customer_name: str,
    status_filter: str = "",
) -> list[dict]:
    """
    发货单列表，同时返回每个发货单的别名待配告警。

    对每个发货单，检查其明细中是否存在 PENDING_CONFIG 项，
    若存在则在返回数据中附加 pending_alias_count 字段。
    """
    with psycopg2.connect(**_db_config()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            sql = """
                SELECT
                    dn.id,
                    dn.status,
                    dn.customer_name,
                    dn.shipped_at,
                    dn.delivered_at,
                    dn.operator_id,
                    dn.created_at,
                    COUNT(di.id)                                 AS item_count,
                    COUNT(CASE WHEN pca.id IS NULL THEN 1 END) AS pending_alias_count
                FROM delivery_notes dn
                LEFT JOIN delivery_items di ON di.dn_id = dn.id
                LEFT JOIN parts pt ON di.part_id = pt.id
                LEFT JOIN part_customer_aliases pca
                    ON pca.part_id = pt.id
                    AND pca.customer_name = dn.customer_name
                WHERE (%s = '' OR dn.customer_name = %s)
                  AND (%s = '' OR dn.status = %s)
                GROUP BY dn.id
                ORDER BY dn.created_at DESC;
            """
            cur.execute(sql, (
                customer_name, customer_name,
                status_filter, status_filter,
            ))
            return [dict(r) for r in cur.fetchall()]


# ============================================================================
# 内部工具
# ============================================================================

def _db_config() -> dict:
    """从 db_service 导入配置，避免硬编码重复。"""
    from app.services.db_service import DB_CONFIG
    return DB_CONFIG
