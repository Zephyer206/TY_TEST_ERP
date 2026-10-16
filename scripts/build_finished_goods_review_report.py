import asyncio
import csv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import text
from app.database import async_session_maker
OUT = Path(__file__).resolve().parents[1] / 'docs'
def category(errors):
    value = errors or ''
    if '负库存' in value: return '禁止直接入账：负库存'
    if 'B/C' in value: return '人工判断：B/C列不确定'
    if '客户' in value and '零件' in value: return '人工判断：客户与零件都未匹配'
    if '客户' in value: return '人工判断：客户未匹配'
    if '歧义' in value: return '人工判断：零件匹配歧义'
    if '零件' in value: return '人工判断：零件未匹配'
    return '人工判断：其他'
async def main():
    OUT.mkdir(exist_ok=True)
    async with async_session_maker() as session:
        status_rows = (await session.execute(text("SELECT validation_status,count(*) FROM excel_import_rows WHERE batch_id=8 GROUP BY validation_status"))).fetchall()
        status = {row[0]: row[1] for row in status_rows}
        rows = (await session.execute(text("SELECT id,source_sheet,source_row,resolved_customer_id,parsed_customer_part_no,parsed_customer_part_name,validation_errors,raw_data FROM excel_import_rows WHERE batch_id=8 AND validation_status='REVIEW' ORDER BY source_sheet,source_row"))).mappings().all()
        counts = {}; sheet_counts = {}; samples = {}
        csv_path = OUT / 'finished_goods_review_queue_2026-09-24.csv'
        with csv_path.open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle)
            writer.writerow(['导入记录ID','工作表','源行号','客户ID','规范化件号','规范化零件名','结存数量','库位','原始B','原始C','系统错误','判定类别','建议'])
            for row in rows:
                raw = row['raw_data'] or {}; b=(raw.get('B') or {}).get('value'); c=(raw.get('C') or {}).get('value'); qty=raw.get('closing_qty'); location=raw.get('location'); group=category(row['validation_errors'])
                counts[group] = counts.get(group,0)+1; sheet_counts[row['source_sheet']] = sheet_counts.get(row['source_sheet'],0)+1; samples.setdefault(group,[]).append((row['source_sheet'],row['source_row'],row['parsed_customer_part_no'],row['parsed_customer_part_name'],qty,location))
                advice = '确认客户后再匹配零件' if '客户' in group else ('确认B/C哪列是件号' if 'B/C' in group else ('选择唯一内部零件' if '歧义' in group else '确认新增客户件号或新零件'))
                writer.writerow([row['id'],row['source_sheet'],row['source_row'],row['resolved_customer_id'],row['parsed_customer_part_no'],row['parsed_customer_part_name'],qty,location,b,c,row['validation_errors'],group,advice])
        lines = [f'# 成品库存待审理汇总\n\n', f'- 库存日期：2026-09-24\n- 导入批次：8\n- 已确认入账：{status.get("IMPORTED",0)} 条\n- 待审理：{status.get("REVIEW",0)} 条\n\n', '## 待审理分类\n\n']
        for key,value in sorted(counts.items(), key=lambda item:-item[1]): lines.append(f'- {key}：{value} 条\n')
        lines += ['\n## 审理顺序\n\n','1. 确认客户简称与正式客户的对应关系。\n','2. 确认 B/C 列的件号、零件名方向。\n','3. 已有内部零件的，选择唯一 part_id。\n','4. 系统没有内部零件的，决定新增零件或暂不入账。\n','5. 负库存单独说明原因，不能直接转为可用库存。\n\n','## 各工作表待审理数量（前20）\n\n']
        for key,value in sorted(sheet_counts.items(), key=lambda item:-item[1])[:20]: lines.append(f'- {key}：{value} 条\n')
        lines.append('\n## 样例\n')
        for key,values in sorted(samples.items(), key=lambda item:-len(item[1])):
            lines.append(f'\n### {key}\n')
            for item in values[:5]: lines.append(f'- 工作表 {item[0]} 第 {item[1]} 行：件号={item[2]}，零件名={item[3]}，结存={item[4]}，库位={item[5]}\n')
        lines.append('\n详细逐行清单见同目录 CSV 文件。审核后按导入记录ID回写，不需要重新读取原 Excel。\n')
        summary_path=OUT/'finished_goods_review_summary_2026-09-24.md'; summary_path.write_text(''.join(lines),encoding='utf-8'); print({'review_rows':len(rows),'status':status,'categories':counts,'summary_file':str(summary_path),'queue_file':str(csv_path)})
asyncio.run(main())
