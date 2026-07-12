#!/usr/bin/env python3
"""
Excel数据导入脚本
导入五金模具及产品清单表到数据库
"""
import asyncio
import json
import re
import sys
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

import xlrd
from sqlalchemy import text
from app.database import engine

# 确定项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
EXCEL_DIR = Path(__file__).parent

# 加载材料分类数据
materials_file = PROJECT_ROOT / 'materials_classified.json'
with open(materials_file, 'r', encoding='utf-8') as f:
    MATERIALS_CLASSIFIED = json.load(f)

# 材料名称映射（Excel原文 -> 标准名称）
MATERIAL_MAPPING = {}
for mat in MATERIALS_CLASSIFIED:
    for variant in mat['variants']:
        MATERIAL_MAPPING[variant] = mat['name']


def parse_twph(spec_str: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[int]]:
    """
    解析用料规格字符串
    例如: "0.4*116+55 (1出2)" -> (0.4, 116, 55, 2)
    返回: (thickness, width, pitch, cavity_count)
    """
    if not spec_str:
        return None, None, None, None
    
    thickness = width = pitch = None
    cavity_count = None
    
    # 提取穴数 "1出2" -> 2
    cavity_match = re.search(r'(\d+)\s*出\s*(\d+)', spec_str)
    if cavity_match:
        cavity_count = int(cavity_match.group(2))
    
    # 提取尺寸 "0.4*116+55" 或 "1.2*125*37"
    numbers = re.findall(r'(\d+\.?\d*)', spec_str.split('(')[0])
    if len(numbers) >= 1:
        thickness = float(numbers[0])
    if len(numbers) >= 2:
        width = float(numbers[1])
    if len(numbers) >= 3:
        pitch = float(numbers[2])
    
    return thickness, width, pitch, cavity_count


def parse_mold_info(mold_type: str, mold_desc: str) -> Tuple[Optional[int], Optional[int]]:
    """
    解析模具信息
    返回: (forming_steps, cavity_count)
    
    连续模: 从TWP获取穴数
    工程模N: N为成型步数
    """
    forming_steps = None
    cavity_count = None
    
    if not mold_type:
        return forming_steps, cavity_count
    
    # 连续模
    if '连续模' in mold_type:
        # cavity_count从TWP中获取
        pass
    # 工程模
    elif '工程模' in mold_type:
        # 提取数字: "工程模9" -> 9
        match = re.search(r'(\d+)', mold_type)
        if match:
            forming_steps = int(match.group(1))
    
    # 从模数描述提取
    if mold_desc:
        # "9套" -> 9
        match = re.search(r'(\d+)\s*套', str(mold_desc))
        if match and not forming_steps:
            forming_steps = int(match.group(1))
    
    return forming_steps, cavity_count


async def import_materials():
    """导入材料字典"""
    async with engine.begin() as conn:
        print("正在导入材料字典...")

        imported = 0
        for idx, mat in enumerate(MATERIALS_CLASSIFIED):
            # 检查是否已存在
            result = await conn.execute(
                text("SELECT id FROM material_dict WHERE name = :name"),
                {"name": mat['name']}
            )

            if not result.fetchone():
                # 生成材料代码：使用base_material或name的前10个字符
                base = mat.get('base_material', mat['name'][:10]).replace(' ', '_').replace('/', '-')
                code = f"{base}_{idx}"

                await conn.execute(
                    text("""
                        INSERT INTO material_dict (code, name, category, is_active, sort_order)
                        VALUES (:code, :name, :category, TRUE, :sort_order)
                    """),
                    {
                        "code": code,
                        "name": mat['name'],
                        "category": mat['category'],
                        "sort_order": idx
                    }
                )
                imported += 1

        print(f"[OK] 导入 {imported} 种新材料（共 {len(MATERIALS_CLASSIFIED)} 种）")


async def import_customers(workbook):
    """导入客户信息"""
    async with engine.begin() as conn:
        print("正在导入客户信息...")
        
        customers = []
        
        for i in range(3, workbook.nsheets):
            sheet_name = workbook.sheet_names()[i]
            if sheet_name == 'Sheet2':
                continue
            
            # 提取客户名称和编号
            customer_name, customer_code = extract_customer_info(sheet_name)
            
            if customer_name:
                customers.append({
                    'name': customer_name,
                    'sheet_key': customer_code
                })
        
        # 批量插入
        for cust in customers:
            result = await conn.execute(
                text("SELECT id FROM customers WHERE name = :name"),
                {"name": cust['name']}
            )
            
            if not result.fetchone():
                await conn.execute(
                    text("INSERT INTO customers (name, sheet_key) VALUES (:name, :sheet_key)"),
                    cust
                )
        
        print(f"[OK] 导入 {len(customers)} 个客户")


def extract_customer_info(sheet_name: str) -> Tuple[str, Optional[str]]:
    """从Sheet名称提取客户名称和编号"""
    if not sheet_name:
        return None, None

    # 处理特殊格式: "丰铃公司Q" -> ("丰铃公司", "Q")
    match = re.search(r'^(.+?)([A-Z](?:-[A-Z])?)$', sheet_name)
    if match and '(' not in sheet_name:
        return match.group(1).strip(), match.group(2)

    # 标准格式: "浙江万宝机械有限公司(A)" -> ("浙江万宝机械有限公司", "A")
    match = re.search(r'^(.+?)[（(]([A-Z](?:-[A-Z])?)[）)]', sheet_name)
    if match:
        return match.group(1).strip(), match.group(2)

    # 特殊编号: "60T 连续模" -> ("60T 连续模", "60T")
    if sheet_name.startswith('60T'):
        return sheet_name, '60T'

    return sheet_name.strip(), None


def get_cell_value(sheet, row_idx, col_idx):
    """安全获取单元格值"""
    try:
        value = sheet.cell_value(row_idx, col_idx)
        if isinstance(value, str):
            return value.strip()
        return value
    except:
        return None


def is_merged_row(sheet, row_idx, prev_row_data):
    """
    检测当前行是否是合并单元格的延续（左右件）
    通过比较关键列：模具类型(7)、材质(9)
    """
    if not prev_row_data:
        return False

    # 检查零件编号(2)是否为空或连续
    part_no = get_cell_value(sheet, row_idx, 2)
    if not part_no:
        return True  # 零件编号为空，可能是合并单元格

    # 检查模具类型(7)和材质(9)
    mold_type = get_cell_value(sheet, row_idx, 7)
    material = get_cell_value(sheet, row_idx, 9)

    prev_mold_type = prev_row_data.get('mold_type')
    prev_material = prev_row_data.get('material')

    # 如果这些关键字段为空，说明是合并单元格的延续
    if not mold_type and not material:
        return True

    # 如果关键字段相同，且零件编号连续
    if mold_type == prev_mold_type and material == prev_material:
        prev_part_no = prev_row_data.get('part_number')
        if prev_part_no and part_no:
            # 检查是否为连续编号
            try:
                if abs(int(part_no) - int(prev_part_no)) == 1:
                    return True
            except:
                pass

    return False


async def get_material_id(conn, material_name: str) -> Optional[int]:
    """根据材料名称获取材料ID"""
    if not material_name:
        return None

    # 先尝试标准名称匹配
    standard_name = MATERIAL_MAPPING.get(material_name.strip())
    if not standard_name:
        standard_name = material_name.strip()

    result = await conn.execute(
        text("SELECT id FROM material_dict WHERE name = :name"),
        {"name": standard_name}
    )
    row = result.fetchone()
    return row[0] if row else None


async def get_customer_id(conn, customer_name: str) -> Optional[int]:
    """根据客户名称获取客户ID"""
    if not customer_name:
        return None

    result = await conn.execute(
        text("SELECT id FROM customers WHERE name = :name"),
        {"name": customer_name.strip()}
    )
    row = result.fetchone()
    return row[0] if row else None


async def import_customer_sheet(sheet, sheet_name):
    """导入单个客户Sheet的数据"""
    parts_count = 0
    tooling_count = 0
    multi_count = 0
    errors = []
    material_mismatches = []

    # 提取客户信息
    customer_name, customer_code = extract_customer_info(sheet_name)
    if not customer_name:
        return 0, 0, 0, ["无法提取客户信息"], []

    try:
        async with engine.begin() as conn:
            # 获取客户ID
            customer_id = await get_customer_id(conn, customer_name)
            if not customer_id:
                return 0, 0, 0, [f"客户不存在: {customer_name}"], []

            print(f"  处理客户: {customer_name} ({customer_code})")

            # 跳过表头，从第2行开始（索引1，因为0是表头）
            prev_row_data = None
            row_idx = 1

            while row_idx < sheet.nrows:
                # 提取当前行数据
                try:
                    seq = get_cell_value(sheet, row_idx, 0)
                    part_number = get_cell_value(sheet, row_idx, 2)
                    customer_product_name1 = get_cell_value(sheet, row_idx, 3)
                    customer_product_name2 = get_cell_value(sheet, row_idx, 4)
                    tooling_no = get_cell_value(sheet, row_idx, 5)
                    internal_name = get_cell_value(sheet, row_idx, 6)
                    mold_type = get_cell_value(sheet, row_idx, 7)
                    mold_count_str = get_cell_value(sheet, row_idx, 8)
                    material = get_cell_value(sheet, row_idx, 9)
                    spec_twph = get_cell_value(sheet, row_idx, 10)
                    remark = get_cell_value(sheet, row_idx, 11)
                    press_tonnage = get_cell_value(sheet, row_idx, 12)
                    ppap_no = get_cell_value(sheet, row_idx, 13)
                    vehicle_model = get_cell_value(sheet, row_idx, 15)
                    gross_weight = get_cell_value(sheet, row_idx, 16)
                    net_weight = get_cell_value(sheet, row_idx, 17)

                    # 跳过空行
                    if not part_number and not tooling_no:
                        row_idx += 1
                        continue

                    # 合并产品名称
                    customer_product_name = customer_product_name1 or ''
                    if customer_product_name2:
                        customer_product_name += ' ' + str(customer_product_name2)
                    customer_product_name = customer_product_name.strip()

                    # 解析TWP
                    thickness, width, pitch, cavity_count_from_twp = parse_twph(str(spec_twph) if spec_twph else '')

                    # 解析模具信息
                    forming_steps, _ = parse_mold_info(str(mold_type) if mold_type else '', str(mold_count_str) if mold_count_str else '')

                    # 获取材料ID
                    material_id = await get_material_id(conn, str(material) if material else '')
                    if material and not material_id:
                        material_mismatches.append(f"行{row_idx + 1}: {material}")

                    # 检查是否为左右件
                    is_multi = is_merged_row(sheet, row_idx, prev_row_data)

                    if is_multi and prev_row_data:
                        # 这是右件，使用上一行的tooling_id
                        tooling_id = prev_row_data['tooling_id']
                        part_position = 'right'

                        # 更新tooling记录为多产品模式
                        await conn.execute(
                            text("""
                                UPDATE tooling
                                SET is_multi_product = TRUE, product_count = 2
                                WHERE id = :tooling_id
                            """),
                            {"tooling_id": tooling_id}
                        )

                        # 更新左件的位置
                        await conn.execute(
                            text("""
                                UPDATE parts
                                SET part_position = 'left'
                                WHERE id = :part_id
                            """),
                            {"part_id": prev_row_data['part_id']}
                        )

                        multi_count += 1
                    else:
                        # 这是独立产品或左件，创建新的tooling记录
                        part_position = None

                        # 插入tooling记录
                        result = await conn.execute(
                            text("""
                                INSERT INTO tooling (
                                    customer_id, tooling_no, name, customer_product_no,
                                    customer_product_name, mold_type, material, material_id,
                                    forming_steps, press_tonnage, remark,
                                    ppap_no, vehicle_model, seq,
                                    cavity_count, is_multi_product, product_count
                                ) VALUES (
                                    :customer_id, :tooling_no, :name, :customer_product_no,
                                    :customer_product_name, :mold_type, :material, :material_id,
                                    :forming_steps, :press_tonnage, :remark,
                                    :ppap_no, :vehicle_model, :seq,
                                    :cavity_count, FALSE, 1
                                ) RETURNING id
                            """),
                            {
                                "customer_id": customer_id,
                                "tooling_no": tooling_no,
                                "name": internal_name,
                                "customer_product_no": part_number,
                                "customer_product_name": customer_product_name,
                                "mold_type": mold_type,
                                "material": material,
                                "material_id": material_id,
                                "forming_steps": forming_steps,
                                "press_tonnage": press_tonnage,
                                "remark": remark,
                                "ppap_no": ppap_no,
                                "vehicle_model": vehicle_model,
                                "seq": seq if isinstance(seq, (int, float)) else None,
                                "cavity_count": f"1出{cavity_count_from_twp}" if cavity_count_from_twp else None
                            }
                        )
                        tooling_id = result.fetchone()[0]
                        tooling_count += 1

                    # 插入parts记录
                    result = await conn.execute(
                        text("""
                            INSERT INTO parts (
                                customer_id, part_number, internal_name,
                                customer_product_name, material_id, spec_twph,
                                thickness, width, pitch,
                                gross_weight, net_weight, part_position,
                                spray_status, version, part_status, stock_pcs,
                                mold_number, mold_type, press_tonnage, ppap_no,
                                customer_product_no, vehicle_model
                            ) VALUES (
                                :customer_id, :part_number, :internal_name,
                                :customer_product_name, :material_id, :spec_twph,
                                :thickness, :width, :pitch,
                                :gross_weight, :net_weight, :part_position,
                                'pending', 'v1', 'MASS_PRODUCTION', 0,
                                :tooling_no, :mold_type, :press_tonnage, :ppap_no,
                                :customer_product_no, :vehicle_model
                            ) RETURNING id
                        """),
                        {
                            "customer_id": customer_id,
                            "part_number": part_number,
                            "internal_name": internal_name,
                            "customer_product_name": customer_product_name,
                            "material_id": material_id,
                            "spec_twph": spec_twph,
                            "thickness": thickness,
                            "width": width,
                            "pitch": pitch,
                            "gross_weight": gross_weight if isinstance(gross_weight, (int, float)) else None,
                            "net_weight": net_weight if isinstance(net_weight, (int, float)) else None,
                            "part_position": part_position,
                            "tooling_no": tooling_no,
                            "mold_type": mold_type,
                            "press_tonnage": press_tonnage,
                            "ppap_no": ppap_no,
                            "customer_product_no": part_number,
                            "vehicle_model": vehicle_model
                        }
                    )
                    part_id = result.fetchone()[0]
                    parts_count += 1

                    # 保存当前行数据，用于下一行的合并检测
                    prev_row_data = {
                        'tooling_id': tooling_id,
                        'part_id': part_id,
                        'part_number': part_number,
                        'mold_type': mold_type,
                        'material': material
                    }

                except Exception as e:
                    errors.append(f"行{row_idx + 1}: {str(e)}")
                    prev_row_data = None

                row_idx += 1

    except Exception as e:
        return 0, 0, 0, [f"Sheet处理失败: {str(e)}"], []

    return parts_count, tooling_count, multi_count, errors, material_mismatches


async def import_main_data(workbook):
    """导入主数据：零件和模具"""
    print("\n正在导入主数据...")

    total_parts = 0
    total_tooling = 0
    total_multi_product = 0
    all_errors = []
    all_material_mismatches = []

    # 遍历所有客户Sheet（从Sheet 4开始）
    for sheet_idx in range(3, workbook.nsheets):
        sheet = workbook.sheet_by_index(sheet_idx)
        sheet_name = workbook.sheet_names()[sheet_idx]

        # 跳过特殊Sheet
        if sheet_name == 'Sheet2':
            continue

        # 导入单个客户的数据
        parts, tooling, multi, errors, mismatches = await import_customer_sheet(sheet, sheet_name)

        total_parts += parts
        total_tooling += tooling
        total_multi_product += multi

        if errors:
            all_errors.extend([f"{sheet_name} - {e}" for e in errors])
        if mismatches:
            all_material_mismatches.extend([f"{sheet_name} - {m}" for m in mismatches])

    # 打印统计信息
    print(f"\n[OK] 导入完成:")
    print(f"  - 模具记录: {total_tooling}")
    print(f"  - 零件记录: {total_parts}")
    print(f"  - 左右件组: {total_multi_product}")

    if all_material_mismatches:
        print(f"\n[!] 材料匹配失败 ({len(all_material_mismatches)}):")
        for i, msg in enumerate(all_material_mismatches[:10]):
            print(f"    {msg}")
        if len(all_material_mismatches) > 10:
            print(f"    ... 还有 {len(all_material_mismatches) - 10} 条")

    if all_errors:
        print(f"\n[!] 跳过的行 ({len(all_errors)}):")
        for i, msg in enumerate(all_errors[:10]):
            print(f"    {msg}")
        if len(all_errors) > 10:
            print(f"    ... 还有 {len(all_errors) - 10} 条")


async def main():
    """主函数"""
    print("=" * 80)
    print("开始导入Excel数据到数据库")
    print("=" * 80)

    # 打开Excel文件
    excel_path = EXCEL_DIR / '五金模具及产品清单表.xls'
    if not excel_path.exists():
        print(f"错误: 找不到Excel文件: {excel_path}")
        return

    wb = xlrd.open_workbook(str(excel_path), formatting_info=False)

    # 步骤1: 导入材料
    await import_materials()

    # 步骤2: 导入客户
    await import_customers(wb)

    # 步骤3: 导入主数据
    await import_main_data(wb)

    print("\n" + "=" * 80)
    print("导入完成！")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
