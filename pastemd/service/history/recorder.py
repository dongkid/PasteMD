"""HistoryRecorder - 收集粘贴历史数据的独立组件，不耦合 WorkflowRouter。"""

import json
import os

from ...core.state import app_state
from .models import HistoryEntry


class HistoryRecorder:
    """从工作流执行结果收集 HistoryEntry 所需的元数据。"""

    def __init__(self, history_manager):
        self._hm = history_manager

    def record(self, target_app, workflow_key, success, error_msg,
               window_title, content_preview, full_content="",
               workflow=None, original_html="") -> None:
        """收集中元数据后写入 HistoryEntry 到 HistoryManager。"""
        if self._hm is None:
            return

        try:
            cfg = app_state.config.get("history", {})
            save_full = cfg.get("save_full_content", True)

            content_type, source_format = self._meta_from_workflow(workflow)
            pipeline = self._pipeline_from_workflow(workflow)
            filters_info = self._collect_filters(workflow_key)
            output_path, output_bytes = self._resolve_output(workflow)

            entry = HistoryEntry(
                source_format=source_format,
                content_type=content_type,
                target_app=target_app,
                window_title=window_title,
                workflow_key=workflow_key,
                conversion_pipeline=json.dumps(pipeline, ensure_ascii=False),
                preview=content_preview,
                full_content=full_content if save_full else "",
                original_html=original_html,
                output_bytes=output_bytes,
                status="success" if success else "fail",
                error_msg=error_msg,
                filters_json=json.dumps(filters_info, ensure_ascii=False),
                output_file_path=output_path,
            )
            self._hm.record(entry)
        except Exception:
            pass  # 历史记录失败绝不影响主流程

    # ---- 剪贴板预览 ----

    @staticmethod
    def capture_clipboard() -> tuple[str, str, str]:
        """捕获剪贴板内容，返回 (preview, full_text, original_html)。
        必须在 workflow.execute() 之前调用。"""
        try:
            from ...utils.clipboard import (
                get_clipboard_text, read_markdown_files_from_clipboard,
                is_clipboard_files, get_clipboard_files, is_clipboard_empty,
                get_clipboard_html,
            )
            text = get_clipboard_text() or ""

            if not text.strip():
                found, files_data, _ = read_markdown_files_from_clipboard()
                if found and files_data:
                    parts = [f"[{fn}]\n{content.strip()}" for fn, content in files_data]
                    text = "\n\n".join(parts)
                if not text.strip():
                    try:
                        if is_clipboard_files():
                            files = get_clipboard_files()
                            if files:
                                names = [os.path.basename(f) for f in files[:10]]
                                text = "Files: " + ", ".join(names)
                                if len(files) > 10:
                                    text += f" (+{len(files) - 10} more)"
                    except Exception:
                        pass
                if not text.strip() and not is_clipboard_empty():
                    text = "[non-text clipboard content]"

            preview = text.strip()[:200] if text else ""

            html = ""
            try:
                html = get_clipboard_html() or ""
            except Exception:
                pass

            return preview, text, html
        except Exception:
            return "", "", ""

    # ---- 内部 -- 工作流元数据 ----

    @staticmethod
    def _meta_from_workflow(workflow) -> tuple[str, str]:
        try:
            return (
                workflow.content_type or "markdown",
                workflow.source_format or "plain_text",
            )
        except Exception:
            return "markdown", "plain_text"

    @staticmethod
    def _pipeline_from_workflow(workflow) -> dict:
        try:
            return workflow.pipeline
        except Exception:
            return {"input": "clipboard", "steps": ["unknown"]}

    # ---- 内部 -- 输出文件 ----

    @staticmethod
    def _resolve_output(workflow) -> tuple[str, int]:
        if workflow is not None:
            try:
                path = workflow.output_path or ""
                size = workflow.output_bytes or 0
                if path:
                    return path, size
            except Exception:
                pass

        save_dir = app_state.config.get("save_dir", "") or ""
        if not save_dir:
            return "", 0
        try:
            files = sorted(
                [os.path.join(save_dir, f) for f in os.listdir(save_dir)
                 if os.path.isfile(os.path.join(save_dir, f))],
                key=lambda p: os.path.getmtime(p), reverse=True,
            )
            if files:
                return files[0], os.path.getsize(files[0])
        except Exception:
            pass
        return "", 0

    # ---- 内部 -- 过滤器 ----

    def _collect_filters(self, workflow_key: str) -> list[str]:
        filters = []
        cfg = app_state.config
        if cfg.get("enable_latex_replacements", True):
            filters.append("latex-replacements")
        if cfg.get("Keep_original_formula", False):
            filters.append("keep-latex-math")
        if cfg.get("normalize_markdown", True):
            filters.append("normalize-markdown-breaks")

        by_conv = cfg.get("pandoc_filters_by_conversion", {})
        for ck in ["md_to_docx", "html_to_docx", "html_to_md", "md_to_html", "md_to_latex", "md_to_rtf"]:
            for f in (by_conv.get(ck, []) if isinstance(by_conv.get(ck, []), list) else []):
                filters.append(f"{ck}:{self._filter_label(f)}")

        for f in (cfg.get("pandoc_filters", []) if isinstance(cfg.get("pandoc_filters", []), list) else []):
            filters.append(f"global:{self._filter_label(f)}")

        html_fmt = cfg.get("html_formatting", {})
        if isinstance(html_fmt, dict):
            if html_fmt.get("strikethrough_to_del", True):
                filters.append("html:strikethrough_to_del")
            if html_fmt.get("css_font_to_semantic", False):
                filters.append("html:css_font_to_semantic")
            if html_fmt.get("bold_first_row_to_header", False):
                filters.append("html:bold_first_row_to_header")

        ext_cfg = cfg.get("extensible_workflows", {})
        if isinstance(ext_cfg, dict):
            wf_cfg = ext_cfg.get(workflow_key, {})
            if isinstance(wf_cfg, dict):
                wf_html = wf_cfg.get("html_formatting", {})
                if isinstance(wf_html, dict):
                    if wf_html.get("css_font_to_semantic"):
                        filters.append("ext:css_font_to_semantic")
                    if wf_html.get("bold_first_row_to_header"):
                        filters.append("ext:bold_first_row_to_header")

        return filters

    @staticmethod
    def _filter_label(f) -> str:
        if isinstance(f, dict):
            path = f.get("path", "")
            name = os.path.basename(path) if path else str(f)
        else:
            name = os.path.basename(str(f))
        if name.endswith(".lua"):
            name = name[:-4]
        return name
