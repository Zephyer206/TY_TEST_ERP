import sys
import asyncio
import re
from decimal import Decimal
from typing import Tuple, Optional

sys.path.insert(0, ".")

from app.database import async_session_maker
from app.models.part import Part
from app.models.excel_import import ExcelImportRow
from app.models.part_tooling_spec import PartToolingSpec
from sqlalchemy import select


def normalize_spec_string(raw_spec: str) -> str:
    if not raw_spec:
        return raw_spec
    normalized = re.sub(r'\*{2,}', '*', raw_spec)
    return normalized


def parse_twp_from_spec(spec_str: str) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    if not spec_str:
        return None, None, None
    
    spec_str = spec_str.strip()
    parts = spec_str.split('*')
    
    t, w, p = None, None, None
    
    if len(parts) >= 1:
        try:
            t = Decimal(parts[0].strip())
        except:
            pass
    
    if len(parts) >= 2:
        try:
            w = Decimal(parts[1].strip())
        except:
            pass
    
    if len(parts) >= 3:
        p_str = parts[2].strip()
        if '(' in p_str:
            p_str = p_str.split('(')[0].strip()
        try:
            p = Decimal(p_str)
        except:
            pass
    
    return t, w, p


async def main():
    target_part_ids = [1235, 2718, 3213, 3214, 3241, 3242, 3270, 3271]
    
    async with async_session_maker() as session:
        print("=== PHASE 1: Verification ===")
        print()
        
        parts_result = await session.execute(
            select(Part).where(Part.id.in_(target_part_ids))
        )
        parts = {p.id: p for p in parts_result.scalars().all()}
        
        print(f"Loaded {len(parts)} target parts")
        
        rows_result = await session.execute(
            select(ExcelImportRow)
            .where(ExcelImportRow.resolved_part_id.in_(target_part_ids))
            .where(ExcelImportRow.resolved_tooling_id.is_not(None))
            .order_by(ExcelImportRow.id)
        )
        rows = rows_result.scalars().all()
        
        print(f"Loaded {len(rows)} Excel import rows with resolved IDs")
        print()
        
        verified_rows = []
        
        for row in rows:
            part = parts.get(row.resolved_part_id)
            if not part:
                print(f"ERROR: Row {row.id} references non-existent part {row.resolved_part_id}")
                continue
            
            if not row.raw_data:
                continue

            if not isinstance(row.raw_data, list) or len(row.raw_data) <= 10:
                continue

            raw_spec = row.raw_data[10]
            if not raw_spec or raw_spec == '':
                continue
            
            if '**' not in str(raw_spec):
                continue
            
            normalized_spec = normalize_spec_string(str(raw_spec))
            parsed_t, parsed_w, parsed_p = parse_twp_from_spec(normalized_spec)
            
            part_t = part.thickness
            part_w = part.width
            part_p = part.pitch
            
            if parsed_t != part_t or parsed_w != part_w or parsed_p != part_p:
                print(f"MISMATCH: Row {row.id}, Part {row.resolved_part_id}")
                print(f"  Raw spec: {raw_spec}")
                print(f"  Normalized: {normalized_spec}")
                print(f"  Parsed: {parsed_t}/{parsed_w}/{parsed_p}")
                print(f"  Part TWP: {part_t}/{part_w}/{part_p}")
                continue
            
            verified_rows.append({
                'row': row,
                'part': part,
                'raw_spec': raw_spec,
                'normalized_spec': normalized_spec,
                'parsed_t': parsed_t,
                'parsed_w': parsed_w,
                'parsed_p': parsed_p,
            })
            
            print(f"Row {row.id}: Part {row.resolved_part_id}, Tooling {row.resolved_tooling_id}")
            print(f"  Source: {row.source_sheet}[{row.source_row}]")
            print(f"  {raw_spec} -> {normalized_spec}")
            print()
        
        print(f"=== PHASE 2: Transaction ===")
        print(f"Verified {len(verified_rows)} rows ready for update")
        print()
        
        if len(verified_rows) == 0:
            print("No rows to process.")
            return
        
        try:
            updated_rows = []
            inserted_specs = []
            
            for item in verified_rows:
                row = item['row']
                
                before_t = row.parsed_thickness
                before_w = row.parsed_width
                before_p = row.parsed_pitch
                
                row.parsed_thickness = item['parsed_t']
                row.parsed_width = item['parsed_w']
                row.parsed_pitch = item['parsed_p']
                
                updated_rows.append({
                    'id': row.id,
                    'source': f"{row.source_sheet}[{row.source_row}]",
                    'part_id': row.resolved_part_id,
                    'tooling_id': row.resolved_tooling_id,
                    'before_t': before_t,
                    'before_w': before_w,
                    'before_p': before_p,
                    'after_t': item['parsed_t'],
                    'after_w': item['parsed_w'],
                    'after_p': item['parsed_p'],
                })
                
                new_spec = PartToolingSpec(
                    part_id=row.resolved_part_id,
                    tooling_id=row.resolved_tooling_id,
                    spec_twph=item['normalized_spec'],
                    thickness=item['parsed_t'],
                    width=item['parsed_w'],
                    pitch=item['parsed_p'],
                    is_primary=False,
                    source_sheet=row.source_sheet,
                    source_row=row.source_row,
                )
                session.add(new_spec)
                
                inserted_specs.append({
                    'part_id': row.resolved_part_id,
                    'tooling_id': row.resolved_tooling_id,
                    'source': f"{row.source_sheet}[{row.source_row}]",
                    'spec_twph': item['normalized_spec'],
                })
            
            await session.commit()
            
            print("Transaction committed!")
            print()
            print("=== RESULTS ===")
            print()
            print(f"Updated {len(updated_rows)} excel_import_rows:")
            for ur in updated_rows:
                print(f"  Row {ur['id']} @ {ur['source']}")
                print(f"    Part {ur['part_id']}, Tooling {ur['tooling_id']}")
                print(f"    Before: {ur['before_t']}/{ur['before_w']}/{ur['before_p']}")
                print(f"    After:  {ur['after_t']}/{ur['after_w']}/{ur['after_p']}")
            
            print()
            print(f"Inserted {len(inserted_specs)} PartToolingSpec records:")
            for ins in inserted_specs:
                print(f"  Part {ins['part_id']}, Tooling {ins['tooling_id']} @ {ins['source']}")
                print(f"    spec_twph: {ins['spec_twph']}, is_primary: False")
            
        except Exception as e:
            await session.rollback()
            print(f"Transaction rolled back: {e}")
            raise


if __name__ == '__main__':
    asyncio.run(main())
