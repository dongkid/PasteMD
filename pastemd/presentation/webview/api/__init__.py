"""Python API classes for webview JavaScript bridge."""

from .settings import SettingsApi
from .hotkey import HotkeyApi
from .permissions import PermissionsApi

__all__ = [
    "SettingsApi",
    "HotkeyApi",
    "PermissionsApi",
]
