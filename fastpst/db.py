"""
FastPST - SQLite3 Database & FTS5 Search Indexer
Stores parsed email metadata, bodies, headers, and attachments.
Provides sub-millisecond full-text search using SQLite's FTS5 engine.
"""

import sqlite3
import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("fastpst.db")


class DatabaseManager:
    """Manages SQLite connection, schema, indexing, and FTS5 search."""

    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a connection with Row factory configured."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def init_db(self):
        """Initializes tables, indexes, and FTS5 virtual tables."""
        conn = self.get_connection()
        try:
            with conn:
                # 1. Indexed files table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS indexed_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT UNIQUE NOT NULL,
                        file_size INTEGER NOT NULL,
                        last_modified REAL NOT NULL,
                        indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_emails INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'indexed'
                    );
                """)

                # 1b. System state table (for high-water mark timestamp anti-tamper)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """)

                # 2. Emails table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS emails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        folder_path TEXT NOT NULL,
                        message_index INTEGER NOT NULL,
                        subject TEXT,
                        sender TEXT,
                        sender_name TEXT,
                        sender_email TEXT,
                        recipients TEXT,
                        date_sent TEXT,
                        plain_body TEXT,
                        html_body TEXT,
                        headers TEXT,
                        has_attachments INTEGER DEFAULT 0,
                        attachments_json TEXT,
                        body_snippet TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(file_path, folder_path, message_index)
                    );
                """)

                # Indexes for fast filtering and sorting
                conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date_sent DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_file ON emails(file_path);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);")

                # 3. FTS5 Virtual Table for full-text search
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
                        subject,
                        sender,
                        recipients,
                        plain_body,
                        content='emails',
                        content_rowid='id'
                    );
                """)

                # 4. Triggers to automatically sync emails with emails_fts
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
                        INSERT INTO emails_fts(rowid, subject, sender, recipients, plain_body)
                        VALUES (new.id, new.subject, new.sender, new.recipients, new.plain_body);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
                        INSERT INTO emails_fts(emails_fts, rowid, subject, sender, recipients, plain_body)
                        VALUES('delete', old.id, old.subject, old.sender, old.recipients, old.plain_body);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
                        INSERT INTO emails_fts(emails_fts, rowid, subject, sender, recipients, plain_body)
                        VALUES('delete', old.id, old.subject, old.sender, old.recipients, old.plain_body);
                        INSERT INTO emails_fts(rowid, subject, sender, recipients, plain_body)
                        VALUES (new.id, new.subject, new.sender, new.recipients, new.plain_body);
                    END;
                """)
        finally:
            conn.close()

    def is_file_indexed_and_current(self, file_path: str, file_size: int, mtime: float) -> bool:
        """Returns True if the file has already been indexed and hasn't changed."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_size, last_modified FROM indexed_files WHERE file_path = ?",
                (os.path.abspath(file_path),),
            )
            row = cursor.fetchone()
            if row:
                if row["file_size"] == file_size and abs(row["last_modified"] - mtime) < 1.0:
                    return True
            return False
        finally:
            conn.close()

    def remove_file_records(self, file_path: str):
        """Removes existing email records and file tracking for a file."""
        abs_path = os.path.abspath(file_path)
        conn = self.get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM emails WHERE file_path = ?", (abs_path,))
                conn.execute("DELETE FROM indexed_files WHERE file_path = ?", (abs_path,))
        finally:
            conn.close()

    def insert_emails_batch(self, emails: List[Dict[str, Any]]):
        """Inserts a batch of emails in a single transaction."""
        if not emails:
            return

        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                query = """
                    INSERT OR REPLACE INTO emails (
                        file_path, file_name, folder_path, message_index,
                        subject, sender, sender_name, sender_email, recipients,
                        date_sent, plain_body, html_body, headers,
                        has_attachments, attachments_json, body_snippet
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                rows = []
                for e in emails:
                    rows.append((
                        os.path.abspath(e["file_path"]),
                        e.get("file_name", os.path.basename(e["file_path"])),
                        e.get("folder_path", ""),
                        e.get("message_index", 0),
                        e.get("subject", ""),
                        e.get("sender", ""),
                        e.get("sender_name", ""),
                        e.get("sender_email", ""),
                        e.get("recipients", ""),
                        e.get("date_sent", ""),
                        e.get("plain_body", ""),
                        e.get("html_body", ""),
                        e.get("headers", ""),
                        e.get("has_attachments", 0),
                        json.dumps(e.get("attachments", [])),
                        e.get("body_snippet", ""),
                    ))
                cursor.executemany(query, rows)
        finally:
            conn.close()

    def record_file_indexed(self, file_path: str, file_size: int, mtime: float, total_emails: int):
        """Records file indexing completion."""
        conn = self.get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO indexed_files (
                        file_path, file_size, last_modified, total_emails, status
                    ) VALUES (?, ?, ?, ?, 'indexed')
                """, (os.path.abspath(file_path), file_size, mtime, total_emails))
        finally:
            conn.close()

    def get_all_emails(self, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieves all indexed emails ordered by date descending."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_path, file_name, folder_path, message_index,
                       subject, sender, recipients, date_sent, has_attachments, body_snippet
                FROM emails
                ORDER BY date_sent DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_emails(
        self, query: str, field_filter: str = "all", has_attachments_only: bool = False, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Executes Full-Text Search using SQLite FTS5.
        query: search string (supports prefix matching e.g. "search*")
        field_filter: "all", "subject", "sender", "recipients", "body"
        """
        query = query.strip()
        if not query:
            return self.get_all_emails(limit=limit)

        # Sanitize query for FTS5 syntax
        # Escape double quotes
        sanitized = query.replace('"', '""')
        
        # Build FTS expression
        if field_filter == "subject":
            fts_query = f'subject: "{sanitized}"'
        elif field_filter == "sender":
            fts_query = f'sender: "{sanitized}"'
        elif field_filter == "recipients":
            fts_query = f'recipients: "{sanitized}"'
        elif field_filter == "body":
            fts_query = f'plain_body: "{sanitized}"'
        else:
            # All fields: token search with wildcard support
            tokens = [t for t in sanitized.split() if t]
            if len(tokens) == 1:
                # Single word: append * for prefix search
                fts_query = f'"{tokens[0]}"*'
            else:
                fts_query = f'"{sanitized}"'

        sql = """
            SELECT e.id, e.file_path, e.file_name, e.folder_path, e.message_index,
                   e.subject, e.sender, e.recipients, e.date_sent, e.has_attachments, e.body_snippet,
                   rank
            FROM emails_fts fts
            JOIN emails e ON fts.rowid = e.id
            WHERE emails_fts MATCH ?
        """
        params = [fts_query]

        if has_attachments_only:
            sql += " AND e.has_attachments = 1"

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS query '{fts_query}' failed ({e}), falling back to LIKE query.")
            return self._search_fallback(query, field_filter, has_attachments_only, limit)
        finally:
            conn.close()

    def _search_fallback(self, query: str, field_filter: str, has_attachments_only: bool, limit: int):
        """Fallback to standard SQL LIKE query."""
        like_pattern = f"%{query}%"
        sql = """
            SELECT id, file_path, file_name, folder_path, message_index,
                   subject, sender, recipients, date_sent, has_attachments, body_snippet
            FROM emails
            WHERE 1=1
        """
        params = []
        if field_filter == "subject":
            sql += " AND subject LIKE ?"
            params.append(like_pattern)
        elif field_filter == "sender":
            sql += " AND sender LIKE ?"
            params.append(like_pattern)
        elif field_filter == "recipients":
            sql += " AND recipients LIKE ?"
            params.append(like_pattern)
        elif field_filter == "body":
            sql += " AND (plain_body LIKE ? OR html_body LIKE ?)"
            params.extend([like_pattern, like_pattern])
        else:
            sql += " AND (subject LIKE ? OR sender LIKE ? OR recipients LIKE ? OR plain_body LIKE ?)"
            params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

        if has_attachments_only:
            sql += " AND has_attachments = 1"

        sql += " ORDER BY date_sent DESC LIMIT ?"
        params.append(limit)

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_email_by_id(self, email_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves full email record including full body and headers."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                try:
                    d["attachments"] = json.loads(d.get("attachments_json") or "[]")
                except Exception:
                    d["attachments"] = []
                return d
            return None
        finally:
            conn.close()

    def get_total_email_count(self) -> int:
        """Returns the total number of indexed emails in the database."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM emails")
            row = cursor.fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Returns database statistics."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_emails FROM emails")
            total_emails = cursor.fetchone()["total_emails"]
            cursor.execute("SELECT COUNT(*) as total_files FROM indexed_files")
            total_files = cursor.fetchone()["total_files"]
            return {
                "total_emails": total_emails,
                "total_files": total_files,
                "db_size": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            }
        finally:
            conn.close()

    def record_clock_seen(self, timestamp: float):
        """Records current timestamp for anti-clock-rollback tracking."""
        conn = self.get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES ('last_clock', ?)",
                    (str(timestamp),),
                )
        finally:
            conn.close()

    def get_last_clock_seen(self) -> float:
        """Returns the highest recorded system timestamp."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = 'last_clock'")
            row = cursor.fetchone()
            if row and row["value"]:
                return float(row["value"])
            return 0.0
        finally:
            conn.close()

    def clear_all(self):
        """Clears all indexed data."""
        conn = self.get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM emails")
                conn.execute("DELETE FROM indexed_files")
        finally:
            conn.close()
