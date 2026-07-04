"""Mold Type Dictionary Model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MoldTypeDict(Base):
    """模具类型字典表 - 标准化模具类型"""

    __tablename__ = "mold_type_dict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="类型代码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="类型名称")
    name_en: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="英文名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="描述说明")

    # 特性
    typical_lifecycle: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="典型寿命（万次）")
    complexity_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="复杂度（简单、中等、复杂）")
    typical_tonnage_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="适用吨位范围")

    # 元数据
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")

    # 审计
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
