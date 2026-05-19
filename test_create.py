import urllib.request, json

data = json.dumps({
    'part_number': 'test-v12-001',
    'internal_name': 'V12\u6d4b\u8bd5\u96f6\u4ef6',
    'thickness': 1.0,
    'width': 12.0,
    'press_stroke': 123.0,
    'cavity_count': 1,
    'material_name': '\u6210\u578b\u673a SUS 301',
    'pricing_mode': 'independent',
    'machine_type': '110T',
    'material_utilization': 50.0,
}).encode('utf-8')

req = urllib.request.Request(
    'http://localhost:8000/api/parts/create',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=10)
    print('Status:', r.status)
    print('Body:', r.read().decode())
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code)
    print('Body:', e.read().decode())
except Exception as ex:
    print('Error:', ex)
