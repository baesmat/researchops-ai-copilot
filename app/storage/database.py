"""SQLite persistence for documents, analyses, checklist edits, chat turns."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    num_pages INTEGER NOT NULL DEFAULT 0,
    num_chunks INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded|parsed|analyzed|error
    error TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extraction_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS checklist_items (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    task TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    source_reference TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL,
    requires_human_review INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS qa_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    citations TEXT NOT NULL DEFAULT '',
    grounded INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
"""

LOCK = threading.RLock()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with LOCK:
        conn.executescript(SCHEMA)
        conn.commit()


def now() -> float:
    return time.time()


def new_id() -> str:  # type: ignore[valid-type]
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- documents

def add_document(
    conn: sqlite3.Connection, doc_id: str, filename: str, doc_type: str, stored_path: str
) -> None:
    with LOCK:
        conn.execute(
            "INSERT INTO documents(id, filename, doc_type, stored_path, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?)",
            (doc_id, filename, doc_type, stored_path, now(), now()),
        )
        conn.commit()


def update_document(conn: sqlite3.Connection, doc_id: str, **fields: object) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with LOCK:
        conn.execute(
            f"UPDATE documents SET {cols}, updated_at=? WHERE id=?",  # noqa: S608
            [*fields.values(), now(), doc_id],
        )
        conn.commit()


def get_document(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:  # type: ignore[valid-type]
    with LOCK:
        return conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()


def list_documents(conn: sqlite3.Connection) -> list[sqlite3.Row]:  # type: ignore[valid-type]
    with LOCK:
        return conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()


def delete_document(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:  # type: ignore[valid-type]
    with LOCK:
        row = get_document(conn, doc_id)
        if row is None:
            return None
        for table in ("analyses", "checklist_items", "qa_log"):
            conn.execute(f"DELETE FROM {table} WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.commit()
    return row


# ---------------------------------------------------------------- analyses

def save_analysis(conn: sqlite3.Connection, doc_id: str, extraction_json: str) -> None:
    with LOCK:
        conn.execute(
            "INSERT INTO analyses(doc_id, extraction_json, created_at) VALUES(?,?,?)",
            (doc_id, extraction_json, now()),
        )
        conn.commit()


def latest_analysis(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:  # type: ignore[valid-type]
    with LOCK:
        return conn.execute(
            "SELECT * FROM analyses WHERE doc_id=? ORDER BY id DESC LIMIT 1", (doc_id,)
        ).fetchone()


# ---------------------------------------------------------------- checklist

def replace_checklist(conn: sqlite3.Connection, doc_id: str, items: list[dict]) -> None:
    with LOCK:
        conn.execute("DELETE FROM checklist_items WHERE doc_id=?", (doc_id,))
        for item in items:
            conn.execute(
                "INSERT INTO checklist_items(id, doc_id, task, category, priority, status,"
                " source_reference, rationale, task_type, requires_human_review)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    item.get("id") or new_id(), doc_id, item["task"], item["category"],
                    item.get("priority", "Medium"), item.get("status", "Not Started"),
                    item.get("source_reference", ""), item.get("rationale", ""),
                    item["task_type"], int(item.get("requires_human_review", True)),
                ),
            )
        conn.commit()


def list_checklist(conn: sqlite3.Connection, doc_id: str) -> list[sqlite3.Row]:  # type: ignore[valid-type]
    with LOCK:
        return conn.execute(
            "SELECT * FROM checklist_items WHERE doc_id=? ORDER BY id", (doc_id,)
        ).fetchall()


def update_checklist_item(
    conn: sqlite3.Connection, item_id: str, **fields: object
) -> sqlite3.Row | None:  # type: ignore[valid-type]
    allowed = {"status", "priority"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_checklist_item(conn, item_id)
    cols = ", ".join(f"{k}=?" for k in fields)
    with LOCK:
        conn.execute(f"UPDATE checklist_items SET {cols} WHERE id=?", (*fields.values(), item_id))
        conn.commit()
    return get_checklist_item(conn, item_id)


def get_checklist_item(conn: sqlite3.Connection, item_id: str) -> sqlite3.Row | None:  # type: ignore[valid-type]
    with LOCK:
        return conn.execute("SELECT * FROM checklist_items WHERE id=?", (item_id,)).fetchone()


# --------------------------------------------------------------------- qa

def log_qa(
    conn: sqlite3.Connection, doc_id: str, question: str, answer: str, citations: list[str], grounded: bool
) -> None:
    with LOCK:
        conn.execute(
            "INSERT INTO qa_log(doc_id, question, answer, citations, grounded, created_at)"
            " VALUES(?,?,?,?,?,?)",
            (doc_id, question, answer, json.dumps(citations), int(grounded), now()),
        )
        conn.commit()


def stats(conn: sqlite3.Connection) -> dict:
    with LOCK:
        docs = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
        analyzed = conn.execute(
            "SELECT COUNT(DISTINCT doc_id) c FROM analyses"
        ).fetchone()["c"]
        items = conn.execute("SELECT COUNT(*) c FROM checklist_items").fetchone()["c"]
        clarify = conn.execute(
            "SELECT COUNT(*) c FROM checklist_items WHERE task_type='Needs Clarification'"
        ).fetchone()["c"]
        recent = conn.execute(
            "SELECT id, filename, status, datetime(updated_at, 'unixepoch') ts FROM documents"
            " ORDER BY updated_at DESC LIMIT 5"
        ).fetchall()
    return {
        "documents": docs,
        "analyzed": analyzed,
        "checklist_items": items,
        "needs_clarification": clarify,
        "recent": [dict(r) for r in recent],
    }
