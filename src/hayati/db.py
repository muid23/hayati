"""
SQLite persistence layer.

Replaces the in-memory session dict and the audit_log.jsonl file from the
first version of the prototype with a single hayati.db file. Each message
row doubles as an audit log entry -- the user's message row carries the
triage_level and matched_flags produced by the classifier at the time it
ran, so the audit trail and the conversation history are the same table.

Uses short-lived sqlite3 connections per call rather than one shared
connection, which keeps this safe to call from FastAPI's threadpool
(sync routes) and from the websocket's async handler without worrying
about cross-thread connection reuse. Fine for a prototype; a real
deployment would use a connection pool or an async driver.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "hayati.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS surveillance_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            location TEXT NOT NULL,
            condition TEXT,
            severity TEXT NOT NULL DEFAULT 'unknown',
            symptoms TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'chatbot',
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )
        """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            triage_level TEXT,
            matched_flags TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )
        """)
    conn.commit()
    conn.close()


def ensure_session(session_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?)",
        (session_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_history(session_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def log_message(
    session_id: str,
    role: str,
    content: str,
    triage_level: str | None = None,
    matched_flags: list[str] | None = None,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO messages (session_id, role, content, triage_level, matched_flags, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            role,
            content,
            triage_level,
            json.dumps(matched_flags) if matched_flags is not None else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def add_surveillance_report(session_id: str, location: str, condition: str | None, severity: str, symptoms: list[str]) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO surveillance_reports (session_id, timestamp, location, condition, severity, symptoms)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, datetime.now(timezone.utc).isoformat(), location.strip(), condition, severity, json.dumps(symptoms)),
    )
    conn.commit()
    conn.close()


def get_surveillance_reports() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT timestamp, location, condition, severity, symptoms FROM surveillance_reports ORDER BY id ASC").fetchall()
    conn.close()
    return [{"timestamp": r["timestamp"], "location": r["location"], "condition": r["condition"], "severity": r["severity"], "symptoms": json.loads(r["symptoms"] or "[]")} for r in rows]
