"""WebView window manager."""

from __future__ import annotations

import json
import os
import threading
from typing import Optional, Callable, TYPE_CHECKING

import webview

from ...config.paths import resource_path
from ...utils.logging import log
from ...utils.system_detect import is_windows, is_macos
from ...core.state import app_state

if is_macos():
    try:
        from ...utils.macos.dock import begin_ui_session, end_ui_session, activate_app
    except Exception:
        begin_ui_session = end_ui_session = activate_app = lambda *args, **kwargs: None
else:
    begin_ui_session = end_ui_session = activate_app = lambda *args, **kwargs: None

if TYPE_CHECKING:
    from ...app.wiring import Container


def get_assets_path() -> str:
    """获取前端资源目录路径"""
    # 首先尝试打包后的资源路径
    path = resource_path(os.path.join("presentation", "webview", "assets"))
    if os.path.isdir(path):
        return path

    # 回退到源码目录
    src_path = os.path.join(os.path.dirname(__file__), "assets")
    if os.path.isdir(src_path):
        return src_path

    return path


def get_settings_html_path() -> str:
    """获取设置页面 HTML 路径"""
    assets_path = get_assets_path()
    html_path = os.path.join(assets_path, "index.html")

    if os.path.isfile(html_path):
        return html_path

    raise FileNotFoundError(f"Settings HTML not found at: {html_path}")


class WebViewManager:
    """
    WebView 窗口管理器

    负责:
    - 创建和管理 webview 窗口
    - 处理窗口的显示/隐藏
    - 管理 Python-JavaScript API 桥接
    - macOS Dock 图标联动
    """

    def __init__(self, container: "Container"):
        self._container = container
        self._settings_window: Optional[webview.Window] = None
        self._is_settings_visible = False
        self._on_settings_save_callback: Optional[Callable] = None
        self._on_settings_close_callback: Optional[Callable] = None

        # API 实例
        self._settings_api = None
        self._hotkey_api = None
        self._permissions_api = None

    def set_settings_callbacks(
        self,
        on_save: Optional[Callable] = None,
        on_close: Optional[Callable] = None
    ) -> None:
        """设置回调"""
        self._on_settings_save_callback = on_save
        self._on_settings_close_callback = on_close

        if self._settings_api:
            self._settings_api.set_callbacks(on_save, on_close)

    def create_settings_window(self) -> webview.Window:
        """创建设置窗口"""
        from .api import SettingsApi, HotkeyApi, PermissionsApi

        # 创建 API 实例
        self._settings_api = SettingsApi(self._container)
        self._hotkey_api = HotkeyApi(self._container)
        self._permissions_api = PermissionsApi(self._container)

        # 设置回调
        if self._on_settings_save_callback or self._on_settings_close_callback:
            self._settings_api.set_callbacks(
                self._on_settings_save_callback,
                self._on_settings_close_callback
            )

        # 创建综合 API 类
        class CombinedApi:
            def __init__(self, settings_api, hotkey_api, permissions_api):
                self.settings = settings_api
                self.hotkey = hotkey_api
                self.permissions = permissions_api

                # 直接暴露 settings 的方法到顶层 (兼容性)
                for attr in dir(settings_api):
                    if not attr.startswith('_') and callable(getattr(settings_api, attr)):
                        if not hasattr(self, attr):
                            setattr(self, attr, getattr(settings_api, attr))

        combined_api = CombinedApi(
            self._settings_api,
            self._hotkey_api,
            self._permissions_api
        )

        # 窗口配置
        window_config = {
            "title": "PasteMD Settings",
            "width": 650,
            "height": 550,
            "resizable": True,
            "min_size": (500, 400),
            "js_api": combined_api,
            "hidden": True,  # 初始隐藏
            "background_color": "#1e1e1e",
        }

        # 根据平台确定 HTML 路径
        try:
            html_path = get_settings_html_path()
            window_config["url"] = html_path
        except FileNotFoundError as e:
            log(f"Warning: {e}")
            # 使用内嵌的基础 HTML 作为后备
            window_config["html"] = self._get_fallback_html()

        # macOS 特定配置
        if is_macos():
            window_config["text_select"] = True

        # 创建窗口
        window = webview.create_window(**window_config)
        self._settings_window = window

        # 设置 API 的窗口引用
        self._settings_api.set_window(window)
        self._hotkey_api.set_window(window)
        self._permissions_api.set_window(window)

        # 绑定关闭事件
        window.events.closing += self._on_window_closing

        return window

    def _get_fallback_html(self) -> str:
        """获取后备 HTML (当资源文件不存在时)"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>PasteMD Settings</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #1e1e1e;
                    color: #e0e0e0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .error {
                    text-align: center;
                    padding: 40px;
                }
                h1 { color: #ff6b6b; }
            </style>
        </head>
        <body>
            <div class="error">
                <h1>资源文件缺失</h1>
                <p>无法找到设置页面资源文件。</p>
                <p>请检查安装是否完整。</p>
            </div>
        </body>
        </html>
        """

    def _on_window_closing(self) -> bool:
        """窗口关闭事件处理"""
        self._is_settings_visible = False

        # macOS: 隐藏 Dock 图标
        if is_macos():
            end_ui_session()

        # 调用关闭回调
        if self._on_settings_close_callback:
            try:
                self._on_settings_close_callback()
            except Exception as e:
                log(f"Settings close callback error: {e}")

        # 返回 False 阻止窗口销毁，改为隐藏
        if self._settings_window:
            self._settings_window.hide()

        return False  # 阻止默认关闭行为

    def show_settings(self, tab: Optional[str] = None) -> None:
        """显示设置窗口"""
        if not self._settings_window:
            log("Settings window not created")
            return

        try:
            # macOS: 显示 Dock 图标
            if is_macos():
                begin_ui_session()
                activate_app()

            # 通知前端切换到指定选项卡（通过队列安全调用）
            if tab:
                def task():
                    try:
                        self._settings_window.evaluate_js(f"window.selectTab && window.selectTab({json.dumps(tab)})")
                    except Exception as e:
                        log(f"Failed to select tab: {e}")
                app_state.queue_ui_task(task)

            self._settings_window.show()
            self._is_settings_visible = True

        except Exception as e:
            log(f"Failed to show settings window: {e}")

    def hide_settings(self) -> None:
        """隐藏设置窗口"""
        if not self._settings_window:
            return

        try:
            self._settings_window.hide()
            self._is_settings_visible = False

            # macOS: 隐藏 Dock 图标
            if is_macos():
                end_ui_session()

        except Exception as e:
            log(f"Failed to hide settings window: {e}")

    def toggle_settings(self) -> None:
        """切换设置窗口显示状态"""
        if self._is_settings_visible:
            self.hide_settings()
        else:
            self.show_settings()

    def is_settings_visible(self) -> bool:
        """检查设置窗口是否可见"""
        return self._is_settings_visible

    def refresh_hotkey_display(self) -> None:
        """刷新热键显示"""
        if self._settings_window and self._is_settings_visible:
            def task():
                try:
                    self._settings_window.evaluate_js("window.refreshHotkeyDisplay && window.refreshHotkeyDisplay()")
                except Exception as e:
                    log(f"Failed to refresh hotkey display: {e}")
            app_state.queue_ui_task(task)

    def get_hotkey_api(self):
        """获取热键 API"""
        return self._hotkey_api

    def destroy(self) -> None:
        """销毁所有窗口"""
        try:
            if self._settings_window:
                self._settings_window.destroy()
                self._settings_window = None
        except Exception as e:
            log(f"Failed to destroy settings window: {e}")
