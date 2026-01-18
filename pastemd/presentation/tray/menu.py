"""Tray menu construction and callbacks."""

import os
import subprocess
import pystray
import threading
import webbrowser
from typing import Optional

from ... import __version__
from ...core.state import app_state
from ...config.loader import ConfigLoader
from ...config.paths import get_log_path, get_config_path
from ...service.notification.manager import NotificationManager
from ...utils.fs import ensure_dir, open_dir, open_file
from ...utils.logging import log
from ...utils.version_checker import VersionChecker
from ...utils.system_detect import is_windows, is_macos
from ...i18n import t, iter_languages, get_language, set_language, get_language_label, get_no_app_action_map
from .icon import create_status_icon

try:
    if is_macos():
        from ...utils.macos.dock import begin_ui_session, end_ui_session, activate_app
    else:  # pragma: no cover
        begin_ui_session = end_ui_session = activate_app = lambda *args, **kwargs: None
except Exception:  # pragma: no cover
    begin_ui_session = end_ui_session = activate_app = lambda *args, **kwargs: None


class TrayMenuManager:
    """托盘菜单管理器"""

    def __init__(self, config_loader: ConfigLoader, notification_manager: NotificationManager):
        self.config_loader = config_loader
        self.notification_manager = notification_manager
        self.restart_hotkey_callback = None  # 将由外部设置
        self.pause_hotkey_callback = None  # 暂停热键监听
        self.resume_hotkey_callback = None  # 恢复热键监听
        self.version_checker = None  # 将由外部设置或按需创建
        self.latest_version = None  # 存储最新版本号
        self.latest_release_url = None  # 存储最新版本的下载链接
    
    def set_restart_hotkey_callback(self, callback):
        """设置重启热键的回调函数"""
        self.restart_hotkey_callback = callback
    
    def set_pause_hotkey_callback(self, callback):
        """设置暂停热键的回调函数"""
        self.pause_hotkey_callback = callback
    
    def set_resume_hotkey_callback(self, callback):
        """设置恢复热键的回调函数"""
        self.resume_hotkey_callback = callback
    
    def build_menu(self) -> pystray.Menu:
        """构建托盘菜单"""
        config = app_state.config

        # 构建常规菜单项
        normal_menu_items = [
            pystray.MenuItem(
                t("tray.menu.hotkey_display", hotkey=app_state.config['hotkey']),
                lambda icon, item: None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                t("tray.menu.enable_hotkey"),
                self._on_toggle_enabled,
                checked=lambda item: app_state.enabled
            ),
            pystray.MenuItem(
                t("tray.menu.show_notifications"),
                self._on_toggle_notify,
                checked=lambda item: config.get("notify", True)
            )
        ]

        if is_windows():
            normal_menu_items.append(
                pystray.MenuItem(
                    t("tray.menu.move_cursor"),
                    self._on_toggle_move_cursor,
                    checked=lambda item: config.get("move_cursor_to_end", True)
                )
            )

        # 构建版本菜单项
        version_menu_items = [
            pystray.MenuItem(
                t("tray.menu.current_version", version=__version__),
                lambda icon, item: None,
                enabled=False
            ),
        ]
        if self.latest_version:
            version_menu_items.append(
                pystray.MenuItem(
                    t("tray.menu.new_version", version=self.latest_version),
                    self._on_open_release_page,
                    enabled=True
                )
            )
        else:
            version_menu_items.append(
                pystray.MenuItem(
                    t("tray.menu.check_update"),
                    self._on_check_update
                )
            )

        return pystray.Menu(
            *normal_menu_items,
            self._build_no_app_action_menu(),
            self._build_html_formatting_menu(),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.menu.set_hotkey"), self._on_set_hotkey),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                t("tray.menu.keep_file"),
                self._on_toggle_keep,
                checked=lambda item: config.get("keep_file", False)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.menu.open_save_dir"), self._on_open_save_dir),
            pystray.MenuItem(t("tray.menu.open_log"), self._on_open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("settings.dialog.title"), self._on_open_settings),
            pystray.Menu.SEPARATOR,
            *version_menu_items,
            pystray.MenuItem(
                t("tray.menu.about"),
                self._on_open_about_page
            ),
            pystray.MenuItem(t("tray.menu.quit"), self._on_quit)
        )

    # 菜单回调函数
    def _on_toggle_enabled(self, icon, item):
        """切换热键启用状态"""
        app_state.enabled = not app_state.enabled
        icon.icon = create_status_icon(ok=app_state.enabled)
        
        status = t("tray.status.hotkey_enabled") if app_state.enabled else t("tray.status.hotkey_paused")
        icon.menu = self.build_menu()
        self.notification_manager.notify("PasteMD", status, ok=app_state.enabled)
    
    def _on_set_hotkey(self, icon, item):
        """设置热键，使用 webview 打开设置窗口"""
        # 使用 WebView 打开设置窗口并显示热键模态框
        try:
            begin_ui_session()
            activate_app()

            manager = app_state.webview_manager
            if manager:
                manager.show_settings()
                # 通过队列安全调用 evaluate_js（跨线程安全）
                def task():
                    window = app_state.webview_window
                    if window:
                        window.evaluate_js("openHotkeyModal()")
                # 使用 Timer 非阻塞延迟，避免阻塞托盘线程
                threading.Timer(0.3, lambda: app_state.queue_ui_task(task)).start()
        except Exception as e:
            log(f"Failed to open hotkey settings: {e}")
            self.notification_manager.notify("PasteMD", t("tray.error.open_hotkey_dialog", error=str(e)), ok=False)
            end_ui_session()
    
    def _on_toggle_notify(self, icon, item):
        """切换通知状态"""
        current = app_state.config.get("notify", True)
        app_state.config["notify"] = not current
        self._save_config()
        icon.menu = self.build_menu()
        if app_state.config["notify"]:
            self.notification_manager.notify("PasteMD", t("tray.status.notifications_enabled"), ok=True)
        else:
            log("Notifications disabled via tray toggle")
    
    def _on_toggle_move_cursor(self, icon, item):
        """切换插入后光标移动到末尾状态"""
        current = app_state.config.get("move_cursor_to_end", True)
        app_state.config["move_cursor_to_end"] = not current
        self._save_config()
        icon.menu = self.build_menu()
        status = t("tray.status.move_cursor_on") if app_state.config["move_cursor_to_end"] else t("tray.status.move_cursor_off")
        self.notification_manager.notify("PasteMD", status, ok=True)
        
    def _on_toggle_excel(self, icon, item):
        """切换启用 Excel 插入"""
        current = app_state.config.get("enable_excel", True)
        app_state.config["enable_excel"] = not current
        self._save_config()
        icon.menu = self.build_menu()
        status = t("tray.status.excel_insert_on") if app_state.config["enable_excel"] else t("tray.status.excel_insert_off")
        self.notification_manager.notify("PasteMD", status, ok=True)
        
    def _on_toggle_excel_format(self, icon, item):
        """切换 Excel 粘贴时是否保留格式"""
        current = app_state.config.get("excel_keep_format", True)
        app_state.config["excel_keep_format"] = not current
        self._save_config()
        icon.menu = self.build_menu()
        status = t("tray.status.excel_format_on") if app_state.config["excel_keep_format"] else t("tray.status.excel_format_off")
        self.notification_manager.notify("PasteMD", status, ok=True)
    
    def _on_toggle_keep(self, icon, item):
        """切换保留文件状态"""
        current = app_state.config.get("keep_file", False)
        app_state.config["keep_file"] = not current
        self._save_config()
        icon.menu = self.build_menu()
        status = t("tray.status.keep_file_on") if app_state.config["keep_file"] else t("tray.status.keep_file_off")
        self.notification_manager.notify("PasteMD", status, ok=True)
    
    def _on_open_save_dir(self, icon, item):
        """打开保存目录"""
        save_dir = app_state.config.get("save_dir", "")
        save_dir = os.path.expandvars(save_dir)
        ensure_dir(save_dir)
        open_dir(save_dir)
    
    def _on_open_log(self, icon, item):
        """打开日志文件"""
        log_path = get_log_path()
        if not os.path.exists(log_path):
            # 创建空日志文件
            open(log_path, "w", encoding="utf-8").close()
        open_file(log_path)
    
    def _on_open_settings(self, icon, item):
        """打开设置界面"""
        self._open_settings(icon, item, None)

    def open_settings_tab(self, tab_key: Optional[str]) -> None:
        """Open settings and select a specific tab."""
        self._open_settings(getattr(app_state, "icon", None), None, tab_key)

    def _open_settings(self, icon, item, select_tab: Optional[str]) -> None:
        """打开设置界面 (使用 webview)"""
        try:
            begin_ui_session()
            activate_app()

            manager = app_state.webview_manager
            if manager:
                manager.show_settings(select_tab)
            else:
                log("WebView manager not available")
                self.notification_manager.notify("PasteMD", "Settings not available", ok=False)
                end_ui_session()
        except Exception as e:
            log(f"Failed to open settings: {e}")
            self.notification_manager.notify("PasteMD", f"Error opening settings: {e}", ok=False)
            end_ui_session()

    def _build_html_formatting_menu(self) -> pystray.MenuItem:
        """构建 HTML 格式化子菜单"""
        return pystray.MenuItem(
            t("tray.menu.html_formatting"),
            pystray.Menu(
                pystray.MenuItem(
                    t("tray.menu.strikethrough_to_del"),
                    self._on_toggle_html_strikethrough,
                    checked=lambda item: self._get_html_formatting_option("strikethrough_to_del", True),
                ),
            ),
        )

    def _build_no_app_action_menu(self) -> pystray.MenuItem:
        """构建无应用时动作子菜单"""
        return pystray.MenuItem(
            t("tray.menu.no_app_action"),
            pystray.Menu(
                pystray.MenuItem(
                    t("action.open"),
                    self._on_set_no_app_action,
                    checked=lambda item: self._get_no_app_action() == "open",
                ),
                pystray.MenuItem(
                    t("action.save"),
                    self._on_set_no_app_action,
                    checked=lambda item: self._get_no_app_action() == "save",
                ),
                pystray.MenuItem(
                    t("action.clipboard"),
                    self._on_set_no_app_action,
                    checked=lambda item: self._get_no_app_action() == "clipboard",
                ),
                pystray.MenuItem(
                    t("action.none"),
                    self._on_set_no_app_action,
                    checked=lambda item: self._get_no_app_action() == "none",
                ),
            ),
        )

    def _get_no_app_action(self) -> str:
        """获取当前无应用动作设置"""
        return app_state.config.get("no_app_action", "open")

    def _on_set_no_app_action(self, icon, item):
        """设置无应用动作"""
        # 从标签文本映射到配置值（反转 action_map）
        action_map = get_no_app_action_map()
        reverse_action_map = {v: k for k, v in action_map.items()}
        
        # 获取点击的菜单项的文本
        clicked_text = getattr(item, 'text', '')
        
        # 设置新的动作
        new_action = reverse_action_map.get(clicked_text, "open")
        app_state.config["no_app_action"] = new_action
        self._save_config()
        icon.menu = self.build_menu()
        
        # 显示状态通知
        status_map = {
            "open": t("tray.status.no_app_action_open"),
            "save": t("tray.status.no_app_action_save"),
            "clipboard": t("tray.status.no_app_action_clipboard"),
            "none": t("tray.status.no_app_action_none")
        }
        
        status = status_map.get(new_action, "")
        self.notification_manager.notify("PasteMD", status, ok=True)

    def _get_html_formatting_option(self, key: str, default: bool) -> bool:
        options = app_state.config.get("html_formatting", {})
        if isinstance(options, dict):
            return bool(options.get(key, default))
        return default

    def _on_toggle_html_strikethrough(self, icon, item):
        """切换删除线转 <del> 的 HTML 格式化配置"""
        current = self._get_html_formatting_option("strikethrough_to_del", True)
        if not isinstance(app_state.config.get("html_formatting"), dict):
            app_state.config["html_formatting"] = {}
        app_state.config["html_formatting"]["strikethrough_to_del"] = not current
        self._save_config()
        icon.menu = self.build_menu()

        status = (
            t("tray.status.html_strike_on")
            if app_state.config["html_formatting"].get("strikethrough_to_del", True)
            else t("tray.status.html_strike_off")
        )
        self.notification_manager.notify("PasteMD", status, ok=True)
    
    def _on_check_update(self, icon, item):
        """检查更新"""
        # 在后台线程中检查更新，避免阻塞 UI
        def check_in_background():
            try:
                # 导入版本号
                from ... import __version__
                
                checker = VersionChecker(__version__)
                result = checker.check_update()
                
                if result is None:
                    # 网络错误或检查失败
                    log("Version check failed - network error")
                    self.notification_manager.notify(
                        f"PasteMD - {t('tray.update.title_failure')}",
                        t("tray.update.network_error"),
                        ok=False
                    )
                elif result.get("has_update"):
                    latest_version = result.get("latest_version")
                    release_url = result.get("release_url")
                    
                    # 使用 update_version_info 方法更新版本信息并重新绘制菜单
                    self.update_version_info(icon, latest_version, release_url)
                    
                    # 通知用户有新版本，并自动打开下载页面
                    message = t("tray.update.opening_release", version=latest_version)
                    self.notification_manager.notify(
                        f"PasteMD - {t('tray.update.title_new_version')}",
                        message,
                        ok=True
                    )
                    
                    # 自动打开下载页面
                    try:
                        webbrowser.open(release_url)
                    except Exception as e:
                        log(f"Failed to open browser: {e}")
                    
                    log(f"New version available: {latest_version}")
                    log(f"Download URL: {release_url}")
                else:
                    # 无需更新，通知用户已是最新版本
                    current_version = result.get("current_version")
                    log(f"Already on latest version: {current_version}")
                    self.notification_manager.notify(
                        f"PasteMD - {t('tray.update.title_latest')}",
                        t("tray.update.latest_version", version=current_version),
                        ok=True
                    )
            except Exception as e:
                error_text = str(e)
                short_error = error_text if len(error_text) <= 15 else error_text[:12] + "..."
                self.notification_manager.notify(
                    f"PasteMD - {t('tray.update.title_unexpected_error')}",
                    t("tray.update.error_with_message", error=short_error),
                    ok=False
                )
                log(f"Error checking update: {e}")
        
        # 启动后台线程
        thread = threading.Thread(target=check_in_background, daemon=True)
        thread.start()
    
    def _on_open_release_page(self, icon, item):
        """打开发布页面"""
        if self.latest_release_url:
            try:
                webbrowser.open(self.latest_release_url)
                log(f"Opening release page: {self.latest_release_url}")
            except Exception as e:
                log(f"Failed to open browser: {e}")
                self.notification_manager.notify(
                    "PasteMD",
                    t("tray.error.open_release_page"),
                    ok=False
                )

    def update_version_info(self, icon, latest_version: str, release_url: str):
        """更新最新版本信息"""
        self.latest_version = latest_version
        self.latest_release_url = release_url
        icon.menu = self.build_menu()
    
    def _on_open_about_page(self, icon, item):
        """打开关于页面"""
        # macOS 使用专门的介绍页面
        if is_macos():
            about_url = "https://pastemd.richqaq.cn/macos"
        else:
            about_url = "http://pastemd.richqaq.cn"
        try:
            webbrowser.open(about_url)
            log(f"Opening about page: {about_url}")
        except Exception as e:
            log(f"Failed to open browser: {e}")
            self.notification_manager.notify(
                "PasteMD",
                t("tray.error.open_about_page", url=about_url),
                ok=False
            )
    
    def _on_quit(self, icon, item):
        """退出应用程序

        退出流程统一由 quit_event 驱动：
        1. 此处只负责停止托盘并发出退出信号
        2. quit_event 监听器（launcher.py）负责销毁 WebView
        3. cleanup()（state.py）负责最终的资源清理
        """
        icon.stop()

        # 设置退出事件（统一的退出信号）
        if app_state.quit_event is None:
            import threading
            app_state.quit_event = threading.Event()

        app_state.quit_event.set()
        log("Quit event set, waiting for quit_event listener to handle cleanup")
    
    def _save_config(self):
        """保存配置"""
        try:
            self.config_loader.save(app_state.config)
        except Exception as e:
            log(f"Failed to save config: {e}")
