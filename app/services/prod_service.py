"""
app/services/prod_service.py
============================
生产执行专项服务 — 报工扣料、首件拦截、机模解耦维修

严格遵守 .cursorrules V3.2 §8 工业执行专项逻辑。

技术守则
--------
- 严禁 ORM（SQLAlchemy），必须使用原生 psycopg2
- 所有 INSERT/UPDATE 必须显式 conn.commit()
- 状态变更必须经由状态机函数，不允许裸 UPDATE status
- 敏感计算（扣料量）严禁放在前端，必须由后端返回

目录归属：app/services/
"""

import re
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": "thehaoshi5DE",
    "host": "localhost",
    "port": "5432",
}


# ============================================================================
# §8.1 常量与枚举
# ============================================================================

# 机台生命周期
EQ_STATUS_IDLE        = "IDLE"
EQ_STATUS_RUNNING     = "RUNNING"
EQ_STATUS_REPAIRING    = "REPAIRING"
EQ_STATUS_OFFLINE      = "OFFLINE"

# 模具生命周期（molds.lifecycle_status）
MOLD_STATUS_AVAILABLE   = "AVAILABLE"    # 可用（空闲）
MOLD_STATUS_IN_USE       = "IN_USE"        # 使用中（在机台）
MOLD_STATUS_MAINTENANCE = "MAINTENANCE"    # 维修中
MOLD_STATUS_CONVERTED   = "CONVERTED"      # 已改模
MOLD_STATUS_SCRAPPED   = "SCRAPPED"       # 已报废

# 工单状态
WO_PENDING    = "PENDING"
WO_SCHEDULED  = "SCHEDULED"
WO_RUNNING    = "RUNNING"
WO_PAUSED     = "PAUSED"
WO_COMPLETED  = "COMPLETED"

# 维修双轨模式（repair_mode）
REPAIR_MODE_MACHINE          = "MACHINE_REPAIR"       # 设备维修
REPAIR_MODE_MOLD_DISMOUNTED = "MOLD_DISMOUNTED"     # 拆模维修
REPAIR_MODE_MOLD_ON_MACHINE  = "MOLD_ON_MACHINE"    # 不拆模维修

# 锁定状态集合（报工熔断 — §8 刚性卡控）
# 非 RUNNING 态严禁报工写入，防止不合格品入良品库
EQ_LOCKED_STATES = {EQ_STATUS_REPAIRING, "pending_check", "offline"}


# ============================================================================
# §8.1 报工扣料 — 核心前置校验
# ============================================================================

def check_all_production_gates(
    work_order_id: int,
    equipment_id: int,
) -> tuple[bool, str]:
    """
    报工前全量门控检查（.cursorrules §8.1）。

    校验链路（任一失败则拒绝）：
      1. 机台状态 → 非 REPAIRING 态
      2. 工单状态 → RUNNING / SCHEDULED
      3. 首件 QA  → is_first_piece_required=False 或已放行
      4. 关联模具 → 非 MAINTENANCE 态

    参数
    ----
    work_order_id : int  工单 ID
    equipment_id  : int  机台 ID

    返回
    ----
    (allowed: bool, reason: str)
      allowed=True  → 全部门控通过
      allowed=False → 拒绝，含具体原因
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 门控 1: 机台状态 ────────────────────────────
            cur.execute("""
                SELECT id, current_status
                FROM equipments
                WHERE id = %s;
            """, (equipment_id,))
            eq = cur.fetchone()
            if not eq:
                return False, f"机台 #{equipment_id} 不存在"
            if eq["current_status"] in EQ_LOCKED_STATES:
                return False, (
                    f"机台状态为【{eq['current_status']}】（非 RUNNING），"
                    "报工已锁定，请等待维修完成"
                )

            # ── 门控 2: 工单状态 ───────────────────────────
            cur.execute("""
                SELECT id, order_status,
                       is_first_piece_required,
                       first_piece_passed_at,
                       part_id,
                       mold_id
                FROM work_orders
                WHERE id = %s;
            """, (work_order_id,))
            wo = cur.fetchone()
            if not wo:
                return False, f"工单 #{work_order_id} 不存在"
            if wo["order_status"] not in (WO_RUNNING, WO_SCHEDULED):
                return False, (
                    f"工单状态【{wo['order_status']}】"
                    "，不允许报工"
                )

            # ── 门控 3: 首件 QA ────────────────────────────
            if wo["is_first_piece_required"] and not wo["first_piece_passed_at"]:
                return False, (
                    "首件 QA 未放行，"
                    "必须完成首件检验后才可开始报工"
                )

            # ── 门控 4: 模具生命周期 ───────────────────────
            mold_id = wo.get("mold_id")
            if mold_id:
                cur.execute("""
                    SELECT id, lifecycle_status, mold_number
                    FROM molds
                    WHERE id = %s;
                """, (mold_id,))
                mold = cur.fetchone()
                if mold and mold["lifecycle_status"] == MOLD_STATUS_MAINTENANCE:
                    return False, (
                        f"模具【{mold['mold_number']}】当前处于维修状态，"
                        "禁止报工"
                    )

    return True, "通过"


# ============================================================================
# §8.1 报工扣料 — 消耗量计算
# ============================================================================

# 钢材料密度（g/cm³），按材料牌号分组
MATERIAL_DENSITY: dict[str, float] = {
    "冷轧钢板": 7.85,
    "热轧钢板": 7.85,
    "镀锌板":  7.85,
    "铝板":    2.70,
    "铝合金":  2.70,
    "铜板":    8.90,
    "黄铜":    8.50,
    "不锈钢":  7.93,
    "SPCC":   7.85,
    "SECC":   7.85,
    "DC01":   7.85,
    "DC04":   7.85,
    "Q235":   7.85,
    "Q345":   7.85,
    # 未知材料默认低碳钢
    "default": 7.85,
}

# 固定换算系数：cm³ → kg
CM3_TO_KG = 0.001


def get_material_density(material_name: str) -> float:
    """根据材料名称返回密度（g/cm³）。未知材料默认 7.85。"""
    if not material_name:
        return MATERIAL_DENSITY["default"]
    # 前缀匹配
    for key, val in MATERIAL_DENSITY.items():
        if key != "default" and material_name.startswith(key):
            return val
    return MATERIAL_DENSITY["default"]


def get_stroke_consumption_rate(
    part_id: int,
    mold_id: int | None,
) -> tuple[float, float]:
    """
    读取单次冲压消耗参数。
    优先从 quotes 表取最新核价参数（T/W/P + cavity_count）。

    返回 (consumed_weight_per_stroke: float, cavity_count: int)
    consumed_weight_per_stroke 单位：kg/冲次

    算法（.cursorrules §8.1）：
      GrossWeight = (T × W × P × Density × cavity_count) / 1_000_000   (kg)
      每冲次消耗 = GrossWeight / cavity_count  ← 注：cavity_count 是每冲次的腔数，
                                                整体产出 cavity_count 件，
                                                所以消耗量就是 GrossWeight
    """
    cavity_count = 1
    thickness_mm = 0.0
    width_mm = 0.0
    density = 7.85

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 优先取该零件最新核准报价中的 T/W/P
            cur.execute("""
                SELECT q.thickness, q.width, q.press_stroke,
                       q.cavity_count, q.scrap_rate
                FROM quotes q
                WHERE q.part_id = %s
                  AND q.approval_status IN ('APPROVED', 'production_ready')
                ORDER BY q.created_at DESC
                LIMIT 1;
            """, (part_id,))
            quote = cur.fetchone()
            if quote:
                thickness_mm = float(quote[0] or 0)
                width_mm     = float(quote[1] or 0)
                press_stroke = float(quote[2] or 0)   # P（mm）
                cavity_count = int(quote[3] or 1)

            # 回退：直接从零件表取材料名查密度
            cur.execute("""
                SELECT material_name FROM parts WHERE id = %s;
            """, (part_id,))
            row = cur.fetchone()
            if row and row[0]:
                density = get_material_density(row[0])
            elif mold_id:
                cur.execute("""
                    SELECT pt.material_name
                    FROM molds mo
                    JOIN parts pt ON mo.part_id = pt.id
                    WHERE mo.id = %s;
                """, (mold_id,))
                r2 = cur.fetchone()
                if r2 and r2[0]:
                    density = get_material_density(r2[0])

    if thickness_mm <= 0 or width_mm <= 0:
        # 完全无参数 → 保守默认值（极小值，防止零除）
        return 0.001, cavity_count

    # GrossWeight = T(cm) × W(cm) × P(mm) × density(g/cm³) / 1000
    #             = T × W × P × density / 1000   (g)
    #             = T × W × P × density / 1_000_000  (kg)
    # 其中 P 以 mm 传入（press_stroke = P）
    press_mm = 0.0
    if quote:
        press_mm = float(quote[2] or 0)

    gross_kg = (thickness_mm * width_mm * press_mm * density) / 1_000_000
    # 每冲次消耗 = gross_kg（一次冲压产生 cavity_count 件，但原料消耗是整块）
    consumed_kg = gross_kg

    return round(consumed_kg, 8), cavity_count


# ============================================================================
# §8.1 报工扣料 — 原料扣重（原子操作）
# ============================================================================

def deduct_material_for_report(
    material_qr_uid: str | None,
    strokes: int,
    part_id: int,
    mold_id: int | None,
) -> dict:
    """
    原料批次扣重（.cursorrules §8.1）。

    消耗公式：
      consumed_weight = strokes × get_stroke_consumption_rate()

    原子操作：UPDATE material_batches SET current_weight = current_weight - consumed
    安全护栏：current_weight 不得低于 0

    参数
    ----
    material_qr_uid : str | None  原料批次码（扫码，可选）
    strokes         : int           冲压次数
    part_id        : int           零件 ID（用于查密度）
    mold_id         : int | None   模具 ID

    返回
    ----
    {
        "material_qr_uid": str,
        "consumed_kg": float,   # 本次总消耗（kg）
        "per_stroke_kg": float, # 单次消耗（kg）
        "previous_weight": float,# 扣减前重量
        "current_weight": float, # 扣减后重量
    }
    若 material_qr_uid 为空，返回全零占位结果。
    """
    if not material_qr_uid or strokes <= 0:
        return {
            "material_qr_uid": material_qr_uid or "",
            "consumed_kg": 0.0,
            "per_stroke_kg": 0.0,
            "previous_weight": 0.0,
            "current_weight": 0.0,
        }

    per_stroke_kg, _ = get_stroke_consumption_rate(part_id, mold_id)
    consumed_kg = round(per_stroke_kg * strokes, 6)

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 读取扣减前重量（乐观锁防止并发超额）
            cur.execute("""
                SELECT qr_uid, current_weight, lifecycle_status
                FROM material_batches
                WHERE qr_uid = %s
                FOR UPDATE;
            """, (material_qr_uid,))
            row = cur.fetchone()
            if not row:
                return {
                    "material_qr_uid": material_qr_uid,
                    "consumed_kg": 0.0,
                    "per_stroke_kg": per_stroke_kg,
                    "previous_weight": 0.0,
                    "current_weight": 0.0,
                    "error": "原料批次不存在",
                }

            prev_weight = float(row[1] or 0)
            new_weight  = max(0.0, prev_weight - consumed_kg)

            # 更新后若重量归零，自动标记为 DEPLETED
            new_status = None
            if new_weight <= 0.0 and row[2] != "DEPLETED":
                new_status = "DEPLETED"

            cur.execute("""
                UPDATE material_batches
                SET current_weight = %s,
                    updated_at     = NOW(),
                    lifecycle_status = COALESCE(%s, lifecycle_status)
                WHERE qr_uid = %s;
            """, (new_weight, new_status, material_qr_uid))

            # 记录原料流水
            cur.execute("""
                INSERT INTO material_transactions
                    (qr_uid, transaction_type, qty_change, balance_after, operator_id, remarks)
                VALUES (%s, 'PRODUCTION_CONSUME', %s, %s, NULL,
                        '报工扣料: ' || %s || ' 冲');
            """, (material_qr_uid, -consumed_kg, new_weight, str(strokes)))

            conn.commit()

    return {
        "material_qr_uid": material_qr_uid,
        "consumed_kg":    consumed_kg,
        "per_stroke_kg":  per_stroke_kg,
        "previous_weight": prev_weight,
        "current_weight":  new_weight,
    }


# ============================================================================
# §8.1 报工扣料 — 成品库存扣件（parts.stock_pcs）
# ============================================================================

def deduct_part_stock(part_id: int, qty: int) -> None:
    """
    报工产出后，累加 parts.stock_pcs。
    （注：本函数为增量，不是扣减；发货时才扣减 parts.stock_pcs）

    参数
    ----
    part_id : int  零件 Primary ID
    qty     : int  本次报工产出件数（yield_qty）
    """
    if qty <= 0:
        return
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE parts
                SET stock_pcs = stock_pcs + %s
                WHERE id = %s;
            """, (qty, part_id))
            conn.commit()


def ship_part_stock(part_id: int, qty: int) -> None:
    """
    发货确认后，扣减 parts.stock_pcs（.cursorrules §8.3）。

    参数
    ----
    part_id : int  零件 Primary ID
    qty     : int  发货件数
    """
    if qty <= 0:
        return
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE parts
                SET stock_pcs = GREATEST(0, stock_pcs - %s)
                WHERE id = %s;
            """, (qty, part_id))
            conn.commit()


# ============================================================================
# §8.1 报工扣料 — 完整报工入口
# ============================================================================

def report_production_with_lock(
    work_order_id: int,
    equipment_id: int,
    strokes: int,
    operator_id: int,
    material_qr_uid: str | None = None,
) -> dict:
    """
    冲压报工（.cursorrules §8.1 完整实现）。

    执行链路：
      1. check_all_production_gates() — 4 重门控校验
      2. strokes × cavity_count → yield_qty（产出件数）
      3. deduct_material_for_report() — 原料扣重
      4. deduct_part_stock() — 成品库存累加
      5. INSERT sf_production_logs — 报工流水写入
      6. UPDATE work_orders.produced_qty — 工单产出累加
      7. 若达到 target_qty → 工单自动 COMPLETED

    参数
    ----
    work_order_id : int       工单 ID
    equipment_id  : int       机台 ID
    strokes       : int       冲压次数（操作工输入）
    operator_id   : int       操作工用户 ID
    material_qr_uid : str | None 原料批次码（可选）

    返回
    ----
    {
        "code": 0,           # 0=成功，1=拒绝
        "message": str,
        "data": {
            "yield_qty": int,
            "strokes": int,
            "cavity_count": int,
            "material_consumed_kg": float,
            "produced_qty_total": int,
            "target_qty": int,
            "is_completed": bool,
        }
    }
    """
    # ── 门控校验 ───────────────────────────────────────
    allowed, reason = check_all_production_gates(work_order_id, equipment_id)
    if not allowed:
        return {"code": 1, "message": reason, "data": None}

    if strokes <= 0:
        return {"code": 1, "message": "冲压次数必须 > 0", "data": None}

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 读取工单 + 模具参数 ─────────────────────
            cur.execute("""
                SELECT wo.*,
                       pt.id       AS part_id,
                       pt.part_number,
                       pt.internal_name,
                       mo.id       AS mold_id,
                       mo.cavity_count,
                       mo.mold_number
                FROM work_orders wo
                JOIN parts pt ON wo.part_id = pt.id
                LEFT JOIN molds mo ON wo.mold_id = mo.id
                WHERE wo.id = %s;
            """, (work_order_id,))
            wo = cur.fetchone()

            cavity_count = wo.get("mold_id") and (wo.get("cavity_count") or 1) or 1
            yield_qty    = strokes * cavity_count
            mold_id      = wo.get("mold_id")

            # ── 原料扣重 ─────────────────────────────────
            mat_result = deduct_material_for_report(
                material_qr_uid=material_qr_uid,
                strokes=strokes,
                part_id=wo["part_id"],
                mold_id=mold_id,
            )

            # ── 成品库存累加 ────────────────────────────
            deduct_part_stock(wo["part_id"], yield_qty)

            # ── 写入报工流水 ───────────────────────────
            cur.execute("""
                INSERT INTO sf_production_logs
                    (work_order_id, equipment_id, strokes, yield_qty,
                     consumed_weight, material_qr_uid, operator_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
            """, (
                work_order_id, equipment_id, strokes, yield_qty,
                mat_result["consumed_kg"],
                material_qr_uid, operator_id,
            ))
            log_id = cur.fetchone()[0]

            # ── 工单产出累加 ────────────────────────────
            cur.execute("""
                UPDATE work_orders
                SET produced_qty = produced_qty + %s,
                    order_status = CASE
                        WHEN produced_qty + %s >= target_qty THEN 'COMPLETED'
                        ELSE order_status
                    END,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING produced_qty, target_qty, order_status;
            """, (yield_qty, yield_qty, work_order_id))
            row = cur.fetchone()
            new_produced = int(row[0])
            target_qty   = int(row[1])
            new_status   = row[2]

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"报工成功：{strokes} 冲次 × {cavity_count} 穴"
            f" = {yield_qty} 件"
            + (f"（原料消耗 {mat_result['consumed_kg']:.4f} kg）"
               if mat_result["consumed_kg"] > 0 else "")
        ),
        "data": {
            "log_id":                log_id,
            "yield_qty":             yield_qty,
            "strokes":               strokes,
            "cavity_count":         cavity_count,
            "material_consumed_kg":  mat_result["consumed_kg"],
            "produced_qty_total":    new_produced,
            "target_qty":            target_qty,
            "is_completed":          new_status == WO_COMPLETED,
        },
    }


# ============================================================================
# §8.2 维保状态机 — 机模解耦逻辑
# ============================================================================

def maintenance_trigger_with_decoupling(
    equipment_id: int,
    mold_id: int | None,
    repair_mode: str,
    reporter_id: int,
    fault_reason: str = "",
) -> dict:
    """
    维修触发（含机模解耦，.cursorrules §8.2）。

    核心逻辑：
      ┌─────────────────────────────────────────────────────┐
      │  报修时：机台 + 关联模具均进入 REPAIRING             │
      │  ┌───────────────┐                                 │
      │  │ 机台 REPAIRING │ ← 生产熔断，禁止报工            │
      │  └───────┬───────┘                                 │
      │          │                                           │
      │   repair_mode 分流                                   │
      │          │                                           │
      │  ┌──────▼──────────┐                               │
      │  │ MOLD_DISMOUNTED  │ → 模具保持 REPAIRING          │
      │  │                  │ → 机台重置 → IDLE（可接新活）  │
      │  ├──────────────────┤                               │
      │  │ MOLD_ON_MACHINE  │ → 模具锁定 REPAIRING          │
      │  │                  │ → 机台锁定 REPAIRING（双锁）   │
      │  ├──────────────────┤                               │
      │  │ MACHINE_REPAIR   │ → 模具不变（仍在 IDLE）       │
      │  │                  │ → 机台 REPAIRING              │
      │  └──────────────────┘                               │
      └─────────────────────────────────────────────────────┘

    参数
    ----
    equipment_id : int    报修机台 ID
    mold_id       : int|None 关联模具 ID（可选，MOLD_* 模式时必填）
    repair_mode   : str    MOLD_DISMOUNTED | MOLD_ON_MACHINE | MACHINE_REPAIR
    reporter_id   : int    报修人用户 ID
    fault_reason  : str    故障描述

    返回
    ----
    {"code": 0/1, "message": str, "data": {...}}
    """
    if repair_mode not in (
        REPAIR_MODE_MOLD_DISMOUNTED,
        REPAIR_MODE_MOLD_ON_MACHINE,
        REPAIR_MODE_MACHINE,
    ):
        return {
            "code": 1,
            "message": (
                f"repair_mode 必须为 {REPAIR_MODE_MOLD_DISMOUNTED} | "
                f"{REPAIR_MODE_MOLD_ON_MACHINE} | {REPAIR_MODE_MACHINE}"
            ),
            "data": None,
        }

    if repair_mode.startswith("MOLD_") and not mold_id:
        return {
            "code": 1,
            "message": "MOLD_* 模式必须传入 mold_id",
            "data": None,
        }

    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 读取机台 & 模具当前状态 ─────────────────
            cur.execute("""
                SELECT id, current_status, equipment_code, current_mold_id
                FROM equipments
                WHERE id = %s;
            """, (equipment_id,))
            eq = cur.fetchone()
            if not eq:
                return {"code": 1, "message": f"机台 #{equipment_id} 不存在", "data": None}

            mold_before = None
            if mold_id:
                cur.execute("""
                    SELECT id, lifecycle_status, mold_number
                    FROM molds
                    WHERE id = %s;
                """, (mold_id,))
                mold_before = cur.fetchone()

            # ── 2. 写入维修日志 ─────────────────────────
            cur.execute("""
                INSERT INTO maintenance_logs
                    (target_type, equipment_id, mold_id, repair_mode,
                     status, tech_id, remarks, start_time)
                VALUES (
                    CASE WHEN %s::VARCHAR LIKE 'MOLD_%'
                         THEN 'MOLD' ELSE 'EQUIPMENT' END,
                    %s, %s, %s,
                    'REPAIRING', %s, %s, %s
                )
                RETURNING id, start_time;
            """, (repair_mode, equipment_id,
                  mold_id, repair_mode,
                  reporter_id, fault_reason, now))
            log = cur.fetchone()

            # ── 3. 联动更新模具 ─────────────────────────
            if mold_id:
                new_mold_status = MOLD_STATUS_MAINTENANCE
                cur.execute("""
                    UPDATE molds
                    SET lifecycle_status = %s,
                        updated_at = %s
                    WHERE id = %s;
                """, (new_mold_status, now, mold_id))

            # ── 4. 联动更新机台 ─────────────────────────
            if repair_mode == REPAIR_MODE_MOLD_DISMOUNTED:
                # 拆模 → 机台立即释放（IDLE），可接其他活
                new_eq_status = EQ_STATUS_IDLE
            else:
                # 机上维修 / 设备维修 → 机台锁定（REPAIRING）
                new_eq_status = EQ_STATUS_REPAIRING

            cur.execute("""
                UPDATE equipments
                SET current_status = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (new_eq_status, now, equipment_id))

            # ── 5. 联动工单熔断 ─────────────────────────
            if new_eq_status == EQ_STATUS_REPAIRING:
                cur.execute("""
                    UPDATE work_orders
                    SET order_status = 'PAUSED', updated_at = %s
                    WHERE equipment_id = %s
                      AND order_status IN ('RUNNING', 'SCHEDULED');
                """, (now, equipment_id))

            # ── 6. 拆模时解除 molds.current_equipment_id ─────
            if repair_mode == REPAIR_MODE_MOLD_DISMOUNTED and mold_id:
                cur.execute("""
                    UPDATE molds
                    SET current_equipment_id = NULL,
                        updated_at = %s
                    WHERE id = %s;
                """, (now, mold_id))

            conn.commit()

    return {
        "code": 0,
        "message": (
            f"维修已记录（{repair_mode}）"
            + (
                f"，机台已{'释放（IDLE）' if new_eq_status == EQ_STATUS_IDLE else '锁定（REPAIRING）'}"
            )
        ),
        "data": {
            "maintenance_log_id": log["id"] if isinstance(log, dict) else log[0],
            "equipment_id":      equipment_id,
            "mold_id":          mold_id,
            "repair_mode":       repair_mode,
            "new_equipment_status": new_eq_status,
            "new_mold_status":   MOLD_STATUS_MAINTENANCE if mold_id else None,
        },
    }


def maintenance_resolve_with_coupling(
    maintenance_log_id: int,
    resolver_id: int,
    resolved: bool = True,
    remarks: str = "",
) -> dict:
    """
    维修复机（含机模耦合重建，.cursorrules §8.2）。

    resolved=True 时的联动逻辑：
      ┌─────────────────────────────────────────────────┐
      │ 1. 维修记录 → RESOLVED                          │
      │ 2. 模具 → AVAILABLE（恢复可用）                │
      │ 3. repair_mode 分流：                           │
      │    MOLD_DISMOUNTED  → 机台 IDLE（已释放，不动） │
      │    MOLD_ON_MACHINE  → 机台 RUNNING（在线修复） │
      │    MACHINE_REPAIR   → 机台 RUNNING（设备恢复） │
      │ 4. PAUSED 工单 → RUNNING（重新排产）            │
      └─────────────────────────────────────────────────┘

    参数
    ----
    maintenance_log_id : int   维修记录 ID
    resolver_id         : int   复机操作员 ID（必须是 tech 部门）
    resolved            : bool  True=完成，False=撤销
    remarks            : str   维修备注

    返回
    ----
    {"code": 0/1, "message": str, "data": {...}}
    """
    now = datetime.datetime.now()

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # ── 1. 读取维修记录 ─────────────────────────
            cur.execute("""
                SELECT * FROM maintenance_logs
                WHERE id = %s
                FOR UPDATE;
            """, (maintenance_log_id,))
            log = cur.fetchone()
            if not log:
                return {"code": 1, "message": f"维修记录 #{maintenance_log_id} 不存在", "data": None}

            if log["status"] != "REPAIRING":
                return {
                    "code": 1,
                    "message": f"当前状态【{log['status']}】，非维修中无法复机",
                    "data": None,
                }

            new_maint_status = "RESOLVED" if resolved else "CANCELLED"
            repair_mode      = log.get("repair_mode") or ""
            eq_id            = log.get("equipment_id")
            mold_id          = log.get("mold_id")

            # ── 2. 更新维修记录状态 ─────────────────────
            cur.execute("""
                UPDATE maintenance_logs
                SET status    = %s,
                    end_time  = %s,
                    remarks   = COALESCE(%s, remarks)
                WHERE id = %s;
            """, (new_maint_status, now, remarks, maintenance_log_id))

            if not resolved:
                conn.commit()
                return {
                    "code": 0,
                    "message": "维修记录已撤销",
                    "data": {
                        "maintenance_log_id": maintenance_log_id,
                        "status": new_maint_status,
                    },
                }

            # ── 3. 模具 → AVAILABLE（恢复可用）────────
            if mold_id:
                cur.execute("""
                    UPDATE molds
                    SET lifecycle_status = %s,
                        updated_at = %s
                    WHERE id = %s;
                """, (MOLD_STATUS_AVAILABLE, now, mold_id))

            # ── 4. 机台状态重建 ─────────────────────────
            new_eq_status = None
            if eq_id:
                if repair_mode == REPAIR_MODE_MOLD_DISMOUNTED:
                    # 拆模维修：模具离线修复，机台保持 IDLE（已被释放）
                    new_eq_status = EQ_STATUS_IDLE
                else:
                    # 机上维修 / 设备维修：修复后立即恢复 RUNNING
                    new_eq_status = EQ_STATUS_RUNNING

                cur.execute("""
                    UPDATE equipments
                    SET current_status = %s,
                        updated_at = %s
                    WHERE id = %s;
                """, (new_eq_status, now, eq_id))

                # ── 5. PAUSED 工单 → RUNNING ──────────────
                if new_eq_status == EQ_STATUS_RUNNING:
                    cur.execute("""
                        UPDATE work_orders
                        SET order_status = 'RUNNING', updated_at = %s
                        WHERE equipment_id = %s
                          AND order_status = 'PAUSED';
                    """, (now, eq_id))

            conn.commit()

    return {
        "code": 0,
        "message": (
            "维修完成" if resolved else "维修已撤销"
            + (
                f" → 机台已{'恢复运行（RUNNING）' if new_eq_status == EQ_STATUS_RUNNING else '保持空闲（IDLE）'}"
                if new_eq_status
                else ""
            )
        ),
        "data": {
            "maintenance_log_id": maintenance_log_id,
            "maint_status":      new_maint_status,
            "equipment_id":      eq_id,
            "equipment_status":   new_eq_status,
            "mold_id":          mold_id,
            "mold_status":       MOLD_STATUS_AVAILABLE if mold_id else None,
        },
    }


# ============================================================================
# §8.2 辅助：机台 ←→ 模具绑定解耦
# ============================================================================

def bind_mold_to_equipment(mold_id: int, equipment_id: int) -> dict:
    """
    将模具绑定到机台（上线安装）。

    写入：
      molds.current_equipment_id = equipment_id
      molds.lifecycle_status       = IN_USE
      equipments.current_mold_id    = mold_id（向后兼容字段）

    注意：本项目 equipments 与 molds 是独立台账，
    molds.current_equipment_id 是快速定位字段，不做强外键约束。
    """
    now = datetime.datetime.now()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE molds
                SET current_equipment_id = %s,
                    lifecycle_status       = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (equipment_id, MOLD_STATUS_IN_USE, now, mold_id))
            conn.commit()
    return {"code": 0, "message": f"模具 #{mold_id} 已安装到机台 #{equipment_id}"}


def unbind_mold_from_equipment(mold_id: int) -> dict:
    """
    将模具从机台解除绑定（下线拆卸）。
    molds.current_equipment_id = NULL
    molds.lifecycle_status       = AVAILABLE
    """
    now = datetime.datetime.now()
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE molds
                SET current_equipment_id = NULL,
                    lifecycle_status       = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (MOLD_STATUS_AVAILABLE, now, mold_id))
            conn.commit()
    return {"code": 0, "message": f"模具 #{mold_id} 已从机台卸下"}


# ============================================================================
# §8.3 发货扣库 — 成品库存扣件
# ============================================================================

def ship_delivery(dn_id: int, operator_id: int) -> dict:
    """
    发货确认时，批量扣减 parts.stock_pcs（.cursorrules §8.3）。

    参数
    ----
    dn_id       : int  发货单 ID
    operator_id : int  操作人 ID

    返回
    ----
    {"code": 0/1, "message": str, "data": {"shipped_count": int}}
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 读取发货明细
            cur.execute("""
                SELECT di.part_id, di.qty
                FROM delivery_items di
                WHERE di.dn_id = %s;
            """, (dn_id,))
            items = cur.fetchall()

            if not items:
                return {"code": 1, "message": "发货单无明细，无法发货", "data": None}

            # 检查发货单状态
            cur.execute("""
                SELECT status FROM delivery_notes WHERE id = %s;
            """, (dn_id,))
            row = cur.fetchone()
            if not row:
                return {"code": 1, "message": f"发货单 #{dn_id} 不存在", "data": None}
            if row[0] != "SHIPPED":
                return {"code": 1, "message": f"发货单状态为【{row[0]}】，仅 SHIPPED 可发货", "data": None}

            total_shipped = 0
            for item in items:
                part_id = int(item[0])
                qty     = int(item[1])
                ship_part_stock(part_id, qty)
                total_shipped += qty

            conn.commit()

    return {
        "code": 0,
        "message": f"发货完成，共扣减 {total_shipped} 件成品库存",
        "data": {"shipped_count": total_shipped},
    }


# ============================================================================
# §8.3 查询：带客户件号翻译的发货明细
# ============================================================================

def get_delivery_items_with_alias(dn_id: int, customer_name: str) -> list:
    """
    发货明细（含客户件号翻译，.cursorrules §8.3）。
    优先取 part_customer_aliases 表的 customer_part_no；
    无映射时返回内部件号。
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    di.id         AS delivery_item_id,
                    di.qty,
                    di.lot_no,
                    di.remark,
                    pt.id         AS part_id,
                    pt.part_number    AS internal_part_no,
                    pt.internal_name  AS internal_name,
                    COALESCE(pca.customer_part_no, pt.part_number)
                                      AS display_part_no,
                    COALESCE(pca.customer_part_name, pt.internal_name)
                                      AS display_name
                FROM delivery_items di
                JOIN parts pt ON di.part_id = pt.id
                LEFT JOIN part_customer_aliases pca
                    ON pca.part_id = pt.id
                    AND pca.customer_name = %s
                WHERE di.dn_id = %s
                ORDER BY di.id;
            """, (customer_name, dn_id))
            return [dict(r) for r in cur.fetchall()]
