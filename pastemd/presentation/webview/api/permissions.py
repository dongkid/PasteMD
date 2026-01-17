"""macOS permissions API for webview."""

from __future__ import annotations

import subprocess
from typing import Optional, TYPE_CHECKING

from .base import BaseApi
from ....utils.logging import log
from ....utils.system_detect import is_macos
from ....i18n import t

if TYPE_CHECKING:
    from ....app.wiring import Container


class PermissionsApi(BaseApi):
    """macOS 权限检测 Python API (仅在 macOS 上有效)"""

    PERMISSION_TYPES = ["accessibility", "screen_recording", "input_monitoring", "automation"]

    def __init__(self, container: "Container"):
        super().__init__(container)

    def is_macos(self) -> str:
        """检查是否是 macOS 平台"""
        return self._success(is_macos())

    def get_all_permissions(self) -> str:
        """获取所有权限状态"""
        if not is_macos():
            return self._error("Not macOS", "PLATFORM_ERROR")

        try:
            results = {}
            for perm_type in self.PERMISSION_TYPES:
                status = self._check_permission_internal(perm_type)
                results[perm_type] = {
                    "status": status,
                    "status_text": self._format_status(status)[0],
                    "status_color": self._format_status(status)[1]
                }

            return self._success(results)
        except Exception as e:
            log(f"Failed to get all permissions: {e}")
            return self._error(str(e), "GET_PERMISSIONS_ERROR")

    def check_permission(self, permission_type: str) -> str:
        """检查单个权限状态"""
        if not is_macos():
            return self._error("Not macOS", "PLATFORM_ERROR")

        try:
            if permission_type not in self.PERMISSION_TYPES:
                return self._error(f"Unknown permission type: {permission_type}", "UNKNOWN_PERMISSION")

            status = self._check_permission_internal(permission_type)
            status_text, status_color = self._format_status(status)

            return self._success({
                "type": permission_type,
                "status": status,
                "status_text": status_text,
                "status_color": status_color
            })
        except Exception as e:
            log(f"Failed to check permission {permission_type}: {e}")
            return self._error(str(e), "CHECK_PERMISSION_ERROR")

    def request_permission(self, permission_type: str) -> str:
        """请求权限"""
        if not is_macos():
            return self._error("Not macOS", "PLATFORM_ERROR")

        try:
            if permission_type not in self.PERMISSION_TYPES:
                return self._error(f"Unknown permission type: {permission_type}", "UNKNOWN_PERMISSION")

            success = self._request_permission_internal(permission_type)
            return self._success({"requested": success})
        except Exception as e:
            log(f"Failed to request permission {permission_type}: {e}")
            return self._error(str(e), "REQUEST_PERMISSION_ERROR")

    def open_system_settings(self, permission_type: str) -> str:
        """打开系统设置中对应的权限页面"""
        if not is_macos():
            return self._error("Not macOS", "PLATFORM_ERROR")

        try:
            url_map = {
                "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
                "screen_recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
                "input_monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
                "automation": "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
            }

            url = url_map.get(permission_type)
            if not url:
                return self._error(f"Unknown permission type: {permission_type}", "UNKNOWN_PERMISSION")

            subprocess.run(["open", url], check=False)
            return self._success(message="System Settings opened")
        except Exception as e:
            log(f"Failed to open System Settings: {e}")
            return self._error(str(e), "OPEN_SETTINGS_ERROR")

    def get_permission_info(self) -> str:
        """获取权限相关的本地化文本"""
        try:
            info = {
                "intro": t("settings.permissions.intro"),
                "add_hint": t("settings.permissions.add_hint"),
                "last_checked": t("settings.permissions.last_checked", time="--:--:--"),
                "refresh": t("settings.permissions.refresh"),
                "open_settings": t("settings.permissions.open_settings"),
                "request_access": t("settings.permissions.request_access"),
                "status": {
                    "granted": t("settings.permissions.status.granted"),
                    "missing": t("settings.permissions.status.missing"),
                    "unknown": t("settings.permissions.status.unknown"),
                    "checking": t("settings.permissions.status.checking"),
                },
                "permissions": {
                    "accessibility": {
                        "title": t("settings.permissions.accessibility.title"),
                        "desc": t("settings.permissions.accessibility.desc"),
                    },
                    "screen_recording": {
                        "title": t("settings.permissions.screen_recording.title"),
                        "desc": t("settings.permissions.screen_recording.desc"),
                    },
                    "input_monitoring": {
                        "title": t("settings.permissions.input_monitoring.title"),
                        "desc": t("settings.permissions.input_monitoring.desc"),
                    },
                    "automation": {
                        "title": t("settings.permissions.automation.title"),
                        "desc": t("settings.permissions.automation.desc"),
                    },
                }
            }
            return self._success(info)
        except Exception as e:
            log(f"Failed to get permission info: {e}")
            return self._error(str(e), "GET_INFO_ERROR")

    # ==================== 内部方法 ====================
    def _check_permission_internal(self, permission_type: str) -> Optional[bool]:
        """内部权限检查方法"""
        if permission_type == "accessibility":
            return self._check_accessibility()
        elif permission_type == "screen_recording":
            return self._check_screen_recording()
        elif permission_type == "input_monitoring":
            return self._check_input_monitoring()
        elif permission_type == "automation":
            return self._check_automation()
        return None

    def _request_permission_internal(self, permission_type: str) -> bool:
        """内部权限请求方法"""
        if permission_type == "accessibility":
            return self._request_accessibility()
        elif permission_type == "screen_recording":
            return self._request_screen_recording()
        elif permission_type == "input_monitoring":
            return self._request_input_monitoring()
        elif permission_type == "automation":
            return self._request_automation()
        return False

    def _format_status(self, status: Optional[bool]) -> tuple:
        """格式化状态显示"""
        if status is True:
            return t("settings.permissions.status.granted"), "#2a7b2e"
        if status is False:
            return t("settings.permissions.status.missing"), "#b32323"
        return t("settings.permissions.status.unknown"), "#666666"

    def _check_accessibility(self) -> Optional[bool]:
        """检查辅助功能权限"""
        # 1) Quartz 路线
        try:
            import Quartz
            if hasattr(Quartz, "AXIsProcessTrustedWithOptions"):
                try:
                    prompt_key = getattr(Quartz, "kAXTrustedCheckOptionPrompt", None)
                    options = {prompt_key: False} if prompt_key is not None else {}
                    return bool(Quartz.AXIsProcessTrustedWithOptions(options))
                except Exception as exc:
                    log(f"AXIsProcessTrustedWithOptions failed: {exc}")

            if hasattr(Quartz, "AXIsProcessTrusted"):
                try:
                    return bool(Quartz.AXIsProcessTrusted())
                except Exception as exc:
                    log(f"AXIsProcessTrusted failed: {exc}")

        except Exception as exc:
            log(f"Quartz not available for accessibility check: {exc}")

        # 2) ctypes fallback
        try:
            import ctypes
            app_services = ctypes.CDLL(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
            app_services.AXIsProcessTrusted.restype = ctypes.c_bool
            app_services.AXIsProcessTrusted.argtypes = []
            return bool(app_services.AXIsProcessTrusted())
        except Exception as exc:
            log(f"AXIsProcessTrusted failed (ctypes): {exc}")
            return None

    def _check_automation(self) -> Optional[bool]:
        """检查自动化权限"""
        script = 'tell application "System Events" to get name of processes'
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2,
            )
        except subprocess.TimeoutExpired:
            return False
        except Exception as exc:
            log(f"Automation check failed: {exc}")
            return None

        if result.returncode == 0:
            return True

        combined = " ".join([result.stdout or "", result.stderr or ""]).lower()
        if "not authorized" in combined or "not authorised" in combined or "not permitted" in combined:
            return False
        return None

    def _check_screen_recording(self) -> Optional[bool]:
        """检查屏幕录制权限"""
        try:
            import Quartz
        except Exception as exc:
            log(f"Quartz not available for screen recording check: {exc}")
            return None

        if hasattr(Quartz, "CGPreflightScreenCaptureAccess"):
            try:
                return bool(Quartz.CGPreflightScreenCaptureAccess())
            except Exception as exc:
                log(f"CGPreflightScreenCaptureAccess failed: {exc}")
                return None
        return None

    def _check_input_monitoring(self) -> Optional[bool]:
        """检查输入监控权限"""
        try:
            import Quartz
        except Exception as exc:
            log(f"Quartz not available for input monitoring check: {exc}")
            return None

        if hasattr(Quartz, "CGPreflightListenEventAccess"):
            try:
                return bool(Quartz.CGPreflightListenEventAccess())
            except Exception as exc:
                log(f"CGPreflightListenEventAccess failed: {exc}")
                return None
        return None

    def _request_accessibility(self) -> bool:
        """请求辅助功能权限"""
        try:
            import Quartz
            prompt_key = getattr(Quartz, "kAXTrustedCheckOptionPrompt", None)
            if hasattr(Quartz, "AXIsProcessTrustedWithOptions"):
                Quartz.AXIsProcessTrustedWithOptions({prompt_key: True})
                return True
        except Exception as exc:
            log(f"Accessibility request failed: {exc}")
        return False

    def _request_screen_recording(self) -> bool:
        """请求屏幕录制权限"""
        try:
            import Quartz
            if hasattr(Quartz, "CGRequestScreenCaptureAccess"):
                Quartz.CGRequestScreenCaptureAccess()
                return True
        except Exception as exc:
            log(f"Screen recording request failed: {exc}")
        return False

    def _request_input_monitoring(self) -> bool:
        """请求输入监控权限"""
        try:
            import Quartz
            if hasattr(Quartz, "CGRequestListenEventAccess"):
                Quartz.CGRequestListenEventAccess()
                return True
        except Exception as exc:
            log(f"Input monitoring request failed: {exc}")
        return False

    def _request_automation(self) -> bool:
        """请求自动化权限 (触发系统提示)"""
        script = 'tell application "System Events" to get name of processes'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2,
            )
            return True
        except Exception as exc:
            log(f"Automation request failed: {exc}")
            return False
