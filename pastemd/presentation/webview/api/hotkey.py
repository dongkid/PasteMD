"""Hotkey recording API for webview."""

from __future__ import annotations

import json
import threading
from typing import Optional, Set, TYPE_CHECKING

from .base import BaseApi
from ....core.state import app_state
from ....config.loader import ConfigLoader
from ....utils.logging import log
from ....utils.system_detect import is_windows, is_macos
from ....utils.hotkey_checker import HotkeyChecker
from ....i18n import t

if TYPE_CHECKING:
    from ....app.wiring import Container


class HotkeyApi(BaseApi):
    """热键录制 Python API"""

    def __init__(self, container: "Container"):
        super().__init__(container)
        self.config_loader = ConfigLoader()
        self._is_recording = False
        self._recorder = None
        self._pressed_keys: Set[str] = set()
        self._on_hotkey_saved_callback = None

    def set_hotkey_saved_callback(self, callback: Optional[callable]) -> None:
        """设置热键保存后的回调"""
        self._on_hotkey_saved_callback = callback

    # ==================== 热键信息 ====================
    def get_current_hotkey(self) -> str:
        """获取当前热键"""
        try:
            hotkey = app_state.config.get("hotkey") or getattr(app_state, "hotkey_str", "<ctrl>+<shift>+b")
            formatted = self._format_hotkey(hotkey)
            return self._success({
                "raw": hotkey,
                "formatted": formatted
            })
        except Exception as e:
            log(f"Failed to get current hotkey: {e}")
            return self._error(str(e), "GET_HOTKEY_ERROR")

    def _format_hotkey(self, hotkey: str) -> str:
        """格式化热键显示"""
        return hotkey.replace("<", "").replace(">", "").replace("+", " + ").title()

    # ==================== 热键录制 (Windows) ====================
    def start_recording_windows(self) -> str:
        """开始热键录制 (Windows 平台, 使用 pynput)"""
        if is_macos():
            return self._error("Use JavaScript recording on macOS", "PLATFORM_ERROR")

        try:
            if self._is_recording:
                return self._error("Already recording", "ALREADY_RECORDING")

            from ....service.hotkey.recorder import HotkeyRecorder

            self._is_recording = True
            self._pressed_keys.clear()
            self._recorder = HotkeyRecorder()

            def on_update(display_text: str):
                # 通过 evaluate_js 发送更新到前端
                if self._window:
                    try:
                        self._window.evaluate_js(f"window.onHotkeyUpdate('{display_text}')")
                    except Exception as e:
                        log(f"Failed to send hotkey update: {e}")

            def on_finish(hotkey_str: Optional[str], error: Optional[str]):
                self._is_recording = False
                if self._window:
                    try:
                        result = json.dumps({
                            "hotkey": hotkey_str,
                            "error": error
                        }, ensure_ascii=False)
                        self._window.evaluate_js(f"window.onHotkeyFinish({result})")
                    except Exception as e:
                        log(f"Failed to send hotkey finish: {e}")

            self._recorder.start_recording(on_update=on_update, on_finish=on_finish)
            return self._success(message="recording started")

        except Exception as e:
            self._is_recording = False
            log(f"Failed to start recording: {e}")
            return self._error(str(e), "START_RECORDING_ERROR")

    def stop_recording_windows(self) -> str:
        """停止热键录制 (Windows)"""
        try:
            if self._recorder:
                self._recorder.stop_recording()
                self._recorder = None
            self._is_recording = False
            return self._success(message="recording stopped")
        except Exception as e:
            log(f"Failed to stop recording: {e}")
            return self._error(str(e), "STOP_RECORDING_ERROR")

    # ==================== 热键验证 (跨平台) ====================
    def validate_hotkey(self, keys_json: str) -> str:
        """
        验证热键组合

        Args:
            keys_json: JSON 数组，包含按下的键名 (如 ["ctrl", "shift", "b"])

        Returns:
            成功时返回热键字符串，失败时返回错误信息
        """
        try:
            keys = set(json.loads(keys_json))

            if not keys:
                return self._error(t("hotkey.recorder.error.no_key_detected"), "NO_KEYS")

            # 生成热键预览用于验证
            hotkey_preview = " + ".join(k.title() for k in ["ctrl", "shift", "alt", "cmd"] if k in keys)
            normal_keys = [k for k in keys if k not in ["ctrl", "shift", "alt", "cmd"]]
            if normal_keys:
                if hotkey_preview:
                    hotkey_preview += " + "
                hotkey_preview += " + ".join(k.title() for k in normal_keys)

            # 验证热键
            error = HotkeyChecker.validate_hotkey_keys(
                keys,
                hotkey_repr=hotkey_preview.replace(" + ", "+"),
                detailed=True
            )

            if error:
                return self._error(error, "INVALID_HOTKEY")

            # 构建热键字符串
            modifier_order = ["ctrl", "shift", "alt", "cmd"]
            modifiers = [f"<{m}>" for m in modifier_order if m in keys]
            normal = sorted(k for k in keys if k not in modifier_order)
            wrapped = [f"<{k}>" if len(k) > 1 else k for k in normal]
            hotkey_str = "+".join(modifiers + wrapped)

            return self._success({
                "hotkey": hotkey_str,
                "formatted": self._format_hotkey(hotkey_str)
            })

        except json.JSONDecodeError as e:
            log(f"Failed to parse keys JSON: {e}")
            return self._error(str(e), "JSON_PARSE_ERROR")
        except Exception as e:
            log(f"Failed to validate hotkey: {e}")
            return self._error(str(e), "VALIDATE_ERROR")

    def check_hotkey_conflict(self, hotkey_str: str) -> str:
        """检查热键是否与其他程序冲突"""
        try:
            is_available = HotkeyChecker.is_hotkey_available(hotkey_str)
            return self._success({
                "is_available": is_available,
                "hotkey": hotkey_str
            })
        except Exception as e:
            log(f"Failed to check hotkey conflict: {e}")
            return self._error(str(e), "CHECK_CONFLICT_ERROR")

    # ==================== 热键保存 ====================
    def save_hotkey(self, hotkey_str: str) -> str:
        """保存新热键"""
        try:
            if not hotkey_str:
                return self._error("Hotkey is empty", "EMPTY_HOTKEY")

            # 更新配置
            app_state.config["hotkey"] = hotkey_str
            app_state.hotkey_str = hotkey_str
            self.config_loader.save(app_state.config)

            # 调用保存回调 (重启热键绑定)
            if self._on_hotkey_saved_callback:
                try:
                    self._on_hotkey_saved_callback()
                except Exception as e:
                    log(f"Hotkey saved callback error: {e}")

            log(f"Hotkey changed to: {hotkey_str}")
            return self._success({
                "hotkey": hotkey_str,
                "formatted": self._format_hotkey(hotkey_str)
            }, message=t("tray.status.hotkey_saved", hotkey=self._format_hotkey(hotkey_str)))

        except Exception as e:
            log(f"Failed to save hotkey: {e}")
            return self._error(str(e), "SAVE_HOTKEY_ERROR")

    def get_platform(self) -> str:
        """获取当前平台"""
        try:
            platform = "macos" if is_macos() else "windows" if is_windows() else "linux"
            return self._success({"platform": platform})
        except Exception as e:
            log(f"Failed to get platform: {e}")
            return self._error(str(e), "GET_PLATFORM_ERROR")
