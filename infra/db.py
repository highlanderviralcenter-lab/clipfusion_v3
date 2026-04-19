"""
Módulo de persistência para o ClipFusion V3 usando SQLite.

Este arquivo define funções utilitárias para criar o banco de dados e
persistir objetos como projetos, transcrições, candidatos, cortes e
jobs.  Cada função abre uma conexão local e garante commit das
operações.  O banco fica armazenado em ~/.clipfusion/clipfusion_v3.db.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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

def init_db() -> None:
    with get_db() as conn:
        cur = conn.cursor()
        cur.executescript(
            """
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
            CREATE TABLE IF NOT EXISTS cuts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                candidate_id INTEGER NOT NULL,
                output_path TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                state TEXT DEFAULT 'queued',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()

def create_project(name: str, video_path: str, language: str = 'pt') -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, video_path, language) VALUES (?, ?, ?)",
            (name, video_path, language),
        )
        conn.commit()
        return cur.lastrowid

def list_projects() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM projects")
        rows = [dict(row) for row in cur.fetchall()]
    return rows

def save_transcription(project_id: int, full_text: str, segments_json: str, quality_score: float) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO transcripts (project_id, full_text, segments_json, quality_score) VALUES (?, ?, ?, ?)",
            (project_id, full_text, segments_json, quality_score),
        )
        conn.commit()
        return cur.lastrowid

def get_transcription(project_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM transcripts WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

def save_candidate(project_id: int, transcript_id: int, start: float, end: float, text: str, scores: Dict[str, float]) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO candidates (
                project_id, transcript_id, start_time, end_time, text,
                hook_strength, retention_score, moment_strength, shareability,
                platform_fit_tiktok, platform_fit_reels, platform_fit_shorts, combined_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                transcript_id,
                start,
                end,
                text,
                scores.get('hook_strength', 0.0),
                scores.get('retention_score', 0.0),
                scores.get('moment_strength', 0.0),
                scores.get('shareability', 0.0),
                scores.get('platform_fit_tiktok', 0.0),
                scores.get('platform_fit_reels', 0.0),
                scores.get('platform_fit_shorts', 0.0),
                scores.get('combined_score', 0.0),
            ),
        )
        conn.commit()
        return cur.lastrowid

def get_candidates(project_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM candidates WHERE project_id = ?", (project_id,))
        return [dict(row) for row in cur.fetchall()]

def save_cut(project_id: int, candidate_id: int, output_path: str) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO cuts (project_id, candidate_id, output_path) VALUES (?, ?, ?)",
            (project_id, candidate_id, output_path),
        )
        conn.commit()
        return cur.lastrowid

def get_cuts(project_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM cuts WHERE project_id = ?", (project_id,))
        return [dict(row) for row in cur.fetchall()]

def update_cut_status(cut_id: int, status: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE cuts SET status = ? WHERE id = ?", (status, cut_id))
        conn.commit()

def update_cut_output(cut_id: int, output_path: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE cuts SET output_path = ? WHERE id = ?", (output_path, cut_id))
        conn.commit()

def enqueue_job(project_id: int) -> int:
    with get_db() as conn:
        cur = conn.execute("INSERT INTO jobs (project_id) VALUES (?)", (project_id,))
        conn.commit()
        return cur.lastrowid

def fetch_next_job() -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM jobs WHERE state = 'queued' ORDER BY id LIMIT 1"
        )
        row = cur.fetchone()
        return dict(row) if row else None

def finish_job(job_id: int) -> None:
    with get_db() as conn:
        conn.execute("UPDATE jobs SET state = 'done' WHERE id = ?", (job_id,))
        conn.commit()

def fail_job(job_id: int, message: str) -> None:
    with get_db() as conn:
        conn.execute("UPDATE jobs SET state = 'error', error_message = ? WHERE id = ?", (message, job_id))
        conn.commit()

# Inicializa banco ao importar
init_db()
