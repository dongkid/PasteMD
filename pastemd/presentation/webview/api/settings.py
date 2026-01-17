"""Settings page API for webview."""

from __future__ import annotations

import copy
import json
import os
import webview
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .base import BaseApi
from ....core.state import app_state
from ....config.loader import ConfigLoader
from ....config.defaults import DEFAULT_CONFIG
from ....i18n import t, iter_languages, get_language_label, get_no_app_action_map, set_language
from ....utils.logging import log
from ....utils.system_detect import is_windows, is_macos

if TYPE_CHECKING:
    from ....app.wiring import Container


class SettingsApi(BaseApi):
    """设置页面 Python API"""

    def __init__(self, container: "Container"):
        super().__init__(container)
        self.config_loader = ConfigLoader()
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

    # ==================== 配置保存 ====================
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

            # 更新各项配置
            if "language" in new_settings:
                config["language"] = new_settings["language"]
            if "save_dir" in new_settings:
                config["save_dir"] = new_settings["save_dir"]
            if "keep_file" in new_settings:
                config["keep_file"] = bool(new_settings["keep_file"])
            if "notify" in new_settings:
                config["notify"] = bool(new_settings["notify"])
            if "startup_notify" in new_settings:
                config["startup_notify"] = bool(new_settings["startup_notify"])
            if "no_app_action" in new_settings:
                config["no_app_action"] = new_settings["no_app_action"]

            # Windows 特有选项
            if is_windows() and "move_cursor_to_end" in new_settings:
                config["move_cursor_to_end"] = bool(new_settings["move_cursor_to_end"])

            # 转换设置
            if "pandoc_path" in new_settings:
                config["pandoc_path"] = new_settings["pandoc_path"]
            if "reference_docx" in new_settings:
                ref = new_settings["reference_docx"]
                config["reference_docx"] = ref if ref else None

            # HTML 格式化
            if "html_formatting" in new_settings:
                if "html_formatting" not in config:
                    config["html_formatting"] = {}
                if "strikethrough_to_del" in new_settings["html_formatting"]:
                    config["html_formatting"]["strikethrough_to_del"] = bool(
                        new_settings["html_formatting"]["strikethrough_to_del"]
                    )

            # 其他转换选项
            if "md_disable_first_para_indent" in new_settings:
                config["md_disable_first_para_indent"] = bool(new_settings["md_disable_first_para_indent"])
            if "html_disable_first_para_indent" in new_settings:
                config["html_disable_first_para_indent"] = bool(new_settings["html_disable_first_para_indent"])
            if "Keep_original_formula" in new_settings:
                config["Keep_original_formula"] = bool(new_settings["Keep_original_formula"])
            if "enable_latex_replacements" in new_settings:
                config["enable_latex_replacements"] = bool(new_settings["enable_latex_replacements"])
            if "fix_single_dollar_block" in new_settings:
                config["fix_single_dollar_block"] = bool(new_settings["fix_single_dollar_block"])

            # Pandoc request headers
            if "pandoc_request_headers" in new_settings:
                headers = new_settings["pandoc_request_headers"]
                if isinstance(headers, str):
                    headers = [h.strip() for h in headers.split("\n") if h.strip()]
                config["pandoc_request_headers"] = headers

            # Pandoc filters
            if "pandoc_filters" in new_settings:
                config["pandoc_filters"] = new_settings["pandoc_filters"]

            # Excel 选项
            if "enable_excel" in new_settings:
                config["enable_excel"] = bool(new_settings["enable_excel"])
            if "excel_keep_format" in new_settings:
                config["excel_keep_format"] = bool(new_settings["excel_keep_format"])

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
            if initial_dir:
                initial_dir = os.path.expandvars(initial_dir)

            result = self._window.create_file_dialog(
                webview.FOLDER_DIALOG,
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
            if initial_dir:
                initial_dir = os.path.expandvars(initial_dir)

            # 解析文件类型
            file_types_list = []
            if file_types:
                try:
                    types = json.loads(file_types)
                    for ft in types:
                        file_types_list.append((ft.get("name", "Files"), ft.get("pattern", "*")))
                except (json.JSONDecodeError, TypeError):
                    pass

            if not file_types_list:
                file_types_list = [("All Files", "*")]

            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=initial_dir if initial_dir and os.path.isdir(os.path.dirname(initial_dir)) else "",
                file_types=tuple(file_types_list)
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
        """获取当前语言的常用翻译文本"""
        try:
            # 返回常用的翻译键
            translations = {
                # 设置对话框
                "settings.dialog.title": t("settings.dialog.title"),
                "settings.buttons.save": t("settings.buttons.save"),
                "settings.buttons.cancel": t("settings.buttons.cancel"),

                # 选项卡
                "settings.tab.general": t("settings.tab.general"),
                "settings.tab.conversion": t("settings.tab.conversion"),
                "settings.tab.advanced": t("settings.tab.advanced"),
                "settings.tab.experimental": t("settings.tab.experimental"),
                "settings.tab.permissions": t("settings.tab.permissions"),

                # 常规设置
                "settings.general.save_dir": t("settings.general.save_dir"),
                "settings.general.browse": t("settings.general.browse"),
                "settings.general.restore_default": t("settings.general.restore_default"),
                "settings.general.no_app_action": t("settings.general.no_app_action"),
                "settings.general.keep_file": t("settings.general.keep_file"),
                "settings.general.notify": t("settings.general.notify"),
                "settings.general.startup_notify": t("settings.general.startup_notify"),
                "settings.general.move_cursor": t("settings.general.move_cursor"),
                "settings.general.hotkey": t("settings.general.hotkey"),
                "settings.general.set_hotkey": t("settings.general.set_hotkey"),
                "settings.general.language": t("settings.general.language"),

                # 转换设置
                "settings.conversion.pandoc_path": t("settings.conversion.pandoc_path"),
                "settings.conversion.reference_docx": t("settings.conversion.reference_docx"),
                "settings.general.clear": t("settings.general.clear"),
                "settings.conversion.pandoc_filters": t("settings.conversion.pandoc_filters"),
                "settings.conversion.add_filter": t("settings.conversion.add_filter"),
                "settings.conversion.remove_filter": t("settings.conversion.remove_filter"),
                "settings.conversion.move_up": t("settings.conversion.move_up"),
                "settings.conversion.move_down": t("settings.conversion.move_down"),
                "settings.conversion.pandoc_filters_note": t("settings.conversion.pandoc_filters_note"),
                "settings.conversion.html_formatting": t("settings.conversion.html_formatting"),
                "settings.conversion.strikethrough": t("settings.conversion.strikethrough"),
                "settings.conversion.first_paragraph_heading": t("settings.conversion.first_paragraph_heading"),
                "settings.conversion.md_indent": t("settings.conversion.md_indent"),
                "settings.conversion.html_indent": t("settings.conversion.html_indent"),

                # 高级设置
                "settings.advanced.excel_enable": t("settings.advanced.excel_enable"),
                "settings.advanced.excel_format": t("settings.advanced.excel_format"),

                # 实验性功能
                "settings.conversion.keep_formula": t("settings.conversion.keep_formula"),
                "settings.conversion.enable_latex_replacements": t("settings.conversion.enable_latex_replacements"),
                "settings.conversion.latex_replacements_note": t("settings.conversion.latex_replacements_note"),
                "settings.conversion.fix_single_dollar_block": t("settings.conversion.fix_single_dollar_block"),
                "settings.conversion.fix_single_dollar_block_note": t("settings.conversion.fix_single_dollar_block_note"),
                "settings.conversion.pandoc_request_headers": t("settings.conversion.pandoc_request_headers"),
                "settings.conversion.pandoc_request_headers_enable": t("settings.conversion.pandoc_request_headers_enable"),
                "settings.conversion.pandoc_request_headers_note": t("settings.conversion.pandoc_request_headers_note"),
                "settings.conversion.pandoc_request_headers_fill_example": t("settings.conversion.pandoc_request_headers_fill_example"),

                # 消息
                "settings.success.saved": t("settings.success.saved"),
                "settings.title.success": t("settings.title.success"),
                "settings.title.error": t("settings.title.error"),

                # 热键对话框
                "hotkey.dialog.title": t("hotkey.dialog.title"),
                "hotkey.dialog.current_hotkey": t("hotkey.dialog.current_hotkey"),
                "hotkey.dialog.new_hotkey": t("hotkey.dialog.new_hotkey"),
                "hotkey.dialog.record_button": t("hotkey.dialog.record_button"),
                "hotkey.dialog.recording_button": t("hotkey.dialog.recording_button"),
                "hotkey.dialog.record_again": t("hotkey.dialog.record_again"),
                "hotkey.dialog.waiting_input": t("hotkey.dialog.waiting_input"),
                "hotkey.dialog.cancel_button": t("hotkey.dialog.cancel_button"),
                "hotkey.dialog.save_button": t("hotkey.dialog.save_button"),
                "hotkey.dialog.instruction": t("hotkey.dialog.instruction"),
                "hotkey.dialog.input_placeholder": t("hotkey.dialog.input_placeholder"),

                # 权限相关
                "settings.permissions.intro": t("settings.permissions.intro"),
                "settings.permissions.add_hint": t("settings.permissions.add_hint"),
                "settings.permissions.refresh": t("settings.permissions.refresh"),
                "settings.permissions.last_checked": t("settings.permissions.last_checked"),
                "settings.permissions.open_settings": t("settings.permissions.open_settings"),
                "settings.permissions.request_access": t("settings.permissions.request_access"),
                "settings.permissions.status.checking": t("settings.permissions.status.checking"),
                "settings.permissions.accessibility.title": t("settings.permissions.accessibility.title"),
                "settings.permissions.accessibility.desc": t("settings.permissions.accessibility.desc"),
                "settings.permissions.screen_recording.title": t("settings.permissions.screen_recording.title"),
                "settings.permissions.screen_recording.desc": t("settings.permissions.screen_recording.desc"),
                "settings.permissions.input_monitoring.title": t("settings.permissions.input_monitoring.title"),
                "settings.permissions.input_monitoring.desc": t("settings.permissions.input_monitoring.desc"),
                "settings.permissions.automation.title": t("settings.permissions.automation.title"),
                "settings.permissions.automation.desc": t("settings.permissions.automation.desc"),

                # 错误和成功消息
                "settings.error.init_failed": t("settings.error.init_failed"),
                "settings.error.load_failed": t("settings.error.load_failed"),
                "settings.error.save_failed": t("settings.error.save_failed"),
                "settings.error.hotkey_save_failed": t("settings.error.hotkey_save_failed"),
                "settings.error.hotkey_not_recorded": t("settings.error.hotkey_not_recorded"),
                "settings.success.hotkey_saved": t("settings.success.hotkey_saved"),

                # 其他UI文本
                "settings.general.options": t("settings.general.options"),
                "settings.advanced.excel_options": t("settings.advanced.excel_options"),
                "settings.experimental.formula_processing": t("settings.experimental.formula_processing"),
                "settings.conversion.reference_docx_placeholder": t("settings.conversion.reference_docx_placeholder"),
                "settings.conversion.pandoc_request_headers_placeholder": t("settings.conversion.pandoc_request_headers_placeholder"),
            }

            return self._success(translations)
        except Exception as e:
            log(f"Failed to get translations: {e}")
            return self._error(str(e), "GET_TRANSLATIONS_ERROR")

    def get_platform(self) -> str:
        """获取当前平台信息"""
        try:
            return self._success({
                "is_windows": is_windows(),
                "is_macos": is_macos(),
            })
        except Exception as e:
            log(f"Failed to get platform: {e}")
            return self._error(str(e), "GET_PLATFORM_ERROR")

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
