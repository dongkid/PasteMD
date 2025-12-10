"""Default configuration values."""

import os
import sys
from typing import Dict, Any


# 检测打包的 Pandoc 路径
_bundled_pandoc = os.path.join(os.path.dirname(sys.executable), "pandoc", "pandoc.exe")

# 统一的默认配置
DEFAULT_CONFIG: Dict[str, Any] = {
    "hotkey": "<ctrl>+b",
    "pandoc_path": _bundled_pandoc if os.path.exists(_bundled_pandoc) else "pandoc",
    "reference_docx": None,  # 可选：Pandoc 参考模板；不需要就设为 None
    "save_dir": r"%USERPROFILE%\Documents\pastemd",
    "keep_file": False,
    "notify": True,
    "enable_excel": True,  # 是否启用智能识别 Markdown 表格并粘贴到 Excel
    "excel_keep_format": True,  # Excel 粘贴时是否保留格式（粗体、斜体等）
    "no_app_action": "open",  # 无应用检测时的动作：open=自动打开, save=仅保存, clipboard=复制到剪贴板, none=无操作
    "md_disable_first_para_indent": True,  # Markdown 转换时是否禁用标题后第一段的特殊格式
    "html_disable_first_para_indent": True,  # HTML 转换时是否禁用标题后第一段的特殊格式
    "html_formatting": {
        "strikethrough_to_del": True,
    },
    "move_cursor_to_end": True,  # 插入后光标移动到插入内容的末尾
    "Keep_original_formula": False,  # 是否保留原始数学公式,不进行转换
    "language": "zh",  # UI 语言（默认简体中文）
}