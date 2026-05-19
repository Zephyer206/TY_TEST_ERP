"""
scripts/test_auth.py
---
V3.1 准则第 7 点第 2 条：核心登录防保自检脚本。
使用 TestClient 模拟 POST /login（admin / 123456），
  成功 → 输出 [SUCCESS]
  失败 → 抛出 [FATAL] 异常

终端独立运行：
  python scripts/test_auth.py
"""

import sys
import os

# 确保项目根目录在 sys.path，以便能导入 main.app
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    try:
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app, raise_server_exceptions=True)

        response = client.post(
            "/login",
            data={"username": "admin", "password": "123456"},
            follow_redirects=False,
        )

        # 成功：302 或 303 重定向，说明 Cookie 设置正常
        if response.status_code in (302, 303):
            # 确认 Cookie 中存在 user_id（登录成功的硬指标）
            set_cookie = response.headers.get("set-cookie", "")
            if "user_id" in set_cookie.lower() or "user_id" in {
                c.name for c in response.cookies
            }:
                print("[SUCCESS] Login /login (admin/123456) — cookie set, redirect confirmed.")
                return
            else:
                raise AssertionError(
                    f"[FATAL] POST /login returned {response.status_code} "
                    "but no user_id cookie found in response."
                )
        else:
            raise AssertionError(
                f"[FATAL] POST /login (admin/123456) returned HTTP {response.status_code}, "
                f"expected 302/303. Body: {response.text[:200]}"
            )

    except AssertionError:
        raise  # 原样抛出，不吞掉 [FATAL]
    except Exception as exc:
        # 任何未预期错误都标记为 [FATAL]
        raise RuntimeError(f"[FATAL] Unexpected error during auth test: {exc}") from exc


if __name__ == "__main__":
    main()
