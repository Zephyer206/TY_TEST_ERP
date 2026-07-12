#!/usr/bin/env python3
"""
测试导入脚本 - 仅导入前3个客户
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

import xlrd
from sqlalchemy import text
from app.database import engine

# 设置控制台编码
import sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


async def test_import():
    """测试导入功能"""
    print("=" * 60)
    print("测试Excel数据导入")
    print("=" * 60)

    # 打开Excel文件
    excel_path = Path(__file__).parent / '五金模具及产品清单表.xls'
    if not excel_path.exists():
        print(f"错误: 找不到Excel文件")
        return

    wb = xlrd.open_workbook(str(excel_path))

    print(f"\nExcel文件信息:")
    print(f"  总Sheet数: {wb.nsheets}")
    print(f"  Sheet列表:")
    for i in range(min(10, wb.nsheets)):
        print(f"    [{i}] {wb.sheet_names()[i]}")

    # 测试读取第一个客户Sheet
    if wb.nsheets > 3:
        sheet = wb.sheet_by_index(3)
        print(f"\n测试读取Sheet: {wb.sheet_names()[3]}")
        print(f"  行数: {sheet.nrows}")
        print(f"  列数: {sheet.ncols}")

        # 读取前3行
        print(f"\n前3行数据:")
        for row_idx in range(min(3, sheet.nrows)):
            row_data = []
            for col_idx in range(min(10, sheet.ncols)):
                try:
                    val = sheet.cell_value(row_idx, col_idx)
                    if isinstance(val, str):
                        val = val[:20]  # 限制字符串长度
                    row_data.append(str(val))
                except:
                    row_data.append("ERR")
            print(f"  行{row_idx}: {' | '.join(row_data)}")

    # 测试数据库连接
    print(f"\n测试数据库连接:")
    async with engine.begin() as conn:
        # 统计现有数据
        result = await conn.execute(text("SELECT COUNT(*) FROM material_dict"))
        mat_count = result.fetchone()[0]
        print(f"  material_dict: {mat_count} 条")

        result = await conn.execute(text("SELECT COUNT(*) FROM customers"))
        cust_count = result.fetchone()[0]
        print(f"  customers: {cust_count} 条")

        result = await conn.execute(text("SELECT COUNT(*) FROM tooling"))
        tool_count = result.fetchone()[0]
        print(f"  tooling: {tool_count} 条")

        result = await conn.execute(text("SELECT COUNT(*) FROM parts"))
        parts_count = result.fetchone()[0]
        print(f"  parts: {parts_count} 条")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(test_import())
