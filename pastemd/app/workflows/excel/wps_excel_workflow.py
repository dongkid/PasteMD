"""WPS Excel spreadsheet workflow."""

from pastemd.app.workflows.excel.excel_base import ExcelBaseWorkflow
from pastemd.service.spreadsheet import WPSExcelPlacer


class WPSExcelWorkflow(ExcelBaseWorkflow):
    """WPS 表格工作流"""

    display_name: str = "WPS Excel"

    def __init__(self):
        super().__init__()
        self._placer = WPSExcelPlacer()

    @property
    def app_name(self) -> str:
        return "WPS 表格"

    @property
    def placer(self):
        return self._placer

