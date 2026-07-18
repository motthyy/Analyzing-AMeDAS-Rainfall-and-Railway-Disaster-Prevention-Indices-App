"""ダウンロードジョブ管理用SQLiteデータベース（5.5節）。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS download_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_code TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    saved_file TEXT,
    row_count INTEGER,
    file_size_bytes INTEGER,
    min_datetime TEXT,
    max_datetime TEXT,
    error_message TEXT,
    last_attempt_at TEXT,
    parent_job_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(station_code, start_date, end_date)
);
CREATE INDEX IF NOT EXISTS idx_jobs_station ON download_jobs(station_code);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON download_jobs(status);
"""


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        init_db(path)
        yield conn
        conn.commit()
    finally:
        conn.close()
