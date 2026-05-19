"""app/core/templates.py - Shared Jinja2 template engine."""
import os, datetime
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "..", "templates"))
templates.env.globals["now"] = datetime.datetime.now


def _qc_type_cn(value):
    return {
        "first_piece": "首件检验",
        "patrol": "机台巡检",
        "oqc": "出货检验",
        "iqc": "来料检验",
    }.get(str(value), value or "")


templates.env.filters["qc_type_cn"] = _qc_type_cn


def _error_type_cn(value):
    return {
        "pkg_entry": "包装补录",
        "pkg_scan": "扫码异常",
        "pkg_mismatch": "数量不匹配",
        "pkg_block": "卡控触发",
        "pkg_release": "卡控解除",
        "pkg_shipping": "发货异常",
    }.get(str(value), value or "")


templates.env.filters["error_type_cn"] = _error_type_cn


_CN_DIGITS = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def _int_to_cn(n):
    """将 0-10 的整数转换为中文数字"""
    if 0 <= n <= 10:
        return _CN_DIGITS[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        if ones == 0:
            return _CN_DIGITS[tens] + "十"
        return _CN_DIGITS[tens] + "十" + _CN_DIGITS[ones]
    return str(n)


def _cavity_cn(value):
    """模具出数过滤器：将 cavity_count (int) 转换为中文模具术语

    行业惯例：1 -> "一出"，2 -> "一出二"，3 -> "一出三"，etc.
    模板用法：{{ m.cavity_count | cavity_cn }}  →  "一出二"
    """
    if value is None:
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value) if value else ""
    if n <= 0:
        return ""
    if n == 1:
        return "一出"
    return "一出" + _int_to_cn(n)


templates.env.filters["cavity_cn"] = _cavity_cn


def _cavity_out(value):
    """模具出数展示过滤器（用于详情卡等非列表场景）"""
    if value is None:
        return "-"
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value) if value else "-"
    if n <= 0:
        return "-"
    return _int_to_cn(n)


templates.env.filters["cavity_out"] = _cavity_out


def _is_anomaly(value):
    """Jinja2 测试器：判断行记录是否含异常（has_anomaly 属性为真值）"""
    return bool(value)


templates.env.tests["has_anomaly"] = _is_anomaly
