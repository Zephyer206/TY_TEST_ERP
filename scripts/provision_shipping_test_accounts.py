"""Provision local-only accounts used by shipping-order browser acceptance."""

from __future__ import annotations

import asyncio
import secrets
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.core.security import get_password_hash
from app.database import async_session_maker
from app.models.user import User


ROOT = Path(__file__).resolve().parents[1]
CREDENTIAL_FILE = ROOT / "shipping_test_accounts.local.txt"

ROLES = (
    ("business", "业务验收", "sales", "业务", 2, False),
    ("label", "标签验收", "warehouse", "标签", 1, False),
    ("warehouse", "仓库验收", "warehouse", "仓库", 1, False),
    ("admin", "管理验收", "admin", "管理员", 4, True),
)


async def provision() -> None:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    credentials: list[tuple[str, str, str]] = []
    async with async_session_maker() as db:
        for suffix, label, dept, position, role_level, is_tech in ROLES:
            username = f"ship_test_{suffix}_{stamp}"
            password = secrets.token_urlsafe(18)
            user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
            if user is None:
                user = User(username=username)
                db.add(user)
            user.password = get_password_hash(password)
            user.real_name = label
            user.dept = dept
            user.position = position
            user.role_level = role_level
            user.is_tech = is_tech
            credentials.append((label, username, password))
        await db.commit()

    lines = [
        "Zephyr 发货系统临时验收账号（仅限本地测试）",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "请勿提交 Git、复制到报告或发送给第三方。",
        "",
    ]
    for label, username, password in credentials:
        lines.extend([f"[{label}]", f"用户名：{username}", f"密码：{password}", ""])
    CREDENTIAL_FILE.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(provision())
