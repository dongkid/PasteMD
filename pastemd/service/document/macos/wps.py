"""macOS WPS document placer."""

from __future__ import annotations

import sys

from ..base import BaseDocumentPlacer
from ....core.types import PlacementResult
from ....utils.logging import log
from ....i18n import t
from ....utils.clipboard import set_clipboard_rich_text, simulate_paste


class WPSPlacer(BaseDocumentPlacer):
    """macOS WPS 内容落地器"""

    def place(self, docx_bytes: bytes, config: dict, **kwargs) -> PlacementResult:
        """
        macOS WPS 采用 HTML+RTF 富文本粘贴落地。

        约定:
            - 入参 `docx_bytes` 实际承载的是 UTF-8 编码的 HTML 字节（由 workflow 生成）。
            - config 可传入内部字段 `_rtf_bytes` 作为 RTF 兜底。
            - config 可传入内部字段 `_plain_text` 作为纯文本兜底。
        """
        if sys.platform != "darwin":
            return PlacementResult(
                success=False,
                method=None,
                error=t("placer.macos_wps.not_supported"),
            )

        try:
            # rtf_bytes = kwargs.get("_rtf_bytes")
            plain_text = kwargs.get("_plain_text")
            html_text = kwargs.get("_html_text")
            set_clipboard_rich_text(
                html=html_text, rtf_bytes=None, text=plain_text, docx_bytes=None
            )
            simulate_paste()

            return PlacementResult(success=True, method="clipboard_rtf_html")
        except Exception as e:
            log(f"macOS WPS RTF/HTML 粘贴失败: {e}")
            return PlacementResult(
                success=False,
                method="clipboard_rtf_html",
                error=str(e),
            )
