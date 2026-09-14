"""SQLite persistence for Hayati prototype.

Stores chat sessions, messages, patient profiles, symptom observations and
One Health surveillance reports. SQLite is suitable for the prototype only;
production patient data should move to a managed PostgreSQL database with
proper authentication, encryption, access controls and audit logging.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "hayati.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT 'Guest Patient',
            age INTEGER,
            sex TEXT,
            location TEXT,
            conditions TEXT NOT NULL DEFAULT '[]',
            allergies TEXT NOT NULL DEFAULT '[]',
            medications TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            patient_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS symptom_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            symptom TEXT NOT NULL,
            source_text TEXT NOT NULL,
            duration_text TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id),
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
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

    # Safe migration for databases created by the previous Hayati version.
    columns = {r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    if "patient_id" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN patient_id TEXT")

    symptom_columns = {r[1] for r in conn.execute("PRAGMA table_info(symptom_records)").fetchall()}
    if "duration_text" not in symptom_columns:
        conn.execute("ALTER TABLE symptom_records ADD COLUMN duration_text TEXT")

    conn.commit()
    conn.close()


def create_patient(patient_id: str, data: dict | None = None) -> dict:
    data = data or {}
    timestamp = now_iso()
    conn = get_connection()
    conn.execute(
        """INSERT INTO patients
        (patient_id, name, age, sex, location, conditions, allergies, medications, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            patient_id,
            (data.get("name") or "Guest Patient").strip()[:120],
            data.get("age"),
            (data.get("sex") or "").strip()[:40] or None,
            (data.get("location") or "").strip()[:120] or None,
            json.dumps(data.get("conditions") or []),
            json.dumps(data.get("allergies") or []),
            json.dumps(data.get("medications") or []),
            (data.get("notes") or "").strip()[:2000],
            timestamp,
            timestamp,
        ),
    )
    conn.commit()
    conn.close()
    return get_patient(patient_id)


def ensure_patient(patient_id: str) -> dict:
    patient = get_patient(patient_id)
    return patient if patient else create_patient(patient_id)


def get_patient(patient_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _patient_from_row(row)


def _patient_from_row(row: sqlite3.Row) -> dict:
    return {
        "patient_id": row["patient_id"],
        "name": row["name"],
        "age": row["age"],
        "sex": row["sex"],
        "location": row["location"],
        "conditions": json.loads(row["conditions"] or "[]"),
        "allergies": json.loads(row["allergies"] or "[]"),
        "medications": json.loads(row["medications"] or "[]"),
        "notes": row["notes"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_patient(patient_id: str, data: dict) -> dict:
    ensure_patient(patient_id)
    current = get_patient(patient_id) or {}
    merged = {
        "name": data.get("name", current.get("name")),
        "age": data.get("age", current.get("age")),
        "sex": data.get("sex", current.get("sex")),
        "location": data.get("location", current.get("location")),
        "conditions": data.get("conditions", current.get("conditions", [])),
        "allergies": data.get("allergies", current.get("allergies", [])),
        "medications": data.get("medications", current.get("medications", [])),
        "notes": data.get("notes", current.get("notes", "")),
    }
    conn = get_connection()
    conn.execute(
        """UPDATE patients SET name=?, age=?, sex=?, location=?, conditions=?, allergies=?, medications=?, notes=?, updated_at=?
           WHERE patient_id=?""",
        (
            (merged["name"] or "Guest Patient").strip()[:120],
            merged["age"],
            (merged["sex"] or "").strip()[:40] or None,
            (merged["location"] or "").strip()[:120] or None,
            json.dumps(merged["conditions"] or []),
            json.dumps(merged["allergies"] or []),
            json.dumps(merged["medications"] or []),
            (merged["notes"] or "").strip()[:2000],
            now_iso(),
            patient_id,
        ),
    )
    conn.commit()
    conn.close()
    return get_patient(patient_id)


def ensure_session(session_id: str, patient_id: str | None = None) -> None:
    conn = get_connection()
    if patient_id:
        ensure_patient(patient_id)
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, patient_id, created_at) VALUES (?, ?, ?)",
        (session_id, patient_id, now_iso()),
    )
    if patient_id:
        conn.execute("UPDATE sessions SET patient_id = ? WHERE session_id = ?", (patient_id, session_id))
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


def log_message(session_id: str, role: str, content: str, triage_level: str | None = None, matched_flags: list[str] | None = None) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO messages (session_id, role, content, triage_level, matched_flags, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, role, content, triage_level, json.dumps(matched_flags) if matched_flags is not None else None, now_iso()),
    )
    conn.commit()
    conn.close()


def add_symptoms(patient_id: str, session_id: str, symptoms: list[str], source_text: str, duration_text: str | None = None) -> None:
    if not symptoms:
        return
    conn = get_connection()
    stamp = now_iso()
    for symptom in dict.fromkeys(symptoms):
        conn.execute(
            "INSERT INTO symptom_records (patient_id, session_id, symptom, source_text, duration_text, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (patient_id, session_id, symptom, source_text[:4000], duration_text, stamp),
        )
    conn.commit()
    conn.close()


def get_patient_memory(patient_id: str, limit: int = 30) -> dict:
    patient = ensure_patient(patient_id)
    conn = get_connection()
    symptoms = conn.execute(
        """SELECT symptom, MAX(timestamp) AS last_seen, COUNT(*) AS mentions,
                  MAX(duration_text) AS duration_text
           FROM symptom_records WHERE patient_id = ? GROUP BY symptom ORDER BY last_seen DESC LIMIT ?""",
        (patient_id, limit),
    ).fetchall()
    recent = conn.execute(
        """SELECT symptom, timestamp, duration_text, source_text FROM symptom_records
           WHERE patient_id = ? ORDER BY id DESC LIMIT ?""",
        (patient_id, limit),
    ).fetchall()
    consultation_count = conn.execute(
        "SELECT COUNT(*) AS n FROM sessions WHERE patient_id = ?", (patient_id,)
    ).fetchone()["n"]
    conn.close()
    return {
        "patient": patient,
        "consultation_count": consultation_count,
        "symptoms": [{"symptom": r["symptom"], "last_seen": r["last_seen"], "mentions": r["mentions"], "duration_text": r["duration_text"]} for r in symptoms],
        "recent_symptoms": [{"symptom": r["symptom"], "timestamp": r["timestamp"], "duration_text": r["duration_text"], "source_text": r["source_text"]} for r in recent],
    }


def add_surveillance_report(session_id: str, location: str, condition: str | None, severity: str, symptoms: list[str]) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO surveillance_reports (session_id, timestamp, location, condition, severity, symptoms)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, now_iso(), location.strip(), condition, severity, json.dumps(symptoms)),
    )
    conn.commit()
    conn.close()


def get_surveillance_reports() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT timestamp, location, condition, severity, symptoms FROM surveillance_reports ORDER BY id ASC").fetchall()
    conn.close()
    return [{"timestamp": r["timestamp"], "location": r["location"], "condition": r["condition"], "severity": r["severity"], "symptoms": json.loads(r["symptoms"] or "[]")} for r in rows]
