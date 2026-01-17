"""Base API class for webview JavaScript bridge."""

from __future__ import annotations

import json
from typing import Any, Optional, TYPE_CHECKING

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
