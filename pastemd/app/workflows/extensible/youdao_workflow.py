# -*- coding: utf-8 -*-
"""Youdao Cloud Note paste workflow."""

from .extensible_base import ExtensibleWorkflow
from ....core.errors import ClipboardError, PandocError
from ....utils.clipboard import (
    get_clipboard_html,
    get_clipboard_text,
    is_clipboard_empty,
)
from ....utils.html_analyzer import is_plain_html_fragment
from ....utils.youdao_html import format_youdao_html
from ....i18n import t
from ....service.paste import RichTextPastePlacer


class YoudaoWorkflow(ExtensibleWorkflow):
    """Paste workflow for Youdao Cloud Note."""

    def __init__(self):
        super().__init__()
        self.placer = RichTextPastePlacer()

    @property
    def workflow_key(self) -> str:
        return "youdao"

    def execute(self) -> None:
        try:
            content_type, content = self._read_clipboard()
            self._log(f"Youdao workflow: content_type={content_type}")

            effective_config = {
                **self.config,
                "Keep_original_formula": True,
            }

            if content_type == "html":
                content = self.html_preprocessor.process(content, effective_config)
                md_text = self.doc_generator.convert_html_to_markdown_text(
                    content, effective_config
                )
            else:
                md_text = content

            md_text = self.markdown_preprocessor.process(md_text, effective_config)
            html_text = self.doc_generator.convert_markdown_to_html_text(
                md_text, effective_config
            )
            html_text = format_youdao_html(html_text)
            result = self.placer.place(
                content=md_text,
                config=effective_config,
                html=html_text,
            )

            if result.success:
                self._notify_success(t("workflow.youdao.paste_success"))
            else:
                self._notify_error(result.error or t("workflow.generic.failure"))

        except ClipboardError as e:
            self._success = False
            self._log(f"Clipboard error: {e}")
            self._notify_error(t("workflow.clipboard.read_failed"))
        except PandocError as e:
            self._success = False
            self._log(f"Pandoc error: {e}")
            self._notify_error(t("workflow.html.convert_failed_generic"))
        except Exception as e:
            self._success = False
            self._log(f"Youdao workflow failed: {e}")
            import traceback
            traceback.print_exc()
            self._notify_error(t("workflow.generic.failure"))

    def _read_clipboard(self) -> tuple[str, str]:
        try:
            html = get_clipboard_html(self.config)
            if not is_plain_html_fragment(html):
                return ("html", html)
        except ClipboardError:
            pass

        if not is_clipboard_empty():
            return ("markdown", get_clipboard_text())

        raise ClipboardError("剪贴板为空或无有效内容")
