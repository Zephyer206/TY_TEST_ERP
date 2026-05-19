"""
router_inspection.py
====================
检查 sales.py 的 api_router 前缀，确认它是否正确映射到 /api/dict/treatments。
"""

import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\Cloud-Stamping")

from app.api import sales

print("=== sales.py api_router 详情 ===")
api_router = sales.api_router
print(f"prefix:       '{api_router.prefix}'")
print(f"tags:         {api_router.tags}")
print(f"routes count: {len(api_router.routes)}")
print()
print("所有路由：")
for route in api_router.routes:
    if hasattr(route, "path"):
        methods = list(getattr(route, "methods", {"GET"}))
        full_path = api_router.prefix + route.path
        print(f"  {methods} /api{route.path}  (实际路径: /{route.path})")

print()
print("=== routes.router 详情 ===")
router = sales.router
print(f"prefix:       '{router.prefix}'")
print(f"routes count: {len(router.routes)}")
