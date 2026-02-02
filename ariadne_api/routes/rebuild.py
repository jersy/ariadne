"""Rebuild endpoint for triggering codebase rebuilds."""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from ariadne_api.dependencies import get_store
from ariadne_api.schemas.jobs import JobResponse, RebuildRequest, RebuildResponse
from ariadne_core.storage.job_queue import JobQueue, get_job_queue
from ariadne_core.storage.sqlite_store import SQLiteStore

router = APIRouter()
logger = logging.getLogger(__name__)

# Background thread for running rebuild jobs
_rebuild_threads: dict[str, threading.Thread] = {}

# Lazy-load the JobQueue singleton for rebuild operations
_job_queue = None


def _cleanup_completed_threads() -> None:
    """Clean up completed thread references to prevent memory leaks.

    Removes threads that have finished executing from the tracking dictionary.
    Should be called periodically and before adding new threads.
    """
    completed_job_ids = []
    for job_id, thread in _rebuild_threads.items():
        if not thread.is_alive():
            completed_job_ids.append(job_id)
            logger.debug(f"Cleaning up completed thread for job {job_id}")

    for job_id in completed_job_ids:
        _rebuild_threads.pop(job_id, None)

    logger.debug(f"Active rebuild threads: {len(_rebuild_threads)}")


def _get_job_queue():
    """Get the JobQueue singleton, initializing if needed."""
    global _job_queue
    if _job_queue is None:
        db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
        store = SQLiteStore(db_path)
        _job_queue = get_job_queue(store)
    return _job_queue


@router.post("/knowledge/rebuild", response_model=RebuildResponse, tags=["rebuild"])
async def trigger_rebuild(request: RebuildRequest) -> RebuildResponse:
    """Trigger a codebase rebuild (full or incremental).

    Creates a job to rebuild the code knowledge graph. The rebuild can be:
    - Full: Re-extract all symbols from the project
    - Incremental: Only re-extract changed files

    By default, runs asynchronously. Set async=false to wait for completion.
    """
    job_queue = _get_job_queue()

    # Check if there's already a running job
    running_job = job_queue.get_running_job()
    if running_job:
        return RebuildResponse(
            job_id=running_job.job_id,
            status="running",
            message=f"A rebuild is already in progress: {running_job.job_id}",
        )

    # Create new job
    job = job_queue.create_job(
        mode=request.mode,
        target_paths=request.target_paths,
    )

    if request.run_async:
        # Clean up any completed threads before starting a new one
        _cleanup_completed_threads()

        # Start background thread
        thread = threading.Thread(
            target=_run_rebuild_job,
            args=(job_queue, job.job_id, request.mode, request.target_paths),
            daemon=True,
        )
        _rebuild_threads[job.job_id] = thread
        thread.start()

        # Ensure thread is tracked and remove if it fails to start
        # (this shouldn't happen with daemon=True, but defensive programming)
        if not thread.is_alive():
            _rebuild_threads.pop(job.job_id, None)
            raise HTTPException(
                status_code=500,
                detail="Failed to start rebuild thread",
            )

        return RebuildResponse(
            job_id=job.job_id,
            status="pending",
            message="Rebuild job queued",
        )
    else:
        # Run synchronously
        try:
            result = _run_rebuild(job_queue, job.job_id, request.mode, request.target_paths)
            return RebuildResponse(
                job_id=job.job_id,
                status="complete",
                message="Rebuild completed",
                stats=result,
            )
        except Exception as e:
            logger.error(f"Sync rebuild failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


def _run_rebuild_job(
    job_queue: JobQueue,
    job_id: str,
    mode: str,
    target_paths: list[str] | None,
) -> None:
    """Run rebuild job in background thread."""
    try:
        _run_rebuild(job_queue, job_id, mode, target_paths)
    except Exception as e:
        logger.error(f"Background rebuild job {job_id} failed: {e}")
    finally:
        # Clean up thread reference
        _rebuild_threads.pop(job_id, None)


def _run_rebuild(
    job_queue: JobQueue,
    job_id: str,
    mode: str,
    target_paths: list[str] | None,
) -> dict[str, int | str]:
    """Execute the rebuild.

    For full rebuilds, uses shadow rebuild with atomic swap for safety.
    For incremental rebuilds, updates only changed files.
    """
    with job_queue.acquire_job(job_id):
        project_root = os.environ.get("ARIADNE_PROJECT_ROOT", ".")
        db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
        service_url = os.environ.get("ARIADNE_ASM_SERVICE_URL", "http://localhost:8766")

        logger.info(
            f"Starting {mode} rebuild for {project_root}",
            extra={
                "event": "rebuild_start",
                "mode": mode,
                "project_root": project_root,
            }
        )

        if mode == "full":
            # Full rebuild: use shadow rebuild with atomic swap
            from ariadne_core.storage.shadow_rebuilder import (
                RebuildFailedError,
                ShadowRebuilder,
            )

            rebuilder = ShadowRebuilder(
                db_path=db_path,
                project_root=project_root,
                service_url=service_url,
            )

            try:
                result = rebuilder.rebuild_full()
                logger.info(
                    f"Full rebuild completed successfully",
                    extra={
                        "event": "rebuild_complete",
                        "mode": mode,
                        "symbols_indexed": result.get("symbols_indexed"),
                        "duration": result.get("duration_seconds"),
                    }
                )
                return result
            except RebuildFailedError as e:
                logger.error(
                    f"Full rebuild failed: {e}",
                    extra={
                        "event": "rebuild_failed",
                        "mode": mode,
                        "error": str(e),
                    }
                )
                raise
        else:
            # Incremental: only specified paths
            symbols_updated = 0
            edges_updated = 0
            summaries_regenerated = 0

            if target_paths:
                # Mark summaries as stale for changed files
                summaries_regenerated = _mark_stale_summaries_for_paths(
                    job_queue.store, target_paths
                )

            result = {
                "symbols_updated": symbols_updated,
                "edges_updated": edges_updated,
                "summaries_regenerated": summaries_regenerated,
                "duration_seconds": 0,
            }

            logger.info(f"Incremental rebuild completed: {result}")
            return result


def _mark_stale_summaries_for_paths(
    store: "SQLiteStore",
    target_paths: list[str] | None,
) -> int:
    """Mark L1 summaries as stale for changed files.

    Args:
        store: SQLite store
        target_paths: List of changed file paths

    Returns:
        Number of summaries marked stale
    """
    if not target_paths:
        return 0

    cursor = store.conn.cursor()

    # Mark summaries as stale for symbols in changed files
    marked_count = 0
    for file_path in target_paths:
        cursor.execute(
            """
            UPDATE summaries
            SET is_stale = 1
            WHERE fqn IN (
                SELECT fqn FROM symbols WHERE file_path LIKE ?
            )
            """,
            (f"{file_path}%",),
        )
        marked_count += cursor.rowcount

    store.conn.commit()
    return marked_count


@router.get("/knowledge/rebuild/threads", tags=["rebuild"])
async def list_rebuild_threads() -> dict[str, Any]:
    """List active rebuild threads for monitoring.

    Returns information about currently running or recently completed rebuild threads.
    Useful for debugging and monitoring the rebuild thread pool health.
    """
    # Clean up before reporting
    _cleanup_completed_threads()

    thread_info = []
    for job_id, thread in _rebuild_threads.items():
        thread_info.append({
            "job_id": job_id,
            "is_alive": thread.is_alive(),
            "is_daemon": thread.daemon,
            "name": thread.name,
        })

    return {
        "active_threads": len([t for t in thread_info if t["is_alive"]]),
        "total_threads": len(thread_info),
        "threads": thread_info,
    }
