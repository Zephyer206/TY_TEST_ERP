#!/usr/bin/env python3
"""
Initialize super admin user for the ERP system.

Usage:
    python scripts/init_admin.py [--create]
    python scripts/init_admin.py --username admin --password your_password --name "系统管理员"

This script creates the default admin user with role_level=10.
"""

import argparse
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

import asyncio


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    import bcrypt
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


async def create_admin_user(
    username: str = 'admin',
    password: str = 'admin123',
    real_name: str = '系统管理员',
    db_url: str = None,
) -> dict:
    """Create or update admin user."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Get database URL from env or use default
    if not db_url:
        db_url = os.getenv(
            'DATABASE_URL',
            'postgresql+asyncpg://postgres:postgres@localhost:5432/zephyr_erp'
        )

    engine = create_async_engine(db_url, echo=True)

    async with AsyncSession(engine) as session:
        # Check if admin exists
        result = await session.execute(
            text("SELECT id, username FROM users WHERE username = :username"),
            {'username': username}
        )
        existing = result.fetchone()

        password_hash = get_password_hash(password)

        if existing:
            # Update existing admin
            await session.execute(
                text("""
                    UPDATE users SET
                        password_hash = :password_hash,
                        real_name = :real_name,
                        is_active = true,
                        updated_at = NOW()
                    WHERE username = :username
                """),
                {
                    'username': username,
                    'password_hash': password_hash,
                    'real_name': real_name,
                }
            )
            action = 'updated'
        else:
            # Create new admin
            await session.execute(
                text("""
                    INSERT INTO users (
                        username, password_hash, real_name,
                        role_level, is_active, is_superuser,
                        department_id, created_at, updated_at
                    ) VALUES (
                        :username, :password_hash, :real_name,
                        10, true, true,
                        1, NOW(), NOW()
                    )
                """),
                {
                    'username': username,
                    'password_hash': password_hash,
                    'real_name': real_name,
                }
            )
            action = 'created'

        await session.commit()

    await engine.dispose()

    return {
        'action': action,
        'username': username,
        'password': password,  # Note: Only shown here, not stored
        'role_level': 10,
        'role_name': '超级管理员',
    }


def create_sync(
    username: str = 'admin',
    password: str = 'admin123',
    real_name: str = '系统管理员',
) -> dict:
    """Synchronous wrapper for create_admin_user."""
    return asyncio.run(create_admin_user(username, password, real_name))


def main():
    parser = argparse.ArgumentParser(description='初始化超级管理员用户')
    parser.add_argument('--username', '-u', default='admin', help='管理员用户名')
    parser.add_argument('--password', '-p', default=None, help='管理员密码（默认：admin123）')
    parser.add_argument('--name', '-n', default='系统管理员', help='管理员姓名')
    parser.add_argument('--create', action='store_true', help='强制创建（即使用户存在）')

    args = parser.parse_args()

    password = args.password or 'admin123'

    print('=' * 50)
    print('云冲压 ERP - 超级管理员初始化')
    print('=' * 50)
    print()
    print(f'用户名: {args.username}')
    print(f'姓名:   {args.name}')
    print(f'角色:   超级管理员 (role_level=10)')
    print()

    try:
        result = create_sync(
            username=args.username,
            password=password,
            real_name=args.name,
        )

        if result['action'] == 'created':
            print('✅ 管理员用户创建成功！')
        else:
            print('✅ 管理员用户更新成功！')

        print()
        print('=' * 50)
        print('⚠️  请立即修改默认密码！')
        print('=' * 50)
        print()
        print(f'登录凭据:')
        print(f'  用户名: {args.username}')
        print(f'  密  码: {password}')
        print()

        return 0

    except Exception as e:
        print(f'❌ 初始化失败: {e}')
        print()
        print('请确保:')
        print('  1. 数据库服务已启动')
        print('  2. 数据库已创建 (CREATE DATABASE zephyr_erp)')
        print('  3. DATABASE_URL 环境变量配置正确')
        return 1


if __name__ == '__main__':
    sys.exit(main())
