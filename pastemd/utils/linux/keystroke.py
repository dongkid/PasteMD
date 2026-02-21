"""Linux keystroke utilities."""

from __future__ import annotations

import shutil
import subprocess

from ...core.errors import ClipboardError


def _run(args: list[str], timeout_s: float) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def simulate_paste(*, timeout_s: float = 5.0) -> None:
    """模拟 Ctrl+V 粘贴（优先 xdotool）。"""
    if shutil.which("xdotool"):
        proc = _run(["xdotool", "key", "ctrl+v"], timeout_s)
        if proc and proc.returncode == 0:
            return

    if shutil.which("wtype"):
        proc = _run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], timeout_s)
        if proc and proc.returncode == 0:
            return

    raise ClipboardError("Failed to simulate Ctrl+V: please install xdotool (X11) or wtype (Wayland)")
