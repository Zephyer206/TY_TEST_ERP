#!/usr/bin/env python3
"""
修复 part 21194 的错误 TWP 数据
客户件号 XC2.39.81/XC2.39.16/XC2.39.15 被误解析为规格
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from app.database import get_db_context


async def main():
    print("=" * 60)
    print("修复 Part 21194 错误 TWP 数据")
    print("=" * 60)

    async with get_db_context() as db:
        # 1. 验证当前状态
        result = await db.execute(text("""
            SELECT id, internal_name, thickness, width, pitch
            FROM parts
            WHERE id = 21194
        """))
        current = result.fetchone()

        if not current:
            print("ERROR: Part 21194 不存在")
            return

        print(f"\n当前状态:")
        print(f"  Part ID: {current[0]}")
        print(f"  名称: {current[1]}")
        print(f"  Thickness: {current[2]}")
        print(f"  Width: {current[3]}")
        print(f"  Pitch: {current[4]}")

        # 2. 验证来源数据
        result = await db.execute(text("""
            SELECT id, source_sheet, raw_data, parsed_thickness, parsed_width, parsed_pitch
            FROM excel_import_rows
            WHERE resolved_part_id = 21194
        """))
        source_rows = result.fetchall()

        print(f"\n来源数据 ({len(source_rows)} 行):")
        for row in source_rows:
            raw_data = row[2]
            print(f"  Row {row[0]} ({row[1]}):")
            if raw_data and len(raw_data) > 2:
                print(f"    raw_data[2] (客户件号): {raw_data[2]}")
            print(f"    parsed_thickness: {row[3]}")
            print(f"    parsed_width: {row[4]}")
            print(f"    parsed_pitch: {row[5]}")

        # 3. 确认错误：所有来源的 parsed 字段都是 NULL，说明规格列为空
        all_null = all(row[3] is None and row[4] is None and row[5] is None for row in source_rows)

        if all_null:
            print(f"\n[OK] 确认：所有 excel_import_rows 的 parsed T/W/P 都为 NULL")
            print(f"  说明原始 Excel 的规格列为空")
            print(f"  当前 parts 表的 T=2.39/W=2.39/P=2.39 是错误数据")
        else:
            print(f"\nWARNING: 发现非空的 parsed 字段，需要人工审核")
            return

        # 4. 创建备份
        backup_file = Path(__file__).parent / "backups" / "part_21194_before_fix.json"
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "part": {
                "id": current[0],
                "internal_name": current[1],
                "thickness": float(current[2]) if current[2] else None,
                "width": float(current[3]) if current[3] else None,
                "pitch": float(current[4]) if current[4] else None
            },
            "source_rows": [
                {
                    "id": row[0],
                    "source_sheet": row[1],
                    "customer_part_no": row[2][2] if row[2] and len(row[2]) > 2 else None,
                    "parsed_thickness": row[3],
                    "parsed_width": row[4],
                    "parsed_pitch": row[5]
                }
                for row in source_rows
            ]
        }

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] 备份已保存: {backup_file}")

        # 5. 执行修复
        print(f"\n执行修复: 将 part 21194 的 thickness/width/pitch 设为 NULL...")

        await db.execute(text("""
            UPDATE parts
            SET thickness = NULL,
                width = NULL,
                pitch = NULL
            WHERE id = 21194
        """))

        await db.commit()

        # 6. 验证修复结果
        result = await db.execute(text("""
            SELECT id, internal_name, thickness, width, pitch
            FROM parts
            WHERE id = 21194
        """))
        fixed = result.fetchone()

        print(f"\n修复后状态:")
        print(f"  Part ID: {fixed[0]}")
        print(f"  名称: {fixed[1]}")
        print(f"  Thickness: {fixed[2]}")
        print(f"  Width: {fixed[3]}")
        print(f"  Pitch: {fixed[4]}")

        if fixed[2] is None and fixed[3] is None and fixed[4] is None:
            print(f"\n[OK] 修复成功")
        else:
            print(f"\n[ERROR] 修复失败")


if __name__ == "__main__":
    asyncio.run(main())
