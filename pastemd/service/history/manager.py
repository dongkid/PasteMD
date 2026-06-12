"""HistoryManager - 线程安全的历史记录 SQLite + FTS5 存储服务."""

import os
import queue
import sqlite3
import threading
import time
from typing import Optional

from ...config.paths import get_history_db_path
from ...utils.logging import log
from ...config.loader import ConfigLoader
from ...core.state import app_state
from .models import HistoryEntry

# DDL – 完整的粘贴管道元数据
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

# 兼容迁移: 为旧表添加缺失列
MIGRATIONS = [
    "ALTER TABLE paste_history ADD COLUMN workflow_key TEXT DEFAULT ''",
    "ALTER TABLE paste_history ADD COLUMN conversion_pipeline TEXT DEFAULT '{}'",
    "ALTER TABLE paste_history ADD COLUMN output_bytes INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE paste_history ADD COLUMN output_file_path TEXT DEFAULT ''",
    "ALTER TABLE paste_history ADD COLUMN filters_json TEXT DEFAULT '[]'",
]


class HistoryManager:
    """线程安全的历史记录管理器。"""

    def __init__(self, config_loader: ConfigLoader):
        self._db_path = get_history_db_path()
        self._config_loader = config_loader
        self._write_queue: queue.Queue = queue.Queue(maxsize=2000)
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._local = threading.local()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def _config(self) -> dict:
        return app_state.config.get("history", {})

    @property
    def _enabled(self) -> bool:
        return self._config.get("enabled", True)

    def start(self) -> None:
        if self._worker is not None:
            return
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        self._ensure_schema()
        self._run_cleanup()
        log("HistoryManager started")

    def stop(self) -> None:
        if self._worker is None:
            return
        self._stop_event.set()
        self._write_queue.put(None)
        self._worker.join(timeout=5.0)
        self._worker = None
        log("HistoryManager stopped")

    # ------------------------------------------------------------------
    # Public API – record
    # ------------------------------------------------------------------

    def record(self, entry: HistoryEntry) -> None:
        if not self._enabled:
            return
        try:
            self._write_queue.put_nowait(entry)
        except queue.Full:
            log("History write queue full, dropping entry")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API – multi-condition search
    # ------------------------------------------------------------------

    def search(self, keyword: str = "", limit: int = 50,
               status_filter: str = "", target_filter: str = "",
               content_type_filter: str = "", workflow_filter: str = "",
               date_from: str = "", date_to: str = "",
               sort_by: str = "created_at", order: str = "DESC",
               offset: int = 0) -> list[dict]:
        """多条件搜索 / 过滤查询。

        有 keyword → FTS5 + 后过滤
        无 keyword → 直接用 query 的 WHERE 条件
        """
        keyword = (keyword or "").strip()
        conn = self._get_read_conn()

        if keyword:
            return self._fts_search(conn, keyword, limit, offset,
                                    status_filter, target_filter,
                                    content_type_filter, workflow_filter,
                                    date_from, date_to,
                                    sort_by, order)

        return self._filtered_query(conn, limit, offset, sort_by, order,
                                    status_filter, target_filter,
                                    content_type_filter, workflow_filter,
                                    date_from, date_to)

    def count(self, status_filter: str = "", target_filter: str = "",
              content_type_filter: str = "", workflow_filter: str = "",
              date_from: str = "", date_to: str = "", keyword: str = "") -> int:
        keyword = (keyword or "").strip()
        conn = self._get_read_conn()
        if keyword:
            if len(keyword) < 3:
                pattern = f"%{keyword}%"
                like_where, like_params = self._build_where(
                    status_filter, target_filter,
                    content_type_filter, workflow_filter,
                    date_from, date_to,
                    extra_where="(preview LIKE ? OR full_content LIKE ? OR "
                                "window_title LIKE ? OR target_app LIKE ? OR "
                                "workflow_key LIKE ?)",
                    extra_params=[pattern, pattern, pattern, pattern, pattern],
                )
                row = conn.execute(
                    f"SELECT COUNT(*) FROM paste_history {like_where}", like_params
                ).fetchone()
            else:
                try:
                    sql = """SELECT COUNT(*) FROM paste_history h
                             JOIN paste_history_fts f ON h.id = f.rowid
                             WHERE paste_history_fts MATCH ?"""
                    row = conn.execute(sql, (keyword,)).fetchone()
                except Exception:
                    pattern = f"%{keyword}%"
                    like_where, like_params = self._build_where(
                        status_filter, target_filter,
                        content_type_filter, workflow_filter,
                        date_from, date_to,
                        extra_where="(preview LIKE ? OR full_content LIKE ? OR "
                                    "window_title LIKE ? OR target_app LIKE ? OR "
                                    "workflow_key LIKE ?)",
                        extra_params=[pattern, pattern, pattern, pattern, pattern],
                    )
                    row = conn.execute(
                        f"SELECT COUNT(*) FROM paste_history {like_where}", like_params
                    ).fetchone()
            return row[0] if row else 0

        where, params = self._build_where(status_filter, target_filter,
                                          content_type_filter, workflow_filter,
                                          date_from, date_to)
        row = conn.execute(f"SELECT COUNT(*) FROM paste_history {where}", params).fetchone()
        return row[0] if row else 0

    def query(self, limit: int = 100, offset: int = 0,
              sort_by: str = "created_at", order: str = "DESC",
              status_filter: str = "", target_filter: str = "",
              content_type_filter: str = "", workflow_filter: str = "",
              date_from: str = "", date_to: str = "") -> list[dict]:
        conn = self._get_read_conn()
        return self._filtered_query(conn, limit, offset, sort_by, order,
                                    status_filter, target_filter,
                                    content_type_filter, workflow_filter,
                                    date_from, date_to)

    # ------------------------------------------------------------------
    # Public API – CRUD
    # ------------------------------------------------------------------

    def get_entry(self, entry_id: int) -> Optional[dict]:
        conn = self._get_read_conn()
        row = conn.execute("SELECT * FROM paste_history WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def delete_entry(self, entry_id: int) -> None:
        self._enqueue_write(("delete", entry_id))

    def clear_all(self) -> None:
        self._enqueue_write(("clear",))

    def toggle_pin(self, entry_id: int) -> None:
        self._enqueue_write(("pin", entry_id))

    def get_stats(self) -> dict:
        conn = self._get_read_conn()
        total = conn.execute("SELECT COUNT(*) FROM paste_history").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM paste_history WHERE created_at >= date('now','localtime')"
        ).fetchone()[0]
        week = conn.execute(
            "SELECT COUNT(*) FROM paste_history WHERE created_at >= date('now','localtime','-7 days')"
        ).fetchone()[0]
        try:
            file_size = sum(
                os.path.getsize(p)
                for p in [self._db_path, self._db_path + "-wal", self._db_path + "-shm"]
                if os.path.isfile(p)
            )
        except Exception:
            file_size = 0
        return {"total": total, "today": today, "week": week, "file_size_kb": round(file_size / 1024, 1)}

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            for ddl in DDL_STATEMENTS:
                conn.execute(ddl)

            # 迁移: 为旧表添加缺失列
            existing = {r[1] for r in conn.execute("PRAGMA table_info('paste_history')").fetchall()}
            for mig in MIGRATIONS:
                col_name = mig.split("ADD COLUMN ")[1].split(" ")[0]
                if col_name not in existing:
                    try:
                        conn.execute(mig)
                    except Exception:
                        pass

            # 迁移 FTS5 → trigram
            cur = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='paste_history_fts'"
            )
            row = cur.fetchone()
            if row and "tokenize='trigram'" not in row[0]:
                conn.execute("DROP TABLE IF EXISTS paste_history_fts")
                conn.execute(DDL_STATEMENTS[8])
                conn.execute(
                    "INSERT INTO paste_history_fts(rowid, preview, full_content, "
                    "window_title, target_app, workflow_key) "
                    "SELECT id, preview, full_content, window_title, target_app, workflow_key "
                    "FROM paste_history"
                )

            for trigger in TRIGGERS_SQL:
                conn.execute(trigger)
            conn.commit()
        except Exception as e:
            log(f"HistoryManager schema error: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internals – search
    # ------------------------------------------------------------------

    def _fts_search(self, conn, keyword, limit, offset,
                    status_filter, target_filter, content_type_filter,
                    workflow_filter, date_from, date_to,
                    sort_by="created_at", order="DESC") -> list[dict]:
        """FTS5 + LIKE 混合搜索，带后过滤。"""
        order_dir = "DESC" if order.upper() == "DESC" else "ASC"

        fetch_limit = max(limit * 4, 500)

        if len(keyword) < 3:
            raw = self._search_like_raw(conn, keyword, fetch_limit,
                                         status_filter, target_filter,
                                         content_type_filter, workflow_filter,
                                         date_from, date_to,
                                         sort_by, order_dir)
            dicts = [self._row_to_dict(r) for r in raw]
        else:
            try:
                sql = f"""SELECT h.id, h.created_at, h.source_format, h.content_type,
                                h.target_app, h.window_title, h.workflow_key,
                                h.conversion_pipeline, h.preview, h.status,
                                h.error_msg, h.pinned, h.full_content,
                                h.output_bytes, h.output_file_path, h.filters_json
                         FROM paste_history h
                         JOIN paste_history_fts f ON h.id = f.rowid
                         WHERE paste_history_fts MATCH ?
                         ORDER BY rank
                         LIMIT ?"""
                raw = conn.execute(sql, (keyword, fetch_limit)).fetchall()
                dicts = self._post_filter_rows(raw, status_filter, target_filter,
                                               content_type_filter, workflow_filter,
                                               date_from, date_to)
            except Exception:
                raw = self._search_like_raw(conn, keyword, fetch_limit,
                                             status_filter, target_filter,
                                             content_type_filter, workflow_filter,
                                             date_from, date_to,
                                             sort_by, order_dir)
                dicts = [self._row_to_dict(r) for r in raw]

        key_fn = self._make_sort_key(sort_by, order_dir)
        dicts.sort(key=key_fn, reverse=(order_dir == "DESC"))
        return dicts[offset:offset + limit]

    def _search_like_raw(self, conn, keyword, limit,
                         status_filter, target_filter, content_type_filter,
                         workflow_filter, date_from, date_to,
                         sort_by="created_at", order="DESC"):
        pattern = f"%{keyword}%"
        like_part = "(preview LIKE ? OR full_content LIKE ? OR window_title LIKE ? OR target_app LIKE ? OR workflow_key LIKE ?)"
        where, params = self._build_where(
            status_filter, target_filter, content_type_filter, workflow_filter,
            date_from, date_to,
            extra_where=like_part, extra_params=[pattern, pattern, pattern, pattern, pattern],
        )
        valid = {"created_at", "target_app", "content_type", "status", "pinned", "workflow_key"}
        sort_col = sort_by if sort_by in valid else "created_at"
        order_dir = "DESC" if order.upper() == "DESC" else "ASC"
        sql = f"""SELECT id, created_at, source_format, content_type,
                         target_app, window_title, workflow_key,
                         conversion_pipeline, preview, status,
                         error_msg, pinned, full_content,
                         output_bytes, output_file_path, filters_json
                  FROM paste_history {where}
                  ORDER BY pinned DESC, {sort_col} {order_dir} LIMIT ?"""
        return conn.execute(sql, params + [limit]).fetchall()

    def _filtered_query(self, conn, limit, offset, sort_by, order,
                        status_filter, target_filter, content_type_filter,
                        workflow_filter, date_from, date_to) -> list[dict]:
        valid = {"created_at", "target_app", "content_type", "status", "pinned", "workflow_key"}
        if sort_by not in valid:
            sort_by = "created_at"
        order = "DESC" if order.upper() == "DESC" else "ASC"
        where, params = self._build_where(status_filter, target_filter,
                                          content_type_filter, workflow_filter,
                                          date_from, date_to)
        sql = f"""SELECT id, created_at, source_format, content_type,
                         target_app, window_title, workflow_key,
                         conversion_pipeline, preview, status,
                         error_msg, pinned, full_content,
                         output_bytes, output_file_path, filters_json
                  FROM paste_history {where}
                  ORDER BY pinned DESC, {sort_by} {order}
                  LIMIT ? OFFSET ?"""
        rows = conn.execute(sql, params + [limit, offset]).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _post_filter_rows(self, rows, status_filter, target_filter,
                          content_type_filter, workflow_filter,
                          date_from, date_to):
        result = []
        for row in rows:
            d = self._row_to_dict(row)
            if status_filter and d["status"] != status_filter:
                continue
            if target_filter and d["target_app"] != target_filter:
                continue
            if content_type_filter and d["content_type"] != content_type_filter:
                continue
            if workflow_filter and d["workflow_key"] != workflow_filter:
                continue
            if date_from and d["created_at"] < date_from:
                continue
            if date_to and d["created_at"] > date_to:
                continue
            result.append(d)
        return result

    @staticmethod
    def _make_sort_key(sort_by: str, order: str):
        """Build a sort key function for the given column and direction."""
        pinned_first = -1 if order == "DESC" else 1
        def _key(d: dict):
            pinned = pinned_first if d.get("pinned") else 0
            val = d.get(sort_by, "")
            return (pinned, val)
        return _key

    @staticmethod
    def _build_where(status_filter="", target_filter="",
                     content_type_filter="", workflow_filter="",
                     date_from="", date_to="",
                     extra_where="", extra_params=None):
        parts = []
        params = []
        if extra_where:
            parts.append(extra_where)
            if extra_params:
                params.extend(extra_params)
        if status_filter:
            parts.append("status = ?"); params.append(status_filter)
        if target_filter:
            parts.append("target_app = ?"); params.append(target_filter)
        if content_type_filter:
            parts.append("content_type = ?"); params.append(content_type_filter)
        if workflow_filter:
            parts.append("workflow_key = ?"); params.append(workflow_filter)
        if date_from:
            parts.append("created_at >= ?"); params.append(date_from)
        if date_to:
            parts.append("created_at <= ?"); params.append(date_to)
        where = ("WHERE " + " AND ".join(parts)) if parts else ""
        return where, params

    # ------------------------------------------------------------------
    # Internals – write
    # ------------------------------------------------------------------

    def _enqueue_write(self, action) -> None:
        try:
            self._write_queue.put_nowait(action)
        except Exception:
            pass

    def _run_cleanup(self) -> None:
        cfg = self._config
        if not cfg.get("auto_cleanup", True):
            return
        self._enqueue_write(("cleanup", cfg.get("max_entries", 500), cfg.get("ttl_days", 90)))

    def _get_write_conn(self) -> sqlite3.Connection:
        if not hasattr(self, "_write_conn") or self._write_conn is None:
            self._write_conn = sqlite3.connect(self._db_path)
            self._write_conn.execute("PRAGMA journal_mode = WAL")
            self._write_conn.execute("PRAGMA synchronous = NORMAL")
            self._write_conn.execute("PRAGMA busy_timeout = 5000")
            self._write_conn.execute("PRAGMA cache_size = -16000")
        return self._write_conn

    def _get_read_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "read_conn") or self._local.read_conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA busy_timeout = 3000")
            self._local.read_conn = conn
        return self._local.read_conn

    def _worker_loop(self) -> None:
        conn = self._get_write_conn()
        while not self._stop_event.is_set():
            try:
                item = self._write_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            if item is None:
                break
            try:
                if isinstance(item, HistoryEntry):
                    cfg = self._config
                    if not cfg.get("dedup_minutes", 0) or not self._is_duplicate(conn, item, cfg.get("dedup_minutes", 0)):
                        conn.execute(HistoryEntry.insert_sql(), item.to_row())
                        conn.commit()
                        self._enforce_max(conn)
                elif isinstance(item, tuple):
                    self._handle_action(conn, item)
            except Exception as e:
                log(f"HistoryManager write error: {e}")

        try:
            conn.close()
        except Exception:
            pass

    def _handle_action(self, conn, action):
        kind = action[0]
        if kind == "delete":
            conn.execute("DELETE FROM paste_history WHERE id = ?", (action[1],)); conn.commit()
        elif kind == "clear":
            conn.execute("DELETE FROM paste_history")
            conn.execute("DELETE FROM paste_history_fts"); conn.commit()
        elif kind == "pin":
            conn.execute("UPDATE paste_history SET pinned = 1 - pinned WHERE id = ?", (action[1],)); conn.commit()
        elif kind == "cleanup":
            ttl = action[2] if len(action) > 2 else 90
            mx  = action[1] if len(action) > 1 else 500
            self._cleanup_expired(conn, ttl)
            self._enforce_max(conn, mx)

    def _enforce_max(self, conn, mx=None):
        if mx is None:
            mx = self._config.get("max_entries", 500)
        conn.execute(
            """DELETE FROM paste_history WHERE id NOT IN (
                SELECT id FROM paste_history ORDER BY pinned DESC, created_at DESC LIMIT ?)""",
            (mx,),
        )
        conn.commit()

    def _cleanup_expired(self, conn, ttl_days):
        conn.execute(
            """DELETE FROM paste_history WHERE pinned = 0
               AND created_at < datetime('now','localtime',?)""",
            (f"-{ttl_days} days",),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_duplicate(self, conn, entry: HistoryEntry, window_minutes: int) -> bool:
        """检查 dedup 时间窗口内是否存在重复条目。"""
        sql = """SELECT 1 FROM paste_history
                 WHERE preview = ? AND target_app = ? AND workflow_key = ?
                   AND created_at >= datetime('now','localtime', ?)
                 LIMIT 1"""
        try:
            row = conn.execute(sql, (
                entry.preview, entry.target_app, entry.workflow_key,
                f"-{window_minutes} minutes",
            )).fetchone()
            return row is not None
        except Exception:
            return False

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        if "pinned" in d:
            d["pinned"] = bool(d["pinned"])
        return d

