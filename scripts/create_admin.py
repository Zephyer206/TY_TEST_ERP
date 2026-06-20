"""创建初始管理员账号"""
import asyncio
import bcrypt
from sqlalchemy import text
from app.database import engine


async def create_admin():
    # 生成密码哈希
    password = '123456'.encode('utf-8')
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    password_hash = hashed.decode('utf-8')

    print(f"密码哈希: {password_hash}")

    # 插入管理员账号
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO users (
                username,
                password,
                real_name,
                role_level,
                dept,
                position,
                is_tech,
                is_superadmin,
                created_at
            ) VALUES (
                :username,
                :password,
                :real_name,
                :role_level,
                :dept,
                :position,
                :is_tech,
                :is_superadmin,
                NOW()
            )
            ON CONFLICT (username) DO UPDATE SET
                password = EXCLUDED.password,
                is_superadmin = EXCLUDED.is_superadmin,
                role_level = EXCLUDED.role_level
            RETURNING id, username, real_name, role_level, is_superadmin
        """), {
            "username": "admin",
            "password": password_hash,
            "real_name": "系统管理员",
            "role_level": 10,
            "dept": "admin",
            "position": "超级管理员",
            "is_tech": False,
            "is_superadmin": True
        })

        user = result.fetchone()
        print(f"\n✓ 管理员创建成功!")
        print(f"  ID: {user[0]}")
        print(f"  用户名: {user[1]}")
        print(f"  姓名: {user[2]}")
        print(f"  权限级别: {user[3]}")
        print(f"  超级管理员: {user[4]}")
        print(f"\n登录信息:")
        print(f"  用户名: admin")
        print(f"  密码: 123456")


if __name__ == "__main__":
    asyncio.run(create_admin())
