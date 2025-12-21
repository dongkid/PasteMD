"""Default configuration values."""

import os
import sys
from typing import Dict, Any
from .paths import resource_path


def find_pandoc() -> str:
    """
    查找 pandoc 路径，兼容：
    - PyInstaller 单文件（exe 同级 pandoc）
    - PyInstaller 非单文件
    - Nuitka 单文件 / 非单文件
    - Inno 安装
    - 源码运行（系统 pandoc）
    """
    # exe 同级 pandoc
    exe_dir = os.path.dirname(sys.executable)
    candidate = os.path.join(exe_dir, "pandoc", "pandoc.exe")
    if os.path.exists(candidate):
        return candidate

    # 打包资源路径（Nuitka / PyInstaller onedir / 新方案）
    candidate = resource_path("pandoc/pandoc.exe")
    if os.path.exists(candidate):
        return candidate

    # 兜底：系统 pandoc
    return "pandoc"


DEFAULT_CONFIG: Dict[str, Any] = {
    "hotkey": "<ctrl>+<shift>+b",
    "pandoc_path": find_pandoc(),
    "reference_docx": None,
    "save_dir": os.path.expandvars(r"%USERPROFILE%\Documents\pastemd"),
    "keep_file": False,
    "notify": True,
    "enable_excel": True,
    "excel_keep_format": True,
    "no_app_action": "open",  # 无应用检测时的动作：open=自动打开, save=仅保存, clipboard=复制到剪贴板, none=无操作
    "md_disable_first_para_indent": True,
    "html_disable_first_para_indent": True,
    "html_formatting": {
        "strikethrough_to_del": True,
    },
    "move_cursor_to_end": True,
    "Keep_original_formula": False,
    "language": "zh",
    "enable_latex_replacements": True,
    "fix_single_dollar_block": True,
    "pandoc_filters": [],
}
