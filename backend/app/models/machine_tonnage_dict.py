"""Machine Tonnage Dictionary Model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MachineTonnageDict(Base):
    """机台吨位字典表 - 合并吨位和机台类型"""

    __tablename__ = "machine_tonnage_dict"
    __table_args__ = (
        UniqueConstraint('tonnage', 'machine_type', name='uq_tonnage_machine_type'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tonnage: Mapped[int] = mapped_column(Integer, nullable=False, comment="吨位值（统一为整数）")
    machine_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="机台类型")
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="显示名称")

    # 分类
    size_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="规模分类（小型、中型、大型、特大型）")
    type_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="类型分类（冲床、液压机、伺服压力机等）")

    # 技术参数
    min_stroke: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="最小行程 mm")
    max_stroke: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="最大行程 mm")
    work_table_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="工作台尺寸")

    # 元数据
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")

    # 审计
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
