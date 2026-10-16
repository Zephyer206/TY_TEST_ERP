"""Compatibility exports for the canonical application settings.

New code must import settings from ``app.core.config``. This module remains
only for older imports so all services read the same environment file.
"""

from app.core.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
