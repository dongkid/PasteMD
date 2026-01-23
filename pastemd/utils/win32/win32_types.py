"""Win32 API constants and structure definitions.

This module provides Win32 API constants and ctypes structure definitions
used by other Windows-specific utility modules.

Follows Single Responsibility Principle: only contains type definitions,
no business logic.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes


# ============================================================================
# Window Position (SetWindowPos) Flags
# ============================================================================
SWP_NOSIZE = 0x0001          # Retains the current size
SWP_NOMOVE = 0x0002          # Retains the current position
SWP_NOZORDER = 0x0004        # Retains the current Z order
SWP_NOREDRAW = 0x0008        # Does not redraw changes
SWP_NOACTIVATE = 0x0010      # Does not activate the window
SWP_FRAMECHANGED = 0x0020    # Sends WM_NCCALCSIZE
SWP_SHOWWINDOW = 0x0040      # Displays the window
SWP_HIDEWINDOW = 0x0080      # Hides the window
SWP_NOCOPYBITS = 0x0100      # Discards the entire contents of the client area
SWP_NOOWNERZORDER = 0x0200   # Does not change the owner window's position
SWP_NOSENDCHANGING = 0x0400  # Does not send WM_WINDOWPOSCHANGING


# ============================================================================
# Monitor Flags
# ============================================================================
MONITOR_DEFAULTTONULL = 0x00000000
MONITOR_DEFAULTTOPRIMARY = 0x00000001
MONITOR_DEFAULTTONEAREST = 0x00000002


# ============================================================================
# DWM Window Attribute Constants
# ============================================================================
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_MICA_EFFECT = 1029  # Undocumented, for Windows 11 21H2
DWMWA_WINDOW_CORNER_PREFERENCE = 33


# ============================================================================
# DWM System Backdrop Types
# ============================================================================
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2       # Mica
DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
DWMSBT_TABBEDWINDOW = 4     # Tabbed Mica (Mica Alt)


# ============================================================================
# DWM Window Corner Preference
# ============================================================================
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3


# ============================================================================
# Win32 Structures
# ============================================================================
class POINT(ctypes.Structure):
    """Win32 POINT structure."""
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


class RECT(ctypes.Structure):
    """Win32 RECT structure."""
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    """Win32 MONITORINFO structure."""
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]
