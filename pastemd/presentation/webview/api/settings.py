"""Settings page API for webview."""

from __future__ import annotations

import copy
import json
import os
import webview
from typing import Optional, TYPE_CHECKING

from .base import BaseApi
from .field_types import FieldType, SETTINGS_FIELD_MAP
from ....core.state import app_state
from ....config.defaults import DEFAULT_CONFIG
from ....i18n import t, iter_languages, get_no_app_action_map, set_language, get_all_translations
from ....utils.logging import log

if TYPE_CHECKING:
    from ....app.wiring import Container


class SettingsApi(BaseApi):
    """设置页面 Python API"""

    def __init__(self, container: "Container"):
        super().__init__(container)
        self.config_loader = container.config_loader
        self._on_save_callback = None
        self._on_close_callback = None

    def set_callbacks(
        self,
        on_save: Optional[callable] = None,
        on_close: Optional[callable] = None
    ) -> None:
        """设置保存和关闭回调"""
        self._on_save_callback = on_save
        self._on_close_callback = on_close

    # ==================== 配置读取 ====================
    def get_settings(self) -> str:
        """获取当前所有设置"""
        try:
            config = copy.deepcopy(app_state.config)

            # 获取热键
            config["hotkey"] = config.get("hotkey") or getattr(app_state, "hotkey_str", "<ctrl>+<shift>+b")

            # 确保 html_formatting 存在
            if "html_formatting" not in config:
                config["html_formatting"] = {}

            # 获取 pandoc_filters 列表
            filters = config.get("pandoc_filters") or []
            if isinstance(filters, str):
                filters = [filters]
            config["pandoc_filters"] = [f for f in filters if isinstance(f, str) and f.strip()]

            # 获取 pandoc_request_headers
            headers = config.get("pandoc_request_headers") or []
            if isinstance(headers, str):
                headers = [headers]
            config["pandoc_request_headers"] = [h for h in headers if isinstance(h, str) and h.strip()]

            return self._success(config)
        except Exception as e:
            log(f"Failed to get settings: {e}")
            return self._error(str(e), "GET_SETTINGS_ERROR")

    def get_languages(self) -> str:
        """获取可用语言列表"""
        try:
            languages = []
            for code, label in iter_languages():
                languages.append({"code": code, "label": label})
            return self._success(languages)
        except Exception as e:
            log(f"Failed to get languages: {e}")
            return self._error(str(e), "GET_LANGUAGES_ERROR")

    def get_no_app_actions(self) -> str:
        """获取无应用时动作选项"""
        try:
            action_map = get_no_app_action_map()
            actions = [{"value": k, "label": v} for k, v in action_map.items()]
            return self._success(actions)
        except Exception as e:
            log(f"Failed to get no_app_actions: {e}")
            return self._error(str(e), "GET_ACTIONS_ERROR")

    def get_theme_options(self) -> str:
        """获取主题选项列表"""
        try:
            options = [
                {"value": "auto", "label": t("settings.general.theme_auto")},
                {"value": "light", "label": t("settings.general.theme_light")},
                {"value": "dark", "label": t("settings.general.theme_dark")},
            ]
            return self._success(options)
        except Exception as e:
            log(f"Failed to get theme_options: {e}")
            return self._error(str(e), "GET_THEME_OPTIONS_ERROR")

    # ==================== 配置保存 ====================
    def _apply_field(self, config: dict, new_settings: dict, key: str) -> None:
        """应用单个字段到配置"""
        if key not in new_settings:
            return

        field_type = SETTINGS_FIELD_MAP.get(key)
        if not field_type:
            return

        value = new_settings[key]

        if field_type == FieldType.STRING:
            config[key] = value
        elif field_type == FieldType.BOOL:
            config[key] = bool(value)
        elif field_type == FieldType.NULLABLE_STRING:
            config[key] = value if value else None
        elif field_type == FieldType.STRING_LIST:
            if isinstance(value, str):
                value = [v.strip() for v in value.split("\n") if v.strip()]
            config[key] = value

    def _apply_all_fields(self, config: dict, new_settings: dict) -> None:
        """应用所有映射字段到配置"""
        for key in SETTINGS_FIELD_MAP:
            self._apply_field(config, new_settings, key)

    def save_settings(self, settings_json: str) -> str:
        """保存设置"""
        try:
            new_settings = json.loads(settings_json)

            # 合并到现有配置
            config = copy.deepcopy(app_state.config)

            # 检测语言是否改变（在更新config之前）
            language_changed = False
            if "language" in new_settings:
                old_language = config.get("language", "en-US")
                new_language = new_settings["language"]
                if old_language != new_language:
                    language_changed = True

            # 应用映射表中的字段（自动处理平台过滤）
            self._apply_all_fields(config, new_settings)

            # HTML 格式化 (嵌套结构，需单独处理)
            if "html_formatting" in new_settings:
                if "html_formatting" not in config:
                    config["html_formatting"] = {}
                if "strikethrough_to_del" in new_settings["html_formatting"]:
                    config["html_formatting"]["strikethrough_to_del"] = bool(
                        new_settings["html_formatting"]["strikethrough_to_del"]
                    )

            # 保存到文件
            self.config_loader.save(config)

            # 更新全局状态
            app_state.config = config

            # 更新语言
            if "language" in new_settings:
                set_language(new_settings["language"])

            # 调用保存回调
            if self._on_save_callback:
                try:
                    self._on_save_callback()
                except Exception as e:
                    log(f"Save callback error: {e}")

            # 如果语言改变，通知前端刷新翻译
            if language_changed and self._window:
                try:
                    self._window.evaluate_js("window.onLanguageChanged && window.onLanguageChanged()")
                except Exception as e:
                    log(f"Failed to notify frontend of language change: {e}")

            log("Settings saved successfully")
            return self._success(message=t("settings.success.saved"))
        except json.JSONDecodeError as e:
            log(f"Failed to parse settings JSON: {e}")
            return self._error(str(e), "JSON_PARSE_ERROR")
        except Exception as e:
            log(f"Failed to save settings: {e}")
            return self._error(str(e), "SAVE_ERROR")

    # ==================== 文件选择 ====================
    def browse_directory(self, initial_dir: str = "") -> str:
        """打开目录选择对话框"""
        try:
            if not self._window:
                return self._error("Window not available", "WINDOW_NOT_READY")

            if initial_dir:
                initial_dir = os.path.expandvars(initial_dir)

            # 使用新的 FileDialog API（兼容旧版本）
            dialog_type = getattr(webview, 'FOLDER_DIALOG', None)
            if hasattr(webview, 'FileDialog'):
                dialog_type = webview.FileDialog.FOLDER

            result = self._window.create_file_dialog(
                dialog_type,
                directory=initial_dir if initial_dir and os.path.isdir(initial_dir) else ""
            )

            if result and len(result) > 0:
                return self._success(result[0])
            return self._success(None, message="cancelled")
        except Exception as e:
            log(f"Failed to browse directory: {e}")
            return self._error(str(e), "BROWSE_ERROR")

    def browse_file(self, file_types: str = "", initial_dir: str = "") -> str:
        """打开文件选择对话框"""
        try:
            if not self._window:
                return self._error("Window not available", "WINDOW_NOT_READY")

            # 处理初始目录
            start_dir = ""
            if initial_dir:
                initial_dir = os.path.expandvars(initial_dir)
                # 如果是文件路径，取其父目录
                if os.path.isfile(initial_dir):
                    start_dir = os.path.dirname(initial_dir)
                elif os.path.isdir(initial_dir):
                    start_dir = initial_dir
                else:
                    # 尝试取父目录
                    parent = os.path.dirname(initial_dir)
                    if parent and os.path.isdir(parent):
                        start_dir = parent

            # 解析文件类型 - pywebview 期望格式: ('Description (*.ext)', 'Description2 (*.ext2)')
            file_types_tuple = ()
            if file_types:
                try:
                    types = json.loads(file_types)
                    # 构建 pywebview 期望的格式: "Name (*.ext)"
                    patterns = []
                    for ft in types:
                        name = ft.get("name", "Files")
                        pattern = ft.get("pattern", "*")
                        if pattern:
                            patterns.append(f"{name} ({pattern})")
                    if patterns:
                        file_types_tuple = tuple(patterns)
                except (json.JSONDecodeError, TypeError):
                    pass

            # 使用新的 FileDialog API（兼容旧版本）
            dialog_type = getattr(webview, 'OPEN_DIALOG', None)
            if hasattr(webview, 'FileDialog'):
                dialog_type = webview.FileDialog.OPEN

            result = self._window.create_file_dialog(
                dialog_type,
                directory=start_dir,
                file_types=file_types_tuple
            )

            if result and len(result) > 0:
                return self._success(result[0])
            return self._success(None, message="cancelled")
        except Exception as e:
            log(f"Failed to browse file: {e}")
            return self._error(str(e), "BROWSE_ERROR")

    # ==================== 工具方法 ====================
    def get_default_config(self) -> str:
        """获取默认配置"""
        try:
            return self._success(copy.deepcopy(DEFAULT_CONFIG))
        except Exception as e:
            log(f"Failed to get default config: {e}")
            return self._error(str(e), "GET_DEFAULT_ERROR")

    def expand_path(self, path: str) -> str:
        """展开环境变量"""
        try:
            expanded = os.path.expandvars(path)
            return self._success(expanded)
        except Exception as e:
            log(f"Failed to expand path: {e}")
            return self._error(str(e), "EXPAND_PATH_ERROR")

    def get_translations(self) -> str:
        """获取当前语言的完整翻译文本"""
        try:
            return self._success(get_all_translations())
        except Exception as e:
            log(f"Failed to get translations: {e}")
            return self._error(str(e), "GET_TRANSLATIONS_ERROR")

    # ==================== 窗口控制 ====================
    def close_window(self) -> str:
        """关闭设置窗口 (隐藏而非销毁)"""
        try:
            if self._on_close_callback:
                try:
                    self._on_close_callback()
                except Exception as e:
                    log(f"Close callback error: {e}")

            if self._window:
                self._window.hide()

            return self._success(message="window hidden")
        except Exception as e:
            log(f"Failed to close window: {e}")
            return self._error(str(e), "CLOSE_ERROR")

    def minimize_window(self) -> str:
        """最小化窗口"""
        try:
            if self._window:
                self._window.minimize()
            return self._success(message="window minimized")
        except Exception as e:
            log(f"Failed to minimize window: {e}")
            return self._error(str(e), "MINIMIZE_ERROR")
