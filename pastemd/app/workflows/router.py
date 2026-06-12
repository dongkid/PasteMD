"""Workflow router - main entry point."""

import json
import os
import re
from ...core.state import app_state
from ...utils.detector import detect_active_app, get_frontmost_window_title
from ...utils.logging import log
from ...service.notification.manager import NotificationManager
from ...service.history.models import HistoryEntry
from ...i18n import t

from .word import WordWorkflow, WPSWorkflow
from .excel import ExcelWorkflow, WPSExcelWorkflow
from .fallback import FallbackWorkflow
from .office_omml import OneNoteWorkflow, PowerPointWorkflow
from .extensible import HtmlWorkflow, MdWorkflow, LatexWorkflow, FileWorkflow, YoudaoWorkflow


class WorkflowRouter:
    """工作流路由器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self.core_workflows = {
            "word": WordWorkflow(),
            "wps": WPSWorkflow(),
            "excel": ExcelWorkflow(),
            "wps_excel": WPSExcelWorkflow(),
            "onenote": OneNoteWorkflow(),
            "powerpoint": PowerPointWorkflow(),
            "youdao": YoudaoWorkflow(),
            "": FallbackWorkflow(),
        }

        self.extensible_registry = {
            "html": HtmlWorkflow(),
            "md": MdWorkflow(),
            "latex": LatexWorkflow(),
            "file": FileWorkflow(),
        }

        # 工作流元数据: key -> (display_name, content_type, source_format)
        self._workflow_meta = {
            "word": ("Word", "markdown", "markdown"),
            "wps": ("WPS", "markdown", "markdown"),
            "excel": ("Excel", "table", "markdown"),
            "wps_excel": ("WPS Excel", "table", "markdown"),
            "onenote": ("OneNote", "html", "html"),
            "powerpoint": ("PowerPoint", "html", "html"),
            "youdao": ("Youdao", "html", "html"),
            "": ("Fallback", "markdown", "markdown"),
            "html": ("HTML+MD", "html", "html"),
            "md": ("Markdown", "markdown", "html"),
            "latex": ("LaTeX", "latex", "html"),
            "file": ("File", "file", "markdown"),
        }

        self.notification_manager = NotificationManager()
        self._history_manager = None
        self._initialized = True
        log("WorkflowRouter initialized")

    def set_history_manager(self, hm) -> None:
        self._history_manager = hm

    def _build_dynamic_routes(self, window_title: str = "") -> dict:
        routes = dict(self.core_workflows)

        ext_config = app_state.config.get("extensible_workflows", {})
        for key, workflow in self.extensible_registry.items():
            cfg = ext_config.get(key, {})
            if cfg.get("enabled", False):
                for app in cfg.get("apps", []):
                    app_id = app.get("id", "") if isinstance(app, dict) else ""
                    if isinstance(app_id, str):
                        app_id = app_id.lower()
                    window_patterns = app.get("window_patterns", []) if isinstance(app, dict) else []

                    app_key = app_id
                    if not app_key:
                        continue

                    if window_patterns and window_title:
                        if self._match_window_patterns(window_title, window_patterns):
                            routes[app_key] = workflow
                            log(f"Registered extensible route (window matched): {app_key} -> {key}")
                    elif not window_patterns:
                        if app_key not in routes:
                            routes[app_key] = workflow
                            log(f"Registered extensible route: {app_key} -> {key}")

        return routes

    def _match_window_patterns(self, window_title: str, patterns: list) -> bool:
        for pattern in patterns:
            if not pattern:
                continue
            try:
                if re.search(pattern, window_title, re.IGNORECASE):
                    log(f"Window title '{window_title}' matched pattern '{pattern}'")
                    return True
            except re.error as e:
                log(f"Invalid regex pattern '{pattern}': {e}")
        return False

    def route(self) -> None:
        target_app = ""
        workflow_key = ""
        error_msg = ""
        window_title = ""
        content_preview = ""
        full_content = ""
        workflow = None
        try:
            target_app = detect_active_app()
            log(f"Detected target app: {target_app}")

            window_title = get_frontmost_window_title()
            log(f"Window title: {window_title}")

            content_preview, full_content = self._capture_clipboard_preview()

            routes = self._build_dynamic_routes(window_title)
            workflow = routes.get(target_app, routes[""])
            for k, v in {**routes, **dict.fromkeys(self.extensible_registry.keys(), None)}.items():
                if v is workflow:
                    workflow_key = k
                    break
            if not workflow_key:
                if workflow in self.extensible_registry.values():
                    workflow_key = list(self.extensible_registry.keys())[
                        list(self.extensible_registry.values()).index(workflow)
                    ]
                # 正向匹配失败 → 不可读的路径回退为空（fallback）
                elif target_app and target_app not in ("word", "wps", "excel", "wps_excel",
                                                       "onenote", "powerpoint", "youdao"):
                    workflow_key = ""
                else:
                    workflow_key = target_app or ""
            workflow.execute()

        except Exception as e:
            log(f"Router failed: {e}")
            import traceback
            traceback.print_exc()
            error_msg = str(e)[:500]
            self.notification_manager.notify("PasteMD", t("workflow.generic.failure"), ok=False)

        # 优先从工作流获取成功标志，否则从异常推导
        try:
            ok = workflow.success if workflow else False
        except Exception:
            ok = not error_msg

        self._record_history(target_app, workflow_key, ok, error_msg,
                             window_title, content_preview, full_content,
                             workflow=workflow)

    @staticmethod
    def _capture_clipboard_preview() -> tuple[str, str]:
        """返回 (preview_200, full_text)，兼容文件剪贴板。"""
        try:
            from ...utils.clipboard import (
                get_clipboard_text,
                read_markdown_files_from_clipboard,
                is_clipboard_files,
                get_clipboard_files,
                is_clipboard_empty,
            )
            text = get_clipboard_text() or ""

            # 文本为空时尝试文件剪贴板
            if not text.strip():
                # MD 文件剪贴板
                found, files_data, _ = read_markdown_files_from_clipboard()
                if found and files_data:
                    parts = []
                    for fn, content in files_data:
                        parts.append(f"[{fn}]\n{content.strip()}")
                    text = "\n\n".join(parts)
                # 其他文件剪贴板：列出文件名
                if not text.strip():
                    try:
                        if is_clipboard_files():
                            files = get_clipboard_files()
                            if files:
                                text = "Files: " + ", ".join(
                                    os.path.basename(f) for f in files[:10]
                                )
                                if len(files) > 10:
                                    text += f" (+{len(files) - 10} more)"
                    except Exception:
                        pass
                # 仍然为空但剪贴板不为空 → 非文本内容
                if not text.strip() and not is_clipboard_empty():
                    text = "[non-text clipboard content]"

            preview = text.strip()[:200] if text else ""
            return preview, text
        except Exception:
            return "", ""

    def _record_history(self, target_app: str, workflow_key: str,
                        success: bool, error_msg: str,
                        window_title: str, content_preview: str,
                        full_content: str = "",
                        workflow=None) -> None:
        hm = self._history_manager
        if hm is None:
            return

        try:
            history_cfg = app_state.config.get("history", {})
            save_full = history_cfg.get("save_full_content", True)

            # 获取工作流元数据
            meta = self._workflow_meta.get(workflow_key, ("Unknown", "markdown", "plain_text"))
            display_name, content_type, source_format = meta

            # 收集激活的过滤器信息
            filters_info = self._collect_active_filters(workflow_key)

            # 构建转换管道描述
            pipeline = self._describe_pipeline(workflow_key)

            # 获取输出文件：优先工作流属性，否则扫目录
            output_path = ""
            output_bytes = 0
            if workflow is not None:
                try:
                    output_path = workflow.output_path or ""
                    output_bytes = workflow.output_bytes or 0
                except Exception:
                    pass

            if not output_path:
                save_dir = app_state.config.get("save_dir", "") or ""
                if save_dir:
                    try:
                        files = sorted(
                            [os.path.join(save_dir, f) for f in os.listdir(save_dir)
                             if os.path.isfile(os.path.join(save_dir, f))],
                            key=lambda p: os.path.getmtime(p), reverse=True,
                        )
                        if files:
                            output_path = files[0]
                            output_bytes = os.path.getsize(output_path)
                    except Exception:
                        pass

            entry = HistoryEntry(
                source_format=source_format,
                content_type=content_type,
                target_app=target_app,
                window_title=window_title,
                workflow_key=workflow_key,
                conversion_pipeline=json.dumps(pipeline, ensure_ascii=False),
                preview=content_preview,
                full_content=full_content if save_full else "",
                output_bytes=output_bytes,
                status="success" if success else "fail",
                error_msg=error_msg,
                filters_json=json.dumps(filters_info, ensure_ascii=False),
                output_file_path=output_path,
            )
            hm.record(entry)
        except Exception:
            pass  # 历史记录失败绝不影响主流程

    def _collect_active_filters(self, workflow_key: str) -> list[str]:
        """收集当前激活的过滤器名。"""
        filters = []
        cfg = app_state.config
        if cfg.get("enable_latex_replacements", True):
            filters.append("latex-replacements")
        if cfg.get("Keep_original_formula", False):
            filters.append("keep-latex-math")
        if cfg.get("normalize_markdown", True):
            filters.append("normalize-markdown-breaks")

        # 特定转换的过滤器
        by_conv = cfg.get("pandoc_filters_by_conversion", {})
        for conv_key in ["md_to_docx", "html_to_docx", "html_to_md", "md_to_html", "md_to_latex", "md_to_rtf"]:
            conv_filters = by_conv.get(conv_key, [])
            for f in (conv_filters if isinstance(conv_filters, list) else []):
                filters.append(f"{conv_key}:{self._filter_label(f)}")

        # 全局 pandoc_filters
        global_filters = cfg.get("pandoc_filters", [])
        for f in (global_filters if isinstance(global_filters, list) else []):
            filters.append(f"global:{self._filter_label(f)}")

        # HTML 格式化选项 (全局)
        html_fmt = cfg.get("html_formatting", {})
        if isinstance(html_fmt, dict):
            if html_fmt.get("strikethrough_to_del", True):
                filters.append("html:strikethrough_to_del")
            if html_fmt.get("css_font_to_semantic", False):
                filters.append("html:css_font_to_semantic")
            if html_fmt.get("bold_first_row_to_header", False):
                filters.append("html:bold_first_row_to_header")

        # 可扩展工作流覆盖的格式化选项
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

    @staticmethod
    def _normalize_target_app(target_app: str) -> str:
        """将路径类 target_app 清洗为可读名或空字符串。"""
        if not target_app:
            return target_app
        # 已知应用类型直接返回
        known = {"word", "wps", "excel", "wps_excel", "onenote", "powerpoint", "youdao"}
        if target_app in known:
            return target_app
        # 包含路径分隔符或盘符 → 提取文件名
        if "\\" in target_app or "/" in target_app or ":" in target_app:
            return os.path.basename(target_app).rsplit(".", 1)[0]
        return target_app

    @staticmethod
    def _describe_pipeline(workflow_key: str) -> dict:
        """描述转换管道。"""
        pipelines = {
            "word":       {"input": "clipboard", "steps": ["detect_type", "preprocess", "to_docx", "com_insert"]},
            "wps":        {"input": "clipboard", "steps": ["detect_type", "preprocess", "to_docx", "com_insert"]},
            "excel":      {"input": "clipboard", "steps": ["parse_table", "to_xlsx", "clipboard_paste"]},
            "wps_excel":  {"input": "clipboard", "steps": ["parse_table", "to_xlsx", "clipboard_paste"]},
            "onenote":    {"input": "clipboard", "steps": ["html", "preprocess", "omml_convert", "rich_paste"]},
            "powerpoint": {"input": "clipboard", "steps": ["html", "preprocess", "omml_convert", "rich_paste"]},
            "youdao":     {"input": "clipboard", "steps": ["html", "preprocess", "md_convert", "rich_paste"]},
            "":           {"input": "clipboard", "steps": ["detect_type", "to_docx_or_xlsx", "open_or_save"]},
            "html":       {"input": "clipboard_html", "steps": ["html_to_md", "md_preprocess", "md_to_html", "rich_paste"]},
            "md":         {"input": "clipboard_html", "steps": ["html_to_md", "md_preprocess", "plain_paste"]},
            "latex":      {"input": "clipboard_html", "steps": ["html_to_md", "md_preprocess", "md_to_latex", "plain_paste"]},
            "file":       {"input": "clipboard", "steps": ["detect_type", "to_docx_or_xlsx", "file_paste"]},
        }
        return pipelines.get(workflow_key, {"input": "clipboard", "steps": ["unknown"]})


# 全局单例
router = WorkflowRouter()


def execute_paste_workflow():
    """热键入口函数"""
    router.route()
