import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict

excel_path = r'C:\Users\WIT_User\Documents\xwechat_files\uhaohan_2ed1\msg\file\2026-07\上海万向.xlsx'

print('=== DETAILED EXCEL ANALYSIS ===')
print()

with zipfile.ZipFile(excel_path, 'r') as zip_ref:
    ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

    # Read shared strings
    try:
        shared_strings_xml = zip_ref.read('xl/sharedStrings.xml')
        shared_strings_root = ET.fromstring(shared_strings_xml)
        shared_strings = []
        for si in shared_strings_root.findall('.//main:si', ns):
            t = si.find('.//main:t', ns)
            if t is not None and t.text:
                shared_strings.append(t.text)
    except KeyError:
        shared_strings = []

    # Process Sheet1 (main data sheet with images)
    print('=== SHEET 1 DETAILED ANALYSIS (sheet1.xml) ===')
    print()

    sheet_xml = zip_ref.read('xl/worksheets/sheet1.xml')
    sheet_root = ET.fromstring(sheet_xml)

    rows = sheet_root.findall('.//main:row', ns)

    # Analyze header row
    print('HEADER ROW ANALYSIS:')
    if rows:
        header_row = rows[0]
        header_cells = header_row.findall('.//main:c', ns)
        print(f'Header cells count: {len(header_cells)}')
        print('Headers:')
        for cell in header_cells:
            cell_ref = cell.get('r')
            cell_type = cell.get('t', 'n')
            v = cell.find('.//main:v', ns)
            if v is not None and v.text:
                if cell_type == 's':
                    try:
                        idx = int(v.text)
                        value = shared_strings[idx] if idx < len(shared_strings) else f'[{v.text}]'
                    except:
                        value = v.text
                else:
                    value = v.text
                print(f'  {cell_ref}: {value}')
    print()

    # Analyze merged cell patterns
    print('MERGED CELL PATTERNS:')
    merge_cells = sheet_root.find('.//main:mergeCells', ns)
    if merge_cells is not None:
        merges = merge_cells.findall('.//main:mergeCell', ns)

        # Group by column pattern
        col_patterns = defaultdict(list)
        for merge in merges:
            ref = merge.get('ref')
            # Extract column letter(s)
            col_part = ''.join(c for c in ref.split(':')[0] if c.isalpha())
            col_patterns[col_part].append(ref)

        print(f'Total merged ranges: {len(merges)}')
        print('Merged cells by starting column:')
        for col in sorted(col_patterns.keys()):
            print(f'  Column {col}: {len(col_patterns[col])} merges')
            # Show first 3 examples
            for example in col_patterns[col][:3]:
                print(f'    {example}')
    print()

    # Analyze data rows
    print('DATA ROW ANALYSIS:')
    print(f'Total rows: {len(rows)}')
    print()

    # Sample rows 1-10
    print('Rows 1-10 (full data):')
    for row in rows[:10]:
        row_num = row.get('r')
        cells = row.findall('.//main:c', ns)
        print(f'\nRow {row_num}: ({len(cells)} cells)')
        for cell in cells:
            cell_ref = cell.get('r')
            cell_type = cell.get('t', 'n')
            v = cell.find('.//main:v', ns)
            f = cell.find('.//main:f', ns)  # Formula

            if f is not None and f.text:
                print(f'  {cell_ref}: FORMULA={f.text}')
            elif v is not None and v.text:
                if cell_type == 's':
                    try:
                        idx = int(v.text)
                        value = shared_strings[idx] if idx < len(shared_strings) else f'[{v.text}]'
                    except:
                        value = v.text
                else:
                    value = v.text
                print(f'  {cell_ref}: {value}')
    print()

    # Analyze column B (image column)
    print('COLUMN B (IMAGE COLUMN) ANALYSIS:')
    col_b_formulas = []
    for row in rows[1:]:  # Skip header
        cells = row.findall('.//main:c', ns)
        for cell in cells:
            cell_ref = cell.get('r')
            if cell_ref and cell_ref.startswith('B'):
                f = cell.find('.//main:f', ns)
                if f is not None and f.text:
                    col_b_formulas.append((cell_ref, f.text))

    print(f'Image formulas in column B: {len(col_b_formulas)}')
    print('Sample formulas:')
    for ref, formula in col_b_formulas[:5]:
        print(f'  {ref}: {formula}')
    print()

    # Check for relationships to images
    print('IMAGE RELATIONSHIP ANALYSIS:')
    try:
        rels_xml = zip_ref.read('xl/worksheets/_rels/sheet1.xml.rels')
        rels_root = ET.fromstring(rels_xml)
        ns_rels = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}

        relationships = rels_root.findall('.//r:Relationship', ns_rels)
        image_rels = [rel for rel in relationships if 'image' in rel.get('Target', '').lower()]

        print(f'Total relationships: {len(relationships)}')
        print(f'Image relationships: {len(image_rels)}')
        for rel in image_rels[:5]:
            print(f'  Id={rel.get("Id")}, Target={rel.get("Target")}')
    except KeyError:
        print('No relationship file found for sheet1')
    print()

    # Analyze Sheet2 (simple mapping)
    print('=== SHEET 2 ANALYSIS (sheet2.xml) ===')
    print()

    sheet2_xml = zip_ref.read('xl/worksheets/sheet2.xml')
    sheet2_root = ET.fromstring(sheet2_xml)
    rows2 = sheet2_root.findall('.//main:row', ns)

    print(f'Total rows: {len(rows2)}')
    print('All rows:')
    for row in rows2[:15]:
        row_num = row.get('r')
        cells = row.findall('.//main:c', ns)
        cell_data = []
        for cell in cells:
            cell_type = cell.get('t', 'n')
            v = cell.find('.//main:v', ns)
            if v is not None and v.text:
                if cell_type == 's':
                    try:
                        idx = int(v.text)
                        value = shared_strings[idx] if idx < len(shared_strings) else f'[{v.text}]'
                    except:
                        value = v.text
                else:
                    value = v.text
                cell_data.append(value)
        print(f'  Row {row_num}: {" | ".join(str(c) for c in cell_data)}')
    print()

    # Analyze Sheet3 (pricing)
    print('=== SHEET 3 ANALYSIS (sheet3.xml) ===')
    print()

    sheet3_xml = zip_ref.read('xl/worksheets/sheet3.xml')
    sheet3_root = ET.fromstring(sheet3_xml)
    rows3 = sheet3_root.findall('.//main:row', ns)

    print(f'Total rows: {len(rows3)}')
    print('All rows:')
    for row in rows3[:15]:
        row_num = row.get('r')
        cells = row.findall('.//main:c', ns)
        cell_data = []
        for cell in cells:
            cell_type = cell.get('t', 'n')
            v = cell.find('.//main:v', ns)
            if v is not None and v.text:
                if cell_type == 's':
                    try:
                        idx = int(v.text)
                        value = shared_strings[idx] if idx < len(shared_strings) else f'[{v.text}]'
                    except:
                        value = v.text
                else:
                    value = v.text
                cell_data.append(value)
        print(f'  Row {row_num}: {" | ".join(str(c) for c in cell_data)}')

print()
print('=== ANALYSIS COMPLETE ===')
