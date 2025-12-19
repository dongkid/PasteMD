"""Cross-platform clipboard operations.

This module provides a unified interface for clipboard operations across different platforms.
It automatically detects the operating system and imports the appropriate implementation.
"""

import sys
from ..core.errors import ClipboardError


# 根据操作系统导入对应的实现
if sys.platform == "darwin":
    from .macos.clipboard import (
        get_clipboard_text,
        is_clipboard_empty,
        is_clipboard_html,
        get_clipboard_html,
    )
elif sys.platform == "win32":
    from .win32.clipboard import (
        get_clipboard_text,
        is_clipboard_empty,
        is_clipboard_html,
        get_clipboard_html,
    )
else:
    # 其他平台的后备实现（仅支持基本文本功能）
    import pyperclip
    
    def get_clipboard_text() -> str:
        """
        获取剪贴板文本内容
        
        Returns:
            剪贴板文本内容
            
        Raises:
            ClipboardError: 剪贴板操作失败时
        """
        try:
            text = pyperclip.paste()
            if text is None:
                return ""
            return text
        except Exception as e:
            raise ClipboardError(f"Failed to read clipboard: {e}")
    
    def is_clipboard_empty() -> bool:
        """
        检查剪贴板是否为空
        
        Returns:
            True 如果剪贴板为空或只包含空白字符
        """
        try:
            text = get_clipboard_text()
            return not text or not text.strip()
        except ClipboardError:
            return True
    
    def is_clipboard_html() -> bool:
        """
        检查剪切板内容是否为 HTML 富文本
        
        Note:
            在不支持的平台上始终返回 False
        
        Returns:
            False (不支持的平台)
        """
        return False
    
    def get_clipboard_html(config: dict | None = None) -> str:
        """
        获取剪贴板 HTML 富文本内容
        
        Note:
            在不支持的平台上会抛出异常
        
        Raises:
            ClipboardError: 不支持的平台
        """
        raise ClipboardError(f"HTML clipboard operations not supported on {sys.platform}")


# 导出公共接口
__all__ = [
    "get_clipboard_text",
    "is_clipboard_empty", 
    "is_clipboard_html",
    "get_clipboard_html",
    "ClipboardError",
]


