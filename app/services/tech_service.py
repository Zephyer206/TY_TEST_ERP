"""
app/services/tech_service.py
============================
开发部（Tech）专项服务 — 打样全流程 + 零件主档建档

核心职责
--------
1. create_part_profile()       — 源头建档：录入 T/W/P，cavity_count 默认一出
2. start_prototype()        — 连续模打样开机，机台进入 PROTOTYPING 状态
3. report_prototype()        — 连续模打样报工：填入即生效，不扣料，入 sample_inventory
4. report_simple_prototype() — 简易模打样：纯线下，直接原子累加 sample_inventory

打样双轨逻辑（已确认）
--------------------
- 连续模（is_simple=False）：需扫机台 → 机台 PROTOTYPING → 报工后机台 IDLE，sample_inventory += qty
- 简易模（is_simple=True）：完全线下隐形，无需扫机台，直接 sample_inventory += qty

技术守则（.cursorrules §4）
---------------------------
- 严禁 ORM，必须使用原生 psycopg2
- 所有 INSERT/UPDATE 必须显式 conn.commit()
- 打样不计料耗，原料不减重

目录归属：app/services/
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import datetime

from app.models.constants import (
    EQ_STATUS_IDLE,
    EQ_STATUS_PROTOTYPING,
    SESSION_TYPE_PROTOTYPE,
    SESSION_TYPE_SIMPLE,
    SESSION_TYPE_CONTINUOUS,
    SESSION_RUNNING,
    SESSION_CLOSED,
)
from app.services.db_service import DB_CONFIG


# ============================================================================
# §Tech 源头建档
# ============================================================================

def create_part_profile(
    part_number: str,
    internal_name: str,
    material_name: str,
    thickness: float,
    width: float,
    press_stroke: float,
    cavity_count: int = 1,
    mold_tonnage: float = 0.0,
    created_by: int | None = None,
) -> dict:
    """
    源头建档 — 录入零件物理基因参数（T/W/P + 模具参数）。

    INSERT into parts:
      - T/W/P 存入 parts.thickness / parts.width / parts.press_stroke
      - cavity_count 默认一出（1）
      - mold_tonnage 模具参数（mold_cost 已移至 quotes 层，v11 规范）
      - part_status 默认 'SAMPLING'（打样阶段）

    注意：零件号（part_number）唯一，重复则拒绝。

    参数
    ----
    part_number   : str   零件号（必须唯一）
    internal_name : str   内部名称
    material_name : str   材料牌号
    thickness     : float  料厚 T（mm）
    width         : float  宽度 W（mm）
    press_stroke  : float 步距 P（mm）
    cavity_count  : int   出数（默认 1）
    mold_tonnage  : float 要求吨位（默认 0）
    created_by    : int | None 创建人用户 ID

    返回
    ----
    {"code": 0/1, "message": str, "data": {"part_id": int}}
    """
    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 唯一性校验
            cur.execute(
                "SELECT id FROM parts WHERE part_number = %s;",
                (part_number,),
            )
            if cur.fetchone():
                return {
                    "code": 1,
                    "message": f"零件号 {part_number} 已存在，禁止重复创建",
                    "data": None,
                }

            # 写入主档（mold_cost 已移至 quotes 层，v11 规范禁止写入 parts 表）
            cur.execute("""
                INSERT INTO parts (
                    part_number, internal_name, material_name,
                    thickness, width, press_stroke,
                    cavities, mold_tonnage,
                    part_status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SAMPLING', %s, %s)
                RETURNING id, part_number, internal_name;
            """, (
                part_number,
                internal_name,
                material_name,
                thickness,
                width,
                press_stroke,
                cavity_count,
                mold_tonnage,
                now,
                now,
            ))
            row = cur.fetchone()

            conn.commit()

    return {
        "code": 0,
        "message": f"零件 #{row['id']}（{row['part_number']}）建档成功，状态：SAMPLING",
        "data": {
            "part_id":      row["id"],
            "part_number":  row["part_number"],
            "internal_name": row["internal_name"],
        },
    }


# ============================================================================
# §Tech 连续模打样开机
# ============================================================================

def start_prototype(machine_id: int) -> dict:
    """
    连续模打样开机。

    逻辑：
      1. 校验机台存在
      2. 校验机台状态为 IDLE（非 PROTOTYPING 非 RUNNING）
      3. 机台 → PROTOTYPING
      4. INSERT production_sessions (session_type='Prototype', status='RUNNING')

    注意：打样不扫材料码（material_qr_uid = NULL）。

    参数
    ----
    machine_id : int 机台 ID

    返回
    ----
    {"code": 0/1, "message": str, "data": {"session_id": int, "machine_id": int, "status": str}}
    """
    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 校验机台存在 ─────────────────────────────
            cur.execute("""
                SELECT id, current_status, equipment_code
                FROM equipments
                WHERE id = %s
                FOR UPDATE;
            """, (machine_id,))
            eq = cur.fetchone()
            if not eq:
                return {"code": 1, "message": f"机台 #{machine_id} 不存在", "data": None}

            # ── 2. 校验机台状态允许开机 ───────────────────
            if eq["current_status"] not in (EQ_STATUS_IDLE,):
                return {
                    "code": 1,
                    "message": (
                        f"机台 #{machine_id} 当前状态为【{eq['current_status']}】，"
                        "仅 IDLE 机台可开启打样"
                    ),
                    "data": None,
                }

            # ── 3. 禁止重复 PROTOTYPING ──────────────────
            cur.execute("""
                SELECT id FROM production_sessions
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

            # ── 4. 机台 → PROTOTYPING ───────────────────
            cur.execute("""
                UPDATE equipments
                SET current_status = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (EQ_STATUS_PROTOTYPING, now, machine_id))

            # ── 5. 写入打样会话 ─────────────────────────
            cur.execute("""
                INSERT INTO production_sessions
                    (machine_id, session_type, status, start_time,
                     reported_qty, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 0, %s, %s)
                RETURNING id, machine_id, session_type, status, start_time;
            """, (
                machine_id,
                SESSION_TYPE_PROTOTYPE,
                SESSION_RUNNING,
                now,
                now,
                now,
            ))
            row = cur.fetchone()

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"连续模打样已开启（会话 #{row['id']}），"
            f"机台 #{machine_id} 设为 PROTOTYPING"
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
# §Tech 连续模打样报工
# ============================================================================

def report_prototype(
    machine_id: int,
    qty: int,
    operator_id: int | None = None,
) -> dict:
    """
    连续模打样报工 — 填入即生效（.cursorrules 打样双轨）。

    逻辑（单事务）：
      1. 找到机台的 PROTOTYPING 会话（RUNNING）
      2. 零件物理参数查 cavities（parts.cavities）
      3. 成品量 = qty × cavities
      4. 原料扣减：零（打样不计料耗，调试料不扣批次）
      5. sample_inventory.sample_qty += 成品量
      6. production_sessions.reported_qty += qty，状态 → CLOSED
      7. 机台 → IDLE（立即释放）

    参数
    ----
    machine_id  : int         机台 ID
    qty        : int         冲次（填入即生效）
    operator_id : int | None 操作工 ID

    返回
    ----
    {"code": 0/1, "message": str,
     "data": {"session_id": int, "qty": int, "sample_added": int}}
    """
    if qty <= 0:
        return {"code": 1, "message": "冲次必须 > 0", "data": None}

    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 找 PROTOTYPING 会话 ────────────────────
            cur.execute("""
                SELECT ps.id, ps.status,
                       ps.work_order_id,
                       wo.part_id
                FROM production_sessions ps
                LEFT JOIN work_orders wo ON wo.id = ps.work_order_id
                WHERE ps.machine_id = %s
                  AND ps.session_type = %s
                  AND ps.status = %s
                ORDER BY ps.start_time DESC
                LIMIT 1
                FOR UPDATE;
            """, (machine_id, SESSION_TYPE_PROTOTYPE, SESSION_RUNNING))
            session = cur.fetchone()
            if not session:
                return {
                    "code": 1,
                    "message": f"机台 #{machine_id} 无 PROTOTYPING 会话，请先开启打样",
                    "data": None,
                }

            # ── 2. 查 cavities（零件一出几）──────────────
            wo_part_id = session.get("work_order_id")
            cavities = 1
            part_id = None

            if wo_part_id:
                cur.execute("""
                    SELECT pt.id, COALESCE(pt.cavities, 1) AS cc
                    FROM work_orders wo
                    JOIN parts pt ON pt.id = wo.part_id
                    WHERE wo.id = %s;
                """, (wo_part_id,))
                row = cur.fetchone()
                if row:
                    part_id = row["id"]
                    cavities = int(row["cc"] or 1)

            # 如果没有关联工单，尝试从 sample_inventory 中找
            if not part_id:
                cur.execute("""
                    SELECT si.part_id, COALESCE(pt.cavities, 1) AS cc
                    FROM sample_inventory si
                    JOIN parts pt ON pt.id = si.part_id
                    ORDER BY si.id DESC
                    LIMIT 1;
                """)
                row = cur.fetchone()
                if row:
                    part_id = row["part_id"]
                    cavities = int(row["cc"] or 1)

            sample_added = qty * cavities

            # ── 3. sample_inventory 累加 ──────────────────
            if part_id:
                cur.execute("""
                    INSERT INTO sample_inventory (part_id, sample_qty, created_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (part_id) DO UPDATE
                        SET sample_qty = sample_inventory.sample_qty + EXCLUDED.sample_qty,
                            updated_at = EXCLUDED.updated_at;
                """, (part_id, sample_added, now, now))

            # ── 4. 会话结账 ─────────────────────────────
            cur.execute("""
                UPDATE production_sessions
                SET status       = %s,
                    reported_qty = reported_qty + %s,
                    end_time    = %s,
                    updated_at  = %s
                WHERE id = %s
                RETURNING id;
            """, (SESSION_CLOSED, qty, now, now, session["id"]))
            session_id = cur.fetchone()["id"]

            # ── 5. 机台 → IDLE（完工释放）────────────────
            cur.execute("""
                UPDATE equipments
                SET current_status = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (EQ_STATUS_IDLE, now, machine_id))

            conn.commit()

            return {
        "code": 0,
        "message": (
            f"打样报工成功：{qty} 冲次"
            + (f" × {cavities} 穴 = {sample_added} 件" if cavities > 1 else f" = {sample_added} 件")
            + " → sample_inventory，机台已释放（IDLE）"
        ),
        "data": {
            "session_id":    session_id,
            "qty":          qty,
            "cavities":     cavities,
            "sample_added": sample_added,
        },
    }


# ============================================================================
# §Tech 简易模打样（完全线下，无需扫机台）
# ============================================================================

def report_simple_prototype(
    part_id: int,
    qty: int,
    operator_id: int | None = None,
) -> dict:
    """
    简易模打样 — 完全线下隐形，直接累加 sample_inventory。

    逻辑：
      1. 校验零件存在，读取 cavities
      2. 成品量 = qty × cavities
      3. 原料扣减：零（打样不计料耗）
      4. 原子性 sample_inventory.sample_qty += 成品量
      5. 不写入 production_sessions（完全线下，无系统机台占用）

    参数
    ----
    part_id    : int  零件 ID
    qty       : int  产出件数
    operator_id : int | None 操作人 ID（可选）

    返回
    ----
    {"code": 0/1, "message": str, "data": {"part_id": int, "qty": int, "sample_added": int}}
    """
    if qty <= 0:
        return {"code": 1, "message": "产出件数必须 > 0", "data": None}

    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 读取零件参数 ─────────────────────────
            cur.execute("""
                SELECT id, part_number, cavities
                FROM parts
                WHERE id = %s;
            """, (part_id,))
            part = cur.fetchone()
            if not part:
                return {"code": 1, "message": f"零件 #{part_id} 不存在", "data": None}

            cavities = int(part["cavities"] or 1)
            sample_added = qty * cavities

            # ── 2. 原子累加 sample_inventory ──────────────
            cur.execute("""
                INSERT INTO sample_inventory (part_id, sample_qty, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (part_id) DO UPDATE
                    SET sample_qty = sample_inventory.sample_qty + EXCLUDED.sample_qty,
                        updated_at = EXCLUDED.updated_at
                RETURNING sample_qty;
            """, (part_id, sample_added, now, now))
            new_total = int(cur.fetchone()["sample_qty"])

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"简易模打样 #{part_id}（{part['part_number']}）录入成功："
            f"{qty} 件"
            + (f" × {cavities} 穴 = {sample_added} 件" if cavities > 1 else "")
            + f"，累计库存 {new_total} 件"
        ),
        "data": {
            "part_id":       part_id,
            "qty":          qty,
            "cavities":     cavities,
            "sample_added":  sample_added,
            "sample_total":  new_total,
        },
    }


# ============================================================================
# 辅助查询：打样虚拟库视图
# ============================================================================

def get_sample_inventory(part_id: int | None = None) -> list[dict]:
    """
    查询打样虚拟库（sample_inventory）。

    参数
    ----
    part_id : int | None 按零件过滤（None = 全部）

    返回
    ----
    list[dict]，含：part_id, part_number, internal_name, sample_qty, created_at
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if part_id:
                cur.execute("""
                    SELECT si.part_id,
                           pt.part_number,
                           pt.internal_name,
                           si.sample_qty,
                           si.updated_at
                    FROM sample_inventory si
                    JOIN parts pt ON pt.id = si.part_id
                    WHERE si.part_id = %s;
                """, (part_id,))
            else:
                cur.execute("""
                    SELECT si.part_id,
                           pt.part_number,
                           pt.internal_name,
                           si.sample_qty,
                           si.updated_at
                    FROM sample_inventory si
                    JOIN parts pt ON pt.id = si.part_id
                    WHERE si.sample_qty > 0
                    ORDER BY si.updated_at DESC
                    LIMIT 100;
                """)
            return [dict(r) for r in cur.fetchall()]


def get_part_profile(part_id: int) -> dict | None:
    """
    读取零件主档（含 T/W/P + 模具参数）。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, part_number, internal_name, material_name,
                       thickness, width, press_stroke,
                       cavity_count, mold_tonnage,
                       part_status, created_at
                FROM parts
                WHERE id = %s;
            """, (part_id,))
            row = cur.fetchone()
            return dict(row) if row else None
