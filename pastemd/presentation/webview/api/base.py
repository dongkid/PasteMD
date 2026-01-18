"""Base API class for webview JavaScript bridge."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from ....core.state import app_state
from ....utils.system_detect import is_windows, is_macos

if TYPE_CHECKING:
    from ....app.wiring import Container


class BaseApi:
    """
    webview JavaScript API 基类

    所有公开方法会自动暴露给 JavaScript:
    - 方法名: pywebview.api.method_name()
    - 返回值: 自动序列化为 JSON 字符串
    """

    def __init__(self, container: "Container"):
        self._container = container
        self._window = None

    def set_window(self, window) -> None:
        """设置关联的 webview 窗口"""
        self._window = window

    def process_ui_queue(self) -> str:
        """
        处理 UI 任务队列 (由前端 JS 定时调用)

        此方法在 WebView 的 GUI 线程中执行，确保所有队列中的
        evaluate_js() 等 GUI 操作都在正确的线程上下文中运行。

        Returns:
            JSON 响应，包含处理的任务数量
        """
        try:
            count = app_state.process_ui_queue()
            return self._success({"processed": count})
        except Exception as e:
            return self._error(str(e), "QUEUE_PROCESS_ERROR")

    def _success(self, data: Any = None, message: str = "") -> str:
        """返回成功响应"""
        return json.dumps({
            "success": True,
            "data": data,
            "message": message
        }, ensure_ascii=False)

    def _error(self, message: str, code: str = "ERROR") -> str:
        """返回错误响应"""
        return json.dumps({
            "success": False,
            "error": {
                "code": code,
                "message": message
            }
        }, ensure_ascii=False)

    def get_platform(self) -> str:
        """获取当前平台信息"""
        if is_macos():
            platform = "macos"
        elif is_windows():
            platform = "windows"
        else:
            platform = "linux"

        return self._success({
            "platform": platform,
            "is_windows": is_windows(),
            "is_macos": is_macos(),
            "is_linux": platform == "linux",
        })
