# -*- coding: utf-8 -*-
"""
价格台账 Excel 导入脚本
按客户逐一导入：武汉万向 → 芜湖伯特利 → 上海万向

每行流程：
  1. 按 (customer_id, customer_product_no) 查 parts
  2. 未命中 → 按 part_number 查 parts
  3. 仍未命中 → 新建 parts
  4. 在 prices 中找 (part_id, customer_id)
  5. 未命中 → INSERT prices
  6. 在 price_years 中写入 2025 年单价和销量
"""
import re
import sys
import os
import openpyxl

# 路径
BASE = os.path.dirname(os.path.abspath(__file__))
PRICES_DIR = os.path.join(BASE, "..", "static", "uploads", "prices")

# 客户映射（文件夹名 → tooling_customers 表 id）
CUSTOMER_MAP = {
    "B-C武汉万向汽车制动器有限公司": 55,
    "B-G芜湖伯特利":               59,
    "上海万向钱潮A-A":             27,
}

# ======================================================================
# Excel 解析
# ======================================================================

def parse_twph(raw: str):
    """从 '0.4*96*184' 解析 T, W, PH，返回 (thickness, width, press_height)"""
    if not raw:
        return None, None, None
    m = re.findall(r'[\d.]+', str(raw))
    if len(m) >= 3:
        return float(m[0]), float(m[1]), float(m[2])
    if len(m) == 2:
        return float(m[0]), float(m[1]), None
    return None, None, None


def parse_float(v, default=None):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ("", "None", "#N/A"):
        return default
    try:
        return float(s)
    except:
        return default


def g(v):
    """safe get, returns '' if None"""
    return v if v is not None else ""


# ======================================================================
# 各客户 Sheet 解析器
# ======================================================================

def parse_wuhan(filepath):
    """武汉万向.xlsx → [{零件号, 材质, T, W, PH, 净重kg, 毛重kg, 材料单价, 废料价, 表面处理成本, 2025单价, 年销量}]"""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb["Sheet1"]
    rows = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # 列: 序号(A), 原图产品编号(B), 图片(C), 本厂产品名称(D), 模具类型(E),
        #      材质(F), 用料规格(G), 备注(H), 单件毛重量(I), 单件净重量(J),
        #      材料价格(K), 废料价格(L), 材料成本(M), 外协成本(N), 成本(O),
        #      2025年价格(P), 2025销量(Q), 销售额(R)
        part_no_raw = row[1]
        if part_no_raw is None:
            continue
        # 零件号去掉"（喷涂）"等工艺后缀，再判断是否有效
        part_no = re.sub(r'[（(][^）)]*(?:涂|热|电|镀|磷|钝|氧)[^）)]*[）)]', '',
                          str(part_no_raw).strip())
        part_no = part_no.strip()
        if not part_no or part_no in ("None", "总计", "合计", "sum"):
            continue
        # 跳过全空行：零件号有值，但后续关键字段（材质、用料规格、毛重、净重）全为空
        material = str(row[5]).strip() if row[5] else ""
        twph_raw = str(row[6]).strip() if row[6] else ""
        gross_g = parse_float(row[8])       # 单件毛重量(g)
        net_g   = parse_float(row[9])        # 单件净重量(g)
        if not material and not twph_raw and gross_g is None and net_g is None:
            print(f"    [跳过] 行{i}: {part_no} - 全行数据为空（仅有零件号）")
            continue

        T, W, PH = parse_twph(twph_raw)
        mat_price = parse_float(row[10])     # 材料价格
        scrap_price = parse_float(row[11])    # 废料价格
        surface_cost = parse_float(row[13])   # 外协成本(N列)
        unit_2025 = parse_float(row[15])     # 2025年价格(P列)
        sales_2025 = parse_float(row[16])    # 2025销量(Q列)
        # D列(index 3) = 本厂产品名称
        internal_name = str(row[3]).strip() if row[3] else ""

        rows.append({
            "part_no": part_no,
            "material": material,
            "internal_name": internal_name,
            "T": T, "W": W, "PH": PH,
            "gross_g": gross_g,
            "net_g": net_g,
            "mat_price": mat_price,
            "scrap_price": scrap_price,
            "surface_cost": surface_cost,
            "unit_2025": unit_2025,
            "sales_2025": int(sales_2025) if sales_2025 else None,
            "remark": str(row[7]) if row[7] else "",
        })
    wb.close()
    # 去重：同一零件号只保留第一条（优先取有数据的行）
    seen = {}
    for r in rows:
        if r["part_no"] not in seen:
            seen[r["part_no"]] = r
    result = list(seen.values())
    skipped = len(rows) - len(result)
    if skipped:
        print(f"    [去重] 去掉 {skipped} 条重复零件号")
    return result


def parse_berteli(filepath):
    """芜湖伯特利.xlsx → 同上格式"""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb["Sheet2"]  # Sheet2 是成本明细
    rows = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # 列: 原图产品编号(A), 图片(B), 本厂产品名称(C), 模具类型(D),
        #      材质(E), 用料规格(F), 参考冲床吨位(G), 单件毛重量(H),
        #      产品净重/g(I), 材料价格(J), 废料价格(K), 材料成本(L),
        #      表面处理(M), 胶成本(N), 喷涂成本/外协成本(O), 成本(P),
        #      2025年开票价格(Q), 2025销量(R)
        part_no_raw = row[0]
        if part_no_raw is None:
            continue
        part_no = str(part_no_raw).strip()
        if not part_no or part_no in ("None", "无", "—", "-"):
            continue
        # 去掉工艺后缀
        part_no = re.sub(r'[（(][^）)]*(?:涂|热|电|镀|喷|磷|钝|氧)[^）)]*[）)]', '', part_no).strip()
        if not part_no:
            continue
        material = str(row[4]).strip() if row[4] else ""
        twph_raw = str(row[5]).strip() if row[5] else ""
        T, W, PH = parse_twph(twph_raw)
        gross_g = parse_float(row[7])
        net_g   = parse_float(row[8])
        mat_price = parse_float(row[9])
        scrap_price = parse_float(row[10])
        surface_treat = str(row[12]).strip() if row[12] else ""
        # 表面处理成本 = 胶成本 + 喷涂/外协成本
        glue_cost = parse_float(row[13], 0) or 0
        spray_cost = parse_float(row[14], 0) or 0
        surface_cost = round(glue_cost + spray_cost, 4)
        surface_treatments = [{"name": surface_treat, "fee": surface_cost}] if surface_treat else []
        unit_2025 = parse_float(row[16])
        sales_2025 = parse_float(row[17])

        rows.append({
            "part_no": part_no,
            "material": material,
            "internal_name": str(row[2]).strip() if row[2] else "",  # C列 = 本厂产品名称
            "T": T, "W": W, "PH": PH,
            "gross_g": gross_g,
            "net_g": net_g,
            "mat_price": mat_price,
            "scrap_price": scrap_price,
            "surface_cost": surface_cost,
            "surface_treatments": surface_treatments,
            "unit_2025": unit_2025,
            "sales_2025": int(sales_2025) if sales_2025 else None,
            "remark": "",
        })
    wb.close()
    return rows


def parse_shanghai(filepath):
    """上海万向.xlsx → 同上格式"""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb["Sheet3"]
    rows = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # 列: 原图产品编号(A), 图片(B), 原图产品名称1(C), 模具类型(D),
        #      材质(E), 用料规格(F), 备注(G), 毛重(H), 单件净重量(I),
        #      材料价格(J), 废料价格(K), 材料成本(L), 回火(M), 喷涂(N),
        #      表面处理(O), 成本(P), 2025单价(Q), 2025年销量(R), 销售额(S), ...
        part_no_raw = row[0]
        if part_no_raw is None:
            continue
        part_no = str(part_no_raw).strip()
        # 跳过汇总行、无效行
        if not part_no or part_no in ("None", "0", "总计", "合计", "sum"):
            continue
        # 去掉工艺后缀
        part_no_orig = part_no
        part_no = re.sub(r'[（(][^）)]*(?:涂|热|电|镀|喷|磷|钝|氧)[^）)]*[）)]', '', part_no).strip()
        if not part_no:
            continue
        internal_name = str(row[2]).strip() if row[2] else ""
        material = str(row[4]).strip() if row[4] else ""
        twph_raw = str(row[5]).strip() if row[5] else ""
        gross_g = parse_float(row[7])
        net_g   = parse_float(row[8])
        # 跳过全空行：只有零件号，其他关键字段全为空
        if not material and not twph_raw and gross_g is None and net_g is None:
            print(f"    [跳过] 行{i}: {part_no} - 全行数据为空")
            continue
        T, W, PH = parse_twph(twph_raw)
        mat_price = parse_float(row[9])
        scrap_price = parse_float(row[10])
        temper = parse_float(row[12], 0) or 0   # 回火
        spray  = parse_float(row[13], 0) or 0    # 喷涂
        surf   = parse_float(row[14], 0) or 0     # 表面处理
        surface_cost = round(temper + spray + surf, 4)
        surface_treatments = []
        if temper > 0:
            surface_treatments.append({"name": "回火", "fee": temper})
        if spray > 0:
            surface_treatments.append({"name": "喷涂", "fee": spray})
        if surf > 0:
            surface_treatments.append({"name": "表面处理", "fee": surf})
        unit_2025 = parse_float(row[16])
        sales_2025 = parse_float(row[17])

        rows.append({
            "part_no": part_no,
            "internal_name": internal_name,
            "material": material,
            "T": T, "W": W, "PH": PH,
            "gross_g": gross_g,
            "net_g": net_g,
            "mat_price": mat_price,
            "scrap_price": scrap_price,
            "surface_cost": surface_cost,
            "surface_treatments": surface_treatments,
            "unit_2025": unit_2025,
            "sales_2025": int(sales_2025) if sales_2025 else None,
            "remark": str(row[6]) if row[6] else "",
        })
    wb.close()
    # 去重：同一零件号只保留第一条（优先取有数据的行）
    seen = {}
    for r in rows:
        if r["part_no"] not in seen:
            seen[r["part_no"]] = r
    result = list(seen.values())
    skipped = len(rows) - len(result)
    if skipped:
        print(f"    [去重] 去掉 {skipped} 条重复零件号")
    return result


# ======================================================================
# 数据库操作
# ======================================================================

import psycopg2
import json

DB_CONFIG = {
    "dbname": "stamping_system",
    "user": "postgres",
    "password": __import__("os").environ.get("ZEPHYR_DB_PASSWORD", ""),
    "host": "localhost",
    "port": "5432"
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def find_or_create_part(conn, part_no, customer_id, material, internal_name, remark, twph_str):
    """查找或新建零件，返回 (part_id, is_new)"""
    # 优先按 (customer_id, customer_product_no) 查
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM parts WHERE customer_id=%s AND customer_product_no=%s LIMIT 1",
            (customer_id, part_no))
        row = cur.fetchone()
        if row:
            part_id = row[0]
            # 如果 internal_name 为空但我们有值，补全
            if internal_name:
                cur.execute(
                    "UPDATE parts SET internal_name=%s WHERE id=%s AND (internal_name IS NULL OR internal_name='')",
                    (internal_name, part_id))
                conn.commit()
            return part_id, False

    # 按 part_number 查
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM parts WHERE part_number=%s LIMIT 1",
            (part_no,))
        row = cur.fetchone()
        if row:
            part_id = row[0]
            # 补全 customer_id, customer_product_no, internal_name
            cur.execute("""
                UPDATE parts
                SET customer_id=COALESCE(%s, customer_id),
                    customer_product_no=COALESCE(%s, customer_product_no),
                    internal_name=COALESCE(NULLIF(%s, ''), NULLIF(internal_name, ''), %s)
                WHERE id=%s;
            """, (customer_id, part_no, internal_name, internal_name, part_id))
            conn.commit()
            return part_id, False

    # 新建
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO parts (part_number, customer_product_no, customer_id,
                               material_name, internal_name, remark, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'DRAFT', NOW(), NOW())
            RETURNING id;
        """, (part_no, part_no, customer_id, material, internal_name, remark))
        part_id = cur.fetchone()[0]
        conn.commit()
        return part_id, True


def upsert_price(conn, part_id, customer_id, material, net_kg, gross_kg,
                 mat_price, scrap_price, surface_cost, surface_treatments):
    """插入或更新 prices 表，返回 price_id"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM prices WHERE part_id=%s AND customer_id=%s",
            (part_id, customer_id))
        row = cur.fetchone()

        surf_json = json.dumps(surface_treatments) if surface_treatments else "[]"

        if row:
            # UPDATE
            price_id = row[0]
            cur.execute("""
                UPDATE prices SET
                    material_name = %s,
                    net_weight = %s,
                    gross_weight = %s,
                    material_unit_price = %s,
                    scrap_price = %s,
                    surface_treatment_cost = %s,
                    surface_treatment = %s,
                    updated_at = NOW()
                WHERE id = %s;
            """, (material, net_kg, gross_kg, mat_price, scrap_price,
                  surface_cost, surf_json, price_id))
            conn.commit()
            return price_id, False
        else:
            # INSERT
            cur.execute("""
                INSERT INTO prices (part_id, customer_id, material_name, net_weight,
                                   gross_weight, material_unit_price, scrap_price,
                                   surface_treatment_cost, surface_treatment,
                                   created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id;
            """, (part_id, customer_id, material, net_kg, gross_kg,
                  mat_price, scrap_price, surface_cost, surf_json))
            price_id = cur.fetchone()[0]
            conn.commit()
            return price_id, True


def upsert_price_year(conn, price_id, year, unit_price, annual_sales):
    """插入或更新 price_years（若单价为空则跳过）"""
    if unit_price is None:
        return None, False
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM price_years WHERE price_id=%s AND year=%s",
            (price_id, year))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE price_years SET unit_price=%s, annual_sales=%s, updated_at=NOW()
                WHERE id=%s;
            """, (unit_price, annual_sales, row[0]))
            conn.commit()
            return row[0], False
        else:
            cur.execute("""
                INSERT INTO price_years (price_id, year, unit_price, annual_sales, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING id;
            """, (price_id, year, unit_price, annual_sales))
            row_id = cur.fetchone()[0]
            conn.commit()
            return row_id, True


# ======================================================================
# 导入流程
# ======================================================================

def import_customer(folder_name, parse_func):
    """导入一个客户的所有数据"""
    customer_id = CUSTOMER_MAP.get(folder_name)
    if customer_id is None:
        print(f"[错误] 文件夹 '{folder_name}' 未在 CUSTOMER_MAP 中注册")
        return

    folder_path = os.path.join(PRICES_DIR, folder_name)
    if not os.path.isdir(folder_path):
        print(f"[错误] 目录不存在: {folder_path}")
        return

    # 找 xlsx 文件
    xlsx_files = [f for f in os.listdir(folder_path) if f.endswith(".xlsx")]
    if not xlsx_files:
        print(f"[错误] 目录 {folder_path} 中无 xlsx 文件")
        return

    filepath = os.path.join(folder_path, xlsx_files[0])
    print(f"\n{'='*60}")
    print(f"开始导入: {folder_name} ({xlsx_files[0]})")
    print(f"  客户ID: {customer_id}")
    print(f"  文件: {filepath}")
    print(f"{'='*60}")

    rows = parse_func(filepath)
    print(f"  解析出 {len(rows)} 条有效数据")

    conn = get_conn()
    try:
        created_parts = 0
        matched_parts = 0
        created_prices = 0
        updated_prices = 0
        created_years = 0
        updated_years = 0
        errors = 0

        for row in rows:
            try:
                part_no = row["part_no"]
                material = row["material"] or ""
                remark = row.get("remark", "")
                twph_str = ""
                if row.get("T") and row.get("W") and row.get("PH"):
                    twph_str = f"{row['T']}*{row['W']}*{row['PH']}"
                    remark = (remark + f" | T×W×PH: {twph_str}").strip(" | ")

                # 净重/毛重 (g → kg)
                net_kg = round(row["net_g"] / 1000.0, 6) if row["net_g"] else None
                gross_kg = round(row["gross_g"] / 1000.0, 6) if row["gross_g"] else None

                surface_cost = row.get("surface_cost", 0) or 0
                surface_treatments = row.get("surface_treatments", [])

                # 零件
                part_id, is_new_part = find_or_create_part(
                    conn, part_no, customer_id, material,
                    row.get("internal_name", ""), remark, twph_str)
                if is_new_part:
                    created_parts += 1
                    print(f"  [新建零件] {part_no} (id={part_id})")
                else:
                    matched_parts += 1

                # 价格台账
                price_id, is_new_price = upsert_price(
                    conn, part_id, customer_id, material, net_kg, gross_kg,
                    row["mat_price"], row["scrap_price"],
                    surface_cost, surface_treatments)
                if is_new_price:
                    created_prices += 1
                else:
                    updated_prices += 1

                # 年份价格
                year_id, is_new_year = upsert_price_year(
                    conn, price_id, 2025, row["unit_2025"], row.get("sales_2025"))
                if is_new_year:
                    created_years += 1
                else:
                    updated_years += 1

            except Exception as e:
                errors += 1
                print(f"  [错误] {row.get('part_no','?')}: {e}")

    finally:
        conn.close()

    print(f"\n  【{folder_name}】导入结果:")
    print(f"    新建零件: {created_parts}  |  匹配零件: {matched_parts}")
    print(f"    新建价格: {created_prices}  |  更新价格: {updated_prices}")
    print(f"    新建年份: {created_years}  |  更新年份: {updated_years}")
    print(f"    错误: {errors}")


# ======================================================================
# 入口
# ======================================================================

def main():
    # 顺序执行
    import_customer("B-C武汉万向汽车制动器有限公司", parse_wuhan)
    import_customer("B-G芜湖伯特利", parse_berteli)
    import_customer("上海万向钱潮A-A", parse_shanghai)

    print("\n\n" + "=" * 60)
    print("全部导入完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
