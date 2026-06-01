# 测试 calc-pricing API（含 mold_cost 参数）
import urllib.request
import json

body = {
    "thickness": 3.0,
    "width": 130.0,
    "press_stroke": 40.0,
    "material_name": "65Mn",
    "cavity_count": 1,
    "scrap_rate": 0.54,
    "gross_weight_g": 122.46,
    "net_weight_g": 56.3316,
    "scrap_weight_g": 66.1284,
    "material_utilization": 46.0,
    "stamping_fee": 0.1,
    "inspection_fee": 0.01,
    "packaging_fee": 0.1,
    "surface_fee": 0.0,
    "treatment_fee": 0.5,
    "mold_cost": 0.01,  # 模摊：1000元模费/100000pcs
    "profit_margin": 5.0,
}

data = json.dumps(body).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/calc-pricing",
    data=data,
    headers={"Content-Type": "application/json"}
)
try:
    resp = urllib.request.urlopen(req, timeout=5000)
    result = json.loads(resp.read().decode())
    d = result.get('data', {})
    print(f"final_price: {d.get('final_price')}")
    print(f"material_net_cost: {d.get('material_net_cost')}")
    print(f"mold_cost: {d.get('mold_cost')}")
    print(f"treatment_fee: {d.get('treatment_fee')}")
    # base_total = 0.9699 + 0.1 + 0.01 + 0.1 + 0 + 0.5 + 0.01 = 1.6899
    # final = 1.6899 * 1.05 = 1.7744
    base_total = d.get('material_net_cost', 0) + d.get('stamping_fee', 0) + d.get('inspection_fee', 0) + d.get('packaging_fee', 0) + d.get('surface_fee', 0) + d.get('treatment_fee', 0) + d.get('mold_cost', 0)
    expected = base_total * 1.05
    print(f"base_total: {base_total}")
    print(f"expected final: {expected}")
except Exception as e:
    print(f"Error: {e}")
