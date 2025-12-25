"""macOS WPS Spreadsheet placer (clipboard paste)."""

from __future__ import annotations

import sys
from html import escape
from typing import List

from ..base import BaseSpreadsheetPlacer
from ..formatting import CellFormat
from ....core.types import PlacementResult
from ....i18n import t
from ....utils.logging import log

from ....utils.clipboard import set_clipboard_rich_text, simulate_paste


def _wrap_tag(tag: str, content: str) -> str:
    return f"<{tag}>{content}</{tag}>"


def _cell_to_html(cell_value: str, *, keep_format: bool) -> tuple[str, bool]:
    """
    Convert a Markdown-ish cell payload to HTML.

    Returns:
        (html, needs_code_bg)
    """
    cf = CellFormat(cell_value)
    clean_text = cf.parse()

    if not keep_format:
        return escape(clean_text).replace("\n", "<br />"), False

    if cf.is_code_block:
        inner = escape(clean_text)
        inner = inner.replace("\n", "<br />")
        return _wrap_tag("code", inner), True

    parts: list[str] = []
    needs_code_bg = False

    for seg in cf.segments:
        seg_text = escape(seg.text or "").replace("\n", "<br />")
        chunk = seg_text

        if seg.is_code:
            needs_code_bg = True
            chunk = _wrap_tag("code", chunk)
        if seg.strikethrough:
            chunk = _wrap_tag("s", chunk)
        if seg.italic:
            chunk = _wrap_tag("i", chunk)
        if seg.bold:
            chunk = _wrap_tag("b", chunk)
        if seg.hyperlink_url:
            url = escape(seg.hyperlink_url, quote=True)
            chunk = f'<a href="{url}">{chunk}</a>'

        parts.append(chunk)

    return "".join(parts) or escape(clean_text), needs_code_bg


def _table_to_html(table_data: List[List[str]], *, keep_format: bool) -> str:
    rows_html: list[str] = []

    for r, row in enumerate(table_data):
        cell_tag = "th" if r == 0 else "td"
        cell_html: list[str] = []

        for cell_value in row:
            content_html, needs_code_bg = _cell_to_html(
                cell_value, keep_format=keep_format
            )
            style_parts = ["padding:2px 6px", "vertical-align:middle"]
            if r == 0:
                style_parts.extend(["font-weight:bold", "background-color:#D3D3D3"])
            if needs_code_bg:
                style_parts.extend(
                    ["background-color:#F0F0F0", "font-family:Menlo,Consolas,monospace"]
                )
            style_attr = ";".join(style_parts)
            cell_html.append(f"<{cell_tag} style=\"{style_attr}\">{content_html}</{cell_tag}>")

        rows_html.append("<tr>" + "".join(cell_html) + "</tr>")

    return (
        "<html><head><meta charset=\"utf-8\" />"
        "<style>"
        "table{border-collapse:collapse}"
        "td,th{border:1px solid #D0D0D0}"
        "a{color:#0563C1;text-decoration:underline}"
        "</style>"
        "</head><body>"
        "<table>"
        + "".join(rows_html)
        + "</table>"
        "</body></html>"
    )


def _table_to_tsv(table_data: List[List[str]]) -> str:
    lines: list[str] = []
    for row in table_data:
        out_cells: list[str] = []
        for cell_value in row:
            cf = CellFormat(cell_value)
            text = cf.parse()
            text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
            out_cells.append(text)
        lines.append("\t".join(out_cells))
    return "\n".join(lines)


class WPSExcelPlacer(BaseSpreadsheetPlacer):
    """macOS WPS 表格内容落地器（剪贴板粘贴）。"""

    def place(self, table_data: List[List[str]], config: dict) -> PlacementResult:
        if sys.platform != "darwin":
            return PlacementResult(
                success=False,
                method=None,
                error=t("placer.macos_wps_excel.not_supported"),
            )

        try:
            keep_format = config.get(
                "excel_keep_format", config.get("keep_format", True)
            )
            html_text = _table_to_html(table_data, keep_format=keep_format)
            tsv_text = _table_to_tsv(table_data)

            # WPS 表格通常能吃下 HTML table；Plain TSV 作为兜底。
            set_clipboard_rich_text(html=html_text, text=tsv_text)
            simulate_paste()

            return PlacementResult(
                success=True,
                method="clipboard_html_table" if keep_format else "clipboard_tsv",
            )
        except Exception as e:
            log(f"macOS WPS 表格粘贴失败: {e}")
            return PlacementResult(
                success=False,
                method="clipboard_html_table",
                error=t("placer.macos_wps_excel.insert_failed", error=str(e)),
            )
