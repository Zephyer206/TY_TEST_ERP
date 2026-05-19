"""
HTTP API 诊断套件 — 登录态 + Treatments 接口验证
用法：python scripts/http_test.py
依赖：Python 3 标准库（urllib / http.cookiejar）
"""
import urllib.request, http.cookiejar, json, urllib.parse, time

BASE = 'http://localhost:8000'


def make_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def login(opener, username='admin', password='123456'):
    data = urllib.parse.urlencode({'username': username, 'password': password}).encode()
    req = urllib.request.Request(BASE + '/login', data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with opener.open(req, timeout=5) as resp:
        return resp.status


def get_json(opener, path):
    req = urllib.request.Request(BASE + path)
    req.add_header('Accept', 'application/json')
    try:
        with opener.open(req, timeout=5) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body) if body else None
    except Exception as e:
        return 0, {'error': str(e)}


def main():
    opener = make_opener()

    print('=== 登录 ===')
    status = login(opener)
    print(f'登录响应: {status}')

    print()
    print('=== GET /api/dict/treatments ===')
    status, body = get_json(opener, '/api/dict/treatments')
    print(f'Status: {status}')
    print(f'Body: {json.dumps(body, indent=2, ensure_ascii=False) if body else "empty"}')

    print()
    print('=== GET /api/materials ===')
    status, body = get_json(opener, '/api/materials')
    print(f'Status: {status}')
    if body and 'data' in body:
        print(f'材料数量: {len(body["data"])}')
        for m in body['data'][:5]:
            print(f'  {m}')


if __name__ == '__main__':
    main()
