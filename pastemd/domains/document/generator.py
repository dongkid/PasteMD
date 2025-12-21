"""Document generator service - centralized DOCX generation and conversion."""

from typing import Optional

from ...integrations.pandoc import PandocIntegration
from ...utils.docx_processor import DocxProcessor
from ...utils.fs import generate_output_path
from ...utils.latex import convert_latex_delimiters
from ...utils.md_normalizer import normalize_markdown
from ...utils.logging import log
from ...core.state import app_state
from ...core.errors import PandocError
from ...config.defaults import DEFAULT_CONFIG
from ...config.loader import ConfigLoader


class DocumentGeneratorService:
    """
    文档生成服务
    
    负责 Markdown/HTML → DOCX 的转换，管理 Pandoc 初始化与兜底逻辑。
    不做任何通知/UI 操作，只抛出/透传 PandocError、ClipboardError 等异常。
    """
    
    def __init__(self) -> None:
        self._pandoc_integration: Optional[PandocIntegration] = None
    
    def _ensure_pandoc_integration(self) -> None:
        """
        确保 Pandoc 集成已初始化
        
        优先使用 app_state.config["pandoc_path"]，
        失败后回退到 DEFAULT_CONFIG["pandoc_path"]，
        并回写 app_state.config["pandoc_path"] 并保存配置。
        
        Raises:
            PandocError: 如果 Pandoc 初始化失败
        """
        if self._pandoc_integration is not None:
            return
        
        pandoc_path = app_state.config.get("pandoc_path", "pandoc")
        try:
            self._pandoc_integration = PandocIntegration(pandoc_path)
        except PandocError as e:
            log(f"Failed to initialize PandocIntegration: {e}")
            # 回退到默认路径
            try:
                default_path = DEFAULT_CONFIG.get("pandoc_path", "pandoc")
                self._pandoc_integration = PandocIntegration(default_path)
                # 回写配置并保存
                app_state.config["pandoc_path"] = default_path
                config_loader = ConfigLoader()
                config_loader.save(config=app_state.config)
                log(f"Fallback to default pandoc_path: {default_path}")
            except PandocError as e2:
                log(f"Retry to initialize PandocIntegration failed: {e2}")
                self._pandoc_integration = None
                raise PandocError(f"Pandoc initialization failed: {e2}")
    
    def convert_markdown_to_docx_bytes(self, md_text: str, config: dict) -> bytes:
        """
        将 Markdown 文本转换为 DOCX 字节流
        
        等价于原 _handle_word_flow 中的转换逻辑：
        normalize_markdown + convert_latex_delimiters + pandoc.convert_to_docx_bytes + DocxProcessor 首段缩进处理
        
        Args:
            md_text: Markdown 文本
            config: 配置字典
            
        Returns:
            DOCX 文件的字节流
            
        Raises:
            PandocError: 转换失败时
        """
        # 1. 规范化 Markdown 格式
        md_text = normalize_markdown(md_text)
        
        # 2. 处理 LaTeX 公式
        fix_dollar = config.get("fix_single_dollar_block", True)
        md_text = convert_latex_delimiters(md_text, fix_single_dollar_block=fix_dollar)
        
        # 3. 转换为 DOCX 字节流
        self._ensure_pandoc_integration()
        docx_bytes = self._pandoc_integration.convert_to_docx_bytes(
            md_text=md_text,
            reference_docx=config.get("reference_docx"),
            Keep_original_formula=config.get("Keep_original_formula", False),
            enable_latex_replacements=config.get("enable_latex_replacements", True),
            custom_filters=config.get("pandoc_filters", []),
            cwd=config.get("save_dir"),
        )
        
        # 4. 处理 DOCX 样式
        if config.get("md_disable_first_para_indent", True):
            docx_bytes = DocxProcessor.apply_custom_processing(
                docx_bytes,
                disable_first_para_indent=True,
                target_style="Body Text"
            )
        
        return docx_bytes
    
    def convert_html_to_docx_bytes(self, html_text: str, config: dict) -> bytes:
        """
        将 HTML 文本转换为 DOCX 字节流
        
        等价于原 _handle_html_to_word_flow 中的转换逻辑：
        pandoc.convert_html_to_docx_bytes + DocxProcessor 首段缩进处理
        
        Args:
            html_text: HTML 文本
            config: 配置字典
            
        Returns:
            DOCX 文件的字节流
            
        Raises:
            PandocError: 转换失败时
        """
        # 1. 转换为 DOCX 字节流
        self._ensure_pandoc_integration()
        docx_bytes = self._pandoc_integration.convert_html_to_docx_bytes(
            html_text=html_text,
            reference_docx=config.get("reference_docx"),
            Keep_original_formula=config.get("Keep_original_formula", False),
            enable_latex_replacements=config.get("enable_latex_replacements", True),
            custom_filters=config.get("pandoc_filters", []),
            cwd=config.get("save_dir"),
        )
        
        # 2. 处理 DOCX 样式
        if config.get("html_disable_first_para_indent", True):
            docx_bytes = DocxProcessor.apply_custom_processing(
                docx_bytes,
                disable_first_para_indent=True,
                target_style="Body Text"
            )
        
        return docx_bytes
    
    def generate_docx_file_from_markdown(
        self,
        md_text: str,
        config: dict,
        keep_file: bool = True
    ) -> tuple[bytes, str]:
        """
        从 Markdown 生成 DOCX 字节流和输出路径
        
        逻辑与旧 _generate_docx_from_markdown 完全一致。
        
        Args:
            md_text: Markdown 文本
            config: 配置字典
            keep_file: 是否持久化保存文件（影响输出路径生成）
            
        Returns:
            (docx_bytes, output_path) 元组
            
        Raises:
            PandocError: 转换失败时
        """
        # 1. 规范化 Markdown 格式
        md_text = normalize_markdown(md_text)
        
        # 2. 处理 LaTeX 公式
        fix_dollar = config.get("fix_single_dollar_block", True)
        md_text = convert_latex_delimiters(md_text, fix_single_dollar_block=fix_dollar)
        
        # 3. 生成输出路径
        output_path = generate_output_path(
            keep_file=keep_file,
            save_dir=config.get("save_dir", ""),
            md_text=md_text
        )
        
        # 4. 转换为 DOCX 字节流
        self._ensure_pandoc_integration()
        docx_bytes = self._pandoc_integration.convert_to_docx_bytes(
            md_text=md_text,
            reference_docx=config.get("reference_docx"),
            Keep_original_formula=config.get("Keep_original_formula", False),
            enable_latex_replacements=config.get("enable_latex_replacements", True),
            custom_filters=config.get("pandoc_filters", []),
            cwd=config.get("save_dir"),
        )
        
        # 5. 处理 DOCX 样式
        if config.get("md_disable_first_para_indent", True):
            docx_bytes = DocxProcessor.apply_custom_processing(
                docx_bytes,
                disable_first_para_indent=True,
                target_style="Body Text"
            )
        
        return docx_bytes, output_path
    
    def generate_docx_file_from_html(
        self,
        md_text: str,
        config: dict,
        html_text: Optional[str] = None,
        keep_file: bool = True
    ) -> tuple[bytes, str]:
        """
        从 HTML 生成 DOCX 字节流和输出路径
        
        逻辑与旧 _generate_docx_from_html 完全一致。
        
        Args:
            md_text: Markdown 文本（用于生成文件名）
            config: 配置字典
            html_text: HTML 文本，如果为 None 需由调用方提供
            keep_file: 是否持久化保存文件（影响输出路径生成）
            
        Returns:
            (docx_bytes, output_path) 元组
            
        Raises:
            PandocError: 转换失败时
            ValueError: html_text 为 None 时
        """
        if html_text is None:
            raise ValueError("html_text is required for generate_docx_file_from_html")
        
        log(f"Retrieved HTML from clipboard, length: {len(html_text)}")
        
        # 1. 转换为 DOCX 字节流
        self._ensure_pandoc_integration()
        docx_bytes = self._pandoc_integration.convert_html_to_docx_bytes(
            html_text=html_text,
            reference_docx=config.get("reference_docx"),
            Keep_original_formula=config.get("Keep_original_formula", False),
            enable_latex_replacements=config.get("enable_latex_replacements", True),
            custom_filters=config.get("pandoc_filters", []),
            cwd=config.get("save_dir"),
        )
        
        # 2. 处理 DOCX 样式
        if config.get("html_disable_first_para_indent", True):
            docx_bytes = DocxProcessor.apply_custom_processing(
                docx_bytes,
                disable_first_para_indent=True,
                target_style="Body Text"
            )
        
        # 3. 生成输出路径
        output_path = generate_output_path(
            keep_file=keep_file,
            save_dir=config.get("save_dir", ""),
            md_text=md_text,
            html_text=html_text
        )
        
        return docx_bytes, output_path