import sqlite3
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path

from config.settings import settings
from .models import Task, TaskStatus

class SQLiteQueue:
    def __init__(self, db_path: str = settings.db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    checkpoint_json TEXT
                )
            """)
            # Reset tasks that were in progress before a crash/restart, but only if they haven't exceeded max_retries
            conn.execute("""
                UPDATE tasks
                SET status = ?, updated_at = ?
                WHERE status = ? AND attempts < ?
            """, (TaskStatus.PENDING.value, datetime.now(timezone.utc).isoformat(), TaskStatus.IN_PROGRESS.value, settings.max_retries))
            
            # Mark tasks that exceeded max_retries as FAILED
            conn.execute("""
                UPDATE tasks
                SET status = ?, updated_at = ?
                WHERE status = ? AND attempts >= ?
            """, (TaskStatus.FAILED.value, datetime.now(timezone.utc).isoformat(), TaskStatus.IN_PROGRESS.value, settings.max_retries))
            conn.commit()

    def enqueue(self, payload: dict) -> Task:
        now = datetime.now(timezone.utc)
        task = Task(
            id=str(uuid.uuid4()),
            status=TaskStatus.PENDING,
            payload=payload,
            created_at=now,
            updated_at=now
        )
        with self._get_conn() as conn:
            data = task.to_dict()
            conn.execute("""
                INSERT INTO tasks (id, status, payload_json, created_at, updated_at, attempts, checkpoint_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data["id"], data["status"], data["payload_json"], data["created_at"], data["updated_at"], data["attempts"], data["checkpoint_json"]))
            conn.commit()
        return task

    def dequeue(self) -> Optional[Task]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, status, payload_json, created_at, updated_at, attempts, checkpoint_json
                FROM tasks
                WHERE status = ? AND attempts < ?
                ORDER BY created_at ASC
                LIMIT 1
            """, (TaskStatus.PENDING.value, settings.max_retries))
            row = cursor.fetchone()
            
            if not row:
                conn.rollback()
                return None
                
            task = Task.from_row(row)
            task.status = TaskStatus.IN_PROGRESS
            task.updated_at = datetime.fromisoformat(now)
            task.attempts += 1
            
            cursor.execute("""
                UPDATE tasks
                SET status = ?, updated_at = ?, attempts = ?
                WHERE id = ?
            """, (task.status.value, task.updated_at.isoformat(), task.attempts, task.id))
            conn.commit()
            return task

    def update_task(self, task: Task) -> None:
        task.updated_at = datetime.now(timezone.utc)
        with self._get_conn() as conn:
            data = task.to_dict()
            conn.execute("""
                UPDATE tasks
                SET status = ?, payload_json = ?, updated_at = ?, attempts = ?, checkpoint_json = ?
                WHERE id = ?
            """, (data["status"], data["payload_json"], data["updated_at"], data["attempts"], data["checkpoint_json"], data["id"]))
            conn.commit()

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, status, payload_json, created_at, updated_at, attempts, checkpoint_json
                FROM tasks
                WHERE id = ?
            """, (task_id,))
            row = cursor.fetchone()
            if row:
                return Task.from_row(row)
            return None

    def list_tasks(self, limit: int = 10, offset: int = 0) -> List[Task]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, status, payload_json, created_at, updated_at, attempts, checkpoint_json
                FROM tasks
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            rows = cursor.fetchall()
            return [Task.from_row(row) for row in rows]
