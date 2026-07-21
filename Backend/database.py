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
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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
    # Migración: si la tabla 'conversations' ya existía de una versión anterior sin user_id,
    # la añadimos ahora. Las conversaciones antiguas quedarán con user_id NULL (inaccesibles
    # hasta que se reasignen o se borren manualmente).
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
    if "user_id" not in cols:
        conn.execute("ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id)")
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------- Usuarios y sesiones ----------

def create_user(username: str, password_salt: str, password_hash: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (username, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (username, password_salt, password_hash, now_iso()),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_session(token: str, user_id: int, expires_at: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now_iso(), expires_at),
    )
    conn.commit()
    conn.close()


def get_session(token: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(token: str):
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# ---------- Conversaciones ----------

def create_conversation(user_id: int, language_code: str, language_name: str, flag: str, level: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO conversations
           (user_id, language_code, language_name, flag, level, title, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, language_code, language_name, flag, level, f"{language_name} ({level})", now_iso(), now_iso()),
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return conv_id


def list_conversations(user_id: int):
    conn = get_conn()
    rows = conn.execute(
        """SELECT c.*,
                  (SELECT content FROM messages m WHERE m.conversation_id = c.id
                   ORDER BY m.id DESC LIMIT 1) AS last_message
           FROM conversations c
           WHERE c.user_id = ?
           ORDER BY c.updated_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_all_conversations():
    """Todas las conversaciones de todos los usuarios. Solo para uso interno (job programado)."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM conversations WHERE user_id IS NOT NULL").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_conversation(conv_id: int, user_id: Optional[int] = None) -> Optional[dict]:
    """Si se pasa user_id, solo devuelve la conversación si pertenece a ese usuario (control de acceso)."""
    conn = get_conn()
    if user_id is not None:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id)
        ).fetchone()
    else:
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
