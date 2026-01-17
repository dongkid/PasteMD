"""Application entry point and initialization."""

import sys
import threading
from ..config.paths import get_app_icon_path, is_first_launch
from ..utils.system_detect import is_macos

# macOS: 首次启动时打开使用说明页面
IS_FIRST_LAUNCH = is_first_launch()

if is_macos() and IS_FIRST_LAUNCH:
    try:
        import webbrowser
        webbrowser.open("https://pastemd.richqaq.cn/macos")
    except Exception:
        pass

# 设置 Windows 应用程序 ID (仅在 Windows 上)
try:
    import ctypes
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RichQAQ.PasteMD")
except Exception:
    pass

from ..utils.dpi import set_dpi_awareness

from .. import __version__
from ..core.state import app_state
from ..core.singleton import check_single_instance
from ..config.loader import ConfigLoader
from ..utils.logging import log
from ..utils.version_checker import VersionChecker
from ..service.notification.manager import NotificationManager
from ..i18n import FALLBACK_LANGUAGE, detect_system_language, set_language, t
from .wiring import Container


def initialize_application() -> Container:
    """初始化应用程序"""
    # 1. 加载配置
    config_loader = ConfigLoader()
    config = config_loader.load()
    app_state.config = config
    app_state.hotkey_str = config.get("hotkey", "<ctrl>+<shift>+b")

    language_value = config.get("language")
    if not language_value:
        detected_language = detect_system_language()
        if detected_language:
            language = detected_language
        else:
            language = FALLBACK_LANGUAGE
        app_state.config["language"] = language
        try:
            config_loader.save(app_state.config)
        except Exception as exc:
            log(f"Failed to persist auto-detected language: {exc}")
        log(f"First launch: detected system language '{language}'")
    else:
        language = str(language_value)
    set_language(language)
    
    # 2. 创建依赖注入容器
    container = Container()
    
    log("Application initialized successfully")
    return container


def show_startup_notification(notification_manager: NotificationManager) -> None:
    """显示启动通知"""
    try:
        # 检查是否启用开机通知
        if app_state.config.get("startup_notify", True) is False:
            return
        
        # 确保图标路径存在（仅用于验证）
        get_app_icon_path()
        notification_manager.notify(
            "PasteMD",
            t("app.startup.success"),
            ok=True
        )
    except Exception as e:
        log(f"Failed to show startup notification: {e}")


def check_update_in_background(notification_manager: NotificationManager, tray_menu_manager=None) -> None:
    """在后台检查版本更新"""
    def _check():
        try:

            checker = VersionChecker(__version__)
            result = checker.check_update()
            
            if result and result.get("has_update"):
                latest_version = result.get("latest_version")
                release_url = result.get("release_url")
                
                # 使用菜单管理器的方法更新版本信息并重新绘制菜单
                if tray_menu_manager and app_state.icon:
                    tray_menu_manager.update_version_info(app_state.icon, latest_version, release_url)
                
                log(f"New version available: {latest_version}")
                log(f"Download URL: {release_url}")
        except Exception as e:
            log(f"Background version check failed: {e}")
    
    # 启动后台线程，不阻塞主程序
    thread = threading.Thread(target=_check, daemon=True)
    thread.start()


def main() -> None:
    """应用程序主入口点"""
    container = None  # 提升到 try 块外部，以便在 finally 中访问

    try:
        # 设置 DPI 感知（尽早调用）
        set_dpi_awareness()

        # 检查单实例运行
        if not check_single_instance():
            # 已有实例：macOS 上尝试通知已运行实例打开设置页（类似"再次点击应用图标"）
            if is_macos():
                try:
                    from ..utils.macos.ipc import send_command

                    if send_command("open_settings"):
                        sys.exit(0)
                except Exception as exc:
                    log(f"Failed to send reopen command: {exc}")

            log("Application is already running")
            sys.exit(1)

        # 初始化应用程序
        container = initialize_application()

        # 初始化退出事件
        app_state.quit_event = threading.Event()

        # macOS: 默认隐藏 Dock 图标，仅在弹窗打开时临时显示
        if is_macos():
            try:
                from ..utils.macos.dock import set_dock_visible

                set_dock_visible(False)
            except Exception as exc:
                log(f"Failed to hide Dock icon: {exc}")

        # 从 Container 获取 WebView 启动器
        launcher = container.get_webview_launcher()

        def on_started():
            """WebView 初始化完成后的回调"""
            # 获取通知管理器和菜单管理器
            notification_manager = container.get_notification_manager()
            tray_menu_manager = container.tray_menu_manager

            # 显示启动通知
            show_startup_notification(notification_manager)

            # 启动后台版本检查
            check_update_in_background(notification_manager, tray_menu_manager)

            # macOS: 首次启动时打开权限设置页
            if is_macos() and IS_FIRST_LAUNCH:
                try:
                    manager = launcher.get_manager()
                    if manager:
                        manager.show_settings("permissions")
                except Exception as exc:
                    log(f"Failed to open permissions settings on first launch: {exc}")

        # 启动 WebView 应用（阻塞主线程）
        launcher.start(on_started=on_started)

    except KeyboardInterrupt:
        log("Application interrupted by user")
    except Exception as e:
        log(f"Fatal error: {e}")
        raise
    finally:
        # P2-2: 统一资源清理
        try:
            app_state.cleanup()
        except Exception as e:
            log(f"Error during cleanup: {e}")

        # 释放锁
        if app_state.instance_checker:
            app_state.instance_checker.release_lock()
        log("Application shutting down")


if __name__ == "__main__":
    main()
