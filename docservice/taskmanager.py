import time
from typing import Optional
from uuid import UUID
import aiosqlite

class TaskManager:
    """
    SQLite-backed task status tracker for the submit-and-fetch (job/task) flow.

    Timestamps:
    - created_at:    task row inserted (queued)
    - processing_at: worker picked up the task (set on mark_running)
    - finish_at:     task reached a terminal state (done/failed)

    These three timestamps allow distinguishing:
    - stuck in queue (created_at old, processing_at still null)
    - stuck while processing (processing_at old, finish_at still null)
    - completed but past TTL (finish_at old) -> cleanup target
    """

    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path

    async def init(self) -> None:
        """
        Ensure the database file and tasks table exist.
        Call once at app startup (e.g. in lifespan).
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    template_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    file_name TEXT,
                    data_hash TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    processing_at REAL,
                    finish_at REAL
                )
            """)
            await db.commit()

    async def create_task(self, task_id: UUID, template_name: str, file_name: str) -> None:
        """
        Insert a new task with status='pending'.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(
                "INSERT INTO tasks (task_id, template_name, status, file_name, created_at) VALUES (?, ?, 'pending',?, ?)",
                (str(task_id), template_name, file_name, time.time())
            )
            await db.commit()

    async def mark_running(self, task_id: UUID) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(
                "UPDATE tasks SET status='running', processing_at=? WHERE task_id=?",
                (time.time(), str(task_id))
            )
            await db.commit()

    async def complete_task(self, task_id: UUID, data_hash: str) -> None:
        """
        Mark task as done with the resulting file name and cache hash.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(
                "UPDATE tasks SET status='done', data_hash=?, finish_at=? WHERE task_id=?",
                (data_hash, time.time(), str(task_id))
            )
            await db.commit()

    async def fail_task(self, task_id: UUID, error: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute(
                "UPDATE tasks SET status='failed', error=?, finish_at=? WHERE task_id=?",
                (error, time.time(), str(task_id))
            )
            await db.commit()

    async def get_task(self, task_id: UUID) -> Optional[dict]:
        """
        Return task row as a dict, or None if not found.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT task_id, template_name, status, file_name, data_hash, error, "
                "created_at, processing_at, finish_at "
                "FROM tasks WHERE task_id=?",
                (str(task_id),)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_stuck_in_queue_task_ids(self, ttl_seconds: float) -> list[str]:
        """
        Tasks that have been pending too long without ever being picked up by a worker.
        (created_at old, processing_at still null)
        """
        cutoff = time.time() - ttl_seconds
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT task_id FROM tasks "
                "WHERE processing_at IS NULL AND created_at < ?",
                (cutoff,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    async def get_stuck_processing_task_ids(self, ttl_seconds: float) -> list[str]:
        """
        Tasks that started processing but never reached a terminal state.
        (processing_at old, finish_at still null)
        """
        cutoff = time.time() - ttl_seconds
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT task_id FROM tasks "
                "WHERE finish_at IS NULL AND processing_at IS NOT NULL AND processing_at < ?",
                (cutoff,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    async def get_expired_finished_task_ids(self, ttl_seconds: float) -> list[str]:
        """
        Completed (done/failed) tasks past their result TTL -> safe to clean up.
        """
        cutoff = time.time() - ttl_seconds
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT task_id FROM tasks "
                "WHERE finish_at IS NOT NULL AND finish_at < ?",
                (cutoff,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    async def delete_task(self, task_id: UUID) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute("DELETE FROM tasks WHERE task_id=?", (str(task_id),))
            await db.commit()

    async def get_task_status(self) -> dict[str, int]:
        """
        Get the counts of tasks in 'pending', 'running', 'done', and 'failed' statuses.
        Note: The code checks for 'failed' as the column stores 'failed' in fail_task().
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout=5000")
            async with db.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM tasks
            """) as cursor:
                row = await cursor.fetchone()
                # If table is empty, SUM returns None. Default to 0.
                if row:
                    return {
                        "pending": row[0] or 0,
                        "running": row[1] or 0,
                        "done": row[2] or 0,
                        "failed": row[3] or 0
                    }
                return {"pending": 0, "running": 0, "done": 0, "failed": 0}

    async def get_all_tasks(self) -> list[dict]:
        """
        【新增函数】查询并返回任务表中所有列的数据，按创建时间倒序。
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT task_id, template_name, status, file_name, data_hash, error, 
                       created_at, processing_at, finish_at 
                FROM tasks 
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]