"""Rebuild endpoint for triggering codebase rebuilds."""

import logging
import os
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ariadne_api.schemas.jobs import JobResponse, RebuildRequest, RebuildResponse
from ariadne_core.storage.job_queue import JobQueue, get_job_queue
from ariadne_core.storage.sqlite_store import SQLiteStore

router = APIRouter()
logger = logging.getLogger(__name__)

# Background thread for running rebuild jobs
_rebuild_threads: dict[str, threading.Thread] = {}


def get_store() -> SQLiteStore:
    """Dependency to get SQLite store."""
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database not available")
    return SQLiteStore(db_path)


@router.post("/knowledge/rebuild", response_model=RebuildResponse, tags=["rebuild"])
async def trigger_rebuild(request: RebuildRequest) -> RebuildResponse:
    """Trigger a codebase rebuild (full or incremental).

    Creates a job to rebuild the code knowledge graph. The rebuild can be:
    - Full: Re-extract all symbols from the project
    - Incremental: Only re-extract changed files

    By default, runs asynchronously. Set async=false to wait for completion.
    """
    store = get_store()
    job_queue = get_job_queue(store)

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
        # Start background thread
        thread = threading.Thread(
            target=_run_rebuild_job,
            args=(store, job.job_id, request.mode, request.target_paths),
            daemon=True,
        )
        _rebuild_threads[job.job_id] = thread
        thread.start()

        return RebuildResponse(
            job_id=job.job_id,
            status="pending",
            message="Rebuild job queued",
        )
    else:
        # Run synchronously
        try:
            result = _run_rebuild(store, job.job_id, request.mode, request.target_paths)
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
    store: SQLiteStore,
    job_id: str,
    mode: str,
    target_paths: list[str] | None,
) -> None:
    """Run rebuild job in background thread."""
    try:
        _run_rebuild(store, job_id, mode, target_paths)
    except Exception as e:
        logger.error(f"Background rebuild job {job_id} failed: {e}")
    finally:
        # Clean up thread reference
        _rebuild_threads.pop(job_id, None)


def _run_rebuild(
    store: SQLiteStore,
    job_id: str,
    mode: str,
    target_paths: list[str] | None,
) -> dict[str, int | str]:
    """Execute the rebuild.

    This is a placeholder implementation. In a real implementation, this would:
    1. Get the project root from environment or config
    2. Run the extractor to re-index changed files
    3. Update symbols and edges in the database
    4. Mark stale L1 summaries for regeneration
    """
    job_queue = get_job_queue(store)

    with job_queue.acquire_job(job_id):
        project_root = os.environ.get("ARIADNE_PROJECT_ROOT", ".")
        db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")

        logger.info(f"Starting {mode} rebuild for {project_root}")

        # Import here to avoid circular dependency
        from ariadne_core.extractors.asm.extractor import Extractor

        if mode == "full":
            # Full rebuild: re-extract everything
            with Extractor(db_path=db_path, init=False) as extractor:
                result = extractor.extract_project(project_root)

                if not result.success:
                    raise Exception(f"Extraction failed: {result.errors}")

                symbols_updated = result.stats.get("total_symbols", 0)
                edges_updated = result.stats.get("total_edges", 0)

        else:
            # Incremental rebuild: only process target paths
            if not target_paths:
                # No target paths specified, skip
                logger.info("Incremental rebuild with no target paths - skipping")
                symbols_updated = 0
                edges_updated = 0
            else:
                # Process each target path
                symbols_updated = 0
                edges_updated = 0

                for target_path in target_paths:
                    target_file = Path(target_path)
                    if not target_file.exists():
                        logger.warning(f"Target path not found: {target_path}")
                        continue

                    # For now, we do a simple re-extraction
                    # In production, this would be more sophisticated
                    with Extractor(db_path=db_path, init=False) as extractor:
                        result = extractor.extract_project(str(target_file.parent))

                        if result.success:
                            symbols_updated += result.stats.get("total_symbols", 0)
                            edges_updated += result.stats.get("total_edges", 0)

        # Mark stale summaries
        summaries_regenerated = _mark_stale_summaries(store, target_paths)

        logger.info(f"Rebuild complete: {symbols_updated} symbols, {edges_updated} edges")

        return {
            "symbols_updated": symbols_updated,
            "edges_updated": edges_updated,
            "summaries_regenerated": summaries_regenerated,
            "duration_seconds": 0,  # Would track actual duration
        }


def _mark_stale_summaries(
    store: SQLiteStore,
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
            UPDATE summaries SET is_stale = TRUE
            WHERE target_fqn IN (
                SELECT fqn FROM symbols WHERE file_path = ?
            )
            """,
            (file_path,),
        )
        marked_count += cursor.rowcount

    store.conn.commit()
    return marked_count
