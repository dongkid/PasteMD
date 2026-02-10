"""macOS Excel spreadsheet placer (HTML clipboard paste)."""

from ..base import ClipboardHTMLSpreadsheetPlacer


class ExcelPlacer(ClipboardHTMLSpreadsheetPlacer):
    """macOS Excel 内容落地器（HTML 剪贴板粘贴方式）"""
    
    app_name = "macOS Excel"
