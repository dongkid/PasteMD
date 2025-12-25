"""Windows keystroke helpers (via SendInput)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from ...core.errors import ClipboardError


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

VK_CONTROL = 0x11
VK_V = 0x56


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.ULONG_PTR),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


def _send_key(vk: int, *, key_up: bool) -> None:
    flags = KEYEVENTF_KEYUP if key_up else 0
    inp = _INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=_KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)))
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
    if sent != 1:
        raise ClipboardError("SendInput failed")


def simulate_paste(*, timeout_s: float = 5.0) -> None:
    """
    Simulate paste in the frontmost app (Ctrl+V on Windows).

    `timeout_s` is currently unused.
    """
    try:
        _send_key(VK_CONTROL, key_up=False)
        _send_key(VK_V, key_up=False)
        _send_key(VK_V, key_up=True)
        _send_key(VK_CONTROL, key_up=True)
    except Exception as e:
        raise ClipboardError(f"Failed to simulate Ctrl+V: {e}") from e
