"""WebView window manager."""

from __future__ import annotations

import json
import os
from typing import Optional, Callable, TYPE_CHECKING

import webview

from ...config.paths import resource_path
from ...config.loader import ConfigLoader
from ...utils.logging import log
from ...utils.system_detect import is_windows, is_macos
from ...core.state import app_state

# 设置窗口尺寸常量
SETTINGS_WINDOW_WIDTH = 650
SETTINGS_WINDOW_HEIGHT = 550

# Windows Mica 效果支持
if is_windows():
    try:
        from ...utils.win32.mica import (
            apply_mica_effect,
            is_mica_supported,
            update_mica_dark_mode,
            find_window_by_title,
        )
        MICA_AVAILABLE = True
    except ImportError:
        apply_mica_effect = is_mica_supported = update_mica_dark_mode = find_window_by_title = None
        MICA_AVAILABLE = False
else:
    MICA_AVAILABLE = False
    apply_mica_effect = is_mica_supported = update_mica_dark_mode = find_window_by_title = None

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


def _is_system_dark_mode() -> bool:
    """检测系统是否为深色模式"""
    if is_windows():
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except Exception:
            return True  # 默认深色
    elif is_macos():
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True
            )
            return "Dark" in result.stdout
        except Exception:
            return True  # 默认深色
    return True


def _get_background_color_for_theme(theme: str) -> str:
    """根据主题配置获取背景色"""
    if theme == "light":
        return "#ffffff"
    elif theme == "dark":
        return "#1e1e1e"
    else:  # auto
        return "#1e1e1e" if _is_system_dark_mode() else "#ffffff"


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
        self._is_quitting = False  # 退出标志：用于区分正常关闭和程序退出
        self._on_settings_save_callback: Optional[Callable] = None
        self._on_settings_close_callback: Optional[Callable] = None
        self._needs_center_on_show = False  # 标记是否需要首次显示时居中（透明窗口屏幕外初始化）

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
        from .api import SettingsApi, HotkeyApi, PermissionsApi, ExtensionsApi, CombinedApi

        # 创建 API 实例
        self._settings_api = SettingsApi(self._container)
        self._hotkey_api = HotkeyApi(self._container)
        self._permissions_api = PermissionsApi(self._container)
        self._extensions_api = ExtensionsApi(self._container)

        # 设置回调
        if self._on_settings_save_callback or self._on_settings_close_callback:
            self._settings_api.set_callbacks(
                self._on_settings_save_callback,
                self._on_settings_close_callback
            )

        # 创建综合 API
        combined_api = CombinedApi(
            self._settings_api,
            self._hotkey_api,
            self._permissions_api,
            self._extensions_api
        )

        # 获取当前主题配置并决定背景色
        theme = app_state.config.get("theme", "auto")
        background_color = _get_background_color_for_theme(theme)

        # 检查是否可以使用 Mica 效果
        use_mica = is_windows() and MICA_AVAILABLE and is_mica_supported and is_mica_supported()

        # 窗口配置
        window_config = {
            "title": "PasteMD Settings",
            "width": SETTINGS_WINDOW_WIDTH,
            "height": SETTINGS_WINDOW_HEIGHT,
            "resizable": True,
            "min_size": (500, 400),
            "js_api": combined_api,
            "hidden": True,  # 初始隐藏
            "background_color": background_color,
        }

        # Windows 11: 启用透明以支持 Mica
        if use_mica:
            window_config["transparent"] = True
            # 注意：pywebview 不支持 8 位十六进制色，透明由 transparent=True 处理
            # 移除 background_color 让 CSS 控制背景
            window_config.pop("background_color", None)
            # 屏幕外初始化：避免透明窗口 hidden=True 失效
            # 参考 dev_doc/pywebview-transparent-window-gotchas.md
            window_config["x"] = -9999
            window_config["y"] = -9999
            self._needs_center_on_show = True
            log("Mica: window will be created off-screen")

        # macOS: 启用 vibrancy
        if is_macos():
            window_config["transparent"] = True
            window_config["vibrancy"] = True
            window_config["text_select"] = True
            # 透明窗口需要移除 background_color
            window_config.pop("background_color", None)
            log("macOS vibrancy enabled")

        # 根据平台确定 HTML 路径
        try:
            html_path = get_settings_html_path()
            window_config["url"] = html_path
        except FileNotFoundError as e:
            log(f"Warning: {e}")
            # 使用内嵌的基础 HTML 作为后备
            window_config["html"] = self._get_fallback_html()

        # 创建窗口
        window = webview.create_window(**window_config)
        self._settings_window = window

        # 设置 API 的窗口引用
        self._settings_api.set_window(window)
        self._hotkey_api.set_window(window)
        self._permissions_api.set_window(window)

        # 绑定关闭事件
        window.events.closing += self._on_window_closing

        # Windows 11: 绑定加载事件以应用 Mica 效果
        if use_mica:
            window.events.loaded += self._on_window_loaded_mica

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

    def _on_window_loaded_mica(self) -> None:
        """Windows 窗口加载后应用 Mica 效果"""
        if not self._settings_window:
            return

        try:
            # 首先隐藏窗口，防止任务栏出现图标
            self._settings_window.hide()
            log("Mica: window hidden after load")

            # 获取窗口句柄
            hwnd = find_window_by_title(self._settings_window.title) if find_window_by_title else None

            if hwnd and apply_mica_effect:
                # 确定当前主题
                theme = app_state.config.get("theme", "auto")
                is_dark = theme == "dark" or (theme == "auto" and _is_system_dark_mode())

                # 应用 Mica 效果
                if apply_mica_effect(hwnd, dark_mode=is_dark, use_alt=True):
                    # 通知前端启用 Mica 样式
                    def notify_mica():
                        try:
                            self._settings_window.evaluate_js(
                                "document.documentElement.classList.add('mica-enabled')"
                            )
                            log("Frontend notified: mica-enabled class added")
                        except Exception as e:
                            log(f"Failed to notify frontend about Mica: {e}")

                    app_state.queue_ui_task(notify_mica)
                    log(f"Mica effect applied successfully, dark_mode={is_dark}")
                else:
                    log("Failed to apply Mica effect")
            else:
                log(f"Could not apply Mica: hwnd={hwnd}, apply_mica_effect={apply_mica_effect}")

        except Exception as e:
            log(f"Error in _on_window_loaded_mica: {e}")

    def _center_window_on_screen(self) -> None:
        """使用 Win32 API 将窗口居中到主显示器工作区

        透明窗口使用屏幕外初始化策略，首次显示时需要手动居中。
        使用 SetWindowPos 而非 pywebview.move() 以获得更可靠的结果。
        """
        if not self._settings_window or not is_windows():
            return

        try:
            import ctypes
            from ...utils.win32.win32_types import (
                POINT, MONITORINFO, MONITOR_DEFAULTTOPRIMARY,
                SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE
            )

            user32 = ctypes.windll.user32
            hwnd = find_window_by_title(self._settings_window.title) if find_window_by_title else None
            if not hwnd:
                log("Center: could not find window handle")
                return

            # 获取 DPI 缩放
            dpi = user32.GetDpiForWindow(hwnd)
            dpi_scale = dpi / 96.0 if dpi else 1.0

            # 获取主显示器（窗口在屏幕外时不能用 MonitorFromWindow）
            point = POINT(0, 0)
            monitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTOPRIMARY)

            # 获取工作区尺寸
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(monitor, ctypes.byref(mi))

            work_left = mi.rcWork.left
            work_top = mi.rcWork.top
            work_width = mi.rcWork.right - mi.rcWork.left
            work_height = mi.rcWork.bottom - mi.rcWork.top

            # 窗口尺寸转换为物理像素
            physical_width = int(SETTINGS_WINDOW_WIDTH * dpi_scale)
            physical_height = int(SETTINGS_WINDOW_HEIGHT * dpi_scale)

            # 计算居中位置
            x = work_left + (work_width - physical_width) // 2
            y = work_top + (work_height - physical_height) // 2

            # 使用 SetWindowPos 移动窗口
            user32.SetWindowPos(
                hwnd, 0, x, y, 0, 0,
                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
            )
            log(f"Center: moved to ({x}, {y}), DPI scale={dpi_scale}")

        except Exception as e:
            log(f"Center: failed - {e}")

    def update_mica_theme(self, is_dark: bool) -> bool:
        """更新 Mica 效果的深色/浅色模式

        Args:
            is_dark: 是否使用深色模式

        Returns:
            是否成功更新
        """
        if not self._settings_window or not MICA_AVAILABLE:
            return False

        try:
            hwnd = find_window_by_title(self._settings_window.title) if find_window_by_title else None
            if hwnd and update_mica_dark_mode:
                return update_mica_dark_mode(hwnd, is_dark)
        except Exception as e:
            log(f"Failed to update Mica theme: {e}")

        return False

    def _on_window_closing(self) -> bool:
        """窗口关闭事件处理"""
        # 如果正在退出，允许窗口销毁
        if self._is_quitting:
            return True

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
            # 首次显示时居中（针对透明窗口的屏幕外初始化）
            if self._needs_center_on_show:
                self._needs_center_on_show = False
                self._center_window_on_screen()

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
        """
        销毁所有窗口

        此方法应该只由 quit_event 监听器调用（统一退出点）。
        cleanup() 中的调用作为兜底，会检查 _is_quitting 标志避免重复执行。
        """
        # 安全检查：防止意外的重复调用
        if self._is_quitting:
            return

        self._is_quitting = True
        log("WebViewManager: destroying windows")

        try:
            if self._settings_window:
                self._settings_window.destroy()
                self._settings_window = None
                log("WebViewManager: settings window destroyed")
        except Exception as e:
            log(f"Failed to destroy settings window: {e}")
