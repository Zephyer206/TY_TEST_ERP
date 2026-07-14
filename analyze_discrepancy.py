#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path

# 加载报告
base_dir = Path('backend/scripts/backups/customer_cleanup/legacy_ref_audit')
with open(base_dir / 'new_customer_required_review_20260714_012229.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

# 加载分类结果
with open(base_dir / 'classification_20260714_011307.json', 'r', encoding='utf-8') as f:
    classification = json.load(f)

print('=== 问题分析 ===')
print()
print('Missing from classification (Excel有但分类没有):')
missing = report['comparison']['missing_from_classification']
for item in missing:
    sheet = item['sheet']
    row = item['row']
    # 从Excel扫描结果中找这一行
    excel_rows = report['excel_scan']['rows']
    matching = [r for r in excel_rows if r['sheet'] == sheet and r['row'] == row]
    if matching:
        r = matching[0]
        print(f"  {sheet} row {row}: {r['tooling_number']} | {r['internal_name']} | {r['customer_part_no']}")

        # 在分类中查找这个tooling_number
        for cls_item in classification['classifications']:
            if cls_item.get('invalid_part_number') == r['tooling_number']:
                evidence = cls_item.get('evidence', {}).get('excel_row_evidence', [])
                if evidence:
                    ev = evidence[0]
                    print(f"    -> 找到在分类中: category={cls_item['category']}, Excel位置={ev.get('sheet')} row {ev.get('row')}")
                break

print()
print('Extra in classification (分类有但Excel扫描没有):')
extra = report['comparison']['extra_in_classification']
for item in extra:
    sheet = item['sheet']
    row = item['row']
    print(f"  {sheet} row {row}")

    # 在分类中找这个位置的记录
    for cls_item in classification['classifications']:
        if cls_item['category'] == 'new_customer_required':
            evidence = cls_item.get('evidence', {}).get('excel_row_evidence', [])
            if evidence and evidence[0].get('sheet') == sheet and evidence[0].get('row') == row:
                print(f"    -> 分类记录: part_id={cls_item['part_id']}, tooling={cls_item.get('invalid_part_number')}, customer={cls_item.get('invalid_customer_name')}")
                break

print()
print('=== 结论 ===')
print(f"Excel扫描找到36条，分类也有36条，但位置有2条不匹配")
print(f"这说明分类器记录的Excel行号与实际动态表头扫描的行号有偏差")
