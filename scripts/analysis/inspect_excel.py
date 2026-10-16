import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
import re

excel_path = r'C:\Users\WIT_User\Documents\xwechat_files\uhaohan_2ed1\msg\file\2026-07\上海万向.xlsx'

print('=== EXCEL WORKBOOK INSPECTION ===')
print(f'File: 上海万向.xlsx')
print()

with zipfile.ZipFile(excel_path, 'r') as zip_ref:
    # List all files in the archive
    print('=== ARCHIVE CONTENTS ===')
    file_list = zip_ref.namelist()
    print(f'Total files: {len(file_list)}')

    # Show structure
    sheets = [f for f in file_list if f.startswith('xl/worksheets/')]
    drawings = [f for f in file_list if f.startswith('xl/drawings/')]
    media = [f for f in file_list if f.startswith('xl/media/')]

    print(f'Worksheets: {len(sheets)}')
    print(f'Drawings: {len(drawings)}')
    print(f'Media files: {len(media)}')
    print()

    # Read workbook.xml to get sheet names
    print('=== WORKBOOK METADATA ===')
    workbook_xml = zip_ref.read('xl/workbook.xml')
    workbook_root = ET.fromstring(workbook_xml)

    # Parse namespaces
    ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

    sheets_info = []
    for sheet in workbook_root.findall('.//main:sheet', ns):
        sheet_name = sheet.get('name')
        sheet_id = sheet.get('sheetId')
        r_id = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        sheets_info.append((sheet_name, sheet_id, r_id))
        print(f'Sheet: {sheet_name} (ID: {sheet_id}, rId: {r_id})')

    print()

    # Read shared strings
    try:
        shared_strings_xml = zip_ref.read('xl/sharedStrings.xml')
        shared_strings_root = ET.fromstring(shared_strings_xml)
        shared_strings = []
        for si in shared_strings_root.findall('.//main:si', ns):
            t = si.find('.//main:t', ns)
            if t is not None and t.text:
                shared_strings.append(t.text)
        print(f'Shared strings: {len(shared_strings)} entries')
        print()
    except KeyError:
        shared_strings = []
        print('No shared strings found')
        print()

    # Process each worksheet
    for idx, sheet_file in enumerate(sorted(sheets)):
        # Skip directories
        if sheet_file.endswith('/'):
            continue

        print(f'=== SHEET {idx + 1}: {sheet_file} ===')

        try:
            sheet_xml = zip_ref.read(sheet_file)
            if len(sheet_xml) == 0:
                print('Empty file, skipping')
                print()
                continue
            sheet_root = ET.fromstring(sheet_xml)
        except Exception as e:
            print(f'Error parsing sheet: {e}')
            print()
            continue

        # Get dimensions
        dimension = sheet_root.find('.//main:dimension', ns)
        if dimension is not None:
            ref = dimension.get('ref')
            print(f'Dimension: {ref}')

        # Count rows and columns
        rows = sheet_root.findall('.//main:row', ns)
        print(f'Row elements: {len(rows)}')

        if rows:
            first_row = rows[0].get('r')
            last_row = rows[-1].get('r')
            print(f'Row range: {first_row} to {last_row}')

        # Get merged cells
        merge_cells = sheet_root.find('.//main:mergeCells', ns)
        if merge_cells is not None:
            merges = merge_cells.findall('.//main:mergeCell', ns)
            print(f'Merged cell ranges: {len(merges)}')
            for merge in merges[:10]:
                print(f'  {merge.get("ref")}')
            if len(merges) > 10:
                print(f'  ... and {len(merges) - 10} more')
        else:
            print('No merged cells')

        print()

        # Sample first few rows
        print('First 5 rows (sample cells):')
        for row in rows[:5]:
            row_num = row.get('r')
            cells = row.findall('.//main:c', ns)
            cell_values = []
            for cell in cells[:10]:  # First 10 cells
                cell_ref = cell.get('r')
                cell_type = cell.get('t', 'n')  # n=number, s=shared string, str=string
                v = cell.find('.//main:v', ns)
                if v is not None and v.text:
                    if cell_type == 's':  # Shared string
                        try:
                            idx = int(v.text)
                            value = shared_strings[idx] if idx < len(shared_strings) else f'[{v.text}]'
                        except:
                            value = v.text
                    else:
                        value = v.text
                    cell_values.append(f'{cell_ref}={value}')

            if cell_values:
                print(f'  Row {row_num}: {", ".join(cell_values)}')

        print()
        print('-' * 80)
        print()

    # Check for images/drawings
    if media:
        print('=== MEDIA FILES ===')
        for media_file in media:
            print(f'  {media_file}')
        print()

    if drawings:
        print('=== DRAWINGS ===')
        for drawing_file in drawings:
            print(f'  {drawing_file}')
            try:
                drawing_xml = zip_ref.read(drawing_file)
                drawing_root = ET.fromstring(drawing_xml)
                # Try to find anchor information
                ns_drawing = {
                    'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
                    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'
                }
                anchors = drawing_root.findall('.//xdr:oneCellAnchor', ns_drawing)
                anchors.extend(drawing_root.findall('.//xdr:twoCellAnchor', ns_drawing))

                if anchors:
                    print(f'    Anchored objects: {len(anchors)}')
                    for anchor in anchors[:3]:
                        from_elem = anchor.find('.//xdr:from', ns_drawing)
                        if from_elem is not None:
                            col = from_elem.find('.//xdr:col', ns_drawing)
                            row = from_elem.find('.//xdr:row', ns_drawing)
                            if col is not None and row is not None:
                                print(f'      Anchor at col={col.text}, row={row.text}')
            except Exception as e:
                print(f'    Error reading drawing: {e}')
        print()

print('=== INSPECTION COMPLETE ===')
