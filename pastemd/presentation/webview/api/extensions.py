"""Extensions API for webview."""

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING

from .base import BaseApi
from ....core.state import app_state
from ....config.defaults import RESERVED_APPS
from ....utils.logging import log
from ....utils.system_detect import is_windows, is_macos
from ....i18n import t

if TYPE_CHECKING:
    from ....app.wiring import Container


class ExtensionsApi(BaseApi):
    """扩展工作流配置 API"""

    def __init__(self, container: "Container"):
        super().__init__(container)
        self.config_loader = container.config_loader

    # ==================== 配置读取 ====================
    def get_extensible_workflows(self) -> str:
        """获取可扩展工作流配置"""
        try:
            config = app_state.config
            ext_config = config.get("extensible_workflows", {})
            return self._success(ext_config)
        except Exception as e:
            log(f"Failed to get extensible_workflows: {e}")
            return self._error(str(e), "GET_EXTENSIONS_ERROR")

    def get_running_apps(self) -> str:
        """获取当前正在运行的应用列表

        Returns:
            JSON 响应，包含应用列表 [{name, id, icon?}, ...]
        """
        try:
            apps = []

            if is_windows():
                apps = self._get_running_apps_windows()
            elif is_macos():
                apps = self._get_running_apps_macos()
            else:
                return self._error(
                    t("settings.extensions.unsupported_platform"),
                    "UNSUPPORTED_PLATFORM"
                )

            # 过滤保留应用
            filtered_apps = [
                app for app in apps
                if app.get("id", "").lower() not in RESERVED_APPS
            ]

            return self._success(filtered_apps)
        except Exception as e:
            log(f"Failed to get running apps: {e}")
            return self._error(str(e), "GET_APPS_ERROR")

    def _get_running_apps_windows(self) -> list:
        """获取 Windows 运行中的应用"""
        apps = []
        try:
            import ctypes
            from ctypes import wintypes

            # Windows API
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # 定义类型
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )

            seen_processes = set()

            def enum_windows_callback(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    # 获取窗口标题
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        title = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, title, length + 1)

                        # 获取进程 ID
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                        if pid.value not in seen_processes:
                            seen_processes.add(pid.value)

                            # 尝试获取进程路径
                            process_path = self._get_process_path_windows(pid.value)
                            if process_path:
                                # 提取应用名称
                                import os
                                app_name = os.path.splitext(os.path.basename(process_path))[0]

                                # 跳过系统进程
                                if app_name.lower() not in (
                                    "explorer", "searchhost", "shellexperiencehost",
                                    "startmenuexperiencehost", "textinputhost",
                                    "applicationframehost", "systemsettings"
                                ):
                                    apps.append({
                                        "name": app_name,
                                        "id": process_path.lower(),
                                        "title": title.value
                                    })
                return True

            user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

        except Exception as e:
            log(f"Windows get_running_apps error: {e}")
            # 如果失败，返回错误信息
            return self._error(
                t("settings.extensions.win32_import_error"),
                "WIN32_IMPORT_ERROR"
            )

        return apps

    def _get_process_path_windows(self, pid: int) -> str:
        """获取 Windows 进程路径"""
        try:
            import ctypes
            from ctypes import wintypes

            # 常量
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            MAX_PATH = 260

            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi

            # 打开进程
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                try:
                    # 获取进程路径
                    path = ctypes.create_unicode_buffer(MAX_PATH)
                    size = wintypes.DWORD(MAX_PATH)
                    if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                        return path.value
                finally:
                    kernel32.CloseHandle(handle)
        except Exception as e:
            log(f"Get process path error: {e}")
        return ""

    def _get_running_apps_macos(self) -> list:
        """获取 macOS 运行中的应用"""
        apps = []
        try:
            from AppKit import NSWorkspace

            workspace = NSWorkspace.sharedWorkspace()
            running_apps = workspace.runningApplications()

            for app in running_apps:
                # 只获取常规应用（不是后台服务）
                if app.activationPolicy() == 0:  # NSApplicationActivationPolicyRegular
                    bundle_id = app.bundleIdentifier()
                    if bundle_id:
                        apps.append({
                            "name": app.localizedName(),
                            "id": bundle_id,
                        })
        except Exception as e:
            log(f"macOS get_running_apps error: {e}")

        return apps

    # ==================== 配置保存 ====================
    def save_extensible_workflows(self, config_json: str) -> str:
        """保存可扩展工作流配置

        Args:
            config_json: JSON 格式的配置
        """
        try:
            new_ext_config = json.loads(config_json)

            # 获取当前配置
            config = copy.deepcopy(app_state.config)
            config["extensible_workflows"] = new_ext_config

            # 检查冲突
            conflicts = self.config_loader.check_workflow_conflicts(config)
            if conflicts:
                # 格式化冲突信息
                conflict_lines = []
                for app_name, workflows in conflicts.items():
                    workflow_names = ", ".join(workflows)
                    conflict_lines.append(f"  • {app_name}: {workflow_names}")
                conflict_text = "\n".join(conflict_lines)

                return self._error(
                    t("settings.extensions.config_conflict_warning", conflicts=conflict_text),
                    "CONFLICT_WARNING"
                )

            # 保存配置
            self.config_loader.save(config)
            app_state.config = config

            log("Extensible workflows saved")
            return self._success(message=t("settings.success.saved"))

        except json.JSONDecodeError as e:
            log(f"Failed to parse extensible workflows JSON: {e}")
            return self._error(str(e), "JSON_PARSE_ERROR")
        except Exception as e:
            log(f"Failed to save extensible workflows: {e}")
            return self._error(str(e), "SAVE_ERROR")

    # ==================== 验证 ====================
    def check_app_conflict(self, workflow_key: str, app_id: str) -> str:
        """检查应用是否在其他工作流中已配置

        Args:
            workflow_key: 当前工作流键名 (html, md, latex, file)
            app_id: 应用 ID

        Returns:
            JSON 响应，包含冲突的工作流名称（如果有）
        """
        try:
            ext_config = app_state.config.get("extensible_workflows", {})

            for key in ["html", "md", "latex", "file"]:
                if key == workflow_key:
                    continue

                cfg = ext_config.get(key, {})
                apps = cfg.get("apps", [])

                for app in apps:
                    if isinstance(app, dict):
                        if app.get("id", "").lower() == app_id.lower():
                            return self._success({
                                "has_conflict": True,
                                "conflict_workflow": key
                            })
                    elif str(app).lower() == app_id.lower():
                        return self._success({
                            "has_conflict": True,
                            "conflict_workflow": key
                        })

            return self._success({"has_conflict": False})

        except Exception as e:
            log(f"Failed to check app conflict: {e}")
            return self._error(str(e), "CHECK_CONFLICT_ERROR")

    def is_reserved_app(self, app_id: str) -> str:
        """检查应用是否为保留应用

        Args:
            app_id: 应用 ID

        Returns:
            JSON 响应，包含是否为保留应用
        """
        try:
            app_id_lower = app_id.lower()
            is_reserved = any(
                reserved in app_id_lower
                for reserved in RESERVED_APPS
            )
            return self._success({"is_reserved": is_reserved})
        except Exception as e:
            log(f"Failed to check reserved app: {e}")
            return self._error(str(e), "CHECK_RESERVED_ERROR")
