"""
Capa de acceso a datos (SQLite) para LingoBot.
Guarda idiomas favoritos, conversaciones y mensajes.
"""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "lingobot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT NOT NULL,
            language_name TEXT NOT NULL,
            flag TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'A2',
            title TEXT NOT NULL DEFAULT 'Nueva conversación',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            daily_class_enabled INTEGER NOT NULL DEFAULT 1,
            daily_class_hour INTEGER NOT NULL DEFAULT 8,
            daily_class_minute INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL,               -- 'user' | 'assistant' | 'system_class'
            content TEXT NOT NULL,            -- texto mostrado (respuesta del profesor o mensaje del alumno)
            corrections_json TEXT,            -- JSON con correcciones (solo para role='assistant')
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------- Conversaciones ----------

def create_conversation(language_code: str, language_name: str, flag: str, level: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO conversations
           (language_code, language_name, flag, level, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (language_code, language_name, flag, level, f"{language_name} ({level})", now_iso(), now_iso()),
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return conv_id


def list_conversations():
    conn = get_conn()
    rows = conn.execute(
        """SELECT c.*,
                  (SELECT content FROM messages m WHERE m.conversation_id = c.id
                   ORDER BY m.id DESC LIMIT 1) AS last_message
           FROM conversations c
           ORDER BY c.updated_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_conversation(conv_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def touch_conversation(conv_id: int):
    conn = get_conn()
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now_iso(), conv_id))
    conn.commit()
    conn.close()


def delete_conversation(conv_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))  # ON DELETE CASCADE borra sus mensajes
    conn.commit()
    conn.close()


# ---------- Mensajes ----------

def add_message(conv_id: int, role: str, content: str, corrections: Optional[list] = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO messages (conversation_id, role, content, corrections_json, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (conv_id, role, content, json.dumps(corrections) if corrections is not None else None, now_iso()),
    )
    conn.commit()
    conn.close()
    touch_conversation(conv_id)
    return cur.lastrowid


def list_messages(conv_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC", (conv_id,)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["corrections"] = json.loads(d["corrections_json"]) if d["corrections_json"] else None
        del d["corrections_json"]
        out.append(d)
    return out
