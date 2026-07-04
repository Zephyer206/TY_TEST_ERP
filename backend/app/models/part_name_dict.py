"""Part Name Dictionary Model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PartNameDict(Base):
    """零件名称字典表 - 标准化零件名称"""

    __tablename__ = "part_name_dict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 三级分类结构
    primary_category: Mapped[str] = mapped_column(String(100), nullable=False, comment="一级分类（必填）- 零件主名称")
    secondary_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="二级分类（可选）")
    customer_part_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="三级分类（可选）- 客户零件名称")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注说明")

    # 保留旧字段以兼容
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="[已废弃] 零件名称")
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="[已废弃] 旧分类字段")

    # 元数据
    usage_count: Mapped[int] = mapped_column(Integer, default=0, comment="使用次数（统计用）")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")

    # 审计
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="创建人")
