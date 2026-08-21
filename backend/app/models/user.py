"""User model - canonical LV1-LV4 permission system."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """User model with canonical LV1-LV4 role system.

    Canonical 4-level permission system (role_level):
    - LV1 (role_level=1): Ordinary staff - operators, warehouse staff, QC staff, spray workers, maintenance workers
    - LV2 (role_level=2): Managers & business/technical staff - team leaders, technical staff, business staff, dept supervisors, accountants, HR, equipment supervisors
    - LV3 (role_level=3): Boss - final approval, global data visibility
    - LV4 (role_level=4): Super administrator - system management, context switching

    Database fields (users table):
    - id: integer
    - username: varchar (unique)
    - password: varchar (bcrypt hash)
    - real_name: varchar (nullable)
    - dept: varchar (department code string, not FK)
    - role_level: integer (1-4 only, enforced by CHECK constraint)
    - created_at: timestamp
    - position: varchar (position string, not FK) - orthogonal business metadata
    - is_tech: boolean - orthogonal business metadata (technical vs non-technical role)
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint('role_level >= 1 AND role_level <= 4', name='ck_users_role_level_1_4'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dept: Mapped[str] = mapped_column(String(50), nullable=False, default='prod')
    role_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default='员工')
    is_tech: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.username} LV{self.role_level}>"
