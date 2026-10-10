"""İzleme geçmişi, kaldığı yeri hatırlama ve yer imleri veritabanı (SQLite)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from lumina.services.paths import app_data_dir

class HistoryManager:
    def __init__(self, db_path: Optional[Path] = None):
        self._path = db_path or (app_data_dir() / "history.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS playback_progress (
                    path TEXT PRIMARY KEY,
                    position_ms INTEGER,
                    duration_ms INTEGER,
                    is_watched INTEGER,
                    last_played INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT,
                    position_ms INTEGER,
                    title TEXT,
                    created_at INTEGER
                )
            """)
            conn.commit()

    def save_progress(self, path: str, position_ms: int, duration_ms: int) -> None:
        if not path or duration_ms <= 0:
            return
        is_watched = 1 if position_ms > (duration_ms * 0.90) else 0
        now = int(time.time())

        with sqlite3.connect(self._path) as conn:
            conn.execute("""
                INSERT INTO playback_progress (path, position_ms, duration_ms, is_watched, last_played)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    position_ms = excluded.position_ms,
                    duration_ms = excluded.duration_ms,
                    is_watched = excluded.is_watched,
                    last_played = excluded.last_played
            """, (path, position_ms, duration_ms, is_watched, now))
            conn.commit()

    def get_progress(self, path: str) -> Optional[int]:
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT position_ms, duration_ms, is_watched FROM playback_progress WHERE path = ?", (path,))
            row = cursor.fetchone()
            if row:
                pos_ms, dur_ms, is_watched = row
                # Eğer film/video bitmemişse kaldığı yeri döndür
                if not is_watched and pos_ms > 5000 and (dur_ms - pos_ms > 10000):
                    return pos_ms
        return None

    def add_bookmark(self, path: str, position_ms: int, title: str = "") -> None:
        now = int(time.time())
        with sqlite3.connect(self._path) as conn:
            conn.execute("""
                INSERT INTO bookmarks (path, position_ms, title, created_at)
                VALUES (?, ?, ?, ?)
            """, (path, position_ms, title, now))
            conn.commit()

    def get_bookmarks(self, path: str) -> List[Dict]:
        with sqlite3.connect(self._path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, position_ms, title, created_at FROM bookmarks WHERE path = ? ORDER BY position_ms ASC", (path,))
            return [{"id": r[0], "position_ms": r[1], "title": r[2], "created_at": r[3]} for r in cursor.fetchall()]
