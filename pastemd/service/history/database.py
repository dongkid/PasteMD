"""HistoryDatabase - 数据库 schema 定义与迁移管理."""

import sqlite3

DDL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS paste_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        source_format TEXT NOT NULL DEFAULT 'plain_text',
        content_type TEXT NOT NULL DEFAULT 'markdown',
        target_app TEXT DEFAULT '',
        window_title TEXT DEFAULT '',
        workflow_key TEXT DEFAULT '',
        conversion_pipeline TEXT DEFAULT '{}',
        preview TEXT NOT NULL DEFAULT '',
        full_content TEXT DEFAULT '',
        original_html TEXT DEFAULT '',
        output_bytes INTEGER NOT NULL DEFAULT 0,
        output_file_path TEXT DEFAULT '',
        filters_json TEXT DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'success',
        error_msg TEXT DEFAULT '',
        pinned INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_hist_created ON paste_history(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_hist_status ON paste_history(status)",
    "CREATE INDEX IF NOT EXISTS idx_hist_target ON paste_history(target_app)",
    "CREATE INDEX IF NOT EXISTS idx_hist_srcfmt ON paste_history(source_format)",
    "CREATE INDEX IF NOT EXISTS idx_hist_content_type ON paste_history(content_type)",
    "CREATE INDEX IF NOT EXISTS idx_hist_workflow ON paste_history(workflow_key)",
    "CREATE INDEX IF NOT EXISTS idx_hist_pinned ON paste_history(pinned)",
    """CREATE VIRTUAL TABLE IF NOT EXISTS paste_history_fts USING fts5(
        preview, full_content, window_title, target_app, workflow_key,
        content='paste_history', content_rowid='id',
        tokenize='trigram'
    )""",
]

TRIGGERS_SQL = [
    """CREATE TRIGGER IF NOT EXISTS hist_fts_ai AFTER INSERT ON paste_history BEGIN
        INSERT INTO paste_history_fts(rowid, preview, full_content, window_title, target_app, workflow_key)
        VALUES (new.id, new.preview, new.full_content, new.window_title, new.target_app, new.workflow_key);
    END""",
    """CREATE TRIGGER IF NOT EXISTS hist_fts_ad AFTER DELETE ON paste_history BEGIN
        INSERT INTO paste_history_fts(paste_history_fts, rowid, preview, full_content, window_title, target_app, workflow_key)
        VALUES('delete', old.id, old.preview, old.full_content, old.window_title, old.target_app, old.workflow_key);
    END""",
    """CREATE TRIGGER IF NOT EXISTS hist_fts_au AFTER UPDATE ON paste_history BEGIN
        INSERT INTO paste_history_fts(paste_history_fts, rowid, preview, full_content, window_title, target_app, workflow_key)
        VALUES('delete', old.id, old.preview, old.full_content, old.window_title, old.target_app, old.workflow_key);
        INSERT INTO paste_history_fts(rowid, preview, full_content, window_title, target_app, workflow_key)
        VALUES (new.id, new.preview, new.full_content, new.window_title, new.target_app, new.workflow_key);
    END""",
]

MIGRATIONS = [
    "ALTER TABLE paste_history ADD COLUMN workflow_key TEXT DEFAULT ''",
    "ALTER TABLE paste_history ADD COLUMN conversion_pipeline TEXT DEFAULT '{}'",
    "ALTER TABLE paste_history ADD COLUMN output_bytes INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE paste_history ADD COLUMN output_file_path TEXT DEFAULT ''",
    "ALTER TABLE paste_history ADD COLUMN filters_json TEXT DEFAULT '[]'",
    "ALTER TABLE paste_history ADD COLUMN original_html TEXT DEFAULT ''",
]


class HistoryDatabase:
    """纯 SQL schema 管理与迁移。"""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def ensure_schema(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            for ddl in DDL_STATEMENTS:
                conn.execute(ddl)

            existing = {r[1] for r in conn.execute("PRAGMA table_info('paste_history')").fetchall()}
            for mig in MIGRATIONS:
                col_name = mig.split("ADD COLUMN ")[1].split(" ")[0]
                if col_name not in existing:
                    try:
                        conn.execute(mig)
                    except Exception:
                        pass

            # 迁移 FTS5：检查 tokenizer 或列是否过时
            fts5_ddl = [s for s in DDL_STATEMENTS if "fts5" in s.lower()][0]
            cur = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='paste_history_fts'"
            )
            row = cur.fetchone()
            needs_rebuild = False
            if row:
                fts_sql = row[0]
                if "tokenize='trigram'" not in fts_sql:
                    needs_rebuild = True
                elif "full_content" not in fts_sql.lower():
                    needs_rebuild = True
            if needs_rebuild:
                conn.execute("DROP TABLE IF EXISTS paste_history_fts")
                conn.execute(fts5_ddl)
                conn.execute(
                    "INSERT INTO paste_history_fts(rowid, preview, full_content, "
                    "window_title, target_app, workflow_key) "
                    "SELECT id, preview, full_content, window_title, target_app, workflow_key "
                    "FROM paste_history"
                )

            for trigger in TRIGGERS_SQL:
                conn.execute(trigger)
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
