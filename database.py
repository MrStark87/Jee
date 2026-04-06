"""
database.py — SQLite schema & helper functions
"""

import sqlite3
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── Users ──────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY,
        tg_id       INTEGER UNIQUE NOT NULL,
        name        TEXT,
        streak      INTEGER DEFAULT 0,
        last_active TEXT,
        joined      TEXT DEFAULT (date('now'))
    )""")

    # ── Tasks (per user, per day) ──────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL,
        text     TEXT NOT NULL,
        subject  TEXT DEFAULT '',
        done     INTEGER DEFAULT 0,
        date     TEXT DEFAULT (date('now')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    # ── Lectures (per user) ────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS lectures (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        title      TEXT NOT NULL,
        link       TEXT NOT NULL,
        subject    TEXT DEFAULT '',
        alert_time TEXT NOT NULL,
        message    TEXT DEFAULT '',
        active     INTEGER DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    # ── Memories (silly / error / important) ──────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        mem_type   TEXT NOT NULL,
        title      TEXT NOT NULL,
        content    TEXT DEFAULT '',
        file_id    TEXT DEFAULT '',
        file_type  TEXT DEFAULT '',
        answer     TEXT DEFAULT '',
        ans_file   TEXT DEFAULT '',
        keypoints  TEXT DEFAULT '',
        created    TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    # ── Thoughts (per user) ────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS thoughts (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL,
        content   TEXT DEFAULT '',
        file_id   TEXT DEFAULT '',
        file_type TEXT DEFAULT '',
        created   TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    # ── Formulas (shared, admin-uploaded) ─────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS formulas (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        class_num  TEXT NOT NULL,
        chapter    TEXT NOT NULL,
        subject    TEXT DEFAULT '',
        file_id    TEXT DEFAULT '',
        file_type  TEXT DEFAULT '',
        content    TEXT DEFAULT '',
        added_by   INTEGER,
        created    TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── Motivation quotes (per user, private) ─────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS motivation (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL,
        content   TEXT DEFAULT '',
        file_id   TEXT DEFAULT '',
        file_type TEXT DEFAULT '',
        created   TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    conn.commit()
    conn.close()
    print("Database ready.")


# ── Generic helpers ────────────────────────────────────────────

def upsert_user(tg_id: int, name: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users(tg_id, name) VALUES(?,?)
        ON CONFLICT(tg_id) DO UPDATE SET name=excluded.name
    """, (tg_id, name))
    conn.commit()
    conn.close()


def get_user(tg_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    conn.close()
    return row


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT tg_id FROM users").fetchall()
    conn.close()
    return [r["tg_id"] for r in rows]
