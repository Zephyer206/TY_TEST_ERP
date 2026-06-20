#!/usr/bin/env python3
"""初始化超级管理员账号脚本。

用法:
    python scripts/init_admin.py [--force]

参数:
    --force: 如果管理员已存在则强制更新

示例:
    python scripts/init_admin.py
    python scripts/init_admin.py --force
"""

import argparse
import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from database import get_db_connection


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hash password with salt using SHA256.

    Returns:
        Tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt


def create_admin_user(
    conn,
    username: str = "admin",
    password: str = "admin123",
    real_name: str = "系统管理员",
    dept: str = "admin",
    role_level: int = 10,
    force: bool = False,
) -> bool:
    """Create or update admin user.

    Args:
        conn: Database connection
        username: Admin username
        password: Admin password
        real_name: Display name
        dept: Department
        role_level: Role level (10 = super admin)
        force: Force update if exists

    Returns:
        True if created/updated successfully
    """
    cursor = conn.cursor()

    # Check if admin exists
    cursor.execute("SELECT id, username FROM users WHERE username = %s", (username,))
    existing = cursor.fetchone()

    hashed_password, salt = hash_password(password)
    now = datetime.utcnow()

    if existing:
        if force:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    password_salt = %s,
                    real_name = %s,
                    dept = %s,
                    role_level = %s,
                    is_active = true,
                    is_tech = false,
                    updated_at = %s
                WHERE username = %s
                """,
                (hashed_password, salt, real_name, dept, role_level, now, username),
            )
            print(f"[更新] 管理员账号已存在，已强制更新: {username}")
            return True
        else:
            print(f"[跳过] 管理员账号已存在: {username} (使用 --force 强制更新)")
            return False

    # Create new admin
    cursor.execute(
        """
        INSERT INTO users (
            username,
            password_hash,
            password_salt,
            real_name,
            dept,
            role_level,
            is_active,
            is_tech,
            created_at,
            updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, true, false, %s, %s)
        """,
        (username, hashed_password, salt, real_name, dept, role_level, now, now),
    )
    print(f"[创建] 管理员账号创建成功: {username}")
    return True


def create_demo_users(conn) -> None:
    """Create demo users for testing.

    Args:
        conn: Database connection
    """
    cursor = conn.cursor()

    demo_users = [
        # (username, password, real_name, dept, role_level)
        ("boss", "boss123", "老板", "boss", 9),
        ("sales", "sales123", "业务经理", "sales", 5),
        ("production", "prod123", "生产主管", "production", 3),
        ("quality", "qa123", "质检主管", "quality", 3),
        ("warehouse", "wh123", "仓库主管", "warehouse", 3),
        ("designer", "des123", "设计工程师", "design", 4),
        ("mold_eng", "mold123", "模具工程师", "mold", 2),
        ("worker1", "worker123", "操作工张三", "production", 1),
    ]

    created = 0
    for username, password, real_name, dept, role_level in demo_users:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            continue

        hashed_password, salt = hash_password(password)
        now = datetime.utcnow()

        cursor.execute(
            """
            INSERT INTO users (
                username, password_hash, password_salt, real_name,
                dept, role_level, is_active, is_tech, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, true, false, %s, %s)
            """,
            (username, hashed_password, salt, real_name, dept, role_level, now, now),
        )
        print(f"[创建] 演示账号: {username} (角色: {role_level})")
        created += 1

    if created > 0:
        conn.commit()
        print(f"[完成] 已创建 {created} 个演示账号")


def main():
    parser = argparse.ArgumentParser(description="初始化超级管理员账号")
    parser.add_argument("--username", default="admin", help="管理员用户名 (默认: admin)")
    parser.add_argument("--password", default="admin123", help="管理员密码 (默认: admin123)")
    parser.add_argument("--real-name", default="系统管理员", help="管理员显示名")
    parser.add_argument("--force", action="store_true", help="强制更新已存在的管理员")
    parser.add_argument("--with-demo", action="store_true", help="同时创建演示账号")
    args = parser.parse_args()

    print("=" * 50)
    print("云冲压 ERP - 管理员初始化脚本")
    print("=" * 50)
    print(f"用户名: {args.username}")
    print(f"密码: {args.password}")
    print(f"角色: 超级管理员 (role_level=10)")
    print("=" * 50)

    try:
        conn = get_db_connection()
        try:
            # Create admin
            create_admin_user(
                conn,
                username=args.username,
                password=args.password,
                real_name=args.real_name,
                force=args.force,
            )

            # Create demo users if requested
            if args.with_demo:
                create_demo_users(conn)

            conn.commit()
            print("\n[成功] 初始化完成!")
            print("\n演示账号说明:")
            print("-" * 40)
            print("| 角色     | 用户名      | 密码      |")
            print("-" * 40)
            print("| 老板     | boss        | boss123   |")
            print("| 业务经理 | sales       | sales123  |")
            print("| 生产主管 | production  | prod123   |")
            print("| 质检主管 | quality     | qa123     |")
            print("| 仓库主管 | warehouse   | wh123     |")
            print("| 操作工   | worker1     | worker123 |")
            print("-" * 40)

        finally:
            conn.close()

    except Exception as e:
        print(f"\n[错误] 初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
