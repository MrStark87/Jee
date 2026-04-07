"""
database.py — SQLite schema and helper functions
Tables: users, tasks, lectures, memories, thoughts, formulas, motivation,
        study_log, test_scores, revision_schedule, syllabus, doubts
"""

import sqlite3
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY,
        tg_id       INTEGER UNIQUE NOT NULL,
        name        TEXT DEFAULT '',
        streak      INTEGER DEFAULT 0,
        last_active TEXT DEFAULT '',
        is_banned   INTEGER DEFAULT 0,
        joined      TEXT DEFAULT (date('now'))
    )""")

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS lectures (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL,
        title        TEXT NOT NULL,
        link         TEXT NOT NULL,
        subject      TEXT DEFAULT '',
        alert_time   TEXT NOT NULL,
        message      TEXT DEFAULT '',
        repeat_daily INTEGER DEFAULT 0,
        active       INTEGER DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

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
        ans_ftype  TEXT DEFAULT '',
        keypoints  TEXT DEFAULT '',
        created    TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS daily_reports (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL,
        date     TEXT NOT NULL,
        content  TEXT DEFAULT '',
        file_id  TEXT DEFAULT '',
        file_type TEXT DEFAULT '',
        created  TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS formulas (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        class_num TEXT NOT NULL,
        chapter   TEXT NOT NULL,
        subject   TEXT DEFAULT '',
        file_id   TEXT DEFAULT '',
        file_type TEXT DEFAULT '',
        content   TEXT DEFAULT '',
        added_by  INTEGER,
        created   TEXT DEFAULT (datetime('now','localtime'))
    )""")

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

    c.execute("""
    CREATE TABLE IF NOT EXISTS study_log (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL,
        subject  TEXT DEFAULT '',
        minutes  INTEGER DEFAULT 0,
        date     TEXT DEFAULT (date('now')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS test_scores (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        test_name TEXT DEFAULT '',
        phy     INTEGER DEFAULT 0,
        chem    INTEGER DEFAULT 0,
        math    INTEGER DEFAULT 0,
        total   INTEGER DEFAULT 0,
        date    TEXT DEFAULT (date('now')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS revision_schedule (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        lecture_id INTEGER,
        topic      TEXT NOT NULL,
        due_date   TEXT NOT NULL,
        done       INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS doubts (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL,
        subject  TEXT DEFAULT '',
        text     TEXT NOT NULL,
        resolved INTEGER DEFAULT 0,
        created  TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(user_id) REFERENCES users(tg_id)
    )""")

    conn.commit()
    conn.close()
    print("[DB] All tables ready.")


# ── User helpers ───────────────────────────────────────────────

def upsert_user(tg_id: int, name: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users(tg_id, name)
        VALUES(?,?)
        ON CONFLICT(tg_id) DO UPDATE SET name=excluded.name
    """, (tg_id, name))
    conn.commit()
    conn.close()


def get_user(tg_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    conn.close()
    return row


def is_banned(tg_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT is_banned FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    conn.close()
    return bool(row and row["is_banned"])


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT tg_id FROM users WHERE is_banned=0").fetchall()
    conn.close()
    return [r["tg_id"] for r in rows]


def update_streak(user_id: int):
    """Call when a task is marked done. Updates streak logic."""
    import datetime
    today = datetime.date.today().isoformat()
    conn  = get_conn()
    user  = conn.execute("SELECT streak, last_active FROM users WHERE tg_id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return
    last   = user["last_active"] or ""
    streak = user["streak"] or 0
    if last == today:
        conn.close()
        return
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    new_streak = streak + 1 if last == yesterday else 1
    conn.execute(
        "UPDATE users SET streak=?, last_active=? WHERE tg_id=?",
        (new_streak, today, user_id)
    )
    conn.commit()
    conn.close()
