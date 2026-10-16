#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path

base_dir = Path('backend/scripts/backups/customer_cleanup/legacy_ref_audit')

# 加载报告
with open(base_dir / 'new_customer_required_review_20260714_012229.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

# 加载分类
with open(base_dir / 'classification_20260714_011307.json', 'r', encoding='utf-8') as f:
    classification = json.load(f)

print('=== 验证行号偏差假设 ===')
print()

# 提取Excel扫描的位置（原始）
excel_locations = {(r['sheet'], r['row']) for r in report['excel_scan']['rows']}

# 提取分类的位置（尝试-1修正）
classified_locations_minus1 = set()
for item in classification['classifications']:
    if item['category'] == 'new_customer_required':
        evidence = item.get('evidence', {}).get('excel_row_evidence', [])
        if evidence:
            ev = evidence[0]
            sheet = ev.get('sheet')
            row = ev.get('row') - 1
            classified_locations_minus1.add((sheet, row))

print(f'Excel扫描位置数: {len(excel_locations)}')
print(f'分类位置数（减1后）: {len(classified_locations_minus1)}')
print()

missing = excel_locations - classified_locations_minus1
extra = classified_locations_minus1 - excel_locations

print(f'Missing: {len(missing)}')
print(f'Extra: {len(extra)}')
print()

if len(missing) == 0 and len(extra) == 0:
    print('[OK] 完美匹配！分类器的行号需要减1才能对齐Excel原始行号')
else:
    print('[!] 仍有不匹配')
    if missing:
        print('Missing:')
        for sheet, row in sorted(missing)[:5]:
            print(f'  {sheet} row {row}')
    if extra:
        print('Extra:')
        for sheet, row in sorted(extra)[:5]:
            print(f'  {sheet} row {row}')
