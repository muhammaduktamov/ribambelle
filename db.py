import sqlite3
from contextlib import closing

def get_conn(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn):
    with closing(conn.cursor()) as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS guests (
            tg_user_id INTEGER PRIMARY KEY,
            username TEXT,
            phone TEXT,
            created_at TEXT
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            visit_id TEXT PRIMARY KEY,
            tg_user_id INTEGER,
            created_at TEXT
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER,
            visit_id TEXT,
            service INTEGER,
            taste INTEGER,
            speed INTEGER,
            clean INTEGER,
            comment TEXT,
            photo_id TEXT,
            created_at TEXT,
            alert_sent INTEGER DEFAULT 0
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS prizes (
            code TEXT PRIMARY KEY,
            title TEXT,
            type TEXT,
            valid_until TEXT,
            user_id INTEGER,
            visit_id TEXT,
            status TEXT,
            created_at TEXT,
            redeemed_at TEXT,
            redeemed_by INTEGER
        )""")
        conn.commit()
