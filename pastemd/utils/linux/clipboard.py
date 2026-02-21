"""Linux clipboard operations (text/html/files) with graceful fallback."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import pyperclip

from ...core.errors import ClipboardError
from ..clipboard_file_utils import (
    filter_markdown_files,
    read_file_with_encoding,
    read_markdown_files,
)
from ..logging import log


def _has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run_command(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout_s: float = 1.0,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            input=input_text,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _read_via_wl_paste(mime: str | None = None) -> str:
    if not _has_command("wl-paste"):
        return ""
    cmd = ["wl-paste", "--no-newline"]
    if mime:
        cmd.extend(["--type", mime])
    proc = _run_command(cmd)
    if not proc or proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip("\x00")


def _read_via_xclip(target: str) -> str:
    if not _has_command("xclip"):
        return ""
    proc = _run_command(["xclip", "-selection", "clipboard", "-t", target, "-o"])
    if not proc or proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip("\x00")


def _write_via_wl_copy(content: str, mime: str) -> bool:
    if not _has_command("wl-copy"):
        return False
    proc = _run_command(["wl-copy", "--type", mime], input_text=content)
    return bool(proc and proc.returncode == 0)


def _write_via_xclip(content: str, target: str) -> bool:
    if not _has_command("xclip"):
        return False
    proc = _run_command(
        ["xclip", "-selection", "clipboard", "-t", target],
        input_text=content,
    )
    return bool(proc and proc.returncode == 0)


def get_clipboard_text() -> str:
    """获取剪贴板文本内容。"""
    errors: list[str] = []

    try:
        text = pyperclip.paste()
        if text is not None:
            return str(text)
    except Exception as e:
        errors.append(f"pyperclip: {e}")

    text = _read_via_wl_paste("text/plain")
    if text:
        return text

    text = _read_via_wl_paste()
    if text:
        return text

    text = _read_via_xclip("text/plain")
    if text:
        return text

    text = _read_via_xclip("UTF8_STRING")
    if text:
        return text

    if errors:
        raise ClipboardError(f"Failed to read clipboard: {'; '.join(errors)}")
    return ""


def set_clipboard_text(text: str) -> None:
    """设置剪贴板纯文本内容。"""
    try:
        pyperclip.copy(text)
        return
    except Exception:
        pass

    if _write_via_wl_copy(text, "text/plain"):
        return

    if _write_via_xclip(text, "text/plain"):
        return

    raise ClipboardError("Failed to set clipboard text: no available backend")


def is_clipboard_empty() -> bool:
    """检查剪贴板是否为空。"""
    try:
        if is_clipboard_files():
            return False
        text = get_clipboard_text()
        return not text or not text.strip()
    except ClipboardError:
        return True


def is_clipboard_html() -> bool:
    """检查剪贴板是否包含 HTML。"""
    try:
        html = get_clipboard_html()
        return bool(html.strip())
    except ClipboardError:
        return False


def get_clipboard_html(config: dict | None = None) -> str:
    """获取剪贴板 HTML 内容。"""
    _ = config

    html = _read_via_wl_paste("text/html")
    if html.strip():
        return html

    html = _read_via_xclip("text/html")
    if html.strip():
        return html

    raise ClipboardError("No HTML format data in clipboard")


def set_clipboard_rich_text(
    *,
    html: str | None = None,
    rtf_bytes: bytes | None = None,
    docx_bytes: bytes | None = None,
    text: str | None = None,
) -> None:
    """写入富文本剪贴板（Linux 最小实现）。"""
    _ = rtf_bytes
    _ = docx_bytes

    if html:
        if _write_via_wl_copy(html, "text/html") or _write_via_xclip(html, "text/html"):
            return

    if text is not None:
        set_clipboard_text(text)
        return

    if html:
        set_clipboard_text(html)
        return

    raise ClipboardError("Failed to write rich text to clipboard: empty payload")


def _normalize_file_paths(file_paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for path in file_paths:
        p = os.path.abspath(path)
        if os.path.exists(p):
            normalized.append(p)
    return normalized


def copy_files_to_clipboard(file_paths: list) -> None:
    """将文件路径复制到剪贴板（优先 text/uri-list）。"""
    paths = _normalize_file_paths([str(p) for p in file_paths])
    if not paths:
        raise ClipboardError("No valid files to copy to clipboard")

    uris = "\n".join(Path(p).as_uri() for p in paths)
    if _write_via_wl_copy(uris, "text/uri-list"):
        return

    if _write_via_xclip(uris, "text/uri-list"):
        return

    # 退化为纯文本文件路径
    set_clipboard_text("\n".join(paths))


def _parse_uri_list_to_paths(raw: str) -> list[str]:
    paths: list[str] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("file://"):
            parsed = urlparse(line)
            path = unquote(parsed.path)
            if parsed.netloc and parsed.netloc != "localhost":
                path = f"//{parsed.netloc}{path}"
            if path and os.path.exists(path):
                paths.append(os.path.abspath(path))
        elif os.path.exists(line):
            paths.append(os.path.abspath(line))

    # 保序去重
    return list(dict.fromkeys(paths))


def get_clipboard_files() -> list[str]:
    """获取剪贴板中的文件路径列表。"""
    raw = _read_via_wl_paste("text/uri-list")
    if not raw:
        raw = _read_via_xclip("text/uri-list")

    paths = _parse_uri_list_to_paths(raw)
    if paths:
        log(f"Got {len(paths)} files from clipboard")
        return paths

    # 最后尝试把纯文本逐行当作路径
    try:
        text = get_clipboard_text()
        maybe_paths = [p.strip() for p in text.splitlines() if p.strip()]
        fallback = [os.path.abspath(p) for p in maybe_paths if os.path.exists(p)]
        return list(dict.fromkeys(fallback))
    except Exception:
        return []


def is_clipboard_files() -> bool:
    """检测剪贴板是否包含文件。"""
    try:
        result = bool(get_clipboard_files())
        log(f"Clipboard files check: {result}")
        return result
    except Exception:
        return False


def get_markdown_files_from_clipboard() -> list[str]:
    """从剪贴板获取 Markdown 文件路径列表。"""
    all_files = get_clipboard_files()
    return filter_markdown_files(all_files)


def read_markdown_files_from_clipboard() -> tuple[bool, list[tuple[str, str]], list[tuple[str, str]]]:
    """从剪贴板读取 Markdown 文件内容。"""
    md_files = get_markdown_files_from_clipboard()
    return read_markdown_files(md_files)


@contextlib.contextmanager
def preserve_clipboard(*, restore_delay_s: float = 0.25):
    """尽力保留并恢复用户剪贴板内容。"""
    snapshot_text: str | None = None
    snapshot_html: str | None = None
    snapshot_files: list[str] = []

    try:
        snapshot_files = get_clipboard_files()
        if not snapshot_files:
            try:
                snapshot_html = get_clipboard_html()
            except ClipboardError:
                snapshot_html = None
        try:
            snapshot_text = get_clipboard_text()
        except ClipboardError:
            snapshot_text = None
        yield
    finally:
        if restore_delay_s > 0:
            time.sleep(restore_delay_s)

        try:
            if snapshot_files:
                copy_files_to_clipboard(snapshot_files)
                return

            if snapshot_html is not None:
                set_clipboard_rich_text(html=snapshot_html, text=snapshot_text)
                return

            if snapshot_text is not None:
                set_clipboard_text(snapshot_text)
        except Exception as exc:
            log(f"Failed to restore clipboard: {exc}")


__all__ = [
    "get_clipboard_text",
    "set_clipboard_text",
    "is_clipboard_empty",
    "is_clipboard_html",
    "get_clipboard_html",
    "set_clipboard_rich_text",
    "copy_files_to_clipboard",
    "is_clipboard_files",
    "get_clipboard_files",
    "get_markdown_files_from_clipboard",
    "read_markdown_files_from_clipboard",
    "read_file_with_encoding",
    "preserve_clipboard",
]
