"""Jobs endpoint for job status polling."""

import logging
import os
from fastapi import APIRouter, HTTPException

from ariadne_api.dependencies import get_store
from ariadne_api.schemas.jobs import JobResponse
from ariadne_core.storage.job_queue import get_job_queue
from ariadne_core.storage.sqlite_store import SQLiteStore

router = APIRouter()
logger = logging.getLogger(__name__)

# Lazy-load the JobQueue singleton
_job_queue = None


def _get_job_queue():
    """Get the JobQueue singleton, initializing if needed."""
    global _job_queue
    if _job_queue is None:
        db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
        store = SQLiteStore(db_path)
        _job_queue = get_job_queue(store)
    return _job_queue


@router.get("/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
async def get_job_status(job_id: str) -> JobResponse:
    """Get the status of a rebuild job.

    Returns the current status, progress, and other metadata for a job.
    """
    job_queue = _get_job_queue()

    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobResponse(
        job_id=job.job_id,
        mode=job.mode,
        status=job.status,
        progress=job.progress,
        total_files=job.total_files,
        processed_files=job.processed_files,
        target_paths=job.target_paths,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        created_at=job.created_at,
    )


@router.get("/jobs", tags=["jobs"])
async def list_jobs(
    status: str | None = None,
    limit: int = 50,
) -> dict[str, list[JobResponse]]:
    """List rebuild jobs, optionally filtered by status.

    Returns a list of jobs with the most recent first.
    """
    job_queue = _get_job_queue()

    jobs = job_queue.list_jobs(status=status, limit=limit)

    return {
        "jobs": [
            JobResponse(
                job_id=job.job_id,
                mode=job.mode,
                status=job.status,
                progress=job.progress,
                total_files=job.total_files,
                processed_files=job.processed_files,
                target_paths=job.target_paths,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                created_at=job.created_at,
            )
            for job in jobs
        ]
    }
