# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, r'C:\Users\Administrator\Desktop\Cloud-Stamping')
from app.api.sales import _parse_price_excel_bytes

BASE = r'C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\prices'
EXCEL_FILES = {
    '武汉万向': (55, os.path.join(BASE, 'B-C武汉万向汽车制动器有限公司', '武汉万向.xlsx')),
    '伯特利':   (56, os.path.join(BASE, 'B-G芜湖伯特利', '伯特利.xlsx')),
    '上海万向': (57, os.path.join(BASE, '上海万向钱潮A-A', '上海万向.xlsx')),
}

for name, (cid, path) in EXCEL_FILES.items():
    print(f"\n{'='*60}")
    print(f"=== {name} (customer_id={cid}) ===")
    if not os.path.exists(path):
        print(f"  文件不存在"); continue
    with open(path, 'rb') as f:
        content = f.read()
    try:
        rows, summary = _parse_price_excel_bytes(content, cid)
        print(f"  解析: {summary['total_rows']}行, 有效重量:{summary['with_weight']}, 有价格:{summary['with_price']}")
        for r in rows[:5]:
            net = r['net_weight']; mp = r['material_unit_price']
            mat = r['material_cost']; tot = r['cost_override']
            check = round(net * mp, 6) if (net and mp) else None
            ok = '✓' if (mat is None or check is None or abs(check - mat) < 0.001) else f'✗ calc={check}'
            print(f"    {r['part_number']}: net={net}kg mp={mp} mat={mat} total={tot} {ok}")
    except Exception as e:
        print(f"  失败: {e}")
