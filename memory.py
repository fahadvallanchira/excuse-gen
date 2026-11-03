"""SQLite memory of excuses already used, per recipient."""
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = "data/excuses.db"


def normalize(recipient: str) -> str:
    return recipient.strip().lower()


def init_db(db_path: str = DB_PATH) -> None:
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS excuses ("
            "id INTEGER PRIMARY KEY, recipient TEXT, text TEXT, "
            "level INTEGER, created_at TEXT)"
        )


def save_excuse(recipient: str, text: str, level: int, db_path: str = DB_PATH) -> None:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO excuses (recipient, text, level, created_at) VALUES (?, ?, ?, ?)",
            (normalize(recipient), text, level, datetime.now(timezone.utc).isoformat()),
        )


def past_excuses_for(recipient: str, db_path: str = DB_PATH) -> list[str]:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT text FROM excuses WHERE recipient = ? ORDER BY id",
            (normalize(recipient),),
        ).fetchall()
    return [r[0] for r in rows]
