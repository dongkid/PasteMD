"""Settings field type definitions."""

from enum import Enum, auto


class FieldType(Enum):
    """设置字段类型"""
    STRING = auto()
    BOOL = auto()
    NULLABLE_STRING = auto()
    STRING_LIST = auto()


# 设置字段映射表: key -> FieldType
# 平台限制由前端 UI 控制显示，后端统一处理
SETTINGS_FIELD_MAP: dict[str, FieldType] = {
    # 字符串型
    "language": FieldType.STRING,
    "save_dir": FieldType.STRING,
    "pandoc_path": FieldType.STRING,
    "no_app_action": FieldType.STRING,

    # 布尔型
    "keep_file": FieldType.BOOL,
    "notify": FieldType.BOOL,
    "startup_notify": FieldType.BOOL,
    "md_disable_first_para_indent": FieldType.BOOL,
    "html_disable_first_para_indent": FieldType.BOOL,
    "Keep_original_formula": FieldType.BOOL,
    "enable_latex_replacements": FieldType.BOOL,
    "fix_single_dollar_block": FieldType.BOOL,
    "enable_excel": FieldType.BOOL,
    "excel_keep_format": FieldType.BOOL,
    "move_cursor_to_end": FieldType.BOOL,

    # 可空字符串
    "reference_docx": FieldType.NULLABLE_STRING,

    # 列表型
    "pandoc_filters": FieldType.STRING_LIST,
    "pandoc_request_headers": FieldType.STRING_LIST,
}
