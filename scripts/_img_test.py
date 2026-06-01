# -*- coding: utf-8 -*-
import urllib.request, urllib.error

paths = [
    '/static/uploads/part_images/B-C%E6%B1%9F%E6%B4%8B%E4%B8%87%E5%90%91%E6%B1%BD%E8%BD%A6%E5%88%B6%E5%8A%A8%E5%99%A8%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/3502414AKY00A.jpeg',
]
for path in paths:
    try:
        req = urllib.request.Request('http://127.0.0.1:8000' + path)
        resp = urllib.request.urlopen(req, timeout=5)
        print(f'OK {resp.status}: {path[:70]}')
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {path[:70]}')
    except Exception as e:
        print(f'ERR {e}: {path[:70]}')
