"""
SQLite-backed report storage. Uses the built-in sqlite3 module with asyncio.to_thread
so no extra dependencies are needed. The DB file lives at data/reports.db.

Query the DB with any SQLite client (e.g. DB Browser for SQLite, the sqlite3 CLI,
or any Python script) — the file path is printed at startup.
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from datetime import datetime

_DB_PATH = Path(__file__).parent.parent / "data" / "reports.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables and the data directory. Call once at startup (sync)."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at       TEXT    NOT NULL,
                query            TEXT    NOT NULL,
                short_summary    TEXT,
                markdown_report  TEXT    NOT NULL,
                follow_up_questions TEXT,
                sources          TEXT,
                docx_path        TEXT
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts
            USING fts5(query, short_summary, markdown_report, content='reports', content_rowid='id')
        """)
        conn.commit()
    print(f"[DB] Reports database: {_DB_PATH}")


async def save_report(
    query: str,
    summary: str,
    markdown_report: str,
    follow_up_questions: list[str],
    sources: list[str],
    docx_path: str = "",
) -> int:
    def _save() -> int:
        with _get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO reports
                   (created_at, query, short_summary, markdown_report, follow_up_questions, sources, docx_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.utcnow().isoformat(timespec="seconds"),
                    query,
                    summary,
                    markdown_report,
                    json.dumps(follow_up_questions),
                    json.dumps(sources),
                    docx_path,
                ),
            )
            rowid = cur.lastrowid
            conn.execute(
                "INSERT INTO reports_fts(rowid, query, short_summary, markdown_report) VALUES (?, ?, ?, ?)",
                (rowid, query, summary, markdown_report),
            )
            conn.commit()
            return rowid

    return await asyncio.to_thread(_save)


async def get_all_reports() -> list[dict]:
    def _fetch() -> list[dict]:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT id, created_at, query, short_summary FROM reports ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    return await asyncio.to_thread(_fetch)


async def get_report(report_id: int) -> dict | None:
    def _fetch() -> dict | None:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
            if row is None:
                return None
            data = dict(row)
            data["follow_up_questions"] = json.loads(data["follow_up_questions"] or "[]")
            data["sources"] = json.loads(data["sources"] or "[]")
            return data

    return await asyncio.to_thread(_fetch)


async def search_reports(keyword: str) -> list[dict]:
    def _search() -> list[dict]:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT r.id, r.created_at, r.query, r.short_summary
                   FROM reports r
                   JOIN reports_fts f ON f.rowid = r.id
                   WHERE reports_fts MATCH ?
                   ORDER BY r.created_at DESC""",
                (keyword,),
            ).fetchall()
            return [dict(r) for r in rows]

    return await asyncio.to_thread(_search)


async def update_docx_path(report_id: int, docx_path: str) -> None:
    def _update() -> None:
        with _get_conn() as conn:
            conn.execute("UPDATE reports SET docx_path = ? WHERE id = ?", (docx_path, report_id))
            conn.commit()

    await asyncio.to_thread(_update)
