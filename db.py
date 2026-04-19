import sqlite3
import json
import os
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(os.path.expanduser("~")) / ".clipfusion" / "clipfusion_v3.db"

@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                video_path TEXT NOT NULL,
                language TEXT DEFAULT 'pt',
                status TEXT DEFAULT 'created',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                full_text TEXT,
                segments_json TEXT,
                quality_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                transcript_id INTEGER NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                text TEXT NOT NULL,
                hook_strength REAL,
                retention_score REAL,
                moment_strength REAL,
                shareability REAL,
                platform_fit_tiktok REAL,
                platform_fit_reels REAL,
                platform_fit_shorts REAL,
                combined_score REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()

def create_project(name, video_path, language='pt'):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, video_path, language) VALUES (?, ?, ?)",
            (name, video_path, language)
        )
        conn.commit()
        return cur.lastrowid

init_db()
