"""Python API classes for webview JavaScript bridge."""

from .settings import SettingsApi
from .hotkey import HotkeyApi
from .permissions import PermissionsApi
from .extensions import ExtensionsApi
from .combined import CombinedApi

__all__ = [
    "SettingsApi",
    "HotkeyApi",
    "PermissionsApi",
    "ExtensionsApi",
    "CombinedApi",
]
