"""DOCX document post-processing utilities."""

import io
import zipfile
from xml.etree import ElementTree as ET

from docx import Document
from ..utils.logging import log


class DocxProcessor:
    """DOCX 文档后处理器 - 用于修改已生成的 DOCX 文档样式"""
    
    @staticmethod
    def normalize_first_paragraph_style(
        docx_bytes: bytes,
        target_style: str = "Body Text"
    ) -> bytes:
        """
        将 DOCX 文档中的 "First Paragraph" 样式替换为指定样式
        
        Args:
            docx_bytes: DOCX 文件的字节流
            target_style: 目标样式名称，默认为 "Body Text"
            
        Returns:
            修改后的 DOCX 文件字节流
        """
        try:
            # 从字节流加载文档
            doc = Document(io.BytesIO(docx_bytes))
            
            # 统计修改的段落数量
            modified_count = 0
            
            # 遍历所有段落
            for paragraph in doc.paragraphs:
                # 检查段落样式是否为 "First Paragraph"
                if paragraph.style and paragraph.style.name == "First Paragraph":
                    # 修改为目标样式
                    paragraph.style = target_style
                    modified_count += 1
                    log(f"Changed paragraph style from 'First Paragraph' to '{target_style}'")
            
            # 如果有修改，记录日志
            if modified_count > 0:
                log(f"Total {modified_count} paragraph(s) changed from 'First Paragraph' to '{target_style}'")
            else:
                log("No 'First Paragraph' style found in document")
            
            # 将修改后的文档保存到字节流
            output_stream = io.BytesIO()
            doc.save(output_stream)
            output_stream.seek(0)
            
            return output_stream.read()
            
        except Exception as e:
            log(f"Failed to process DOCX styles: {type(e).__name__}: {e}")
            # 如果处理失败，返回原始字节流
            return docx_bytes

    @staticmethod
    def replace_horizontal_rules_with_paragraph_borders(docx_bytes: bytes) -> bytes:
        """
        将 Pandoc 生成的 VML 横线替换为 Word/WPS 更兼容的段落边框。

        Pandoc 的 Markdown HorizontalRule 在 DOCX 中会生成
        ``<w:pict><v:rect ... o:hr="t" /></w:pict>``。WPS 可能把这个结构显示
        成矩形块；段落边框更接近 Word/WPS 手动输入 ``---`` 后回车的结果。
        """
        namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
            "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
            "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
            "v": "urn:schemas-microsoft-com:vml",
            "o": "urn:schemas-microsoft-com:office:office",
            "w10": "urn:schemas-microsoft-com:office:word",
        }
        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)

        document_path = "word/document.xml"

        try:
            input_stream = io.BytesIO(docx_bytes)
            output_stream = io.BytesIO()

            with zipfile.ZipFile(input_stream, "r") as zin:
                document_xml = zin.read(document_path)
                root = ET.fromstring(document_xml)

                modified_count = 0
                for paragraph in root.findall(".//w:p", namespaces):
                    rects = paragraph.findall(".//v:rect", namespaces)
                    if not any(rect.get(f"{{{namespaces['o']}}}hr") == "t" for rect in rects):
                        continue

                    paragraph.clear()
                    ppr = ET.SubElement(paragraph, f"{{{namespaces['w']}}}pPr")
                    spacing = ET.SubElement(ppr, f"{{{namespaces['w']}}}spacing")
                    spacing.set(f"{{{namespaces['w']}}}before", "0")
                    spacing.set(f"{{{namespaces['w']}}}after", "0")
                    pbdr = ET.SubElement(ppr, f"{{{namespaces['w']}}}pBdr")
                    bottom = ET.SubElement(pbdr, f"{{{namespaces['w']}}}bottom")
                    bottom.set(f"{{{namespaces['w']}}}val", "single")
                    bottom.set(f"{{{namespaces['w']}}}sz", "6")
                    bottom.set(f"{{{namespaces['w']}}}space", "1")
                    bottom.set(f"{{{namespaces['w']}}}color", "auto")
                    modified_count += 1

                if modified_count == 0:
                    log("No VML horizontal rule found in DOCX")
                    return docx_bytes

                updated_document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

                with zipfile.ZipFile(output_stream, "w") as zout:
                    for item in zin.infolist():
                        data = updated_document_xml if item.filename == document_path else zin.read(item.filename)
                        zout.writestr(item, data)

            output_stream.seek(0)
            log(f"Replaced {modified_count} DOCX horizontal rule(s) with paragraph border(s)")
            return output_stream.read()

        except Exception as e:
            log(f"Failed to replace DOCX horizontal rules: {type(e).__name__}: {e}")
            return docx_bytes
    
    @staticmethod
    def apply_custom_processing(
        docx_bytes: bytes,
        disable_first_para_indent: bool = False,
        target_style: str = "Body Text",
        horizontal_rule_style: str = "default",
    ) -> bytes:
        """
        对 DOCX 文档应用自定义后处理
        
        Args:
            docx_bytes: DOCX 文件的字节流
            disable_first_para_indent: 是否禁用第一段特殊格式（替换 First Paragraph 样式）
            target_style: 目标样式名称
            horizontal_rule_style: 水平线样式，paragraph_border 时转为段落边框
            
        Returns:
            处理后的 DOCX 文件字节流
        """
        # 如果需要禁用第一段特殊格式
        if disable_first_para_indent:
            docx_bytes = DocxProcessor.normalize_first_paragraph_style(
                docx_bytes,
                target_style
            )
        
        if horizontal_rule_style == "paragraph_border":
            docx_bytes = DocxProcessor.replace_horizontal_rules_with_paragraph_borders(
                docx_bytes
            )
        
        return docx_bytes
