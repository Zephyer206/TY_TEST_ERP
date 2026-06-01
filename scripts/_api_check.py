import urllib.request, json

req = urllib.request.Request('http://localhost:8000/api/boss/price-cards/detail/179')
req.add_header('Cookie', 'session=<your_session_here>')
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read())
        d = data['data']
        print(f"part: {d['part_number']}")
        print(f"gross_weight (API returned): {d['gross_weight']}")
        print(f"net_weight (API returned): {d['net_weight']}")
        print(f"material_unit_price: {d['material_unit_price']}")
        print(f"scrap_price: {d['scrap_price']}")
        print(f"surface_treatment_cost: {d['surface_treatment_cost']}")
        print(f"cost_override: {d['cost_override']}")
        print(f"material_cost: {d['material_cost']}")
        print(f"current_price: {d['current_price']}")
except Exception as e:
    print(f"Error: {e}")
