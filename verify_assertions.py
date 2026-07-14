#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import codecs

# Fix Windows console encoding for UTF-8 output
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Load the JSON report
with open('ambiguous_ap_ib_excel_review_20260714_015530.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Assertion 1: 26/26 records
assert data['metadata']['total_records'] == 26, f"Expected 26 records, got {data['metadata']['total_records']}"
print('✓ Assertion 1: 26/26 records')

# Assertion 2: exact_match = 26
assert data['finding_summary']['exact_match'] == 26, f"Expected 26 exact_match, got {data['finding_summary']['exact_match']}"
print('✓ Assertion 2: exact_match = 26')

# Assertion 3: Customer distribution
expected_dist = {'IBI': 23, '昊辉': 1, 'H4287': 1, '摩擦1号': 1}
assert data['exact_customer_distribution'] == expected_dist, f"Customer distribution mismatch: {data['exact_customer_distribution']}"
print('✓ Assertion 3: Customer distribution = IBI:23, 昊辉:1, H4287:1, 摩擦1号:1')

# Assertion 4: matches_count == len(excel_evidence) for all records
errors = []
for result in data['results']:
    expected_count = len(result['excel_evidence'])
    actual_count = result['excel_matches_count']
    if expected_count != actual_count:
        errors.append(f"Part {result['part_id']}: matches_count={actual_count}, len(excel_evidence)={expected_count}")

if errors:
    print('✗ Assertion 4 FAILED:')
    for err in errors:
        print(f'  {err}')
    sys.exit(1)
else:
    print('✓ Assertion 4: All matches_count == len(excel_evidence)')

# Assertion 5: Part 1682 has exactly 1 match (was 2 before fix)
part_1682 = [r for r in data['results'] if r['part_id'] == 1682][0]
assert part_1682['excel_matches_count'] == 1, f"Part 1682 should have 1 match, got {part_1682['excel_matches_count']}"
assert len(part_1682['excel_evidence']) == 1, f"Part 1682 should have 1 evidence, got {len(part_1682['excel_evidence'])}"
print('✓ Assertion 5: Part 1682 has exactly 1 match (bug fixed)')

# Assertion 6: Specific customer assertions
part_1741 = [r for r in data['results'] if r['part_id'] == 1741][0]
assert part_1741['exact_excel_customer'] == '昊辉', f"Part 1741 should be 昊辉, got {part_1741['exact_excel_customer']}"
print('✓ Assertion 6a: Part 1741 = 昊辉')

part_1742 = [r for r in data['results'] if r['part_id'] == 1742][0]
assert part_1742['exact_excel_customer'] == 'H4287', f"Part 1742 should be H4287, got {part_1742['exact_excel_customer']}"
print('✓ Assertion 6b: Part 1742 = H4287')

part_1798 = [r for r in data['results'] if r['part_id'] == 1798][0]
assert part_1798['exact_excel_customer'] == '摩擦1号', f"Part 1798 should be 摩擦1号, got {part_1798['exact_excel_customer']}"
print('✓ Assertion 6c: Part 1798 = 摩擦1号')

print()
print('=' * 60)
print('所有断言通过！报告数据完全符合预期。')
print('=' * 60)
