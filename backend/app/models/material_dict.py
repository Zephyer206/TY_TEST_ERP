"""Material Dictionary Model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, TIMESTAMP, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MaterialDict(Base):
    """材质字典表 - 标准化材质信息"""

    __tablename__ = "material_dict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="材质代码（标准）")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="材质名称")
    name_cn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="中文俗称")

    # 物理属性
    density: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 4), nullable=True, comment="密度 g/cm³")
    thickness_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="常用厚度范围")

    # 分类
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="大类（冷轧板、热轧板、不锈钢、铝合金等）")
    standard: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="执行标准（GB/T、JIS等）")

    # 价格相关（可选）
    default_price: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 4), nullable=True, comment="默认单价（元/吨）")
    scrap_price: Mapped[Optional[float]] = mapped_column(DECIMAL(12, 4), nullable=True, comment="废料单价（元/吨）")

    # 元数据
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")

    # 审计
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="创建人")
