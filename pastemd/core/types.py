"""Common type aliases and protocols."""

from enum import Enum
from typing import Protocol, Any, Dict, Callable, Literal, Optional
from abc import abstractmethod


PlacementMethod = Literal[
    # 原生 API 方式
    "com",                   # Windows COM 接口
    "applescript",           # macOS AppleScript
    "clipboard_bridge",      # 剪贴板桥接（保留兼容）
    # 剪贴板方式
    "clipboard_rtf_html",    # RTF/HTML 富文本（macOS WPS）
    "clipboard_file",        # 文件粘贴
    "clipboard_rich_text",   # 富文本粘贴
    "clipboard_plain_text",  # 纯文本粘贴
    "clipboard_html_table",  # HTML 表格粘贴
    "clipboard_tsv",         # TSV 粘贴
]


class PlacementResult:
    """内容落地结果"""
    
    def __init__(
        self, 
        success: bool, 
        method: Optional[PlacementMethod] = None,
        error: Optional[str] = None, 
        metadata: Optional[dict] = None
    ):
        self.success = success
        self.method = method
        self.error = error
        self.metadata = metadata or {}


class NoAppAction(str, Enum):
    """无应用检测时的动作类型"""
    OPEN = "open"
    SAVE = "save"
    CLIPBOARD = "clipboard"
    NONE = "none"


ConfigDict = Dict[str, Any]
InsertTarget = Literal["auto", "word", "wps", "none"]


class Notifier(Protocol):
    """通知器协议"""
    
    @abstractmethod
    def notify(self, title: str, message: str, ok: bool = True) -> None:
        """发送通知"""
        pass


class Inserter(Protocol):
    """文档插入器协议"""
    
    @abstractmethod
    def insert(self, docx_path: str) -> bool:
        """插入文档到目标应用"""
        pass


class ConfigLoader(Protocol):
    """配置加载器协议"""
    
    @abstractmethod
    def load(self) -> ConfigDict:
        """加载配置"""
        pass
    
    @abstractmethod
    def save(self, config: ConfigDict) -> None:
        """保存配置"""
        pass


HotkeyCallback = Callable[[], None]
