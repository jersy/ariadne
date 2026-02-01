"""Job queue for async rebuild operations."""

import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from ariadne_core.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """A rebuild job."""

    job_id: str
    mode: str
    status: str
    progress: int
    total_files: int
    processed_files: int
    target_paths: list[str] | None
    started_at: str | None
    completed_at: str | None
    error_message: str | None
    created_at: str


class JobQueue:
    """Queue for managing async rebuild jobs.

    Features:
    - Thread-safe job creation and status updates via atomic SQL operations
    - Single active job at a time (concurrent jobs are queued)
    - Progress tracking
    - Job status polling

    Thread Safety:
    - Uses atomic SQL operations with RETURNING for thread-safe job acquisition
    - SQLite handles concurrent access with internal locking
    - Each method creates its own cursor for isolation
    """

    def __init__(self, store: SQLiteStore) -> None:
        """Initialize job queue.

        Args:
            store: SQLite database store
        """
        self.store = store

    def create_job(
        self,
        mode: str,
        target_paths: list[str] | None = None,
    ) -> Job:
        """Create a new rebuild job.

        Args:
            mode: Rebuild mode ('full' or 'incremental')
            target_paths: Optional list of target paths for incremental rebuild

        Returns:
            Created job with job_id
        """
        job_id = str(uuid.uuid4())

        cursor = self.store.conn.cursor()
        cursor.execute(
            """
            INSERT INTO impact_jobs
            (job_id, mode, status, progress, total_files, processed_files, target_paths)
            VALUES (?, ?, 'pending', 0, 0, 0, ?)
            """,
            (job_id, mode, ",".join(target_paths) if target_paths else None),
        )
        self.store.conn.commit()

        logger.info(f"Created job {job_id} (mode={mode})")

        return self._get_job(job_id)

    def get_job(self, job_id: str) -> Job | None:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        return self._get_job(job_id)

    def _get_job(self, job_id: str) -> Job | None:
        """Internal method to get job by ID."""
        cursor = self.store.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM impact_jobs WHERE job_id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_job(row)

    def _row_to_job(self, row: Any) -> Job:
        """Convert a database row to a Job object.

        Args:
            row: Database row (dict-like from sqlite3.Row)

        Returns:
            Job object
        """
        job_data = dict(row)
        return Job(
            job_id=job_data["job_id"],
            mode=job_data["mode"],
            status=job_data["status"],
            progress=job_data["progress"],
            total_files=job_data["total_files"],
            processed_files=job_data["processed_files"],
            target_paths=job_data["target_paths"].split(",") if job_data.get("target_paths") else None,
            started_at=job_data.get("started_at"),
            completed_at=job_data.get("completed_at"),
            error_message=job_data.get("error_message"),
            created_at=job_data["created_at"],
        )

    def update_job_status(
        self,
        job_id: str,
        status: str | None = None,
        progress: int | None = None,
        processed_files: int | None = None,
        error_message: str | None = None,
    ) -> bool:
        """Update job status.

        Args:
            job_id: Job ID
            status: New status
            progress: Progress value (0-100)
            processed_files: Number of processed files
            error_message: Error message (if failed)

        Returns:
            True if updated, False if job not found
        """
        updates: list[str] = []
        values: list[Any] = []

        if status is not None:
            updates.append("status = ?")
            values.append(status)

            # Set timestamps based on status
            if status == "running" and not self._get_job(job_id):
                return False
            elif status == "running":
                updates.append("started_at = CURRENT_TIMESTAMP")
            elif status in ("complete", "failed"):
                updates.append("completed_at = CURRENT_TIMESTAMP")

        if progress is not None:
            updates.append("progress = ?")
            values.append(progress)

        if processed_files is not None:
            updates.append("processed_files = ?")
            values.append(processed_files)

        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)

        if not updates:
            return True

        values.append(job_id)

        cursor = self.store.conn.cursor()
        cursor.execute(
            f"UPDATE impact_jobs SET {', '.join(updates)} WHERE job_id = ?",
            values,
        )
        self.store.conn.commit()

        return cursor.rowcount > 0

    def get_pending_job(self) -> Job | None:
        """Get the next pending job.

        Returns:
            Next pending job or None
        """
        cursor = self.store.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM impact_jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None

        return self._get_job(row["job_id"])

    def get_running_job(self) -> Job | None:
        """Get the currently running job.

        Returns:
            Currently running job or None
        """
        cursor = self.store.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM impact_jobs
            WHERE status = 'running'
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None

        return self._get_job(row["job_id"])

    def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """List jobs, optionally filtered by status.

        Args:
            status: Filter by status
            limit: Maximum number of jobs to return

        Returns:
            List of jobs
        """
        cursor = self.store.conn.cursor()

        if status:
            cursor.execute(
                """
                SELECT * FROM impact_jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM impact_jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

        return [self._row_to_job(row) for row in cursor.fetchall()]

    @contextmanager
    def acquire_job(self, job_id: str) -> Any:
        """Context manager to atomically acquire and run a job.

        Uses atomic UPDATE...RETURNING to prevent race conditions:
        - Single SQL operation checks status AND updates to 'running'
        - Only one thread can successfully acquire a pending job
        - Other threads will get None from the UPDATE and fail

        Args:
            job_id: Job ID to acquire

        Yields:
            The job object

        Raises:
            ValueError: If job not found or not pending (already acquired)
        """
        # Atomic UPDATE with RETURNING: check status AND mark running in one operation
        cursor = self.store.conn.cursor()
        cursor.execute(
            """
            UPDATE impact_jobs
            SET status = 'running',
                started_at = CURRENT_TIMESTAMP
            WHERE job_id = ? AND status = 'pending'
            RETURNING *
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        self.store.conn.commit()

        if not row:
            # Job either doesn't exist or was already acquired by another thread
            existing = self._get_job(job_id)
            if not existing:
                raise ValueError(f"Job not found: {job_id}")
            else:
                raise ValueError(f"Job not available: {job_id} (status={existing.status}, already acquired)")

        job = self._row_to_job(row)

        try:
            yield job
            # Mark as complete
            self.update_job_status(job_id, status="complete", progress=100)

        except Exception as e:
            # Mark as failed
            logger.error(f"Job {job_id} failed: {e}")
            self.update_job_status(job_id, status="failed", error_message=str(e))
            raise


# Global job queue singleton
_job_queue_instance: JobQueue | None = None
_job_queue_lock = threading.Lock()


def get_job_queue(store: SQLiteStore) -> JobQueue:
    """Get or create the global job queue instance.

    Args:
        store: SQLite database store

    Returns:
        JobQueue instance
    """
    global _job_queue_instance

    if _job_queue_instance is None:
        with _job_queue_lock:
            if _job_queue_instance is None:
                _job_queue_instance = JobQueue(store)

    return _job_queue_instance
