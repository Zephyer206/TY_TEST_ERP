"""User and Department models - 匹配实际数据库结构."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """User model - 匹配数据库实际表结构."""

    __tablename__ = "users"

    # 数据库实际字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)  # 注意：是 password 不是 hashed_password
    real_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 不是 full_name
    dept: Mapped[str] = mapped_column(String(50), nullable=False, default='prod')  # 字符串，不是外键
    role_level: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default='员工')  # 字符串，不是外键
    is_tech: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superadmin: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)

    # 注意：数据库中没有以下字段
    # - email
    # - hashed_password (是 password)
    # - full_name (是 real_name)
    # - phone
    # - employee_id
    # - role (enum)
    # - department_id (是字符串 dept)
    # - position_id (是字符串 position)
    # - is_active
    # - is_superuser (是 is_superadmin)
    # - last_login
    # - updated_at

    def __repr__(self) -> str:
        return f"<User {self.username}>"
