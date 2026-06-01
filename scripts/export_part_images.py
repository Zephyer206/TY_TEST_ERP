# -*- coding: utf-8 -*-
"""导出零件图片到 static/uploads/part_images/{客户}/{零件号}/"""
import zipfile, re, os, openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
PRICES_DIR = os.path.join(BASE, "..", "static", "uploads", "prices")
EXPORT_DIR = os.path.join(BASE, "..", "static", "uploads", "part_images")


def read_shared_strings(z):
    """读取共享字符串"""
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    content = z.read('xl/sharedStrings.xml').decode('utf-8')
    strings = re.findall(r'<si>(.*?)</si>', content, re.DOTALL)
    result = []
    for si in strings:
        texts = re.findall(r'<t[^>]*>([^<]*)</t>', si)
        result.append(''.join(texts))
    return result


def resolve_sheet_xml(filepath, openpyxl_name):
    """根据 openpyxl sheet 名称找到对应的 xl/worksheets/sheetN.xml"""
    with zipfile.ZipFile(filepath, 'r') as z:
        rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8')
        # rId → target
        rid_map = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels))
        wb_xml = z.read('xl/workbook.xml').decode('utf-8')
        # workbook.xml 中 sheet 顺序对应 rId1, rId2, ...
        rid_list = re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="(rId\d+)"', wb_xml)
        for name, rid in rid_list:
            if name == openpyxl_name:
                target = rid_map.get(rid, '')
                if not target.startswith('xl/'):
                    target = 'xl/' + target
                return target
        # fallback: 用顺序 index
        idx = 0
        for name, _ in rid_list:
            if name == openpyxl_name:
                return f'xl/worksheets/sheet{idx+1}.xml'
            idx += 1
    return f'xl/worksheets/sheet1.xml'


def best_sheet(filepath):
    """返回 DISPIMG 最多的 sheet 对应的 (openpyxl_name, xml_path)"""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    scores = {}
    for sn in wb.sheetnames:
        ws = wb[sn]
        cnt = sum(1 for row in ws.iter_rows(values_only=True)
                  for cell in row if cell and 'DISPIMG' in str(cell))
        has_header = False
        for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
            for h in row[:5]:
                if h and ('原图产品编号' in str(h) or '原图产品名称' in str(h)):
                    has_header = True
                    break
        scores[sn] = (has_header, cnt)
    wb.close()
    best = max(scores, key=lambda sn: (scores[sn][0], scores[sn][1]))
    return best, resolve_sheet_xml(filepath, best)


def get_part_number_from_row(sheet_bytes, row_num, shared_strings):
    """从 sheet XML 某行中提取零件号（B 列和 A 列都尝试）"""
    sheet = sheet_bytes.decode('utf-8')
    row_m = re.search(r'<row r="' + str(row_num) + r'"[^>]*>(.*?)</row>', sheet, re.DOTALL)
    if not row_m:
        return ''
    row_content = row_m.group(1)

    def extract_cell(col):
        c_m = re.search(r'<c r="' + col + str(row_num) + r'"[^>]*>(.*?)</c>', row_content, re.DOTALL)
        if not c_m:
            return ''
        cell = c_m.group(1)
        t_m = re.search(r'\bt="([^"]+)"', cell)
        v_m = re.search(r'<v>([^<]+)</v>', cell)
        if not v_m:
            return ''
        v = v_m.group(1)
        if t_m and t_m.group(1) == 's':
            idx = int(v)
            return shared_strings[idx] if idx < len(shared_strings) else ''
        return v

    # 优先 B 列，其次 A 列
    b_val = extract_cell('B')
    if b_val and 'DISPIMG' not in b_val:
        return b_val.strip()
    a_val = extract_cell('A')
    return a_val.strip() if a_val else ''


def export_customer_images(folder_name):
    folder_path = os.path.join(PRICES_DIR, folder_name)
    xlsx_files = [f for f in os.listdir(folder_path) if f.endswith('.xlsx')]
    if not xlsx_files:
        return 0, 0
    filepath = os.path.join(folder_path, xlsx_files[0])

    # 选最佳 sheet
    best_name, best_xml = best_sheet(filepath)
    print(f"  选用: {best_name} → {best_xml}")

    with zipfile.ZipFile(filepath, 'r') as z:
        sheet_bytes = z.read(best_xml)
        ci_bytes = z.read('xl/cellimages.xml')
        rels_bytes = z.read('xl/_rels/cellimages.xml.rels')
        shared_strings = read_shared_strings(z)

    # 图片: cellimages.xml 中按顺序列出 (ID → media文件)
    ci = ci_bytes.decode('utf-8')
    rels = rels_bytes.decode('utf-8')
    rid_map = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels))
    cellimages = []
    for frag in re.findall(r'<etc:cellImage>(.*?)</etc:cellImage>', ci, re.DOTALL):
        iid = re.search(r'name="(ID_[^"]+)"', frag)
        rid = re.search(r'r:embed="(rId\d+)"', frag)
        if iid and rid:
            media = rid_map.get(rid.group(1), '')
            cellimages.append((iid.group(1), media))

    # 行 → DISPIMG 图片ID
    sheet = sheet_bytes.decode('utf-8')
    row_map = {}
    for row_m in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', sheet, re.DOTALL):
        rn = int(row_m.group(1))
        ids = re.findall(r'(?:_xlfn\.)?DISPIMG\(&quot;([^&]+)&quot;', row_m.group(2))
        if ids:
            row_map[rn] = ids

    # 配对：零件号 → media文件
    part_to_media = {}
    for rn in sorted(row_map.keys()):
        part_no = get_part_number_from_row(sheet_bytes, rn, shared_strings)
        if not part_no or part_no in ('None', '总计', '合计', '序号',
                                      '原图产品编号', '原图产品名称1', ''):
            continue
        # 去掉工艺后缀
        clean = re.sub(r'[（(][^）)]*(?:涂|热|电|镀|磷|钝|氧)[^）)]*[）)]', '', part_no).strip()
        if not clean:
            continue
        for img_id in row_map[rn]:
            if clean in part_to_media:
                continue
            idx = next((j for j, (iid, _) in enumerate(cellimages) if iid == img_id), -1)
            media = cellimages[idx][1] if idx >= 0 else ''
            if media:
                part_to_media[clean] = media

    print(f"  配对成功: {len(part_to_media)} 个零件")

    # 导出
    cust_dir = os.path.join(EXPORT_DIR, folder_name)
    os.makedirs(cust_dir, exist_ok=True)
    exp = skip = 0
    with zipfile.ZipFile(filepath, 'r') as z:
        for pn, media in part_to_media.items():
            if not media:
                skip += 1
                continue
            img_data = z.read(f'xl/{media}')
            pd = os.path.join(cust_dir, pn)
            os.makedirs(pd, exist_ok=True)
            ext = os.path.splitext(media)[1] or '.jpg'
            with open(os.path.join(pd, f'{pn}{ext}'), 'wb') as f:
                f.write(img_data)
            exp += 1
    return exp, skip


def main():
    print("=" * 60)
    print("导出零件图片")
    print("=" * 60)
    total_exp = total_skip = 0
    for fname in ["B-C武汉万向汽车制动器有限公司",
                  "B-G芜湖伯特利",
                  "上海万向钱潮A-A"]:
        print(f"\n>>> {fname}")
        exp, skip = export_customer_images(fname)
        total_exp += exp
        total_skip += skip
    print(f"\n完成: {total_exp} 张导出，{total_skip} 张跳过")
    print(f"目录: {EXPORT_DIR}")


if __name__ == "__main__":
    main()
