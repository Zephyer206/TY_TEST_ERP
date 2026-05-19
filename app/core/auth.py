"""
app/core/auth.py
权限校验与用户会话解析。依赖 app.services.db_service（避免循环导入）。
"""
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import unquote


def get_current_user(request: Request):
    """
    从请求 Cookie 中解析当前登录用户信息。
    支持视图切换（view_as）：仅 is_superadmin 可切换 department 显示，
    真实权限（role_level）保持不变。
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    username = unquote(request.cookies.get("username") or "")
    real_name = unquote(request.cookies.get("real_name") or "")
    role_level = int(request.cookies.get("role_level", 1))
    real_department = request.cookies.get("department") or request.cookies.get("dept") or "prod"
    view_as = request.cookies.get("view_as") or ""
    is_superadmin = role_level >= 9
    if view_as and is_superadmin and view_as in ("sales", "prod", "tech", "qc", "pkg", "admin", "whse", "spraying"):
        display_department = view_as
    else:
        display_department = real_department
        view_as = ""
    position = unquote(request.cookies.get("position") or "")
    if not position:
        if role_level >= 9:
            position = "\u8001\u677f"
        elif role_level == 5:
            position = "\u4e1a\u52a1\u7ecf\u7406" if real_department == "sales" else "\u7ec4\u957f"
        elif role_level == 2:
            position = "\u5f00\u53d1\u5de5\u7a0b\u5e08"
        else:
            position = "\u64cd\u4f5c\u5de5"

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
        "dept": display_department,
        "department": display_department,
        "real_department": real_department,
        "position": position,
        "real_name": real_name,
        "is_tech": is_tech,
        "is_superadmin": is_superadmin,
        "view_as": view_as,
    }


def is_global_admin(user):
    """判断是否为全局管理员（role_level >= 9）"""
    return user and user.get("role_level", 0) >= 9


def can_bypass_dept(user):
    """Global Bypass: is_superadmin=True 或 role_level >= 9 则允许穿透所有部门拦截"""
    return user and (user.get("is_superadmin") or user.get("role_level", 0) >= 9)


def require_login(user):
    """未登录则重定向到登录页"""
    if not user:
        return RedirectResponse("/login")
    return None


def can_see_all_molds(user):
    """Level 9\uff08\u8001\u677f\uff09\u3001Level 5\uff08\u4e1a\u52a1\u7ecf\u7406/\u7ec4\u957f\uff09\u3001Level 2\uff08\u5f00\u53d1\uff09\u53ef\u89c1\u5168\u90e8\u6a21\u5177"""
    return user and user.get("role_level", 0) in (9, 5, 2)
