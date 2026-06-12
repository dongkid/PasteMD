"""历史记录数据模型."""

from dataclasses import dataclass, field
from datetime import datetime
import json


# INSERT 列到 dataclass 字段的映射，保证 SQL 与 Python 同步
_INSERT_COLUMNS = [
    "created_at", "source_format", "content_type",
    "target_app", "window_title", "workflow_key",
    "conversion_pipeline", "preview", "full_content",
    "output_bytes", "output_file_path", "filters_json",
    "status", "error_msg", "pinned",
]


@dataclass
class HistoryEntry:
    """单条粘贴历史记录，包含完整的粘贴管道元数据。"""

    # 时间
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 内容溯源
    source_format: str = "plain_text"   # html / markdown / plain_text / file
    content_type: str = "markdown"      # markdown / html / latex / table / file / richtext

    # 目标
    target_app: str = ""                # word / wps / excel / wps_excel / onenote / notion / ...
    window_title: str = ""             # 前台窗口标题

    # 工作流信息
    workflow_key: str = ""             # 使用的工作流标识符
    conversion_pipeline: str = "{}"    # JSON: 转换管道信息

    # 内容
    preview: str = ""                  # 前 200 字符预览
    full_content: str = ""             # 完整内容 (可配置不保存)

    # 输出
    output_bytes: int = 0              # 输出字节数 (docx/png/...)
    output_file_path: str = ""         # 生成文件的保存路径 (keep_file=true 时)

    # 过滤器信息
    filters_json: str = "[]"           # JSON: 使用的过滤器列表

    # 状态
    status: str = "success"            # success / fail
    error_msg: str = ""               # 错误信息 (截断至 500 字符)
    pinned: bool = False              # 置顶标记

    @classmethod
    def create(cls, **kwargs) -> "HistoryEntry":
        """工厂方法，过滤未知字段。"""
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in kwargs.items() if k in valid})

    @classmethod
    def insert_sql(cls) -> str:
        """根据 _INSERT_COLUMNS 生成 INSERT 语句，保证列与值同步。"""
        cols = ", ".join(_INSERT_COLUMNS)
        placeholders = ", ".join("?" * len(_INSERT_COLUMNS))
        return f"INSERT INTO paste_history ({cols}) VALUES ({placeholders})"

    def to_row(self) -> tuple:
        """转换为 SQLite INSERT 元组，顺序与 insert_sql() 列一致。"""
        return (
            self.created_at, self.source_format, self.content_type,
            self.target_app, self.window_title, self.workflow_key,
            self.conversion_pipeline, self.preview,
            self.full_content, self.output_bytes, self.output_file_path,
            self.filters_json, self.status, self.error_msg[:500],
            1 if self.pinned else 0,
        )
