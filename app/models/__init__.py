"""
app/models/__init__.py
=====================
Pydantic schemas + 常量定义。

规范
----
- 严禁 ORM（SQLAlchemy），Pydantic 仅用于请求/响应校验
- 常量按业务域分组，数值类常量（如状态枚举）统一放在此处
  不得在 services 里重复定义
"""

from app.models.schemas import *
from app.models.constants import *
