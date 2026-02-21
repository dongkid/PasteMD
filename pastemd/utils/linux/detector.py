# -*- coding: utf-8 -*-
"""Linux application detection utilities."""

from __future__ import annotations

import re
import shutil
import subprocess

from ..logging import log


AppDetect = str


def _run(args: list[str], timeout_s: float = 1.0) -> str:
    try:
        proc = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            return ""
        return (proc.stdout or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _get_active_window_id() -> str:
    """获取当前活动窗口 ID（十六进制，形如 0x03a00007）。"""
    if not shutil.which("xprop"):
        return ""

    output = _run(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
    if not output:
        return ""

    match = re.search(r"(0x[0-9a-fA-F]+)", output)
    if not match:
        return ""

    wid = match.group(1).lower()
    if wid == "0x0":
        return ""
    return wid


def get_frontmost_window_title() -> str:
    """获取当前前台窗口标题。"""
    # 方法1：xdotool 直接拿活动窗口标题
    if shutil.which("xdotool"):
        title = _run(["xdotool", "getactivewindow", "getwindowname"])
        if title:
            return title

    # 方法2：wmctrl + xprop 定位活动窗口标题
    if shutil.which("wmctrl"):
        active_id = _get_active_window_id()
        lines = _run(["wmctrl", "-l"]).splitlines()

        if active_id:
            for line in lines:
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                window_id = parts[0].lower()
                if window_id == active_id:
                    return parts[3].strip()

        # 兜底：返回第一个非空标题窗口
        for line in lines:
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            title = parts[3].strip()
            if title:
                return title

    return ""


def detect_wps_type() -> str:
    """检测 WPS 类型（文字/表格）。"""
    title = get_frontmost_window_title().lower()
    if not title:
        return "wps"

    excel_signals = [
        ".xls",
        ".xlsx",
        ".csv",
        "wps 表格",
        "wps spreadsheets",
        "工作簿",
        "sheet",
        "spreadsheet",
    ]
    for signal in excel_signals:
        if signal in title:
            return "wps_excel"

    return "wps"


def _detect_from_window_title(window_name: str) -> AppDetect:
    name = (window_name or "").lower()
    if not name:
        return ""

    # Microsoft Office family
    if "word" in name:
        return "word"
    if "excel" in name:
        return "excel"
    if "onenote" in name:
        return "onenote"
    if "powerpoint" in name or "powerpnt" in name:
        return "powerpoint"

    # WPS family
    if "wps" in name or "kingsoft" in name:
        return detect_wps_type()

    # 回退：返回窗口标题本身，供可扩展工作流匹配
    return name


def detect_active_app() -> AppDetect:
    """检测当前活跃应用。"""
    window_name = get_frontmost_window_title()
    if not window_name:
        return ""

    app = _detect_from_window_title(window_name)
    log(f"Linux active window: {window_name} -> {app}")
    return app
