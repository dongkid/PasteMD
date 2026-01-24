"""Combined API for WebView JavaScript bridge."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings import SettingsApi
    from .hotkey import HotkeyApi
    from .permissions import PermissionsApi
    from .extensions import ExtensionsApi


class CombinedApi:
    """
    综合 API 类

    将多个 API 组合为一个统一的接口，供 pywebview 的 js_api 使用。

    前端可以通过以下方式调用:
    - pywebview.api.settings.xxx()  - 通过子 API 调用
    - pywebview.api.hotkey.xxx()    - 通过子 API 调用
    - pywebview.api.permissions.xxx() - 通过子 API 调用
    - pywebview.api.extensions.xxx() - 通过子 API 调用
    - pywebview.api.xxx()           - 直接调用 (兼容性，仅 settings 方法)
    """

    def __init__(
        self,
        settings_api: "SettingsApi",
        hotkey_api: "HotkeyApi",
        permissions_api: "PermissionsApi",
        extensions_api: "ExtensionsApi"
    ):
        self.settings = settings_api
        self.hotkey = hotkey_api
        self.permissions = permissions_api
        self.extensions = extensions_api

        # 直接暴露 settings 的方法到顶层 (兼容性)
        # 这样前端既可以用 pywebview.api.settings.get_config()
        # 也可以用 pywebview.api.get_config()
        for attr in dir(settings_api):
            if not attr.startswith('_') and callable(getattr(settings_api, attr)):
                if not hasattr(self, attr):
                    setattr(self, attr, getattr(settings_api, attr))
