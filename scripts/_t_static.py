# -*- coding: utf-8 -*-
import os, urllib.request, urllib.error

# Check if static files directory exists
static_dir = r"C:\Users\Administrator\Desktop\Cloud-Stamping\static"
print("static dir exists:", os.path.isdir(static_dir))

js_dir = os.path.join(static_dir, "js")
print("static/js exists:", os.path.isdir(js_dir))

# Test a known static file
for path in [
    '/static/js/api_config.js',
    '/static/uploads/drawings/_unassigned/test.jpeg',
]:
    try:
        req = urllib.request.Request(f'http://127.0.0.1:8000{path}')
        resp = urllib.request.urlopen(req, timeout=5)
        print(f'OK {resp.status}: {path}')
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {path}')
    except Exception as e:
        print(f'ERR {e}: {path}')

# Check if the image file actually exists
img_path = r"C:\Users\Administrator\Desktop\Cloud-Stamping\static\uploads\part_images\B-C武汉万向汽车制动器有限公司\3502414AKY00A.jpeg"
print(f"\nImage file exists: {os.path.exists(img_path)}")
