import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from .settings import DATABASE_PATH, ensure_runtime_dirs


class TaskStore:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create(self, task: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        task = {**task, "created_at": now, "updated_at": now}
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (id, filename, status, progress, stage, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"],
                    task["filename"],
                    task["status"],
                    task["progress"],
                    task["stage"],
                    json.dumps(task, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def update(self, task_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            task = self.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.update(changes)
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE tasks
                    SET status = ?, progress = ?, stage = ?, payload = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        task["status"],
                        task["progress"],
                        task["stage"],
                        json.dumps(task, ensure_ascii=False),
                        task["updated_at"],
                        task_id,
                    ),
                )
        return task

