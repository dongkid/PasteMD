"""Windows 11 Mica effect utilities.

This module provides functions to apply Windows 11 Mica backdrop effect
to application windows using DWM (Desktop Window Manager) APIs.
"""

from __future__ import annotations

import ctypes
from typing import Optional

from ..logging import log
from .win32_types import (
    # DWM 窗口属性常量
    DWMWA_USE_IMMERSIVE_DARK_MODE,
    DWMWA_SYSTEMBACKDROP_TYPE,
    DWMWA_MICA_EFFECT,
    DWMWA_WINDOW_CORNER_PREFERENCE,
    # 系统背景类型
    DWMSBT_AUTO,
    DWMSBT_NONE,
    DWMSBT_MAINWINDOW,
    DWMSBT_TRANSIENTWINDOW,
    DWMSBT_TABBEDWINDOW,
    # 窗口圆角类型
    DWMWCP_DEFAULT,
    DWMWCP_DONOTROUND,
    DWMWCP_ROUND,
    DWMWCP_ROUNDSMALL,
    # SetWindowPos 标志
    SWP_NOMOVE,
    SWP_NOSIZE,
    SWP_NOZORDER,
    SWP_FRAMECHANGED,
)


def get_windows_build() -> int:
    """获取 Windows 构建版本号

    Returns:
        Windows 构建版本号，如 22621。获取失败返回 0。
    """
    try:
        import platform
        version = platform.version()
        # Windows 版本格式: "10.0.22621"
        parts = version.split('.')
        if len(parts) >= 3:
            return int(parts[2])
    except Exception:
        pass
    return 0


def is_mica_supported() -> bool:
    """检查是否支持 Mica 效果

    Mica 效果需要 Windows 11 (Build 22000+)。

    Returns:
        True 如果支持 Mica，否则 False。
    """
    build = get_windows_build()
    return build >= 22000


def apply_mica_effect(hwnd: int, dark_mode: bool = True, use_alt: bool = False) -> bool:
    """为窗口应用 Mica 效果

    Args:
        hwnd: 窗口句柄 (HWND)
        dark_mode: 是否使用深色模式
        use_alt: 是否使用 Mica Alt (Tabbed) 效果，提供更强的背景色

    Returns:
        是否成功应用 Mica 效果
    """
    if not is_mica_supported():
        log("Mica effect not supported on this Windows version")
        return False

    if not hwnd:
        log("Invalid window handle for Mica effect")
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        user32 = ctypes.windll.user32

        # 设置深色/浅色模式标题栏
        dark_value = ctypes.c_int(1 if dark_mode else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_value),
            ctypes.sizeof(dark_value)
        )

        # 设置圆角
        corner_value = ctypes.c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_value),
            ctypes.sizeof(corner_value)
        )

        # 应用 Mica 效果
        build = get_windows_build()
        result = 0

        if build >= 22523:
            # Windows 11 22H2+ 使用官方 API
            backdrop_type = DWMSBT_TABBEDWINDOW if use_alt else DWMSBT_MAINWINDOW
            backdrop_value = ctypes.c_int(backdrop_type)
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(backdrop_value),
                ctypes.sizeof(backdrop_value)
            )
            log(f"Mica effect applied (22H2+ API): dark={dark_mode}, alt={use_alt}, result={result}")
        else:
            # Windows 11 21H2 使用未记录的 API
            mica_value = ctypes.c_int(1)
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_MICA_EFFECT,
                ctypes.byref(mica_value),
                ctypes.sizeof(mica_value)
            )
            log(f"Mica effect applied (21H2 API): dark={dark_mode}, result={result}")

        # 强制刷新窗口非客户区以确保深色/浅色模式生效
        # 这对于初始化时应用正确的 Mica 主题是必须的
        user32.SetWindowPos(
            hwnd,
            0,  # HWND_TOP
            0, 0, 0, 0,  # x, y, cx, cy (不改变)
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
        )

        return result == 0

    except Exception as e:
        log(f"Failed to apply Mica effect: {e}")
        return False


def remove_mica_effect(hwnd: int) -> bool:
    """移除窗口的 Mica 效果

    Args:
        hwnd: 窗口句柄 (HWND)

    Returns:
        是否成功移除 Mica 效果
    """
    if not hwnd:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        backdrop_value = ctypes.c_int(DWMSBT_NONE)
        result = dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop_value),
            ctypes.sizeof(backdrop_value)
        )
        return result == 0
    except Exception as e:
        log(f"Failed to remove Mica effect: {e}")
        return False


def update_mica_dark_mode(hwnd: int, dark_mode: bool) -> bool:
    """更新 Mica 效果的深色/浅色模式

    Args:
        hwnd: 窗口句柄 (HWND)
        dark_mode: 是否使用深色模式

    Returns:
        是否成功更新
    """
    if not hwnd:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        user32 = ctypes.windll.user32

        # 设置深色/浅色模式属性
        dark_value = ctypes.c_int(1 if dark_mode else 0)
        result = dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_value),
            ctypes.sizeof(dark_value)
        )

        # 强制刷新窗口非客户区以应用深色模式
        # 这对于动态切换 Mica 主题是必须的
        user32.SetWindowPos(
            hwnd,
            0,  # HWND_TOP
            0, 0, 0, 0,  # x, y, cx, cy (不改变)
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
        )

        log(f"Mica dark mode updated: dark={dark_mode}, result={result}")
        return result == 0
    except Exception as e:
        log(f"Failed to update Mica dark mode: {e}")
        return False


def find_window_by_title(title: str) -> Optional[int]:
    """通过窗口标题查找窗口句柄

    Args:
        title: 窗口标题

    Returns:
        窗口句柄 (HWND)，未找到返回 None
    """
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
    except Exception as e:
        log(f"Failed to find window by title: {e}")
    return None
