"""User model - 简化版本，仅匹配数据库实际结构."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, PyEnum):
    """User role enumeration - 保留用于兼容性."""

    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    TECH = "tech"
    PRODUCTION = "production"
    QC = "qc"
    WAREHOUSE = "warehouse"
    VIEWER = "viewer"


class User(Base):
    """User model - 匹配数据库实际表结构.

    数据库字段（users 表）:
    - id: integer
    - username: varchar (unique)
    - password: varchar (bcrypt hash)
    - real_name: varchar (nullable)
    - dept: varchar (部门代码字符串，不是外键)
    - role_level: integer (权限级别 1-10)
    - created_at: timestamp
    - position: varchar (职位字符串，不是外键)
    - is_tech: boolean
    - is_superadmin: boolean
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dept: Mapped[str] = mapped_column(String(50), nullable=False, default='prod')
    role_level: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default='员工')
    is_tech: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superadmin: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)

    def __repr__(self) -> str:
        return f"<User {self.username}>"
