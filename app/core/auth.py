"""
app/core/auth.py
权限校验与用户会话解析。依赖 app.services.db_service（避免循环导入）。
"""
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import unquote

# view_as → (display_dept, override_role_level)
# 仅 is_superadmin 可使用，模拟不同部门+角色视角
VIEW_AS_MAP = {
    # 部门视角（保持原 role_level）
    "sales":     ("sales",     None),
    "prod":      ("prod",      None),
    "tech":      ("tech",      None),
    "qc":        ("qc",        None),
    "pkg":       ("pkg",       None),
    "whse":      ("whse",      None),
    "spraying":  ("spraying",  None),
    "admin":     ("admin",     None),
    # 生产部角色视角
    "prod-op":   ("prod",      1),   # 生产部-操作工
    "prod-lead": ("prod",      3),   # 生产部-组长
    # 开发部角色视角
    "dev-mold":  ("dev-mold",  2),   # 开发部-模具工程师
    "dev-design":("dev-design",4),   # 开发部-设计工程师
    # 业务视角
    "sales-mgr": ("sales",     5),   # 业务经理
}


def get_current_user(request: Request):
    """
    从请求 Cookie 中解析当前登录用户信息。
    支持视图切换（view_as）：仅 is_superadmin 可切换 department 显示，
    真实权限（role_level）保持不变（除非使用 prod-op/prod-lead 等角色模拟）。
    is_superadmin 基于真实 role_level（cookie 中的原始值），不受 view_as 影响。
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    username = unquote(request.cookies.get("username") or "")
    real_name = unquote(request.cookies.get("real_name") or "")
    real_role_level = int(request.cookies.get("role_level", 1))
    real_department = request.cookies.get("department") or request.cookies.get("dept") or "prod"
    view_as = request.cookies.get("view_as") or ""
    # is_superadmin 基于真实权限，不受视角切换影响
    is_superadmin = real_role_level > 9

    # view_as 解析：仅 admin 可使用
    if view_as and is_superadmin and view_as in VIEW_AS_MAP:
        display_dept, override_role = VIEW_AS_MAP[view_as]
        role_level = override_role if override_role is not None else real_role_level
    else:
        display_dept = real_department
        role_level = real_role_level
        view_as = ""

    position = unquote(request.cookies.get("position") or "")
    if not position:
        if role_level >= 9:
            position = "老板"
        elif role_level == 5:
            position = "业务经理" if display_dept == "sales" else "组长"
        elif role_level == 4:
            position = "设计工程师"
        elif role_level == 3:
            position = "组长"
        elif role_level == 2:
            position = "模具工程师"
        else:
            position = "操作工"

    # is_tech 仅在需要时从数据库拉取（延迟加载，避免全局导入循环）
    is_tech = False
    try:
        from app.services.db_service import verify_user_by_id
        is_tech = verify_user_by_id(user_id).get("is_tech", False) if verify_user_by_id(user_id) else False
    except Exception:
        pass

    return {
        "id": int(user_id),
        "username": username,
        "role_level": role_level,
        "dept": display_dept,
        "department": display_dept,
        "real_department": real_department,
        "real_role_level": real_role_level,
        "position": position,
        "real_name": real_name,
        "is_tech": is_tech,
        "is_superadmin": is_superadmin,
        "view_as": view_as,
    }


def is_global_admin(user):
    """判断是否为全局管理员（role_level > 9）"""
    return user and user.get("real_role_level", 0) > 9


def can_bypass_dept(user):
    """Global Bypass: is_superadmin=True 或 real_role_level >= 9 则允许穿透所有部门拦截"""
    return user and (user.get("is_superadmin") or user.get("real_role_level", 0) >= 9)


def require_login(user):
    """未登录则重定向到登录页"""
    if not user:
        return RedirectResponse("/login")
    return None


def can_see_all_molds(user):
    """Level 9（老板）、Level 5（业务经理/组长）、Level 2（开发）可见全部模具"""
    return user and user.get("role_level", 0) in (9, 5, 2)
