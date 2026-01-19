"""WebView application launcher."""

from __future__ import annotations

import threading
from typing import Optional, Callable, TYPE_CHECKING

import webview

from .manager import WebViewManager
from ...config.paths import get_app_icon_path
from ...utils.logging import log
from ...utils.system_detect import is_macos
from ...core.state import app_state

if TYPE_CHECKING:
    from ...app.wiring import Container


class WebViewLauncher:
    """
    WebView 应用启动器

    负责:
    - 协调 webview 与其他服务的启动顺序
    - 管理主循环
    - 处理优雅退出
    """

    def __init__(self, container: "Container"):
        self._container = container
        self._manager: Optional[WebViewManager] = None
        self._started = False

    def get_manager(self) -> WebViewManager:
        """获取窗口管理器"""
        if not self._manager:
            self._manager = WebViewManager(self._container)
        return self._manager

    def _refresh_tray_menu(self) -> None:
        """刷新托盘菜单"""
        try:
            tray_icon = getattr(app_state, "icon", None)
            if tray_icon:
                tray_menu = self._container.tray_menu_manager.build_menu()
                tray_icon.menu = tray_menu
                if hasattr(tray_icon, "update_menu"):
                    tray_icon.update_menu()
        except Exception as e:
            log(f"Failed to refresh tray menu: {e}")

    def _start_quit_event_listener(self) -> None:
        """
        P1-15: 启动 quit_event 监听器

        这是统一的退出处理点：
        - 监听 quit_event 信号
        - 收到信号后销毁 WebView，使 webview.start() 返回
        - 由 _on_quit（托盘退出）触发 quit_event
        """
        def _listen():
            quit_event = app_state.quit_event
            if quit_event:
                # 等待退出事件
                quit_event.wait()
                log("Quit event received, destroying webview (primary cleanup point)...")
                try:
                    if self._manager:
                        self._manager.destroy()
                except Exception as e:
                    log(f"Error during quit cleanup: {e}")

        thread = threading.Thread(target=_listen, daemon=True)
        thread.start()
        log("Quit event listener started")

    def _post_start_init(self, on_started: Optional[Callable] = None) -> None:
        """
        webview 启动后的初始化任务

        在后台线程中执行:
        - 启动热键监听
        - 启动托盘图标
        - 启动 IPC 服务器 (macOS)
        - 启动 quit_event 监听器
        - 调用用户回调
        """
        try:
            # 启动热键监听
            hotkey_runner = self._container.get_hotkey_runner()
            hotkey_runner.start()
            log("Hotkey runner started")

            # 启动托盘
            tray_runner = self._container.get_tray_runner()

            if is_macos():
                # macOS: 托盘需要在主线程初始化，但可以在后台运行
                # 由于 webview 占用主线程，我们在这里尝试后台启动
                try:
                    tray_runner.setup()
                except Exception as e:
                    log(f"Failed to setup tray on macOS: {e}")
            else:
                # Windows: 在后台线程运行
                tray_thread = threading.Thread(target=tray_runner.run, daemon=True)
                tray_thread.start()
                log("Tray runner started in background")

            # macOS: 启动 IPC 服务器
            if is_macos():
                try:
                    from ...utils.macos.ipc import start_server

                    def handle_command(cmd: str) -> None:
                        if cmd == "open_settings":
                            try:
                                self._manager.show_settings()
                            except Exception as e:
                                log(f"Failed to open settings from IPC: {e}")

                    start_server(handle_command)
                    log("IPC server started")
                except Exception as e:
                    log(f"Failed to start IPC server: {e}")

                # macOS: Reopen 事件处理
                try:
                    from ...utils.macos.reopen import install_reopen_handler

                    install_reopen_handler(lambda: self._manager.show_settings())
                    log("Reopen handler installed")
                except Exception as e:
                    log(f"Failed to install reopen handler: {e}")

            # P1-15: 启动 quit_event 监听器
            self._start_quit_event_listener()

            # 调用用户回调
            if on_started:
                try:
                    on_started()
                except Exception as e:
                    log(f"on_started callback error: {e}")

        except Exception as e:
            log(f"Post-start initialization error: {e}")

    def start(
        self,
        on_started: Optional[Callable] = None,
    ) -> None:
        """
        启动 webview 应用

        注意: 此方法会阻塞主线程

        Args:
            on_started: webview 初始化完成后调用的回调函数
        """
        if self._started:
            log("WebView already started")
            return

        self._started = True

        # 从配置读取 debug 模式
        debug = app_state.config.get("debug_mode", False)

        # 创建窗口管理器
        self._manager = self.get_manager()

        # 存储到全局状态
        app_state.webview_manager = self._manager

        # 设置设置页面的回调
        def on_settings_save():
            """设置保存后刷新托盘菜单"""
            try:
                from ...i18n import set_language
                set_language(app_state.config.get("language", "en-US"))
                self._refresh_tray_menu()
            except Exception as e:
                log(f"Failed to refresh tray after settings save: {e}")

        def on_settings_close():
            """设置关闭后的处理"""
            # 恢复热键监听 (如果之前暂停了)
            try:
                resume_callback = self._container.tray_menu_manager.resume_hotkey_callback
                if resume_callback:
                    resume_callback()
            except Exception as e:
                log(f"Failed to resume hotkey after settings close: {e}")

        self._manager.set_settings_callbacks(on_settings_save, on_settings_close)

        # 设置热键保存回调
        def on_hotkey_saved():
            """热键保存后重启热键绑定"""
            try:
                restart_callback = self._container.tray_menu_manager.restart_hotkey_callback
                if restart_callback:
                    restart_callback()
                self._refresh_tray_menu()
            except Exception as e:
                log(f"Failed to restart hotkey: {e}")

        # 创建设置窗口 (隐藏状态)
        try:
            window = self._manager.create_settings_window()
            app_state.webview_window = window
            log("Settings window created (hidden)")
        except Exception as e:
            log(f"Failed to create settings window: {e}")
            raise

        # 设置热键保存回调（必须在 create_settings_window 之后，此时 hotkey_api 才存在）
        hotkey_api = self._manager.get_hotkey_api()
        if hotkey_api:
            hotkey_api.set_hotkey_saved_callback(on_hotkey_saved)

        # 启动 webview 主循环
        # func 参数会在 webview 初始化完成后在后台线程中执行
        log("Starting webview main loop...")

        # 获取应用图标路径
        icon_path = get_app_icon_path()

        webview.start(
            func=lambda: self._post_start_init(on_started),
            debug=debug,
            gui=None,  # 自动检测
            icon=icon_path,
        )

        log("WebView main loop ended")
