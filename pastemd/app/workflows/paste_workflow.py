"""Main paste workflow - orchestrates the entire conversion and insertion process."""

import traceback
import io
import os
from typing import Optional

from ...utils.win32.detector import detect_active_app
from ...utils.clipboard import (
    get_clipboard_text,
    is_clipboard_empty,
    is_clipboard_html,
    get_clipboard_html,
    read_markdown_files_from_clipboard,
)
from ...utils.markdown_utils import merge_markdown_contents
from ...domains.document.word import WordInserter
from ...domains.document.wps import WPSInserter
from ...domains.document.generator import DocumentGeneratorService
from ...domains.spreadsheet.parser import parse_markdown_table
from ...domains.spreadsheet.excel import MSExcelInserter
from ...domains.spreadsheet.wps_excel import WPSExcelInserter
from ...domains.notification.manager import NotificationManager
from ...utils.fs import generate_output_path
from ...utils.docx_processor import DocxProcessor
from ...utils.logging import log
from ...core.state import app_state
from ...config.defaults import DEFAULT_CONFIG
from ...config.loader import ConfigLoader
from .output_executor import OutputExecutor
from ...core.errors import ClipboardError, PandocError, InsertError
from ...integrations.pandoc import PandocIntegration
from ...core.types import NoAppAction
from ...utils.win32.memfile import EphemeralFile
from ...utils.html_analyzer import is_plain_html_fragment
from ...i18n import t


class PasteWorkflow:
    """转换并插入工作流 - 业务流程编排"""
    
    def __init__(self) -> None:
        self.word_inserter = WordInserter()
        self.wps_inserter = WPSInserter()
        self.ms_excel_inserter = MSExcelInserter()
        self.wps_excel_inserter = WPSExcelInserter()
        self.notification_manager = NotificationManager()
        self.doc_generator = DocumentGeneratorService()
        self.output_executor = OutputExecutor(self.notification_manager)
        self.pandoc_integration = None  # 延迟初始化
    
    def execute(self) -> None:
        """执行完整的转换和插入流程"""
        try:
            config = app_state.config
            
            # 1. 首先检查剪贴板文本（优先处理文本）
            if not is_clipboard_empty():
                # 剪贴板有文本内容，走原有逻辑
                # 2.1 检测是否为 HTML 富文本，并尝试识别其结构
                is_html = is_clipboard_html()
                html_text = None
                should_use_html = False
                if is_html:
                    try:
                        html_text = get_clipboard_html(config)
                        is_plain = is_plain_html_fragment(html_text)
                        log(f"Clipboard contains HTML (plain_fragment={is_plain})")
                        if not is_plain:
                            should_use_html = True
                        else:
                            log("HTML fragment looks like Markdown, fallback to Markdown flow.")
                    except ClipboardError as e:
                        log(f"Detected HTML clipboard data but failed to read fragment: {e}")
                        is_html = False
                else:
                    log("Clipboard contains HTML: False")
                
                # 3. 检测当前活动应用
                target = detect_active_app()
                log(f"Detected active target: {target}")
                
                # 4. 根据剪贴板内容类型和目标应用选择处理流程
                if should_use_html and target in ("word", "wps"):
                    # HTML 富文本流程：直接转换 HTML 为 DOCX
                    self._handle_html_to_word_flow(target, config, html_text=html_text)
                else:
                    # 原有的 Markdown 流程
                    md_text = get_clipboard_text()
                    
                    if target in ("excel", "wps_excel") and config.get("enable_excel", True):
                        # Excel/WPS表格流程：直接插入表格数据
                        self._handle_excel_flow(md_text, target, config)
                    elif target in ("word", "wps"):
                        # Word/WPS文字流程：转换为DOCX后插入
                        self._handle_word_flow(md_text, target, config)
                    else:
                        # 未检测到应用，尝试自动打开预生成的文件
                        self._handle_no_app_flow(
                            md_text,
                            config,
                            is_html=should_use_html,
                            html_text=html_text if should_use_html else None,
                        )
            else:
                # 2. 文本为空时，检测是否有 MD 文件
                found, files_data, errors = read_markdown_files_from_clipboard()
                
                # 计算原始发现的文件数（成功 + 失败）
                total_found = len(files_data) + len(errors)
                
                # 显示每个失败文件的通知
                for filename, error_msg in errors:
                    self.notification_manager.notify(
                        "PasteMD",
                        t("workflow.md_file.read_failed", filename=filename, error=error_msg),
                        ok=False
                    )
                
                if not found:
                    # 确实为空（没有 MD 文件，或所有文件读取都失败）
                    self.notification_manager.notify(
                        "PasteMD",
                        t("workflow.clipboard.empty"),
                        ok=False
                    )
                    return
                
                # 3. 有 MD 文件，检测目标应用
                target = detect_active_app()
                log(f"Detected active target for MD files: {target}")
                
                if target in ("word", "wps"):
                    # 合并所有文件后插入
                    merged_content = merge_markdown_contents(files_data)
                    self._handle_word_flow(merged_content, target, config,
                                           from_md_file=True, file_count=len(files_data))
                elif target in ("excel", "wps_excel") and config.get("enable_excel", True):
                    # Excel 流程（仅使用第一个文件的表格内容）
                    md_text = files_data[0][1]
                    self._handle_excel_flow(md_text, target, config)
                else:
                    # 无应用，逐个处理
                    self._handle_md_files_no_app_flow(files_data, config)
            
        except ClipboardError as e:
            log(f"Clipboard error: {e}")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.clipboard.read_failed"),
                ok=False
            )
        except PandocError as e:
            log(f"Pandoc error: {e}")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.markdown.convert_failed"),
                ok=False
            )
        except Exception:
            # 记录详细错误
            error_details = io.StringIO()
            traceback.print_exc(file=error_details)
            log(error_details.getvalue())
            
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.generic.failure"),
                ok=False
            )
    
    def _handle_md_files_no_app_flow(
        self,
        files_data: list[tuple[str, str]],
        config: dict
    ) -> None:
        """
        无应用时处理多个 MD 文件（逐个处理）
        
        Args:
            files_data: [(filename, content), ...] 列表
            config: 配置字典
        """
        # 获取动作配置
        action = config.get("no_app_action", "open")
        
        # 检查是否为禁用模式
        if action == NoAppAction.NONE:
            log("no_app_action is 'none', skipping MD files processing")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.no_app_detected"),
                ok=False
            )
            return
        
        # 验证动作类型
        if action not in (NoAppAction.OPEN, NoAppAction.SAVE, NoAppAction.CLIPBOARD):
            log(f"Unknown no_app_action for MD files: {action}")
            return
        
        if len(files_data) == 1:
            filename, content = files_data[0]
            log(f"Processing MD file: {filename}")
            try:
                self._execute_docx_action(action, content, config, from_md_file=True)
            except Exception as e:
                log(f"Failed to process MD file '{filename}': {e}")
            return

        # 批量生成 DOCX items，再由 executor 统一输出与汇总通知
        if action == NoAppAction.CLIPBOARD:
            keep_file = config.get("keep_file", False)
        else:
            keep_file = True

        items: list[tuple[bytes, str, str]] = []
        pre_failures: list[tuple[str, str]] = []

        for filename, content in files_data:
            log(f"Processing MD file: {filename}")
            try:
                docx_bytes, output_path = self.doc_generator.generate_docx_file_from_markdown(
                    content, config, keep_file=keep_file
                )
                items.append((docx_bytes, output_path, filename))
            except PandocError as e:
                log(f"Pandoc error while processing MD file '{filename}': {e}")
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.markdown.convert_failed"),
                    ok=False
                )
                pre_failures.append((filename, str(e)))
            except ClipboardError as e:
                log(f"Clipboard error while processing MD file '{filename}': {e}")
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.html.clipboard_failed"),
                    ok=False
                )
                pre_failures.append((filename, str(e)))
            except Exception as e:
                log(f"Failed to process MD file '{filename}': {e}")
                if action == NoAppAction.CLIPBOARD:
                    self.notification_manager.notify(
                        "PasteMD",
                        t("workflow.action.clipboard_failed"),
                        ok=False
                    )
                else:
                    self.notification_manager.notify(
                        "PasteMD",
                        t("workflow.document.generate_failed"),
                        ok=False
                    )
                pre_failures.append((filename, str(e)))

        self.output_executor.execute_docx_batch(
            action=action,
            items=items,
            from_md_file=True,
            pre_failures=pre_failures
        )

    def _handle_excel_flow(self, md_text: str, target: str, config: dict) -> None:
        """
        Excel/WPS表格流程：解析Markdown表格并直接插入
        
        Args:
            md_text: Markdown文本
            target: 目标应用 (excel 或 wps_excel)
            config: 配置字典
        """
        # 根据目标选择插入器
        if target == "wps_excel":
            inserter = self.wps_excel_inserter
            app_name = "WPS 表格"
        else:  # excel
            inserter = self.ms_excel_inserter
            app_name = "Excel"
        
        # 解析Markdown表格
        table_data = parse_markdown_table(md_text)
        
        if table_data is None:
            # 不是有效的Markdown表格
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.table.invalid_with_app", app=app_name),
                ok=False
            )
            return
        
        # 尝试插入表格
        log(f"Detected Markdown table with {len(table_data)} rows, inserting to {app_name}")
        try:
            keep_format = config.get("excel_keep_format", True)
            success = inserter.insert(table_data, keep_format=keep_format)
            
            if success:
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.table.insert_success", rows=len(table_data), app=app_name),
                    ok=True
                )
        except InsertError as e:
            log(f"{app_name} insert failed: {e}")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.table.insert_failed", app=app_name, error=str(e)),
                ok=False
            )
    
    def _handle_html_to_word_flow(self, target: str, config: dict, html_text: Optional[str] = None) -> None:
        """
        HTML 富文本流程：直接转换 HTML 为 DOCX 并插入到 Word/WPS
        
        Args:
            target: 目标应用 (word 或 wps)
            config: 配置字典
            html_text: 预先读取好的 HTML 片段（可选）
        """
        try:
            # 1. 获取并清理 HTML 内容
            if html_text is None:
                html_text = get_clipboard_html(config)
            log(f"Retrieved HTML from clipboard, length: {len(html_text)}")
            
            # 2. 生成 DOCX 字节流
            self._ensure_pandoc_integration()
            if self.pandoc_integration is None:
                # 已经在 _ensure_pandoc_integration 中显示了错误通知
                return
            
            docx_bytes = self.pandoc_integration.convert_html_to_docx_bytes(
                html_text=html_text,
                reference_docx=config.get("reference_docx"),
                Keep_original_formula=config.get("Keep_original_formula", False),
                enable_latex_replacements=config.get("enable_latex_replacements", True),
                custom_filters=config.get("pandoc_filters", []),
                cwd=config.get("save_dir"),
            )

            # 3. 使用临时文件插入
            temp_dir = config.get("temp_dir")  # 可选：支持 RAM 盘目录
            with EphemeralFile(suffix=".docx", dir_=temp_dir) as eph:
                eph.write_bytes(docx_bytes)
                # 插入
                inserted = self._perform_word_insertion(eph.path, target)
            
            # 4. 可选保存文件
            if config.get("keep_file", False):
                try:
                    output_path = generate_output_path(
                        keep_file=True,
                        save_dir=config.get("save_dir", ""),
                        html_text=html_text
                    )
                    with open(output_path, "wb") as f:
                        f.write(docx_bytes)
                    log(f"Saved HTML-converted DOCX to: {output_path}")
                except Exception as e:
                    log(f"Failed to save HTML-converted DOCX file: {e}")
            
            # 5. 显示结果通知
            if inserted:
                app_name = "Word" if target == "word" else "WPS 文字"
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.html.insert_success", app=app_name),
                    ok=True
                )
            else:
                app_name = "Word" if target == "word" else "WPS 文字"
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.insert_failed_no_app", app=app_name),
                    ok=False
                )
                
        except ClipboardError as e:
            log(f"Failed to get HTML from clipboard: {e}")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.html.clipboard_failed"),
                ok=False
            )
        except PandocError as e:
            log(f"HTML to DOCX conversion failed: {e}")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.html.convert_failed_format"),
                ok=False
            )
        except Exception as e:
            log(f"HTML flow failed: {e}")
            error_details = io.StringIO()
            traceback.print_exc(file=error_details)
            log(error_details.getvalue())
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.html.convert_failed_generic"),
                ok=False
            )
    
    def _handle_word_flow(self, md_text: str, target: str, config: dict,
                          from_md_file: bool = False, file_count: int = 1) -> None:
        """
        Word/WPS文字流程：转换Markdown为DOCX并插入
        
        Args:
            md_text: Markdown文本
            target: 目标应用 (word 或 wps)
            config: 配置字典
            from_md_file: 是否来源于 MD 文件
            file_count: MD 文件数量
        """
        # 1. 生成 DOCX 字节流（使用 DocumentGeneratorService）
        docx_bytes = self.doc_generator.convert_markdown_to_docx_bytes(md_text, config)

        # 3. 检测文件行数，如果较大则提示用户转换已开始
        line_count = md_text.count('\n') + 1
        if line_count >= 100:
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.markdown.conversion_started", lines=line_count),
                ok=True
            )

        # 4. 生成DOCX字节流
        self._ensure_pandoc_integration()
        if self.pandoc_integration is None:
            # 已经在 _ensure_pandoc_integration 中显示了错误通知
            return
        
        docx_bytes = self.pandoc_integration.convert_to_docx_bytes(
            md_text=md_text,
            reference_docx=config.get("reference_docx"),
            Keep_original_formula=config.get("Keep_original_formula", False),
            enable_latex_replacements=config.get("enable_latex_replacements", True),
            custom_filters=config.get("pandoc_filters", []),
            cwd=config.get("save_dir"),
        )

        # 5. 在内存中处理 DOCX 样式
        if config.get("md_disable_first_para_indent", True):
            docx_bytes = DocxProcessor.apply_custom_processing(
                docx_bytes,
                disable_first_para_indent=True,
                target_style="Body Text"
            )

        # 6. 使用临时文件插入
        temp_dir = config.get("temp_dir")  # 可选：支持 RAM 盘目录
        with EphemeralFile(suffix=".docx", dir_=temp_dir) as eph:
            eph.write_bytes(docx_bytes)
            # 插入
            inserted = self._perform_word_insertion(eph.path, target)

        # 7. 保存文件
        if config.get("keep_file", False):
            # 生成输出路径
            try:
                output_path = generate_output_path(
                    keep_file=config.get("keep_file", False),
                    save_dir=config.get("save_dir", "")
                )
                with open(output_path, "wb") as f:
                    f.write(docx_bytes)
                log(f"Saved DOCX to: {output_path}")
            except Exception as e:
                log(f"Failed to save DOCX file: {e}")
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.document.save_failed"),
                    ok=False
                )
        
        # 4. 显示结果通知
        self._show_word_result(target, inserted, from_md_file, file_count)
    

    def _perform_word_insertion(self, docx_path: str, target: str) -> bool:
        """
        执行Word/WPS文档插入
        
        Args:
            docx_path: DOCX文件路径
            target: 目标应用 (word 或 wps)
            
        Returns:
            True 如果插入成功
        """
        if target == "word":
            try:
                return self.word_inserter.insert(docx_path, app_state.config.get("move_cursor_to_end", True))
            except InsertError as e:
                log(f"Word insertion failed: {e}")
                return False
        elif target == "wps":
            try:
                return self.wps_inserter.insert(docx_path, app_state.config.get("move_cursor_to_end", True))
            except InsertError as e:
                log(f"WPS insertion failed: {e}")
                return False
        else:
            log(f"Unknown insert target: {target}")
            return False
    
    def _show_word_result(self, target: str, inserted: bool, from_md_file: bool = False, file_count: int = 1) -> None:
        """显示Word/WPS流程的结果通知"""
        app_name = "Word" if target == "word" else "WPS 文字"
        if inserted:
            if from_md_file:
                if file_count > 1:
                    msg = t("workflow.md_file.insert_success_multi", count=file_count, app=app_name)
                else:
                    msg = t("workflow.md_file.insert_success", app=app_name)
            else:
                msg = t("workflow.word.insert_success", app=app_name)
            self.notification_manager.notify("PasteMD", msg, ok=True)
        else:
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.insert_failed_no_app", app=app_name),
                ok=False
            )

    def _ensure_pandoc_integration(self) -> None:
        """确保 Pandoc 集成已初始化"""
        if self.pandoc_integration is None:
            pandoc_path = app_state.config.get("pandoc_path", "pandoc")
            try:
                self.pandoc_integration = PandocIntegration(pandoc_path)
            except PandocError as e:
                log(f"Failed to initialize PandocIntegration: {e}")
                try:
                    self.pandoc_integration = PandocIntegration(DEFAULT_CONFIG.get("pandoc_path", "pandoc"))
                    app_state.config["pandoc_path"] = DEFAULT_CONFIG["pandoc_path"]
                    config_loader = ConfigLoader()
                    config_loader.save(config=app_state.config)
                except Exception as e2:
                    log(f"Retry to initialize PandocIntegration failed: {e2}")
                    self.notification_manager.notify(
                        "PasteMD",
                        t("workflow.pandoc.init_failed"),
                        ok=False
                    )
                    self.pandoc_integration = None
    
    def _handle_no_app_flow(self, md_text: str, config: dict, is_html: bool = False, html_text: Optional[str] = None) -> None:
        """
        无应用检测时的处理流程：支持多种动作模式
        支持 Markdown 和 HTML 富文本
        
        根据 no_app_action 配置统一分发到 DOCX/XLSX 执行方法。
        
        Args:
            md_text: Markdown文本
            config: 配置字典
            is_html: 剪贴板是否包含 HTML 富文本
            html_text: 预读取的 HTML 富文本内容
        """
        # 获取动作配置
        action = config.get("no_app_action", "open")
        
        # 检查是否为禁用模式
        if action == NoAppAction.NONE:
            log("no_app_action is 'none', skipping")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.no_app_detected"),
                ok=False
            )
            return
        
        # 验证动作类型
        if action not in (NoAppAction.OPEN, NoAppAction.SAVE, NoAppAction.CLIPBOARD):
            log(f"Unknown no_app_action: {action}")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.no_app_detected"),
                ok=False
            )
            return
        
        # HTML 富文本优先处理
        if is_html:
            self._execute_docx_action(action, md_text, config, from_html=True, html_text=html_text)
            return
        
        # 检测内容类型：表格 vs 文档
        table_data = parse_markdown_table(md_text)
        
        if table_data is not None and config.get("enable_excel", True):
            # 是表格，执行 XLSX 动作
            self._execute_xlsx_action(action, md_text, config, table_data)
        else:
            # 是文档，执行 DOCX 动作
            self._execute_docx_action(action, md_text, config)
    
    # ==================== 统一执行方法 ====================
    
    def _execute_docx_action(
        self,
        action: str,
        md_text: str,
        config: dict,
        *,
        from_md_file: bool = False,
        from_html: bool = False,
        html_text: Optional[str] = None
    ) -> None:
        """
        统一执行 DOCX 输出动作
        
        Args:
            action: 输出动作 ("open" | "save" | "clipboard")
            md_text: Markdown 文本
            config: 配置字典
            from_md_file: 是否来源于 MD 文件
            from_html: 是否来源于 HTML
            html_text: HTML 文本（from_html=True 时使用）
        """
        try:
            # 确定 keep_file 策略
            if action == "clipboard":
                keep_file = config.get("keep_file", False)
            else:
                # open 和 save 动作始终保留文件
                keep_file = True
            
            # 生成 DOCX 字节流和输出路径（使用 DocumentGeneratorService）
            if from_html:
                docx_bytes, output_path = self.doc_generator.generate_docx_file_from_html(
                    md_text, config, html_text=html_text, keep_file=keep_file
                )
            else:
                docx_bytes, output_path = self.doc_generator.generate_docx_file_from_markdown(
                    md_text, config, keep_file=keep_file
                )
            
            # 调用统一执行器
            self.output_executor.execute_docx(
                action=action,
                docx_bytes=docx_bytes,
                output_path=output_path,
                from_md_file=from_md_file,
                from_html=from_html
            )
            
        except ClipboardError as e:
            log(f"Clipboard error in DOCX action: {e}")
            self.notification_manager.notify(
                "PasteMD",
                t("workflow.html.clipboard_failed"),
                ok=False
            )
        except PandocError as e:
            log(f"Pandoc error in DOCX action: {e}")
            if from_html:
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.html.convert_failed_format"),
                    ok=False
                )
            else:
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.markdown.convert_failed"),
                    ok=False
                )
        except Exception as e:
            log(f"Failed to execute DOCX action '{action}': {e}")
            if action == "clipboard":
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.action.clipboard_failed"),
                    ok=False
                )
            elif from_html:
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.html.generate_failed"),
                    ok=False
                )
            else:
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.document.generate_failed"),
                    ok=False
                )
    
    def _execute_xlsx_action(
        self,
        action: str,
        md_text: str,
        config: dict,
        table_data: list
    ) -> None:
        """
        统一执行 XLSX 输出动作
        
        Args:
            action: 输出动作 ("open" | "save" | "clipboard")
            md_text: Markdown 文本（未使用，保留接口一致性）
            config: 配置字典
            table_data: 已解析的表格数据
        """
        try:
            # 验证表格数据
            if table_data is None:
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.table.invalid_simple"),
                    ok=False
                )
                return
            
            # 确定 keep_file 策略
            if action == "clipboard":
                keep_file = config.get("keep_file", False)
            else:
                # open 和 save 动作始终保留文件
                keep_file = True
            
            # 准备输出路径
            save_dir = config.get("save_dir", "") if keep_file else ""
            if keep_file and save_dir:
                save_dir = os.path.expandvars(save_dir)
                os.makedirs(save_dir, exist_ok=True)
            
            output_path = generate_output_path(
                keep_file=keep_file,
                save_dir=save_dir,
                table_data=table_data
            )
            
            # 调用统一执行器
            keep_format = config.get("excel_keep_format", True)
            self.output_executor.execute_xlsx(
                action=action,
                table_data=table_data,
                output_path=output_path,
                keep_format=keep_format
            )
            
        except Exception as e:
            log(f"Failed to execute XLSX action '{action}': {e}")
            if action == "clipboard":
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.action.clipboard_failed"),
                    ok=False
                )
            else:
                self.notification_manager.notify(
                    "PasteMD",
                    t("workflow.table.export_failed"),
                    ok=False
                )
