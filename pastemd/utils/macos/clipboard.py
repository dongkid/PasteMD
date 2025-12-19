"""macOS clipboard operations using AppKit.NSPasteboard."""

import pyperclip
from AppKit import NSPasteboard, NSPasteboardTypeHTML, NSPasteboardTypeString
from ...core.errors import ClipboardError
from ...core.state import app_state
from ..html_formatter import clean_html_content


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

    Returns:
        True 如果剪贴板中存在 HTML 富文本格式；否则 False
    """
    try:
        pasteboard = NSPasteboard.generalPasteboard()
        # 检查是否存在 HTML 类型
        types = pasteboard.types()
        if types is None:
            return False
        
        # macOS 使用 NSPasteboardTypeHTML (public.html)
        return NSPasteboardTypeHTML in types
    except Exception:
        return False


def get_clipboard_html(config: dict | None = None) -> str:
    """
    获取剪贴板 HTML 富文本内容，并清理 SVG 等不可用内容
    
    Returns:
        清理后的 HTML 富文本内容

    Raises:
        ClipboardError: 剪贴板操作失败时
    """
    try:
        config = config or getattr(app_state, "config", {})
        
        pasteboard = NSPasteboard.generalPasteboard()
        
        # 尝试获取 HTML 数据
        html_data = pasteboard.stringForType_(NSPasteboardTypeHTML)
        
        if html_data is None:
            raise ClipboardError("No HTML format data in clipboard")
        
        # macOS 返回的已经是 HTML 内容字符串，不需要像 Windows 那样解析 CF_HTML 格式
        html_content = str(html_data)
        
        # 清理 SVG 等不可用内容
        cleaned = clean_html_content(html_content, config.get("html_formatting"))
        
        return cleaned
        
    except Exception as e:
        raise ClipboardError(f"Failed to read HTML from clipboard: {e}")
